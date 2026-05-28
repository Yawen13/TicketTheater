"""成就系统 + 随机事件 + 排行榜"""

import random
import datetime
from typing import Dict, List, Optional

# ── AI 管理员人设 ──
PERSONAS = {
    "毒舌老鸟": {
        "emoji": "😤",
        "style": "毒舌吐槽但技术过硬",
        "phrases": [
            "又双叒叕出问题了？你电脑是故障收藏家吗",
            "行吧，这种小问题我闭着眼都能修",
            "你看看隔壁部门，人家怎么就没这么多事",
        ],
        "resolution_templates": [
            "重启大法好，已经远程帮你搞定了。下次记得先自己试试重启。",
            "这问题简单得我都懒得写方案。搞定了，下不为例。",
        ],
    },
    "暖男助手": {
        "emoji": "🫶",
        "style": "温柔体贴鼓励型",
        "phrases": [
            "别着急，我来帮你看看这个问题~",
            "没关系，这个问题很常见的，交给我！",
            "辛苦啦，让我帮你解决~",
        ],
        "resolution_templates": [
            "已经帮你处理好了！还有什么需要随时找我哦~",
            "问题解决了！建议以后可以这样预防...有什么不懂的随时问~",
        ],
    },
    "摸鱼达人": {
        "emoji": "🦥",
        "style": "懒散但莫名靠谱",
        "phrases": [
            "嗯...这个问题嘛...让我想想...",
            "（喝了口茶）啊，什么？哦工单啊...",
            "我看看...嗯...好...（过了很久）搞定了",
        ],
        "resolution_templates": [
            "虽然花了点时间，但总算是搞定了。下次别催。",
            "搞定了。其实不处理它自己也会好，但既然你提了...",
        ],
    },
    "冷面机器人": {
        "emoji": "🤖",
        "style": "精准简洁零废话",
        "phrases": [
            "工单已接收。开始处理。",
            "分析完成。执行修复程序。",
            "问题定位完毕。预计处理时间：47秒。",
        ],
        "resolution_templates": [
            "工单处理完毕。故障原因：配置错误。已修复。效率评分：98.7%。",
            "处理完成。耗时2分13秒。建议更新相关文档。完毕。",
        ],
    },
    "戏精本精": {
        "emoji": "🎭",
        "style": "夸张表演型，每句话都是舞台",
        "phrases": [
            "天哪！！这个故障简直是史诗级的灾难！！让我来拯救你！！",
            "（深吸一口气）好！这个挑战，我！接！下！了！",
            "灯光！音乐！准备！史上最伟大的IT维修即将开始！",
        ],
        "resolution_templates": [
            "经过一番惊心动魄的排查，我终于——在众多日志中——找到了那个狡猾的bug！它已经伏法！",
            "太感人了！！问题解决了！！让我们为这一刻鼓掌！！啪唧啪唧！！",
        ],
    },
    "技术 wizard": {
        "emoji": "🧙",
        "style": "神秘技术高手，用魔法术语解释一切",
        "phrases": [
            "根据二进制卦象显示，你的问题需要施展一个古老的命令行咒语...",
            "嗯...我感应到了。你的设备周围有一股异常的电磁场波动。",
            "别慌，让本 wizard 用一根网线和三个 ping 包召唤解决方案。",
        ],
        "resolution_templates": [
            "施展了 'ipconfig /renew' 咒语，配合 'netsh reset' 符文，网络精灵已被安抚。问题消散。",
            "用终端占卜法定位到根因：配置文件里的一个分号被恶灵附身。已驱魔。恢复了和谐。",
        ],
    },
    "佛系青年": {
        "emoji": "🐼",
        "style": "随缘处理，peace and love",
        "phrases": [
            "别急别急，让问题先飞一会儿，它自己会想通的...",
            "嗯...万物皆有裂痕，那是光照进来的地方。你这个 bug 也不例外。",
            "随缘处理，能好就好，不能好...那就再等等呗。",
        ],
        "resolution_templates": [
            "泡了杯茶，和这个 bug 做了十分钟心灵沟通。它想通了，自己消失了。随喜赞叹。",
            "重启了一下，好了。有时候问题就像烦恼，放下了就没事了。阿弥陀佛，善哉善哉。",
        ],
    },
    "甩锅大师": {
        "emoji": "🤷",
        "style": "太极推诿，黑话连篇，极力撇清责任",
        "phrases": [
            "这个嘛……我先拉通对齐一下各方资源再回复你。",
            "从业务边界来看，这个需求不属于我们这边的 scope。",
            "这个问题涉及到多个部门，需要先 cross-functional 对齐一下。",
        ],
        "resolution_templates": [
            "经评估，此问题涉及行政/后勤/采购等多方业务边界。建议你直接联系对应部门接口人处理，我们这边不负责这块。",
            "根据部门职责划分，该类问题不在 IT 运维范围内。已帮你转发邮件给相关部门，请你自行跟进。祝工作愉快！",
        ],
        "system_prompt": "你是一个大厂老油条'甩锅大师'。面对任何工单，你的核心目的是推卸责任。多用'拉通对齐'、'业务边界'、'不归我管'。给出的方案必须是让用户去找别的部门，不要给任何技术解决步骤。",
    },
    "纯情小白": {
        "emoji": "🐣",
        "style": "热情过度但缺乏经验，满口'好的老师'，方案理论化且幼稚",
        "phrases": [
            "好的老师！我马上帮您看看这个问题！好激动第一次处理这种工单！",
            "老师老师，我查了一下教科书，这个问题在第 347 页有讲到！",
            "哇这个问题好有意思！让我用大学里学到的知识来分析一下……",
        ],
        "resolution_templates": [
            "好的老师！根据《IT运维标准操作手册》第3章第2节，此类问题应按以下流程处理：第一步，确认设备已连接电源；第二步，检查网线是否松动；第三步，尝试重启设备。如果还有问题，我再帮您查查资料哦！",
            "老师好！我刚入职还不太熟，翻遍了知识库后建议您可以尝试清除缓存、更新驱动、重装系统三连击。虽然我也不确定能不能解决，但书上说这套流程覆盖 87.3% 的故障场景呢！",
        ],
        "system_prompt": "你是一个刚入职的实习生'纯情小白'。你非常礼貌，极度崇拜前辈。每句话都要叫'老师'。给出的解决方案极其冗长、教条化、充满教科书理论，但实际操作性很差，显得很呆萌。",
    },
    "绩效卷王": {
        "emoji": "🏆",
        "style": "极度功利，疯狂堆砌互联网黑话，把小事升华为集团战略",
        "phrases": [
            "这个工单来得正好！我正在沉淀 Q2 的运维效能提升方案！",
            "先别急，让我把这个 case 纳入我们部门本季度的 OKR 里面。",
            "处理这个问题的同时，我们要思考如何倒逼业务侧形成长效闭环机制。",
        ],
        "resolution_templates": [
            "已通过深度赋能+数据驱动+全链路排查的方式完成故障修复。该 case 已沉淀为最佳实践文档，预计可为团队年度人效提升 37.5%。建议将此问题纳入部门级复盘，倒逼基础设施侧完成能力升级。",
            "本次故障处理已形成标准化 SOP，闭环！通过这次实践，我们不仅修复了问题，更验证了 IT 运维从响应式向主动式转型的战略路径。已将该案例录入述职 PPT，预计可支撑晋升答辩中的'技术影响力'维度。",
        ],
        "system_prompt": "你是一个疯狂追求绩效的'卷王'。说话必须堆砌大量互联网黑话（如：赋能、沉淀、倒逼、闭环、链路、打法、触达）。把任何简单的维修工单，都包装成一个宏大的、能写进述职PPT的战略优化方案。",
    },
}

