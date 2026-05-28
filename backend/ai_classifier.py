import os
import random
import requests
from typing import List, Tuple, Optional

DEEPSEEK_API_KEY = "sk-bbde568f378346bd85e643b5dda38336"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
CATEGORIES = [
    "网络问题", "硬件故障", "软件异常", "账号权限",
    "设施报修", "服务申请", "投诉建议", "业务咨询",
    "星际来客",
]
RISK_LEVELS = ["紧急", "高", "中", "低"]

SYSTEM_PROMPT = (
    "你是一个综合服务台分拣员，性格幽默风趣。请阅读用户的描述并严格从以下分类中选一个：\n\n"
    "【网络问题】- 断网、Wi-Fi、VPN、服务器不可达、IP冲突\n"
    "【硬件故障】- 电脑、蓝屏、打印机、屏幕、键盘、电源、设备损坏\n"
    "【软件异常】- 软件崩溃、卡顿、报错、系统异常、无法打开\n"
    "【账号权限】- 密码、登录不上、权限不足、认证失败\n"
    "【设施报修】- 门坏了、灯不亮、空调故障、漏水、桌椅损坏、卫生间\n"
    "【服务申请】- 申请设备、领用物资、开通权限、安装软件、配电脑\n"
    "【投诉建议】- 投诉、意见、建议、表扬、反馈\n"
    "【业务咨询】- 怎么操作、流程问询、使用方法、能不能帮我\n\n"
    "同时评估风险等级（紧急/高/中/低），输出格式：分类名|风险等级\n"
    "紧急=宕机/全局瘫痪/数据丢失/安全隐患，高=核心业务中断/大批影响，中=部分异常，低=轻微/咨询/建议\n\n"
    "如果描述与以上均无关（天气、心情、闲聊等），输出：星际来客|一句幽默点评(≤18字)|低\n"
    "只输出结果，用半角 | 分隔，不要多余文字。"
)
USER_PROMPT_TEMPLATE = "用户描述：\n{description}\n\n请严格按格式输出（分类名|风险等级 或 星际来客|点评|低）："

# 规则分类器用幽默点评池
HUMOR_POOL = [
    "这位工单来自平行宇宙",
    "建议重启一下脑回路试试",
    "IT 部暂时不负责这个业务",
    "检测到一例人类迷惑行为",
    "这不是 bug，这叫 feature",
    "请转接至人生规划部处理",
    "该问题超出地球 IT 服务范围",
    "已转发至宇宙数据中心",
]


# AI 可能输出的分类变体 → 标准分类
CATEGORY_ALIASES = {
    # 网络问题
    "服务器故障": "网络问题", "网络故障": "网络问题", "断网": "网络问题",
    "无法上网": "网络问题", "联网问题": "网络问题", "网络异常": "网络问题",
    # 硬件故障
    "电脑故障": "硬件故障", "设备故障": "硬件故障", "机器故障": "硬件故障",
    "硬件问题": "硬件故障", "打印机故障": "硬件故障",
    # 软件异常
    "程序故障": "软件异常", "系统故障": "软件异常", "软件故障": "软件异常",
    "应用故障": "软件异常", "系统崩溃": "软件异常",
    # 账号权限
    "登录问题": "账号权限", "账号问题": "账号权限", "密码问题": "账号权限",
    "权限问题": "账号权限",
    # 设施报修
    "设施故障": "设施报修", "门坏了": "设施报修", "灯坏了": "设施报修",
    "空调坏了": "设施报修", "漏水": "设施报修", "水管": "设施报修",
    "厕所": "设施报修", "卫生间": "设施报修",
    # 服务申请
    "申请": "服务申请", "领用": "服务申请", "申领": "服务申请",
    "开通": "服务申请",
    # 投诉建议
    "投诉": "投诉建议", "意见": "投诉建议", "建议": "投诉建议",
    "表扬": "投诉建议", "反馈": "投诉建议",
    # 业务咨询
    "咨询": "业务咨询", "怎么": "业务咨询", "如何": "业务咨询",
    "能不能": "业务咨询", "请问": "业务咨询",
}


