
# Medu-SPAgent — Medical Education SP Agent

> **Submission status:** This repository is associated with a manuscript currently under review at *npj Digital Medicine*.

Medu-SPAgent is an AI-powered standardized patient (SP) training and research platform for medical education.

The platform is designed around a controlled comparison between **single-agent** and **multi-agent** learning conditions. It provides four learning methods — **SA / MA / CT / Exam** — together with a **post-test questionnaire**, a centralized prompt registry, and structured data export for research analysis.

> The student pipeline — learning → examination → post-test — is guided by the researcher outside the system.
> The system does not enforce a fixed sequence. Instead, each `TrainingSession` records the selected `method` field, and every training history explicitly indicates which learning method was used.

---

## 1. Four Learning Methods and Post-Test

| ID | Name | Agent Composition | Student-Visible Feedback | UI Entry | Data Storage |
|---|---|---|---|---|---|
| `single_agent` | **Single-Agent Learning (SA)** | AI-SP only | None. The ending page only shows duration and number of questions. | `/single/:caseId` | `messages` + `training_sessions` |
| `multi_agent` | **Multi-Agent Learning (MA)** | AI-SP + Tutor + Turn-Evaluator + Final-Evaluator | Real-time checklist updates and Socratic tutor prompts. At the end, scores are hidden and only narrative feedback is shown. | `/consultation/:caseId` | `messages` + `evaluation_snapshots` + `final_evaluations` |
| `control` | **Control Learning (CT)** | No LLM involvement; deterministic script | Four-stage progressive disclosure with stage-based questions. Reference answers are shown at the end. | `/control/:caseId` | `ct_steps` |
| `exam` | **Exam Method (Exam)** | AI-SP + Final-Evaluator | No feedback during the encounter. After completion, the system displays four-dimensional OSCE results, diagnostic correctness, and checklist hits. | `/exam/:caseId` | `messages` + `final_evaluations` |
| `post_test` | Post-Test Questionnaire | — | SUS 10-item questionnaire + open-ended questions | `/post-test` | `survey_responses` |

> **SA vs MA** is the core comparison.
> The two dialogue interfaces are nearly identical, but SA disables the Tutor and Turn-Evaluator components.
> This design isolates the added value of **multi-agent scaffolding** compared with **plain LLM-based dialogue**.
> In both SA and MA, final scores are not shown to students, reducing the risk that score-related anxiety may affect the learning experience.

---

## 2. System Architecture

Architecture diagrams are located at:

- `docs/medu-spagent-architecture.png`
- `docs/medu-spagent-methods.png`

The methodology document is located at:

- `docs/METHODOLOGY.md`

![Medu-SPAgent System Architecture](docs/medu-spagent-architecture.png)

![Agent collaboration policy across the four learning conditions](docs/medu-spagent-methods.png)

---

### 2.1 Overall Modules

```text
┌────────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                        │
│  Home  →  Case Select  →                                            │
│   ├── SingleAgent  (SA, /single/:caseId)                            │
│   ├── Consultation (MA, /consultation/:caseId)                      │
│   ├── ControlLearning (CT, /control/:caseId)                        │
│   ├── Exam        (Exam, /exam/:caseId)                             │
│   └── PostTest, Dashboard, PromptAdmin                              │
└──────────────────────────────┬─────────────────────────────────────┘
        WebSocket (SA/MA/Exam)        REST (CT / surveys / admin / data)
┌──────────────────────────────┴─────────────────────────────────────┐
│                     Backend (FastAPI, Python 3.11)                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              SessionStrategy  (abstract base class)           │  │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────┐   │  │
│  │  │ SingleAgent  │ MultiAgent   │   Exam       │ Control  │   │  │
│  │  │  Session     │  Session     │   Session    │ Session  │   │  │
│  │  └──────┬───────┴──────┬───────┴──────┬───────┴──────────┘   │  │
│  │         │ SP-only      │ SP+Tutor+Eval│ SP + Final-Eval       │  │
│  └─────────┼──────────────┼──────────────┼─────────────────────┘  │
│            ▼              ▼              ▼                          │
│      ┌──────────────────────────────────────────┐                  │
│      │  Agents:  AI-SP  /  Tutor  /  Turn-Eval  │                  │
│      │           /  Final-Evaluator              │                  │
│      └────────────────────┬─────────────────────┘                  │
│                           │   prompts come from ↓                  │
│      ┌────────────────────▼─────────────────────┐                  │
│      │  Prompt Registry  (YAML defaults + DB)   │                  │
│      └──────────────────────────────────────────┘                  │
│  Case Engine ── Checklist Rubric ── Survey Loader ── Analytics      │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL  +  Qwen │
                    └─────────────────────┘
```

