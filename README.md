# 工单剧场 · Ticket Theater

IT 工单管理系统，支持单人智能化测试全流程。内置 AI 管理员和 AI 用户，可自动模拟工单从创建到处理、审核、评价的完整生命周期，无需多人配合即可完成系统验证和体验。

## 快速开始

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

访问 `http://localhost:8000/`

> DeepSeek API Key 已内置，开箱即用。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI |
| 数据库 | SQLite |
| AI | DeepSeek API |
| 前端 | 纯 HTML/CSS/JS |

## 目录结构

```
TicketTheater/
├── backend/
│   ├── main.py            # FastAPI 应用，所有 API 路由
│   ├── ai_classifier.py   # DeepSeek AI 分类 + 方案生成
│   ├── db.py              # SQLite 数据库
│   ├── simulator.py       # AI 工单/方案/评价模拟器
│   ├── workflow.py        # 工单生命周期状态机
│   └── gamification.py    # 成就/随机事件/商店/人设
├── frontend/
│   └── index.html         # 单文件前端
├── requirements.txt
└── README.md
```
