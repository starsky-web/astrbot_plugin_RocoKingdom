"""查询处理器，查询实际均在此执行"""
import os
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

"""禁止修改路径定义"""
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "rocokingdom.db")


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器，自动处理连接关闭"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except sqlite3.Error as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_query(sql: str, params: tuple = ()) -> List[tuple]:
    """执行查询并返回结果"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            columns = [description[0] for description in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    except sqlite3.Error:
        return []


def select_elf_by_id(pet_number: int) -> Optional[tuple]:
    """根据精灵序号获取详情"""
    rows = execute_query("SELECT * FROM pets WHERE pet_number = ?", (pet_number,))
    return rows[0] if rows else None


def select_elf_by_name(pet_name: str) -> List[tuple]:
    """根据精灵名称获取详情（可能有多个同名精灵）"""
    rows =  execute_query("SELECT * FROM pets WHERE name = ?", (pet_name,))
    return rows[0] if rows else None


def select_skill_by_name(skill_name: str) -> Optional[tuple]:
    """根据技能名称获取技能详情"""
    rows = execute_query("SELECT * FROM skills WHERE name = ?", (skill_name,))
    return rows[0] if rows else None

def select_pet_by_skill_name(skill_name: str) -> List[tuple]:
    """根据技能名称获取拥有技能对应的精灵"""
    rows = execute_query("select DISTINCT pets.name FROM pet_skills,pets where pet_skills.pet_id = pets.id and skill_name = ?" , (skill_name,))
    return rows

def select_skill_normal(pet_id: str) -> List[tuple]:
    """根据精灵ID获取普通技能详情"""
    rows = execute_query("SELECT * FROM pet_skills WHERE pet_id = ? AND skill_type = 'normal'", (pet_id,))
    return rows

def select_skill_stone(pet_id: str) -> List[tuple]:
    """根据精灵ID获取技能石技能详情"""
    rows = execute_query("SELECT * FROM pet_skills WHERE pet_id = ? AND skill_type = 'stone'", (pet_id,))
    return rows

def select_skill_bloodline(pet_id: str) -> List[tuple]:
    """根据精灵ID获取血脉技能详情"""
    rows = execute_query("SELECT * FROM pet_skills WHERE pet_id = ? AND skill_type = 'bloodline'", (pet_id,))
    return rows