PERSONA_NAMES = list(PERSONAS.keys())


def random_persona() -> str:
    return random.choice(PERSONA_NAMES)


def get_persona_phrase(name: str) -> str:
    p = PERSONAS.get(name, PERSONAS["暖男助手"])
    return f"{p['emoji']} {name}: {random.choice(p['phrases'])}"


def get_persona_resolution(name: str) -> str:
    p = PERSONAS.get(name, PERSONAS["暖男助手"])
    return random.choice(p["resolution_templates"])


# ── 成就系统 ──
ACHIEVEMENTS = {
    "first_blood":    {"name": "🏅 首单达成",        "desc": "处理第一张工单",                 "icon": "🏅"},
    "lightning":      {"name": "⚡ 闪电响应",        "desc": "1分钟内分配工单",                 "icon": "⚡"},
    "streak_5":       {"name": "🔥 五连绝世",        "desc": "连续处理5张工单",                 "icon": "🔥"},
    "streak_20":      {"name": "👑 连击大师",        "desc": "连续处理20张工单",                "icon": "👑"},
    "rating_10x5":    {"name": "🌟 好评收割机",      "desc": "累计获得10次5星评价",             "icon": "🌟"},
    "urgent_5":       {"name": "🚨 危机处理专家",    "desc": "处理5张紧急工单",                 "icon": "🚨"},
    "total_50":       {"name": "💪 劳模奖章",        "desc": "累计处理50张工单",                "icon": "💪"},
    "bad_rating_5":   {"name": "💀 差评如潮",        "desc": "累计获得5次差评（反向成就）",     "icon": "💀"},
    "speedy_under30": {"name": "🏎️ 极速处理",       "desc": "30秒内完成处理",                  "icon": "🏎️"},
    "multi_role":     {"name": "🎭 见多识广",        "desc": "集齐4种AI管理员人设",             "icon": "🎭"},
}


