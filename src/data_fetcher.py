"""
洛克王国数据获取模块
从 MediaWiki API 获取精灵和技能数据，写入 SQLite 数据库
整合了数据库初始化和数据获取功能，可直接导入使用
"""
from astrbot.api import logger
import requests
import sqlite3
import time
import os

# API 配置
API_URL = "https://wiki.biligame.com/rocom/api.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PAGE_LIMIT = 500  # API 请求限制
MAX_RETRIES = 3   # 最大重试次数
RETRY_DELAY = 3   # 重试间隔（秒）

# 数据库配置
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "rocokingdom.db")


# ============== 数据库模块 ==============

def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def check_existing_data():
    """检查数据库中是否已有数据"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM pets")
        pet_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM skills")
        skill_count = cursor.fetchone()[0]
        return pet_count, skill_count
    except sqlite3.OperationalError:
        return 0, 0
    finally:
        conn.close()


def init_database():
    """初始化数据库，创建所有表"""
    conn = get_connection()
    cursor = conn.cursor()

    existing_pets, existing_skills = check_existing_data()
    if existing_pets > 0 or existing_skills > 0:
        print(f"检测到已有数据: {existing_pets} 条精灵, {existing_skills} 条技能")
        print("将使用增量更新模式（新数据插入，已有数据更新）")

    # 创建精灵表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            form TEXT,
            stage TEXT,
            element TEXT,
            pet_number TEXT,
            pet_serial TEXT UNIQUE,
            has_shiny INTEGER DEFAULT 0,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pets_name ON pets(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pets_number ON pets(pet_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pets_serial ON pets(pet_serial)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pets_element ON pets(element)")

    # 创建技能表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            serial_number TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            element TEXT,
            category TEXT,
            energy_cost INTEGER,
            power TEXT,
            effect TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_element ON skills(element)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)")

    # 创建精灵-技能关联表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pet_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            skill_type TEXT NOT NULL,
            FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
            UNIQUE(pet_id, skill_name, skill_type)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pet_skills_pet ON pet_skills(pet_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pet_skills_skill ON pet_skills(skill_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pet_skills_type ON pet_skills(skill_type)")

    conn.commit()
    conn.close()

    migrate_constraints()
    print("数据库初始化完成")


def migrate_constraints():
    """为已存在的表添加约束"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pets'")
        indexes = [row[0] for row in cursor.fetchall()]

        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pets_serial_unique ON pets(pet_serial)")
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                print("警告: pet_serial 存在重复值，无法添加唯一约束")
                conn.rollback()
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pets_serial ON pets(pet_serial)")
                conn.commit()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pet_skills'")
        skill_indexes = [row[0] for row in cursor.fetchall()]

        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_pet_skills_unique
                ON pet_skills(pet_id, skill_name, skill_type)
            """)
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                print("警告: pet_skills 存在重复关联记录，无法添加唯一约束")
                conn.rollback()

    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def clear_data():
    """清空所有数据（保留表结构）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pet_skills")
    cursor.execute("DELETE FROM pets")
    cursor.execute("DELETE FROM skills")
    conn.commit()
    conn.close()
    print("数据已清空")


def check_duplicates():
    """检查数据库中是否存在重复数据"""
    conn = get_connection()
    cursor = conn.cursor()
    duplicates = {}

    try:
        cursor.execute("""
            SELECT pet_serial, COUNT(*) as cnt
            FROM pets
            GROUP BY pet_serial
            HAVING cnt > 1
        """)
        pet_dups = cursor.fetchall()
        if pet_dups:
            duplicates['pets'] = pet_dups

        cursor.execute("""
            SELECT pet_id, skill_name, skill_type, COUNT(*) as cnt
            FROM pet_skills
            GROUP BY pet_id, skill_name, skill_type
            HAVING cnt > 1
        """)
        skill_dups = cursor.fetchall()
        if skill_dups:
            duplicates['pet_skills'] = skill_dups

    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

    return duplicates


# ============== 数据获取模块 ==============

