# 工单剧场 · Ticket Theater

IT 工单模拟经营 + 游戏化 Web 应用。扮演 IT 支持团队，处理工单赚取积分，体验故事化的工单管理。

## 功能特性

- **AI 智能工单**：DeepSeek 自动生成工单描述、分类和处理方案
- **多人设管理员**：7 位 AI 管理员（毒舌老鸟、暖男助手、摸鱼达人、冷面机器人等），各具独特语气和风格
- **工单生命周期**：待分配 → 处理中 → 待审核 → 已完成 → 已评价，完整流程
- **游戏化系统**：成就徽章、排行榜、随机灾难事件（如数据库崩溃）
- **积分商店**：道具购买、减压物品、管理员 Buff
- **压力值机制**：管理员压力过高影响效率，需购买减压道具
- **双模式**：用户模式（手动操作）和导演模式（AI 自动推进）
- **征集方案**：并行调用 AI，3-4 位管理员同时出方案供选择

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI |
| 数据库 | SQLite |
| AI | DeepSeek API |
| 前端 | 纯 HTML/CSS/JS（OKLCH 设计系统） |

## 快速开始

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

访问 `http://localhost:8000/`

> API Key 已内置在 `.env` 和代码中，开箱即用。

## 目录结构

```
TicketTheater/
├── backend/
│   ├── main.py            # FastAPI 应用，所有 API 路由
│   ├── ai_classifier.py   # DeepSeek AI 分类 + 方案生成
│   ├── db.py              # SQLite 数据库
│   ├── simulator.py       # AI 工单/方案/评价模拟器
│   ├── workflow.py        # 工单生命周期状态机 + 积分计算
│   ├── gamification.py    # 成就/随机事件/商店/人设
│   └── trend_monitor.py   # 趋势监控
├── frontend/
│   └── index.html         # 单文件前端
├── requirements.txt
└── README.md
```
