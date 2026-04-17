# Medu-SPAgent — Medical Education SP Agent

面向 *Medical Education* 期刊投稿的 AI 标准化病人 (Standardized Patient, SP) 训练与研究平台。
在原有「三智能体协作」架构基础上扩展出 **MultiAgent / Control / Exam** 三种学习方法
与 **后测问卷模块**，并提供集中化 Prompt 库与论文级数据导出。

> 学生 Pipeline（2× 学习 → 1× 考试 → 后测）由研究者**口头指引**，
> 系统不强制顺序，仅在每条 `TrainingSession` 上记录所选 `method` 字段。

## 1. 三种学习方法 + 后测

| ID | 名称 | 是否 LLM | UI 入口 | 数据落库 |
|---|---|---|---|---|
| `multi_agent` | **多智能体学习 (MA)** — AI-SP + Tutor + Silent Evaluator | 是 | `/consultation/:caseId` | `messages` + `evaluation_snapshots` + `training_sessions.checklist_json` |
| `control` | **对照学习 (CT)** — 4 阶段渐进式披露，无系统反馈 | 否 | `/control/:caseId` | `ct_steps`（每阶段披露内容 + 学生输入） |
| `exam` | **考试方法 (Exam)** — 仅 AI-SP，结束后由 final_evaluator 一次性总评 | 是 | `/exam/:caseId` | `messages` + `final_evaluations` |
| `post_test` | **后测问卷** — SUS + 开放题 | — | `/post-test` | `survey_responses` |

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       Frontend (React + Vite)                    │
│  Home (4 entries) ── Consultation (MA) ── ControlLearning (CT)  │
│                  ── Exam ── PostTest ── PromptAdmin (admin)      │
└──────────────────────────────┬──────────────────────────────────┘
              WebSocket (MA / Exam)   REST (CT / surveys / admin)
