import os
import re
import datetime
import random
from pathlib import Path

# Load .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip().strip("\"'"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Dict, List, Optional
from pydantic import BaseModel

from backend.db import (
    init_db, add_ticket, get_ticket, get_all_tickets,
    update_ticket, get_ticket_stats, get_leaderboard, get_analytics,
)
from backend.ai_classifier import classify_description, generate_ai_resolution, rule_based_classification
from backend.workflow import (
    ALL_STATUSES, STATUS_NEW, STATUS_PROGRESS, STATUS_REVIEW,
    STATUS_DONE, STATUS_RATED, can_transition, get_next_status,
    calculate_points, get_status_progress, calculate_stress,
    get_stress_persona_effect,
)
from backend.gamification import (
    PERSONAS, PERSONA_NAMES, random_persona,
    get_persona_phrase, get_persona_resolution,
    check_achievements, ACHIEVEMENTS, random_event,
    DEPARTMENTS, NAMES, SHOP_ITEMS, STRESS_HIGH_BROADCASTS,
    CAT_EVENTS, REQUESTER_PERSONAS, REQUESTER_NAMES,
)
from backend.simulator import generate_ai_ticket, generate_ai_processing, simulate_full_lifecycle, simulate_ai_rating, gather_resolution_options

app = FastAPI(title="工单剧场")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

LIFECYCLE_STEPS = [
    {"step": 1, "label": "创建", "status": STATUS_NEW, "icon": "📝"},
    {"step": 2, "label": "分配", "status": STATUS_PROGRESS, "icon": "🎯"},
    {"step": 3, "label": "处理", "status": STATUS_PROGRESS, "icon": "🔧"},
    {"step": 4, "label": "审核", "status": STATUS_REVIEW, "icon": "🔍"},
    {"step": 5, "label": "完成", "status": STATUS_DONE, "icon": "✅"},
    {"step": 6, "label": "评价", "status": STATUS_RATED, "icon": "⭐"},
]


# ── Pydantic Models ──
class TicketCreate(BaseModel):
    description: str
    creator: str = "匿名用户"
    department: str = "未指定部门"

class TicketWorkflowStep(BaseModel):
    ticket_id: int
    action: str  # assign|resolve_options|resolve_confirm|review|rate
    resolution: Optional[str] = None
    persona: Optional[str] = None

class TicketRate(BaseModel):
    ticket_id: int
    rating: int
    feedback: str = ""

class ModeInit(BaseModel):
    mode: str  # user | director

class Ticket(BaseModel):
    id: int
    ticket_no: str
    creator: str
    department: str
    description: str
    category: str
    risk_level: str
    status: str
    assignee: Optional[str] = None
    resolution: Optional[str] = None
    review_comment: Optional[str] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None
    persona: Optional[str] = None
    points_earned: int = 0
    created_at: str
    assigned_at: Optional[str] = None
    resolved_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    closed_at: Optional[str] = None


def _row_to_ticket(row) -> Ticket:
    return Ticket(
        id=row["id"], ticket_no=row["ticket_no"],
        creator=row["creator"], department=row["department"],
        description=row["description"], category=row["category"],
        risk_level=row["risk_level"], status=row["status"],
        assignee=row["assignee"], resolution=row["resolution"],
        review_comment=row["review_comment"],
        rating=row["rating"], feedback=row["feedback"],
        persona=row["persona"], points_earned=row["points_earned"] or 0,
        created_at=row["created_at"], assigned_at=row["assigned_at"],
        resolved_at=row["resolved_at"], reviewed_at=row["reviewed_at"],
        closed_at=row["closed_at"],
    )


# ── Session state (in-memory) ──
session_state: Dict[str, dict] = {}


@app.on_event("startup")
def on_startup():
    init_db()


# ── 模式初始化 ──
@app.post("/api/mode/init")
def init_mode(body: ModeInit):
    sid = "default"
    state = {
        "mode": body.mode,
        "score": 0,
        "streak": 0,
        "processed": 0,
        "personas_seen": set(),
        "active_event": None,
        "event_multiplier": 1,
        "persona_stress": {name: 0 for name in PERSONA_NAMES},
        "active_buffs": {},
    }
    session_state[sid] = state

    tickets_data = []
    if body.mode == "director":
        # 导演模式：预生成一批 AI 用户工单
        for _ in range(random.randint(3, 6)):
            t = generate_ai_ticket()
            cat, humor, risk = rule_based_classification(t["description"])  # 毫秒级，避免 API 延迟
            tid = add_ticket(t["description"], cat, risk, t["creator"], t["department"])
            tickets_data.append(_row_to_ticket(get_ticket(tid)))
    else:
        # 用户模式：加载已有工单 + 预生成模拟 AI 用户工单
        for _ in range(random.randint(2, 4)):
            t = generate_ai_ticket()
            cat, humor, risk = rule_based_classification(t["description"])
            tid = add_ticket(t["description"], cat, risk, t["creator"], t["department"])
        rows = get_all_tickets()
        tickets_data = [_row_to_ticket(r) for r in rows]

    return {
        "mode": body.mode,
        "message": f"进入{'导演模式 - 你是管理员' if body.mode == 'director' else '用户模式 - 你是报修人'}",
        "tickets": tickets_data,
        "score": 0,
    }


