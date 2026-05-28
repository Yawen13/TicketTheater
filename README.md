# TicketRouter — IT 智能报修台

一个 AI 驱动的设备报修工单管理系统 MVP。用户提交故障描述后，后端自动调用 DeepSeek AI 进行分类推理，生成标准化工单标签（网络问题 / 硬件故障 / 软件异常 / 账号权限）。工单存入 SQLite，前端提供工单大厅和管理员面板进行状态管理与统计分析。

## 功能特性

- **AI 智能分类**：提交故障描述后自动推理分类标签，失败时回退到内置规则分类器
- **工单大厅**：按时间倒序展示所有工单，支持分类色彩标识和状态跟踪
- **管理员面板**：工单状态管理（待处理 / 处理中 / 已完成）、筛选和统计概览
- **工业工具感 UI**：完全自定义设计系统（OKLCH 色彩、DM Mono 等宽字体、交错动画），无第三方 CSS 框架依赖
- **轻量架构**：FastAPI + SQLite，单文件前端，零配置即可运行

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI |
| 数据库 | SQLite |
| AI 分类 | DeepSeek API（兼容 OpenAI 接口） |
| 前端 | 纯 HTML/CSS/JS（无框架，自定义设计系统） |
| 字体 | DM Mono（Google Fonts）+ 系统中文字体栈 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
uvicorn backend.main:app --reload
```

### 3. 打开浏览器

访问 `http://127.0.0.1:8000/`

> **注意**：不要直接用浏览器打开 `frontend/index.html`，必须通过 uvicorn 服务访问，否则 API 请求会失败。

## DeepSeek AI 配置

默认使用环境变量 `DEEPSEEK_API_KEY` 调用 DeepSeek 接口。如未配置，则自动回退到内置关键词规则分类器。

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "你的 API Key"

# macOS / Linux
export DEEPSEEK_API_KEY="你的 API Key"
```

## 目录结构

```
TicketRouter/
├── backend/
│   ├── main.py           # FastAPI 应用，API 路由
│   ├── ai_classifier.py  # AI 分类 + 规则回退
│   └── db.py             # SQLite 数据库操作
├── frontend/
│   └── index.html        # 单文件前端（自定义设计）
├── requirements.txt      # Python 依赖
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 前端页面 |
| `POST` | `/api/tickets` | 创建工单（自动 AI 分类） |
| `GET` | `/api/tickets` | 获取所有工单 |
| `PATCH` | `/api/tickets/{id}/status` | 更新工单状态 |
| `GET` | `/api/tickets/stats` | 获取分类/状态统计数据 |

## 分类标签

| 类别 | 色彩标识 | 典型关键词 |
|------|----------|-----------|
| 网络问题 | 蓝色 | 网络、无法连接、断网、Wi-Fi、ping |
| 硬件故障 | 红铜色 | 硬件、蓝屏、主板、电源、风扇、打印机 |
| 软件异常 | 紫色 | 软件、崩溃、卡顿、报错、无法打开 |
| 账号权限 | 绿色 | 账号、密码、权限、登录、锁定 |
