"""AI 模拟器：AI 用户工单生成 + AI 管理员自动处理"""

import random
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from backend.gamification import (
    DEPARTMENTS, NAMES, PERSONAS, PERSONA_NAMES, random_persona,
    get_persona_phrase, get_persona_resolution, random_event,
    REQUESTER_PERSONAS, REQUESTER_NAMES, GARBLED_POOL, CAT_EVENTS,
)
from backend.ai_classifier import classify_description, CATEGORIES

# ── AI 用户工单模板 ──
USER_TICKET_POOL = [
    # (描述模板, 可能分类)
    ("电脑突然蓝屏了重启好几次都没用", "硬件故障"),
    ("公司Wi-Fi一直连不上显示无法连接", "网络问题"),
    ("Excel打开就闪退重装也没用", "软件异常"),
    ("OA系统登录不上提示密码错误", "账号权限"),
    ("会议室空调不制冷了温度降不下来", "设施报修"),
    ("需要申请一台新笔记本电脑开发用", "服务申请"),
    ("打印机卡纸了怎么都取不出来", "硬件故障"),
    ("公司邮箱发不出邮件附件上传失败", "网络问题"),
    ("VPN连不上在家没法办公了", "网络问题"),
    ("三楼女卫生间水龙头一直在漏水", "设施报修"),
    ("新来的实习生需要开通财务系统权限", "服务申请"),
    ("建议食堂增加素食窗口现在选择太少", "投诉建议"),
    ("报销系统怎么操作第一次用不太会", "业务咨询"),
    ("办公椅轮子坏了一坐就滑走好危险", "设施报修"),
    ("系统自动更新后所有文件都打不开了", "软件异常"),
    ("门禁卡刷不开大门被关在外面半小时", "账号权限"),
    ("共享文件夹权限不对我们组都访问不了", "账号权限"),
    ("电脑运行特别慢开机要十分钟", "硬件故障"),
    ("投诉IT部响应太慢了工单提交三天没人理", "投诉建议"),
    ("怎么申请公司云盘空间流程是什么", "业务咨询"),
    ("显示器一直闪屏眼睛都要瞎了", "硬件故障"),
    ("公司内部系统报500错误所有人用不了", "网络问题"),
    ("申请领用无线键盘鼠标一套", "服务申请"),
    ("办事处装修后网络插座都没电", "设施报修"),
    ("办公软件激活码过期了需要续费", "服务申请"),
    ("对IT部小李的服务非常满意特地表扬", "投诉建议"),
    ("新OA系统怎么设置自动回复功能", "业务咨询"),
    ("电脑中毒了所有文件被加密了急急急", "软件异常"),
]


def generate_ai_ticket() -> dict:
    """AI 模拟用户提交工单，30%概率附带特殊报修人人设"""
    desc, _ = random.choice(USER_TICKET_POOL)
    department = random.choice(DEPARTMENTS)
    name = random.choice(NAMES)
    requester = None
    if random.random() < 0.3:
        rkey = random.choice(REQUESTER_NAMES)
        requester = REQUESTER_PERSONAS[rkey]
        name = f"{requester['title']}·{name}"
        if requester.get("garbled"):
            desc = random.choice(GARBLED_POOL)
    # 添加一些随机性
    if random.random() < 0.3 and not (requester and requester.get("garbled")):
        desc = desc + random.choice(["", "急！", "在线等", "帮帮忙", "谢谢！"])
    return {
        "creator": name,
        "department": department,
        "description": desc,
        "requester": requester["title"] if requester else None,
        "requester_data": requester,
    }


def generate_ai_processing(ticket: dict) -> dict:
    """AI 模拟管理员处理工单，返回处理信息"""
    persona_name = random_persona()
    phrase = get_persona_phrase(persona_name)
    resolution = get_persona_resolution(persona_name)

    # 模拟处理延迟（秒）
    persona_delays = {
        "毒舌老鸟": random.randint(30, 120),
        "暖男助手": random.randint(20, 60),
        "摸鱼达人": random.randint(180, 600),
        "冷面机器人": random.randint(5, 45),
    }
    delay = persona_delays.get(persona_name, 60)

    return {
        "assignee": f"{PERSONAS[persona_name]['emoji']} {persona_name}",
        "persona": persona_name,
        "phrase": phrase,
        "resolution": resolution,
        "processing_delay_seconds": delay,
    }