# ── 提交工单（用户模式） ──
@app.post("/api/tickets", response_model=dict)
def create_ticket(ticket: TicketCreate):
    description = ticket.description.strip()
    if not description or len(description) < 4:
        raise HTTPException(status_code=400, detail="描述太短了")
    if len(description) > 500:
        raise HTTPException(status_code=400, detail="描述太长了")
    if re.search(r"(.)\1{4,}", description):
        raise HTTPException(status_code=400, detail="请描述真实的故障")

    cat, humor, risk = classify_description(description)
    tid = add_ticket(description, cat, risk, ticket.creator, ticket.department)
    row = get_ticket(tid)

    # 模拟 AI 管理员自动处理
    sim = simulate_full_lifecycle(tid)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    persona_name = sim["persona"]
    update_ticket(tid,
        status=STATUS_PROGRESS, assignee=sim["assignee"], persona=persona_name,
        assigned_at=now)

    return {
        "ticket": _row_to_ticket(get_ticket(tid)),
        "ai_response": {
            "persona": persona_name,
            "persona_emoji": PERSONAS[persona_name]["emoji"],
            "phrase": sim["assign_phrase"],
            "assignee": sim["assignee"],
        },
        "humor_note": humor,
    }


# ── 工单列表 ──
@app.get("/api/tickets", response_model=List[Ticket])
def list_tickets(status: str = "all", category: str = "all"):
    rows = get_all_tickets(status, category)
    return [_row_to_ticket(r) for r in rows]


# ── 统计数据（必须在 /{ticket_id} 之前） ──
@app.get("/api/tickets/stats")
def ticket_stats():
    return get_analytics()