---

### 2.2 Agent Call Chains Across the Four Methods

```text
┌──── SA ────┐    ┌──── MA ────┐    ┌──── Exam ───┐    ┌──── CT ────┐
│            │    │            │    │             │    │            │
│  Student   │    │  Student   │    │   Student   │    │  Student   │
│     │      │    │     │      │    │     │       │    │     │      │
│     ▼      │    │     ▼      │    │     ▼       │    │     ▼      │
│  AI-SP     │    │  AI-SP     │    │   AI-SP     │    │  Stage-N   │
│            │    │     │      │    │             │    │  Disclosure│
│            │    │     ├─Tutor│    │             │    │     │      │
│            │    │     ├─TurnE│    │             │    │     ▼      │
│            │    │            │    │             │    │  Free-text │
│            │    │  ⤵ end:    │    │  ⤵ end:     │    │   Answer   │
│  ⤵ end:    │    │  Final-Eval│    │  Final-Eval │    │            │
│   none     │    │  (silent)  │    │  (visible)  │    │  No Agent  │
└────────────┘    └────────────┘    └─────────────┘    └────────────┘
   no score          score hidden     score visible       no score
   no tutor          tutor visible    no tutor            no tutor
```

---

### 2.3 Data Model Overview

| Table | Purpose |
|---|---|
| `users` | Students, teachers, and researchers, including demographic fields |
| `training_sessions` | Each session; includes `method` — SA / MA / CT / Exam — `prompt_versions_json`, and `worksheet_json` |
| `messages` | Full dialogue records; includes `role` — `student/patient/tutor` — `emotion`, `response_latency_ms`, and `evaluator_delta_json` |
| `evaluation_snapshots` | Turn-level checklist snapshots in MA mode; not written in SA mode |
| `final_evaluations` | Final evaluations for MA and Exam modes, including checklist hits, four-dimensional OSCE scores, diagnostic correctness, and narrative feedback |
| `ct_steps` | Stage-based disclosure content and student input in CT mode |
| `survey_responses` | SUS responses, open-ended answers, and demographics |
| `prompts` | Prompt version table; `active=true` marks the currently active version |

---

## 3. Prompt Registry

The system uses a centralized, editable, and traceable prompt registry.

- **YAML defaults**:
  - `backend/app/prompts/sp_agent.yaml`
  - `backend/app/prompts/tutor_agent.yaml`
  - `backend/app/prompts/turn_evaluator.yaml`
  - `backend/app/prompts/final_evaluator.yaml`

- At startup, YAML prompts are loaded into the in-memory cache.
- If the database does not contain an active row for a given `key`, the YAML v1 prompt is inserted into the `prompts` table.
- Researchers and teachers can edit prompts in `/admin/prompts`.
- Saving a prompt creates a new version.
- Once activated, the new version is used in the next inference call.
- When the first student message is sent in a `TrainingSession`, the current `prompt_versions_json` snapshot is written to the session record to support reproducibility.

Prompt usage by method:

| Method | Prompt Usage |
|---|---|
| SA | `sp_agent` only |
| MA | `sp_agent` + `tutor_agent` + `turn_evaluator` + `final_evaluator` |
| Exam | `sp_agent` + `final_evaluator` |
| CT | No LLM prompt |

