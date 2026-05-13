from astrbot.api import logger
from .selectHandler import *

"""处理生成响应文本"""
"""在此调用sql，处理生成响应文本回到main.py"""


def elf_info_by_id(elf_id):
    # logger.info("回复处理开始")
    # 精灵基本信息
    elf = select_elf_by_id(elf_id)
    # logger.info(elf)
    reply = skill_info(elf)
    return reply


def elf_info_by_name(elf_name):
    # 根据精灵名称查询
    # logger.info("回复处理开始")
    # 精灵基本信息
    elf = select_elf_by_name(elf_name)
    return skill_info(elf)


def skill_info(elf):
    # 该类内部调用，用于给精灵信息拼接技能，生成最后回复
    # 三种技能列表
    stone = select_skill_stone(elf["id"])
    normal = select_skill_normal(elf["id"])
    bloodline = select_skill_bloodline(elf["id"])

    normal_names = ", ".join(s["skill_name"] for s in normal) if normal else "无"
    stone_names = ", ".join(s["skill_name"] for s in stone) if normal else "无"
    bloodline_names = ", ".join(s["skill_name"] for s in bloodline) if normal else "无"
    template = (
        f"精灵编号: {elf["pet_number"]}\n"
        f"精灵名称: {elf["name"]}\n"
        f"精灵属性: {elf["element"]}\n"
        f"技能: {normal_names}\n"
        f"技能石: {stone_names}\n"
        f"血脉技能: {bloodline_names}\n"
    )
    return template


def elf_list_by_skill(skill_name):
    elf = select_pet_by_skill_name(skill_name)
    logger.info(elf)
    elf_info = ", ".join(e["name"] for e in elf) if elf else "无"
    template = (
        f"拥有{skill_name}的精灵有\n"
        f"{elf_info}\n"
    )
    return template