# ── 工单详情 ──
@app.get("/api/tickets/{ticket_id}", response_model=Ticket)
def ticket_detail(ticket_id: int):
    row = get_ticket(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    return _row_to_ticket(row)


# ── 生命周期推进 ──
@app.post("/api/tickets/workflow")
def advance_workflow(body: TicketWorkflowStep):
    row = get_ticket(body.ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")

    current = row["status"]
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    if body.action == "assign":
        if not can_transition(current, STATUS_PROGRESS):
            raise HTTPException(status_code=400, detail=f"无法从「{current}」分配到处理中")
        persona_name = random_persona()
        assignee = f"{PERSONAS[persona_name]['emoji']} {persona_name}"
        phrase = get_persona_phrase(persona_name)

        # 计算分配积分 + 更新压力
        pts, reason = calculate_points("assign", random.randint(5, 120), row["risk_level"] or "中")
        st = session_state.get("default", {})
        st_delta = calculate_stress("assign", row["risk_level"] or "中")
        st["persona_stress"][persona_name] = min(100, st["persona_stress"].get(persona_name, 0) + st_delta)
        update_ticket(body.ticket_id, status=STATUS_PROGRESS, assignee=assignee,
                      persona=persona_name, assigned_at=now,
                      points_earned=(row["points_earned"] or 0) + pts)
        return {"ok": True, "status": STATUS_PROGRESS, "assignee": assignee,
                "phrase": phrase, "points": pts, "points_reason": reason,
                "stress_delta": st_delta, "persona_stress": st["persona_stress"][persona_name]}

    elif body.action == "resolve_options":
        if current not in (STATUS_NEW, STATUS_PROGRESS):
            raise HTTPException(status_code=400, detail="只能从待分配或处理中获取方案选项")
        # 生成 3-4 个不同人设的处理方案
        options = gather_resolution_options(row)
        return {"ok": True, "options": options}

    elif body.action == "resolve_confirm":
        if current not in (STATUS_NEW, STATUS_PROGRESS):
            raise HTTPException(status_code=400, detail="只能从待分配或处理中提交解决方案")
        resolution = body.resolution if hasattr(body, 'resolution') and body.resolution else "问题已处理完成。"

        # 如果是从待分配直接确认，同时设置处理人
        persona_name = body.persona if hasattr(body, 'persona') and body.persona else None
        if current == STATUS_NEW and persona_name:
            assignee = f"{PERSONAS[persona_name]['emoji']} {persona_name}"
            update_ticket(body.ticket_id, status=STATUS_REVIEW,
                          assignee=assignee, persona=persona_name,
                          resolution=resolution, assigned_at=now, resolved_at=now)
        else:
            update_ticket(body.ticket_id, status=STATUS_REVIEW, resolution=resolution,
                          resolved_at=now)

        pts, reason = calculate_points("resolve", random.randint(5, 90), row["risk_level"] or "中")
        pts_earned = (row["points_earned"] or 0) + pts
        update_ticket(body.ticket_id, points_earned=pts_earned)
        return {"ok": True, "status": STATUS_REVIEW, "resolution": resolution,
                "points": pts, "points_reason": reason}

    elif body.action == "review":
        if not can_transition(current, STATUS_DONE):
            raise HTTPException(status_code=400, detail=f"无法从「{current}」审核通过")
        review = random.choice(["审核通过，处理方案合理。", "已确认问题解决。", "方案可行，批准关闭。"])
        pts, reason = calculate_points("review", 0, row["risk_level"] or "中")
        pts_earned = (row["points_earned"] or 0) + pts
        # 完成工单降低压力
        st = session_state.get("default", {})
        persona = row["persona"] or ""
        if persona and persona in st.get("persona_stress", {}):
            st_delta = calculate_stress("done")
            st["persona_stress"][persona] = max(0, st["persona_stress"][persona] + st_delta)
        update_ticket(body.ticket_id, status=STATUS_DONE, review_comment=review,
                      reviewed_at=now, closed_at=now,
                      points_earned=pts_earned)
        return {"ok": True, "status": STATUS_DONE, "review": review,
                "points": pts, "points_reason": reason}

    elif body.action == "rate":
        raise HTTPException(status_code=400, detail="请使用评分接口")

    raise HTTPException(status_code=400, detail="无效操作")


# ── 评价 ──
@app.post("/api/tickets/rate")
def rate_ticket(body: TicketRate):
    row = get_ticket(body.ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    if row["status"] != STATUS_DONE:
        raise HTTPException(status_code=400, detail="只能评价已完成的工单")
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="评分须为 1-5")

    pts, reason = calculate_points("rate", 0, row["risk_level"] or "中", body.rating)
    pts_earned = (row["points_earned"] or 0) + pts
    update_ticket(body.ticket_id, status=STATUS_RATED,
                  rating=body.rating, feedback=body.feedback,
                  points_earned=pts_earned)
    return {"ok": True, "status": STATUS_RATED, "points": pts, "points_reason": reason}


class AutoRateRequest(BaseModel):
    ticket_id: int

# ── AI 用户自动评价（导演模式） ──
@app.post("/api/tickets/auto-rate")
def auto_rate_ticket(body: AutoRateRequest):
    row = get_ticket(body.ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    if row["status"] != STATUS_DONE:
        raise HTTPException(status_code=400, detail="只能评价已完成的工单")

    persona = row["persona"] or "暖男助手"
    st = session_state.get("default", {})
    pstress = st.get("persona_stress", {}).get(persona, 0)
    processing_time = random.randint(10, 360)
    # 高压力增加处理延迟
    stress_eff = get_stress_persona_effect(persona, pstress)
    processing_time = int(processing_time * stress_eff["speed_mult"])
    # 提取报修人人设
    req_data = None
    creator = row["creator"] or ""
    for rkey, rval in REQUESTER_PERSONAS.items():
        if rval["title"] in creator:
            req_data = rval; break
    rating_data = simulate_ai_rating(persona, processing_time, pstress, req_data)

    pts, reason = calculate_points("rate", processing_time, row["risk_level"] or "中",
                                   rating_data["rating"])
    pts_earned = (row["points_earned"] or 0) + pts
    # 评分影响压力
    if persona in st.get("persona_stress", {}):
        st_delta = calculate_stress("rated", rating=rating_data["rating"])
        st["persona_stress"][persona] = max(0, min(100, st["persona_stress"][persona] + st_delta))
    update_ticket(body.ticket_id, status=STATUS_RATED,
                  rating=rating_data["rating"], feedback=rating_data["feedback"],
                  points_earned=pts_earned)
    return {
        "ok": True, "status": STATUS_RATED,
        "rating": rating_data["rating"], "feedback": rating_data["feedback"],
        "creator": row["creator"], "points": pts, "points_reason": reason,
        "persona_stress": st["persona_stress"].get(persona, 0)}


# ── 刷新：生成 1-2 张 AI 工单（导演模式） ──
@app.post("/api/refresh")
def refresh_tickets():
    count = random.randint(1, 2)
    generated = []
    for _ in range(count):
        t = generate_ai_ticket()
        cat, humor, risk = classify_description(t["description"])
        tid = add_ticket(t["description"], cat, risk, t["creator"], t["department"])
        generated.append(_row_to_ticket(get_ticket(tid)))
    return {"generated": generated, "count": count}


# ── 排行榜 ──
@app.get("/api/leaderboard")
def leaderboard():
    return get_leaderboard(10)


# ── 成就 ──
@app.get("/api/achievements")
def achievements():
    rows = get_all_tickets()
    stats = {
        "total_processed": len([r for r in rows if r["assignee"]]),
        "current_streak": 0,  # 简化处理
        "rating_5_count": len([r for r in rows if r["rating"] == 5]),
        "urgent_count": len([r for r in rows if r["risk_level"] == "紧急"]),
        "bad_rating_count": len([r for r in rows if r["rating"] is not None and r["rating"] <= 2]),
        "fastest_response": 999,
        "personas_seen": len(set(r["persona"] for r in rows if r["persona"])),
    }
    # 计算连击
    streak = 0
    for r in rows:
        if r["assignee"]:
            streak += 1
        else:
            break
    stats["current_streak"] = streak
    stats["fastest_response"] = 50  # 模拟

    new_achievements = check_achievements(stats)
    all_achievements = [
        {"key": k, "name": v["name"], "desc": v["desc"], "icon": v["icon"],
         "unlocked": _achievement_unlocked(k, stats)}
        for k, v in ACHIEVEMENTS.items()
    ]
    return {"achievements": all_achievements, "new": new_achievements}


def _achievement_unlocked(key: str, stats: dict) -> bool:
    from backend.gamification import _achievement_condition
    return _achievement_condition(key, stats)


# ── 自动完成工单（用户模式） ──
@app.post("/api/tickets/auto-complete/{ticket_id}")
def auto_complete_ticket(ticket_id: int):
    row = get_ticket(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    persona_name = row["persona"] or random_persona()
    p = PERSONAS[persona_name]

    # 生成方案（AI 或模板兜底）
    try:
        resolution = generate_ai_resolution(
            row["description"], row["category"],
            row["risk_level"] or "中", persona_name)
    except Exception:
        resolution = random.choice(p["resolution_templates"])
    if not resolution or len(resolution) < 5:
        resolution = random.choice(p["resolution_templates"])

    # 分配 → 处理 → 审核
    assignee = f"{p['emoji']} {persona_name}"
    update_ticket(ticket_id, status=STATUS_PROGRESS, assignee=assignee,
                  persona=persona_name, assigned_at=now)
    pts, _ = calculate_points("assign", random.randint(5, 60), row["risk_level"] or "中")

    update_ticket(ticket_id, status=STATUS_REVIEW, resolution=resolution,
                  resolved_at=now)

    review_comment = random.choice(["审核通过，处理方案合理。", "已确认问题解决。"])
    pts2, _ = calculate_points("review", 0, row["risk_level"] or "中")
    update_ticket(ticket_id, status=STATUS_DONE, review_comment=review_comment,
                  reviewed_at=now, closed_at=now,
                  points_earned=(row["points_earned"] or 0) + pts + pts2)

    updated = get_ticket(ticket_id)
    return {
        "ok": True,
        "ticket": _row_to_ticket(updated),
        "persona": persona_name,
        "emoji": p["emoji"],
        "assignee": assignee,
        "phrase": random.choice(p["phrases"]),
        "resolution": resolution,
        "review_comment": review_comment,
    }


# ── 随机事件 ──
@app.get("/api/random-event")
def get_random_event():
    state = session_state.get("default", {})
    # 5% 概率触发灾难事件
    if random.random() < 0.05 and not state.get("active_event"):
        cat = random.choice(CAT_EVENTS).copy()
        cat["triggered_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=cat.get("duration", 120))
        cat["expires_at"] = expires.strftime("%Y-%m-%d %H:%M:%S")
        state["active_event"] = cat
        state["event_multiplier"] = cat.get("multiplier", 1)
        state["catastrophe"] = cat
        if cat.get("effect") == "db_crash":
            # 瞬间涌入50条紧急工单
            from backend.simulator import generate_ai_ticket as gen_t
            from backend.ai_classifier import rule_based_classification
            for _ in range(50):
                t = gen_t()
                _, _, _ = rule_based_classification(t["description"])
                add_ticket(t["description"], "软件异常", "紧急", t["creator"], t["department"])
        session_state["default"] = state
        return {"event": cat, "type": "catastrophe"}
    event = random_event()
    if event:
        state["active_event"] = event
        state["event_multiplier"] = event.get("multiplier", 1)
        session_state["default"] = state
    return {"event": event, "type": "normal" if event else None}


# ── 压力值 ──
@app.get("/api/stress")
def get_stress():
    st = session_state.get("default", {})
    cat = st.get("catastrophe")
    resp = {
        "persona_stress": st.get("persona_stress", {}),
        "active_buffs": st.get("active_buffs", {}),
        "score": st.get("score", 0),
    }
    if cat:
        # 检查灾难是否过期
        expires_str = cat.get("expires_at", "")
        expired = False
        if expires_str:
            try:
                exp_dt = datetime.datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
                if datetime.datetime.utcnow() >= exp_dt:
                    expired = True
            except: pass
        if expired and cat.get("effect") == "db_crash":
            # 结算：未解决的工单每条 -5 分
            rows = get_all_tickets()
            unsolved = [r for r in rows if r["status"] in (STATUS_NEW, STATUS_PROGRESS) and r["risk_level"] == "紧急"]
            penalty = len(unsolved) * 5
            if penalty > 0:
                st["score"] = max(0, st["score"] - penalty)
            resp["catastrophe_settled"] = {"unsolved": len(unsolved), "penalty": penalty}
            st["catastrophe"] = None
            st["active_event"] = None
            session_state["default"] = st
        elif expired:
            st["catastrophe"] = None
            st["active_event"] = None
            session_state["default"] = st
        elif not expired:
            resp["catastrophe"] = {
                "type": cat.get("effect"), "name": cat.get("name"),
                "expires_at": cat.get("expires_at"), "duration": cat.get("duration", 0),
            }
    return resp


# ── 积分商店 ──
@app.get("/api/shop/items")
def list_shop_items():
    st = session_state.get("default", {})
    return {"items": SHOP_ITEMS, "score": st.get("score", 0)}


class BuyRequest(BaseModel):
    item_id: str
    persona: Optional[str] = None

@app.post("/api/shop/buy")
def buy_item(body: BuyRequest):
    st = session_state.get("default", {})
    if not st:
        raise HTTPException(status_code=400, detail="请先初始化模式")
    item = next((i for i in SHOP_ITEMS if i["id"] == body.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="道具不存在")
    if st["score"] < item["cost"]:
        raise HTTPException(status_code=400, detail=f"积分不足！需要 {item['cost']} 分，当前 {st['score']} 分")

    st["score"] -= item["cost"]
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    buffs = st.get("active_buffs", {})

    if item["type"] == "single" or item["type"] == "single_reset":
        if not body.persona:
            raise HTTPException(status_code=400, detail="请指定管理员")
        pname = body.persona
        if item["stress_delta"] <= -100:
            st["persona_stress"][pname] = 0
        else:
            st["persona_stress"][pname] = max(0, st["persona_stress"].get(pname, 0) + item["stress_delta"])
        if item.get("buff_minutes", 0) > 0:
            exp = (datetime.datetime.utcnow() + datetime.timedelta(minutes=item["buff_minutes"])).strftime("%Y-%m-%d %H:%M:%S")
            buffs[pname] = {"effect": item["id"], "expires_at": exp, "speed_mult": 1.0 - item.get("speed_buff", 0)}
    else:
        # all / all_reset
        for name in PERSONA_NAMES:
            if item["stress_delta"] <= -100:
                st["persona_stress"][name] = 0
            else:
                st["persona_stress"][name] = max(0, st["persona_stress"].get(name, 0) + item["stress_delta"])
        if item.get("buff_minutes", 0) > 0:
            exp = (datetime.datetime.utcnow() + datetime.timedelta(minutes=item["buff_minutes"])).strftime("%Y-%m-%d %H:%M:%S")
            buffs["all"] = {"effect": item["id"], "expires_at": exp}

    st["active_buffs"] = buffs
    session_state["default"] = st
    return {
        "ok": True, "item": item["name"], "cost": item["cost"],
        "score": st["score"], "persona_stress": st["persona_stress"],
        "msg": f"成功购买 {item['name']}！花费 {item['cost']} 分，剩余 {st['score']} 分。",
    }


# ── 生命周期步骤 ──
@app.get("/api/lifecycle")
def get_lifecycle():
    return {"steps": LIFECYCLE_STEPS}


# ── 前端 ──
@app.get("/")
def read_index():
    html_file = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    return FileResponse(html_file)