---

## 4. Case Library

The MVP case library contains six abdominal surgery cases:

1. Acute appendicitis — migratory right lower quadrant pain
2. Acute pancreatitis — epigastric pain with belt-like radiation
3. Perforated peptic ulcer — sudden board-like abdomen
4. Acute cholecystitis — right upper quadrant colicky pain with Murphy’s sign
5. Intestinal obstruction — abdominal pain, vomiting, distension, and obstipation
6. Mesenteric arterial embolism — discrepancy between severe symptoms and mild physical signs

The same case YAML files are used across SA, MA, CT, and Exam modes.

This ensures that case difficulty is aligned across methods, while the **agent collaboration policy** remains the independent variable.

In CT mode, `build_ct_stages()` automatically divides the `voluntary`, `on_inquiry`, and `deep_inquiry` information layers into four fixed stages.

---

## 5. Data Export

| Endpoint | Purpose | Description |
|---|---|---|
| `GET /api/analytics/export/sessions.csv` | Session-level wide table | Includes demographics, `method` — SA / MA / CT / Exam — duration, checklist completion rate, final score, four OSCE dimensions, diagnostic correctness, and prompt versions |
| `GET /api/analytics/export/messages.jsonl` | Full dialogue export in NDJSON format | Includes role, emotion, latency, and evaluator delta |
| `GET /api/analytics/export/checklist_matrix.csv` | Session × checklist item 0/1 wide matrix | Supports between-group comparison; includes the `method` column |
| `GET /api/analytics/export/surveys.csv` | Survey export | Includes raw SUS 10-item responses, reverse-scored total score, and open-ended responses |
| `GET /api/analytics/export/ct_steps.jsonl` | CT-mode staged responses | Contains students’ free-text inputs for each CT stage |

The legacy endpoint `/api/analytics/export/csv` is retained for compatibility.

---

## 6. WebSocket Protocol

SA, MA, and Exam share the `/ws/consultation` WebSocket endpoint.

```jsonc
// 1. Authentication
{ "token": "<JWT>" }

// 2. Start session
{
  "type": "start_session",
  "case_id": "acute_appendicitis",
  "method": "single_agent" | "multi_agent" | "exam"
}

// 3. Student message
{
  "type": "student_message",
  "content": "..."
}

// 4. End session
// In Exam and MA, this triggers the final evaluator.
// In SA, only metadata is saved.
{
  "type": "end_session"
}
```

CT mode does not use WebSocket. It uses REST endpoints:

```text
POST /api/sessions/control/start          { case_id }
GET  /api/sessions/control/{id}/state     -> current stage; supports resume
POST /api/sessions/control/{id}/submit    { stage_index, student_input }
GET  /api/sessions/control/{id}/steps     -> review all student inputs
```

---

## 7. Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate    # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Edit DASHSCOPE_API_KEY and DATABASE_URL
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database

PostgreSQL is required. When deployed on Railway, `DATABASE_URL` is injected automatically.

For local development:

```bash
createdb spagent
# When the backend starts, it automatically creates all tables
# and idempotently applies ALTER TABLE operations for newly added
# columns such as method, prompt_versions_json, and worksheet_json.
```

---

## 8. Railway Deployment

1. Create a Railway project and add a PostgreSQL service.
2. Connect the backend service to `backend/`.
3. Connect the frontend service to `frontend/`.
4. Configure environment variables:
   - `DATABASE_URL`
   - `DASHSCOPE_API_KEY`
   - `JWT_SECRET`
5. Configure the frontend nginx service to reverse proxy `/api` and `/ws` to the backend internal domain.

---

## 9. Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, asyncpg, WebSockets, JWT, PyYAML
- **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Recharts
- **LLM**: Qwen `qwen-max` via DashScope API
- **Database**: PostgreSQL 15