def normalize_category(text: str) -> Tuple[str, Optional[str], str]:
    cleaned = text.replace("[", "").replace("]", "").replace("【", "").replace("】", "").strip()
    # 也处理全角管道符
    cleaned = cleaned.replace("｜", "|")
    # 解析 | 分隔的格式：category|humor_or_risk|risk
    if "|" in cleaned:
        parts = [p.strip() for p in cleaned.split("|")]
        cat = parts[0]
        # 模糊匹配：AI 可能输出非标准分类名
        cat = CATEGORY_ALIASES.get(cat, cat)
        # 判断是标准分类还是星际来客
        if cat in CATEGORIES:
            if cat == "星际来客":
                humor = parts[1] if len(parts) > 1 else None
                risk = parts[2] if len(parts) > 2 and parts[2] in RISK_LEVELS else "低"
                return cat, humor, risk
            else:
                # IT 分类：第二部分可能是风险等级
                risk = parts[1] if len(parts) > 1 and parts[1] in RISK_LEVELS else "中"
                return cat, None, risk
        # 非标准分类但包含管道符
        humor = parts[1] if len(parts) > 1 else None
        risk = parts[2] if len(parts) > 2 and parts[2] in RISK_LEVELS else "中"
        return (cat if cat in CATEGORIES else "软件异常"), humor, risk
    # 无管道符的简单格式
    for category in CATEGORIES:
        if category in cleaned:
            return category, None, "中"
    if cleaned in CATEGORIES:
        return cleaned, None, "中"
    return "软件异常", None, "中"


def rule_based_classification(description: str) -> Tuple[str, Optional[str], str]:
    text = description.lower()

    # 无关联入关键词检测（至少命中 2 个才判为无关，避免误伤正常工单）
    irrelevant_patterns = [
        "天气", "下雨", "晴天", "多云", "刮风", "下雪", "热死", "冷死",
        "吃饭", "好吃", "午饭", "晚饭", "外卖", "食堂",
        "心情", "无聊", "开心", "难过", "烦躁", "郁闷", "好累",
        "你好", "在吗", "哈哈", "嘿嘿", "嗯嗯", "哦哦", "啊啊",
        "喜欢", "恋爱", "对象", "失恋", "表白", "暗恋",
        "放假", "周末", "节日", "国庆", "过年",
        "股票", "基金", "比特币", "房价", "工资",
        "唱歌", "电影", "打游戏", "追剧", "综艺",
        "帅", "美", "好看", "减肥", "健身", "跑步",
        "人生", "哲学", "宇宙", "意义", "活着",
        "猫", "狗", "宠物", "花", "草",
    ]
    irrelevant_count = 0
    for kw in irrelevant_patterns:
        if kw in text:
            irrelevant_count += 1
    if irrelevant_count >= 2:
        return "星际来客", random.choice(HUMOR_POOL), "低"

    # 风险等级关键词检测（先于分类，因为风险 > 类别）
    urgent_patterns = ["宕机", "瘫痪", "数据丢失", "全部", "全员", "无法启动", "彻底", "灾难", "紧急", "urgent"]
    high_patterns = ["崩溃", "中断", "无法访问", "大批", "生产环境", "核心", "关键", "critical", "大面积"]

    risk = "中"  # 默认
    for kw in urgent_patterns:
        if kw.lower() in text:
            risk = "紧急"
            break
    if risk != "紧急":
        for kw in high_patterns:
            if kw.lower() in text:
                risk = "高"
                break

    # also check for low risk patterns
    low_patterns = ["咨询", "申请", "建议", "小问题", "偶尔", "不太", "一点点", "请问", "帮我看看"]
    for kw in low_patterns:
        if kw.lower() in text:
            if risk == "中":  # only downgrade if not already urgent/high
                risk = "低"
            break

    network_keywords = ["网络", "连不上", "断网", "Wi-Fi", "wifi", "路由", "ping", "掉线", "服务器", "访问不了", "vpn", "ip", "带宽"]
    hardware_keywords = ["硬件", "屏幕", "显示", "蓝屏", "主板", "电源", "风扇", "键盘", "鼠标", "硬盘", "笔记本", "打印机", "坏了", "电脑", "开机", "重启"]
    software_keywords = ["软件", "程序", "系统", "崩溃", "卡顿", "异常", "更新", "安装", "报错", "打不开", "死机", "闪退", "卡死"]
    account_keywords = ["账号", "密码", "权限", "登录", "登录不上", "锁定", "认证", "验证码", "token"]
    facility_keywords = ["门", "灯", "空调", "漏水", "水管", "厕所", "卫生间", "椅子", "桌子", "窗户", "电梯", "墙", "地板", "天花板", "插座", "暖气"]
    service_keywords = ["申请", "领用", "申领", "开通", "配发", "分配", "采购", "借用", "领取", "新员工", "入职", "装机"]
    complaint_keywords = ["投诉", "意见", "建议", "表扬", "反馈", "吐槽", "不满", "态度", "服务差", "效率", "太慢"]
    consult_keywords = ["咨询", "怎么", "如何", "能不能", "请问", "帮我看", "问一下", "不会用", "教程", "指导", "说明"]

    score = {category: 0 for category in CATEGORIES}

    for keyword in network_keywords:
        if keyword.lower() in text:
            score["网络问题"] += 1
    for keyword in hardware_keywords:
        if keyword.lower() in text:
            score["硬件故障"] += 1
    for keyword in software_keywords:
        if keyword.lower() in text:
            score["软件异常"] += 1
    for keyword in account_keywords:
        if keyword.lower() in text:
            score["账号权限"] += 1
    for keyword in facility_keywords:
        if keyword.lower() in text:
            score["设施报修"] += 1
    for keyword in service_keywords:
        if keyword.lower() in text:
            score["服务申请"] += 1
    for keyword in complaint_keywords:
        if keyword.lower() in text:
            score["投诉建议"] += 1
    for keyword in consult_keywords:
        if keyword.lower() in text:
            score["业务咨询"] += 1

    winner = max(score, key=score.get)
    if score[winner] == 0:
        return "星际来客", random.choice(HUMOR_POOL), "低"
    return winner, None, risk