def fetch_skills():
    """
    获取技能数据（带重试）
    返回: list of dict
    """
    params = {
        "action": "askargs",
        "format": "json",
        "conditions": "分类:技能",
        "printouts": "技能名称|属性|技能类别|耗能|威力|效果|技能序号",
        "parameters": f"limit={PAGE_LIMIT}|order=asc|sort=技能序号",
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()

            skills = []
            if "query" in data and "results" in data["query"]:
                results = data["query"]["results"]
                for page_name, page_data in results.items():
                    printouts = page_data.get("printouts", {})
                    skill = {
                        "serial_number": printouts.get("技能序号", [""])[0] if printouts.get("技能序号") else "",
                        "name": printouts.get("技能名称", [""])[0] if printouts.get("技能名称") else "",
                        "element": printouts.get("属性", [""])[0] if printouts.get("属性") else "",
                        "category": printouts.get("技能类别", [""])[0] if printouts.get("技能类别") else "",
                        "energy_cost": printouts.get("耗能", [None])[0] if printouts.get("耗能") else None,
                        "power": printouts.get("威力", [""])[0] if printouts.get("威力") else "",
                        "effect": printouts.get("效果", [""])[0] if printouts.get("效果") else "",
                    }
                    if skill["serial_number"] and skill["name"]:
                        skills.append(skill)

            print(f"获取到 {len(skills)} 条技能数据")
            return skills

        except requests.RequestException as e:
            print(f"技能数据请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)

    print("技能数据获取失败，已达最大重试次数")
    return []


def fetch_pets():
    """
    获取精灵数据（带重试）
    返回: list of dict
    """
    params = {
        "action": "askargs",
        "format": "json",
        "conditions": "分类:精灵",
        "printouts": "精灵名称|精灵形态|精灵阶段|属性|精灵编号|精灵序号|技能|血脉技能|可学技能石|是否有异色",
        "parameters": f"limit={PAGE_LIMIT}|order=asc|sort=精灵编号",
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()

            pets = []
            if "query" in data and "results" in data["query"]:
                results = data["query"]["results"]
                for page_name, page_data in results.items():
                    printouts = page_data.get("printouts", {})

                    skills_str = printouts.get("技能", [""])[0] if printouts.get("技能") else ""
                    bloodline_str = printouts.get("血脉技能", [""])[0] if printouts.get("血脉技能") else ""
                    stone_str = printouts.get("可学技能石", [""])[0] if printouts.get("可学技能石") else ""
                    has_shiny_val = printouts.get("是否有异色", [])
                    has_shiny = 1 if (has_shiny_val and has_shiny_val[0] == "是") else 0

                    elements = printouts.get("属性", [])
                    element_str = ",".join(elements) if elements else ""

                    pet = {
                        "name": printouts.get("精灵名称", [""])[0] if printouts.get("精灵名称") else "",
                        "form": printouts.get("精灵形态", [""])[0] if printouts.get("精灵形态") else "",
                        "stage": printouts.get("精灵阶段", [""])[0] if printouts.get("精灵阶段") else "",
                        "element": element_str,
                        "pet_number": printouts.get("精灵编号", [""])[0] if printouts.get("精灵编号") else "",
                        "pet_serial": printouts.get("精灵序号", [""])[0] if printouts.get("精灵序号") else "",
                        "has_shiny": has_shiny,
                        "skills": [s.strip() for s in skills_str.split(",") if s.strip()],
                        "bloodline_skills": [s.strip() for s in bloodline_str.split(",") if s.strip()],
                        "stone_skills": [s.strip() for s in stone_str.split(",") if s.strip()],
                    }
                    if pet["name"]:
                        pets.append(pet)

            print(f"获取到 {len(pets)} 条精灵数据")
            return pets

        except requests.RequestException as e:
            print(f"精灵数据请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)

    print("精灵数据获取失败，已达最大重试次数")
    return []


# ============== 数据写入模块 ==============

def insert_skills(skills):
    """插入技能数据"""
    if not skills:
        return

    conn = get_connection()
    cursor = conn.cursor()

    for skill in skills:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO skills
                (serial_number, name, element, category, energy_cost, power, effect)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                skill["serial_number"],
                skill["name"],
                skill["element"],
                skill["category"],
                skill["energy_cost"],
                skill["power"],
                skill["effect"]
            ))
        except sqlite3.IntegrityError as e:
            print(f"技能插入失败: {skill['name']} - {e}")

    conn.commit()
    conn.close()
    print(f"已插入 {len(skills)} 条技能数据")


def insert_pets(pets):
    """插入精灵数据及技能关联（增量更新模式）"""
    if not pets:
        return

    conn = get_connection()
    cursor = conn.cursor()

    pet_insert_count = 0
    pet_update_count = 0
    skill_link_count = 0

    for pet in pets:
        try:
            cursor.execute("""
                INSERT INTO pets
                (name, form, stage, element, pet_number, pet_serial, has_shiny)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pet_serial) DO UPDATE SET
                    name=excluded.name,
                    form=excluded.form,
                    stage=excluded.stage,
                    element=excluded.element,
                    pet_number=excluded.pet_number,
                    has_shiny=excluded.has_shiny
            """, (
                pet["name"],
                pet["form"],
                pet["stage"],
                pet["element"],
                pet["pet_number"],
                pet["pet_serial"],
                pet["has_shiny"]
            ))

            cursor.execute("SELECT id FROM pets WHERE pet_serial = ?", (pet["pet_serial"],))
            result = cursor.fetchone()
            pet_id = result[0] if result else None

            if pet_id:
                cursor.execute("SELECT COUNT(*) FROM pet_skills WHERE pet_id = ?", (pet_id,))
                existing_links = cursor.fetchone()[0]

                if existing_links > 0:
                    cursor.execute("DELETE FROM pet_skills WHERE pet_id = ?", (pet_id,))
                    pet_update_count += 1
                else:
                    pet_insert_count += 1

                for skill_name in pet["skills"]:
                    cursor.execute("""
                        INSERT OR IGNORE INTO pet_skills (pet_id, skill_name, skill_type)
                        VALUES (?, ?, 'normal')
                    """, (pet_id, skill_name))
                    skill_link_count += 1

                for skill_name in pet["bloodline_skills"]:
                    cursor.execute("""
                        INSERT OR IGNORE INTO pet_skills (pet_id, skill_name, skill_type)
                        VALUES (?, ?, 'bloodline')
                    """, (pet_id, skill_name))
                    skill_link_count += 1

                for skill_name in pet["stone_skills"]:
                    cursor.execute("""
                        INSERT OR IGNORE INTO pet_skills (pet_id, skill_name, skill_type)
                        VALUES (?, ?, 'stone')
                    """, (pet_id, skill_name))
                    skill_link_count += 1

        except sqlite3.Error as e:
            print(f"精灵处理失败: {pet['name']} - {e}")

    conn.commit()
    conn.close()
    print(f"精灵数据: 新增 {pet_insert_count} 条, 更新 {pet_update_count} 条")
    print(f"技能关联: 插入 {skill_link_count} 条")


# ============== 主入口 ==============

def run(clear_data_flag: bool = False):
    """
    执行数据获取与写入流程

    Args:
        clear_data_flag: 是否在开始前清空现有数据
            - True: 清空所有数据后重新导入
            - False: 使用增量更新模式（默认）

    Returns:
        dict: 执行结果，包含 skills_count, pets_count 等统计信息
    """
    print("=== 洛克王国精灵图鉴数据获取 ===")

    # 初始化数据库
    init_database()

    # 根据参数决定是否清空数据
    if clear_data_flag:
        clear_data()
        print("数据已清空，将重新导入...")

    # 检查重复数据（仅提示，不清空）
    duplicates = check_duplicates()
    if duplicates and not clear_data_flag:
        print("\n警告: 检测到数据库中存在重复数据!")
        for table, dup_list in duplicates.items():
            print(f"  - {table}: {len(dup_list)} 条重复记录")
        print("建议设置 clear_data_flag=True 清空数据后重新导入")

    # 获取并插入技能数据
    print("\n--- 获取技能数据 ---")
    skills = fetch_skills()
    insert_skills(skills)

    # 获取并插入精灵数据
    print("\n--- 获取精灵数据 ---")
    pets = fetch_pets()
    insert_pets(pets)

    print("\n=== 数据获取完成 ===")
    print(f"数据库文件: {DB_PATH}")

    # 返回统计结果
    return {
        "skills_count": len(skills),
        "pets_count": len(pets),
        "db_path": DB_PATH
    }


# if __name__ == "__main__":
#     # 直接运行时使用增量更新模式
#     run(clear_data_flag=True)