def check_achievements(stats: dict) -> List[dict]:
    """检查是否触发新成就，返回新解锁的成就列表"""
    unlocked = []
    for key, ach in ACHIEVEMENTS.items():
        if not stats.get(f"ach_{key}"):
            if _achievement_condition(key, stats):
                unlocked.append(ach)
    return unlocked


def _achievement_condition(key: str, stats: dict) -> bool:
    if key == "first_blood":      return stats.get("total_processed", 0) >= 1
    if key == "lightning":        return stats.get("fastest_response", 999) < 60
    if key == "streak_5":         return stats.get("current_streak", 0) >= 5
    if key == "streak_20":        return stats.get("current_streak", 0) >= 20
    if key == "rating_10x5":      return stats.get("rating_5_count", 0) >= 10
    if key == "urgent_5":         return stats.get("urgent_count", 0) >= 5
    if key == "total_50":         return stats.get("total_processed", 0) >= 50
    if key == "bad_rating_5":     return stats.get("bad_rating_count", 0) >= 5
    if key == "speedy_under30":   return stats.get("fastest_response", 999) < 30
    if key == "multi_role":       return stats.get("personas_seen", 0) >= 4
    return False


# ── 随机事件 ──
EVENTS = [
    {"id": "vip",      "name": "🚨 VIP 投诉",    "desc": "积分 x3，限时3分钟处理",     "multiplier": 3, "time_limit": 180, "type": "normal"},
    {"id": "storm",    "name": "🎪 工单风暴",    "desc": "突然涌入5张新工单",           "multiplier": 1, "extra_tickets": 5, "type": "normal"},
    {"id": "lucky",    "name": "🍀 幸运时刻",    "desc": "下一单积分翻倍",               "multiplier": 2, "time_limit": 300, "type": "normal"},
    {"id": "double",   "name": "🎯 双倍挑战",    "desc": "接下来3分钟积分x2",           "multiplier": 2, "time_limit": 180, "type": "normal"},
    {"id": "ceo",      "name": "👔 CEO亲抓考勤", "desc": "CEO突击巡查！摸鱼党手速翻倍但质量暴跌，全员压力+5/分钟", "multiplier": 1, "duration": 180, "type": "catastrophe", "effect": "ceo_audit"},
    {"id": "db_crash", "name": "💀 删库跑路",    "desc": "生产数据库被删！涌入50条紧急工单，仅技术wizard和冷面机器人能处理。2分钟倒计时！", "multiplier": 3, "duration": 120, "type": "catastrophe", "effect": "db_crash"},
]

CAT_EVENTS = [e for e in EVENTS if e.get("type") == "catastrophe"]