def _gen_one_option(pname: str, ticket: dict) -> dict:
    """生成单个人设的处理方案（供并行调用）"""
    from backend.ai_classifier import generate_ai_resolution
    p = PERSONAS[pname]
    try:
        resolution = generate_ai_resolution(
            ticket["description"], ticket["category"],
            ticket["risk_level"] or "中", pname)
    except Exception:
        resolution = random.choice(p["resolution_templates"])
    if not resolution or len(resolution) < 5:
        resolution = random.choice(p["resolution_templates"])
    return {
        "persona": pname,
        "emoji": p["emoji"],
        "style": p["style"],
        "resolution": resolution,
        "phrase": random.choice(p["phrases"]),
    }


def gather_resolution_options(ticket) -> list:
    """为工单生成 3-4 个不同人设的处理方案（并行调用 AI，大幅加速）"""
    count = random.randint(3, min(4, len(PERSONA_NAMES)))
    assigned = ticket["persona"] if ticket["persona"] else ""
    if assigned and assigned in PERSONA_NAMES:
        others = [n for n in PERSONA_NAMES if n != assigned]
        selected = [assigned] + random.sample(others, count - 1)
    else:
        selected = random.sample(PERSONA_NAMES, count)

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = {executor.submit(_gen_one_option, pname, ticket): pname for pname in selected}
        options = []
        for future in as_completed(futures):
            options.append(future.result())
    return options


def simulate_ai_rating(persona_name: str, processing_time_seconds: int,
                        stress: int = 0, requester_data: dict = None) -> dict:
    """AI 用户根据管理员表现给出评价，高压力降低评分，报修人人设影响评分"""
    # 报修人人设强制评分
    if requester_data:
        if requester_data.get("force_rating") == 5:
            return {"rating": 5, "feedback": "随缘五星好评，阿弥陀佛。"}
        if requester_data.get("timeout_sec") and processing_time_seconds > requester_data["timeout_sec"]:
            return {"rating": 1, "feedback": "太慢了！！你知道我一分钟多少钱吗？！差评！！"}

    # 处理越快，评分越高
    if processing_time_seconds < 30:
        rating_weight = [5,5,5,5,4]
    elif processing_time_seconds < 120:
        rating_weight = [5,4,4,4,3]
    elif processing_time_seconds < 300:
        rating_weight = [4,4,3,3,2]
    else:
        rating_weight = [3,3,2,2,1]

    # 摸鱼达人天然降一档
    if persona_name == "摸鱼达人":
        rating_weight = [max(1, r-1) for r in rating_weight]

    # 高压力降评分
    if stress >= 80:
        rating_weight = [max(1, r-2) for r in rating_weight]
    elif stress >= 60:
        rating_weight = [max(1, r-1) for r in rating_weight]

    rating = random.choice(rating_weight)

    feedbacks = {
        5: ["处理神速！太感谢了！", "完美解决，五星好评！", "效率超高，非常满意！", "太棒了，问题秒解决"],
        4: ["处理得不错，谢谢！", "挺好的，满意。", "问题解决了，赞一个", "还行，给个好评"],
        3: ["还行吧，勉强及格。", "处理了但有点慢。", "凑合，能解决问题就行。"],
        2: ["太慢了，等了好久。", "不太满意，差点意思。", "处理得很敷衍..."],
        1: ["完全没解决我的问题！", "差评，体验太差了。", "等了半天还没处理好，生气！"],
    }
    return {
        "rating": rating,
        "feedback": random.choice(feedbacks.get(rating, feedbacks[3])),
    }


def simulate_full_lifecycle(ticket_id: int) -> dict:
    """为用户模式模拟完整的工单处理生命周期"""
    persona_name = random_persona()
    p = PERSONAS[persona_name]

    return {
        "assignee": f"{p['emoji']} {persona_name}",
        "persona": persona_name,
        "assign_phrase": random.choice(p["phrases"]),
        "resolution": random.choice(p["resolution_templates"]),
        "review_comment": random.choice([
            "审核通过，处理方案合理。", "已确认问题解决，同意关闭。",
            "方案可行，批准完成。", "检查完毕，工单关闭。",
        ]),
        "assign_delay": random.randint(3, 25),
        "resolve_delay": random.randint(15, 90),
        "review_delay": random.randint(5, 20),
    }