def call_deepseek(description: str) -> str:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(description=description)},
        ],
        "max_tokens": 50,
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    if "choices" not in data or not data["choices"]:
        raise ValueError("DeepSeek 返回结果缺失")
    return data["choices"][0]["message"]["content"].strip()


def classify_description(description: str) -> Tuple[str, Optional[str], str]:
    if DEEPSEEK_API_KEY:
        try:
            raw = call_deepseek(description)
            category, humor_note, risk_level = normalize_category(raw)
            if category in CATEGORIES and risk_level in RISK_LEVELS:
                return category, humor_note, risk_level
        except Exception:
            pass
    return rule_based_classification(description)


def generate_ai_resolution(description: str, category: str, risk_level: str,
                           persona_name: str = "暖男助手", stress: int = 0) -> str:
    """调用 AI 生成处理方案（带人设风格），高压力时加入崩坏效果"""
    from backend.gamification import PERSONAS as _PERSONAS
    from backend.workflow import get_stress_persona_effect

    stress_effect = get_stress_persona_effect(persona_name, stress)
    meltdown = stress_effect.get("meltdown", False)

    p = _PERSONAS.get(persona_name)
    if p and p.get("system_prompt"):
        prompt = f"{p['system_prompt']}\n"
    else:
        styles = {
            "毒舌老鸟": "你是个毒舌但技术过硬的老运维，说话带刺但靠谱。用吐槽的方式写处理方案。",
            "暖男助手": "你是个温柔体贴的IT助手，喜欢鼓励用户。用温暖的方式写处理方案。",
            "摸鱼达人": "你是个懒散但莫名靠谱的运维，总是慢吞吞但能搞定。写处理方案时带点拖延症的感觉。",
            "冷面机器人": "你是个精准高效的机器人，说话像AI一样简洁。用最少的字写处理方案。",
            "戏精本精": "你是个把每次维修都演成舞台剧的戏精IT，用夸张的表演风格写处理方案。",
            "技术 wizard": "你是个用魔法术语解释技术的神秘运维高手。用咒语和魔法的比喻写处理方案。",
            "佛系青年": "你是个随缘处理问题的佛系IT，平和淡然地写处理方案，一切随缘。",
        }
        prompt = f"{styles.get(persona_name, styles['暖男助手'])}\n"

    if meltdown:
        prompt += (f"注意：你当前精神压力极高（{stress}%），处于精神崩溃边缘。"
                   f"你的回复应该表现出明显的疲惫、暴躁或崩溃情绪。"
                   f"可以拒绝工作、讽刺用户、或者输出毫无意义的废话。\n")
    else:
        prompt += "你是负责处理这个工单的IT运维，你可以协调其他部门配合处理，但不能让用户自己去联系别人。\n"

    prompt += (f"故障描述：{description}\n分类：{category}\n风险：{risk_level}\n"
               f"写一段不超过80字的处理方案，保持人设风格。")
    if not DEEPSEEK_API_KEY:
        return f"已针对「{category}」进行处理，问题已解决。"
    try:
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个IT运维人员，按指定人设风格回复。"},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 100,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return f"已针对「{category}」进行处理，问题已解决。"
