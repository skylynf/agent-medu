
### 1. Platform and Experimental Conditions

We developed **Medu-SPAgent**, a research platform that operationalizes an
**LLM-powered Standardized Patient (SP)** for medical education. The platform
implements a **single-agent versus multi-agent** controlled comparison and
exposes four learning conditions on top of an identical case bank:

1. **Single-Agent (SA)** — learners converse freely with a single LLM-driven
   AI patient (`AI-SP`) and receive **no scaffolding and no feedback**.
   SA serves as a *pure-LLM-conversation* baseline.
2. **Multi-Agent (MA)** — augments SA with two collaborating agents:
   a **Tutor Agent** that injects rate-limited, Socratic hints (max 4 per
   session, cooldown of 4 turns) when the learner stalls, and a **Turn
   Evaluator** that silently maps each exchange to a history-taking
   checklist, surfacing progress (but not scores) to the learner.
3. **Control (CT)** — a deterministic, no-LLM scaffold in which the same
   case is decomposed into **four progressive-disclosure stages**
   (intake → systematic enquiry → deep enquiry → key reveal); learners
   write structured responses but receive no feedback.
4. **Exam** — free dialogue with `AI-SP` without any in-session feedback;
   on session end, a **Final Evaluator** produces a 4-dimension OSCE
   rubric, checklist coverage, diagnostic accuracy, and narrative
   feedback. Exam doubles as the **post-test** instrument.

All four conditions share **identical case YAMLs and the same checklist
rubric**; only the agent collaboration policy is manipulated.

### 2. System Architecture

A React/Vite frontend communicates with a FastAPI backend over WebSocket
(SA/MA/Exam) or REST (CT, surveys, admin). Backend introduces a
`SessionStrategy` abstract base class with four concrete subclasses
(`SingleAgentSession`, `MultiAgentSession`, `ExamSession`, `ControlSession`),
decoupling the **agent call graph** from persistence and turn-history bookkeeping.
A central **Prompt Registry** loads YAML defaults and a versioned `prompts`
table; the active prompt set is snapshotted into `training_sessions.
prompt_versions_json` at the first student turn, supporting full
reproducibility. The LLM backend is **Qwen-max** (Alibaba DashScope).
PostgreSQL 15 stores users, sessions (indexed by `method`), messages,
per-turn evaluation snapshots, final evaluations, CT step records, and
survey responses.

### 3. Procedure

Each participant completes Pre-Survey → two learning sessions (SA / MA /
CT) → one Exam post-test → Post-Survey (SUS + open-ended). Method order
is logged per session so that exposure order can be modelled.

### 4. Measures

Behavioural: number of student turns, total exchanges, duration,
checklist coverage, tutor-intervention count (MA only), and SP emotional
trajectory. Learning outcomes (Exam): 14-item history-taking checklist
hit-rate, four-dimensional OSCE Likert score (history completeness,
communication, clinical reasoning, diagnostic accuracy), primary
diagnosis correctness, and a list of differentials. Experience:
System Usability Scale (SUS-10) plus six open-ended items.

### Figures

- **Figure 1.** *Medu-SPAgent — System architecture.*
  Three-tier stack: a React/Vite frontend with five entry points
  (SA / MA / CT / Exam / Post-Test), a FastAPI backend that exposes a
  `SessionStrategy` ABC with four concrete subclasses orchestrating the
  AI-SP, Tutor, Turn-Evaluator, and Final-Evaluator agents, and a data
  layer combining PostgreSQL persistence with the Qwen-max LLM service.
  All agents draw their prompt from a centralized, version-controlled
  Prompt Registry. *(see `docs/medu-spagent-architecture.png`)*

- **Figure 2.** *Agent collaboration policy across the four learning
  conditions.* Side-by-side comparison of SA, MA, Exam, and CT.
  All four conditions share identical case YAMLs and the same
  history-taking checklist; only the agent collaboration policy
  (and therefore the feedback exposure profile) differs.
  *(see `docs/medu-spagent-methods.png`)*

### 5. Reproducibility & Data Sharing

All prompt templates, case YAMLs, checklists, and rubrics are version
controlled; per-session `prompt_versions_json` enables exact rerun of
reported experiments. Five paper-grade exports
(`sessions.csv`, `messages.jsonl`, `checklist_matrix.csv`,
`surveys.csv`, `ct_steps.jsonl`) carry the `method` label and are
ready to be ingested by SPSS or R for between-condition comparisons.
