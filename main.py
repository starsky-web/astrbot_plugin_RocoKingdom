from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .src.selectHandler import *
from .src.replyHandler import *
from .src.data_fetcher import *

@register("RocoKingdom", "WJF", "洛克王国图鉴插件", "0.1.0")
class RocoKingdom(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("插件初始化")

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("洛克", alias={'roco', '开始'})
    async def roco(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        template = (
            f"欢迎使用洛克王国图鉴插件\n"
            f"/精灵（/elf）后接精灵编号或名称\n"
            f"/技能（/skill）后接技能名\n"
        )
        yield event.plain_result(template) # 发送一条纯文本消息

    @filter.command("精灵", alias={'elf'})
    async def elf(self, event: AstrMessageEvent, a = str):
        """精灵查询指令"""
        message_str = event.message_str
        # logger.info(f"精灵查询:{message_str}")
        if a.isdigit():
            # 按编号
            # 补0
            b = 3-len(a)
            for i in range(b):
                a = '0' + a
            yield event.plain_result(elf_info_by_id(a))
        else:
            # 按名称查询
            yield event.plain_result(elf_info_by_name(a))

    @filter.command("技能", alias={'skill'})
    async def skill(self, event: AstrMessageEvent, skill_name = str):
        """查询拥有该技能的精灵列表"""
        yield event.plain_result(elf_list_by_skill(skill_name))

    @filter.command("加载数据", alias={'loaddata'})
    async def dataload(self, event: AstrMessageEvent, a = bool):
        """加载数据指令"""
        """true为覆盖，false为增量"""
        """执行数据加载操作"""
        result = run(clear_data_flag=a)
        yield event.plain_result("数据加载成功")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