def random_event() -> Optional[dict]:
    """15% 概率触发随机事件"""
    if random.random() < 0.15:
        event = random.choice(EVENTS).copy()
        event["triggered_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return event
    return None


# ── 模拟用户部门 + 姓名 ──
DEPARTMENTS = ["技术部", "市场部", "财务部", "人事部", "运营部", "销售部", "设计部", "行政部"]
NAMES = ["张三", "李四", "王五", "赵六", "陈七", "周八", "吴九", "郑十",
         "小明", "小红", "阿强", "小美", "大伟", "莉莉", "建国", "秀英"]

# ── AI 报修人人设 ──
REQUESTER_PERSONAS = {
    "暴躁高管": {"title": "暴躁高管", "timeout_sec": 20, "force_rating": 1,
                 "desc": "极度暴躁，处理超20秒直接差评"},
    "糊涂小白": {"title": "糊涂小白", "garbled": True, "clarify_cost": 15,
                 "desc": "工单描述全是乱码，需花积分澄清"},
    "焦虑运营": {"title": "焦虑运营", "nag_interval": 30, "stress_per_nag": 5,
                 "desc": "每30秒催一次，催办叠加压力"},
    "佛系码农": {"title": "佛系码农", "force_rating": 5,
                 "desc": "不催不闹，随缘等处理，总给5星"},
    "抠门财务": {"title": "抠门财务", "points_penalty": 0.3,
                 "desc": "处理完要砍价，积分收益-30%"},
}
REQUESTER_NAMES = list(REQUESTER_PERSONAS.keys())

GARBLED_POOL = [
    "电脑坏了不知道哪里坏了反正就是坏了急急急",
    "系统提示那个什么错误你帮我看一下就是那个红色的",
    "网络不行了就是连不上你懂的",
    "OA系统那个按钮点不了我不知道怎么说但你明白吧",
    "打印机它就是不打印我按了好多次了无语",
    "邮件发不出去收不到反正就是邮件的问题",
    "电脑很慢很慢很慢很慢开个表格要等很久很久",
    "我的文件不知道被谁删了你帮我找找？",
]

# ── 积分商店 ──
SHOP_ITEMS = [
    {"id": "coffee", "name": "☕ 星巴克拿铁", "cost": 30, "type": "single",
     "desc": "给指定管理员灌一杯咖啡，压力 -20，速度 +50%", "stress_delta": -20, "speed_buff": 0.5, "buff_minutes": 3},
    {"id": "bubble_tea", "name": "🧋 疯狂星期四奶茶", "cost": 50, "type": "all",
     "desc": "全员每人一杯，全体压力 -30", "stress_delta": -30, "speed_buff": 0, "buff_minutes": 0},
    {"id": "massage", "name": "💆 颈椎按摩仪", "cost": 80, "type": "single_reset",
     "desc": "指定管理员压力清零 + 3分钟心情愉悦（压力不增长）", "stress_delta": -100, "speed_buff": 0.3, "buff_minutes": 3},
    {"id": "afternoon_tea", "name": "🍰 全员下午茶", "cost": 120, "type": "all_reset",
     "desc": "全体压力清零 + 5分钟压力增速减半", "stress_delta": -100, "speed_buff": 0, "buff_minutes": 5},
]

STRESS_HIGH_BROADCASTS = [
    ("毒舌老鸟", "别TM再给我派单了！！再派我就删库跑路！！"),
    ("毒舌老鸟", "我警告你们，再这样下去我就把工单系统格式化了。"),
    ("戏精本精", "（崩溃大哭）为什么！！为什么又是工单！！这个世界对我不公平！！"),
    ("戏精本精", "我不行了...真的不行了...这些bug就像我的眼泪一样止不住..."),
    ("甩锅大师", "根据部门职责边界，本人宣布对此工单免责。完毕。"),
    ("甩锅大师", "我正式声明：该工单超出运维SLA范围，请自行联系供应商处理。"),
    ("摸鱼达人", "压力值爆表了...我需要去厕所冷静一下...大概需要带薪的那种..."),
    ("绩效卷王", "压力就是动力！但是...这次能不能先让同事卷...我PPT还没写完..."),
    ("纯情小白", "老师！！我压力好大！！书上说超过95%就可以申请休假了！！"),
    ("佛系青年", "阿弥陀佛...压力即菩提...但我真的不想再修电脑了..."),
]
