# SPAgent - 医学教育三智能体训练系统

基于 **Tri-Agent Architecture**（三智能体协作架构）的医学教育标准化病人训练平台，
聚焦消化系统急性腹痛鉴别诊断场景。

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│  Chat UI ─── Eval Sidebar ─── Dashboard ─── Export  │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket / REST
┌──────────────────────┴──────────────────────────────┐
│                  Backend (FastAPI)                    │
│  ┌─────────────────────────────────────────────┐    │
│  │           Agent Orchestrator                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐│    │
│  │  │  AI-SP   │ │Scaffolding│ │   Silent     ││    │
│  │  │(模拟病人)│ │  Tutor   │ │  Evaluator   ││    │
│  │  └──────────┘ └──────────┘ └──────────────┘│    │
│  └─────────────────────────────────────────────┘    │
│  Case Engine ── Checklist ── Analytics Pipeline     │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │  PostgreSQL  │  Qwen API │
          └─────────────────────────┘
```

## 三智能体

| Agent | 角色 | 职责 |
|-------|------|------|
| AI-SP | 模拟病人 | 三层信息隐藏 + 情绪响应，高保真模拟 |
| Scaffolding Tutor | 临床导师 | 超时/偏方向/遗漏关键/过早诊断 四类干预 |
| Silent Evaluator | 隐形考官 | 实时 checklist 打勾 + 增量评分 |

## 病例库 (MVP)

1. 急性阑尾炎 — 转移性右下腹痛
2. 急性胰腺炎 — 上腹痛+束带感
3. 消化性溃疡穿孔 — 突发板状腹
4. 急性胆囊炎 — 右上腹绞痛+Murphy征
5. 肠梗阻 — 痛吐胀闭四大症状
6. 肠系膜动脉栓塞 — 症状体征分离

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY 和 DATABASE_URL
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 数据库

需要 PostgreSQL。Railway 部署时自动配置。本地开发：

```bash
# 创建数据库
createdb spagent
# 应用表会在后端启动时自动创建
```

## Railway 部署

1. 在 Railway 创建新项目
2. 添加 PostgreSQL 服务
3. 添加后端服务 (连接 `backend/` 目录)
4. 添加前端服务 (连接 `frontend/` 目录)
5. 配置环境变量：
   - `DATABASE_URL` — Railway PostgreSQL 自动注入
   - `DASHSCOPE_API_KEY` — 通义千问 API Key
   - `JWT_SECRET` — 生产用安全密钥
6. 前端 nginx 中 `backend` 替换为 Railway 内部域名

## 研究数据导出

- `GET /api/analytics/sessions` — 会话统计
- `GET /api/analytics/learning-curve?user_id=X` — 学习曲线
- `GET /api/analytics/checklist-heatmap` — Checklist覆盖热力图
- `GET /api/analytics/export/csv` — CSV批量导出 (SPSS/R兼容)

## 技术栈

- **后端**: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic
- **前端**: React 18, Vite, TailwindCSS, Recharts
- **LLM**: 通义千问 qwen-max (DashScope API)
- **数据库**: PostgreSQL 15
- **部署**: Railway