┌──────────────────────────────┴──────────────────────────────────┐
│                       Backend (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  SessionStrategy (ABC)                    │   │
│  │  ┌─────────────────┬──────────────────┬───────────────┐ │   │
│  │  │ MultiAgentSession│   ExamSession    │ ControlSession│ │   │
│  │  └────────┬────────┴────────┬─────────┴───────────────┘ │   │
│  │           │                 │                             │   │
│  │  ┌────────▼────────┐ ┌──────▼─────────┐                  │   │
│  │  │  AI-SP Agent    │ │ Final Evaluator │                  │   │
│  │  │  Tutor Agent    │ │     Agent       │                  │   │
│  │  │  Turn Evaluator │ └─────────────────┘                  │   │
│  │  └─────────┬───────┘                                       │   │
│  │            │ 所有 prompt 来自 ↓                            │   │
│  │  ┌─────────▼──────────────┐                                │   │
│  │  │    Prompt Registry      │  ← YAML defaults + DB versioning│
│  │  └─────────────────────────┘                                │   │
│  └─────────────────────────────────────────────────────────────┘ │
│  Case Engine ── Checklist ── Survey Loader ── Analytics Pipeline │
└──────────────────────────────┬──────────────────────────────────┘
                  ┌────────────┴────────────┐
                  │   PostgreSQL   │  Qwen API│
                  └─────────────────────────┘
```

### 2.1 数据模型概览

| 表 | 用途 |
|---|---|
| `users` | 学生 / 教师 / 研究员 |
| `training_sessions` | 每次学习/考试/对照会话；含 `method`、`prompt_versions_json` |
| `messages` | 全量对话；记录 `role` (`student/patient/tutor`)、`emotion`、`response_latency_ms`、`evaluator_delta_json` |
| `evaluation_snapshots` | MA 模式的逐轮 checklist 快照 |
| `final_evaluations` | Exam 模式总评（checklist 命中、4 维 OSCE、诊断正误、叙述反馈） |
| `ct_steps` | CT 模式每阶段披露内容 + 学生输入 |
| `survey_responses` | 后测问卷（SUS / 开放题 / 人口学） |
| `prompts` | Prompt 版本表，每次保存即新增一行；`active=true` 标记当前生效版本 |

## 3. Prompt 库（集中化、可改、可追溯）

- **YAML 默认值**：`backend/app/prompts/{sp_agent,tutor_agent,turn_evaluator,final_evaluator}.yaml`
- 启动时把 YAML 装入内存缓存；若 DB 中相应 `key` 没有 `active` 行，则把 YAML v1 写入 `prompts` 表。
- 研究员/教师可在 `/admin/prompts` 编辑 → 保存即新增版本 → 激活后下一次推理立即生效。
- 每个 `TrainingSession` 在第一条学生消息时把当前 `prompt_versions_json` 快照写入，**保证论文复现性**。

## 4. 病例库 (MVP 6 例)

1. 急性阑尾炎 — 转移性右下腹痛
2. 急性胰腺炎 — 上腹痛 + 束带感
3. 消化性溃疡穿孔 — 突发板状腹
4. 急性胆囊炎 — 右上腹绞痛 + Murphy 征
5. 肠梗阻 — 痛吐胀闭四大症状
6. 肠系膜动脉栓塞 — 症状体征分离

> CT 模式无需修改这些 YAML：`build_ct_stages()` 会自动把 `voluntary` / `on_inquiry` / `deep_inquiry`
> 切成 4 个阶段（接诊 → 系统询问 → 深入追问 → 答案揭示）。

## 5. 数据导出（投稿附录直接可用）

| 端点 | 用途 | 说明 |
|---|---|---|
| `GET /api/analytics/export/sessions.csv` | 每行一个 session 的宽表 | 含人口学、method、duration、checklist 完成率、final_score、4 维 OSCE 得分、诊断正误、prompt_versions |
| `GET /api/analytics/export/messages.jsonl` | 全量对话 (NDJSON) | 含 role / emotion / latency / evaluator_delta，便于定性编码 |
| `GET /api/analytics/export/checklist_matrix.csv` | session × checklist_item 0/1 宽表 | SPSS / R 直接做组间对比 |
| `GET /api/analytics/export/surveys.csv` | SUS 10 题原值 + 反向计分总分 + 开放题原文 | — |
| `GET /api/analytics/export/ct_steps.jsonl` | CT 模式学生分阶段提问原文 | 论文定性分析用 |

> 老的 `/api/analytics/export/csv` 依然保留作兼容。

## 6. WebSocket 协议（MA / Exam 共用 `/ws/consultation`）

```jsonc
// 1) auth
{ "token": "<JWT>" }
// 2) 启动 — 选择方法
{ "type": "start_session", "case_id": "acute_appendicitis", "method": "multi_agent" | "exam" }
// 3) 学生发问
{ "type": "student_message", "content": "..." }
// 4) 结束（Exam 会触发 final_evaluator）
{ "type": "end_session" }
```

CT 模式不走 WS，使用 REST：

```
POST /api/sessions/control/start          { case_id }
GET  /api/sessions/control/{id}/state     -> 当前阶段（断点续答）
POST /api/sessions/control/{id}/submit    { stage_index, student_input }
GET  /api/sessions/control/{id}/steps     -> 学生所有阶段输入回顾
```

## 7. 快速开始

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate    # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # 编辑填入 DASHSCOPE_API_KEY 与 DATABASE_URL
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 数据库

需要 PostgreSQL（Railway 部署时自动注入 `DATABASE_URL`）。本地：

```bash
createdb spagent
# 启动后端时会自动 create_all 所有表
```

## 8. Railway 部署

1. Railway 创建项目并加 PostgreSQL 服务
2. 后端服务连接 `backend/`，前端服务连接 `frontend/`
3. 环境变量：`DATABASE_URL`、`DASHSCOPE_API_KEY`、`JWT_SECRET`
4. 前端 nginx 把 `/api` 与 `/ws` 反代到 backend 服务的内部域名

## 9. 技术栈

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 (asyncpg), Alembic-ready, Websockets, JWT, PyYAML
- **Frontend**: React 18 + Vite + TypeScript + TailwindCSS + Recharts
- **LLM**: 通义千问 `qwen-max` (DashScope API)
- **数据库**: PostgreSQL 15

## 10. 论文投稿建议附录

- 附录 A：病例 YAML 全文（6 个）
- 附录 B：4 个 Prompt 模板及其使用版本
- 附录 C：history-taking checklist 与 holistic OSCE rubric
- 附录 D：导出 CSV/JSONL 字段字典
- 附录 E：SUS + 开放题题目原文
