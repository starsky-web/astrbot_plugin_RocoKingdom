# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 AstrBot 插件项目，用于洛克王国游戏图鉴查询。插件通过命令行指令提供精灵和技能查询功能。

## 架构

```
astrbot_plugin_RocoKingdom/
├── main.py           # 插件入口，注册指令处理器
├── selectHandler.py  # 数据库查询逻辑
├── replyHandler.py   # 响应文本生成（调用 selectHandler 组装回复）
├── data_fetcher.py   # 数据获取模块（从 MediaWiki API 拉取数据写入数据库）
├── data/
│   └── rocokingdom.db    # SQLite 数据库（精灵/技能数据）
├── metadata.yaml     # 插件元信息
└── requirements.txt  # Python 依赖
```

## AstrBot 插件开发要点

- 插件类继承 `Star` 基类，使用 `@register` 装饰器注册
- 指令使用 `@filter.command("指令名", alias={'别名'})` 装饰器注册
- 处理器方法必须是 `async` 方法，接收 `AstrMessageEvent` 参数
- 使用 `yield event.plain_result("回复内容")` 返回消息

## 重要约束

**严格执行用户指令**：该项目严格执行用户指令，用户未提及的内容不允许随意修改。

**DB_PATH 禁止修改**：`selectHandler.py` 中的 `DB_PATH` 已固定，严禁修改该值。

## 数据库结构

- `pets` 表：精灵信息，包含 `id`、`pet_number`（编号）、`name`（名称）、`pet_serial`（序号）、`element`（属性）等字段
- `skills` 表：技能信息，包含 `serial_number`、`name`（技能名称）、`element`、`category` 等字段
- `pet_skills` 表：精灵-技能关联，包含 `pet_id`、`skill_name`、`skill_type`（normal/stone/bloodline）字段

## 当前已注册指令

| 指令 | 别名 | 功能 |
|------|------|------|
| 洛克 | roco, 开始 | 入口指令 |
| 精灵 | elf | 精灵查询（支持编号和名称） |
| 技能 | skill | 技能查询 |
| 加载数据 | load data | 数据加载 |

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 数据库路径（相对插件根目录）
data/rocokingdom.db
```

## 数据加载流程

数据通过 `/加载数据` 指令从 MediaWiki API (`https://wiki.biligame.com/rocom/api.php`) 获取：
- 参数 `true`：清空现有数据后重新导入
- 参数 `false` 或无参数：增量更新模式

## 参考文档

- [AstrBot 插件开发文档（中文）](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 插件开发文档（英文）](https://docs.astrbot.app/en/dev/star/plugin-new.html)