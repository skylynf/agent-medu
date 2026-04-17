# Methodology — Medu-SPAgent

> 本文为 Medu-SPAgent 平台**方法学描述**，可直接整合进论文 *Methods* 章节。
> 中英双语并行，便于按目标期刊语言裁剪。

---

## 中文版（用于中文期刊 / 论文初稿）

### 1. 平台与对照设计

我们开发了 Medu-SPAgent —— 一个面向 *medical education* 期刊投稿的 AI 标准化病人 (Standardized Patient, SP) 训练平台。
平台围绕**「单智能体 vs 多智能体」**的对照实验设计，为同一组临床病例提供 **四种** 学习方式 与一套后测问卷：

1. **单智能体学习 (Single-Agent, SA)**
   学生仅与一个**大语言模型驱动的 AI 病人** (`AI-SP`) 进行自由对话，
   无任何过程性评估反馈，也无导师式提示。SA 用以表征
   「**纯 LLM 对话**」基线，与多智能体方法形成最小可比单元。
2. **多智能体学习 (Multi-Agent, MA)**
   在 SA 基础上额外引入两个协作智能体：
   - **导师智能体 (Tutor Agent)**：基于学生当前问诊状态
     做出**苏格拉底式提示**（限频、设冷却、上限 4 次），
     仅在学生陷入困境时介入；
   - **静默评估智能体 (Turn Evaluator)**：在每轮交流后比对
     History-Taking Checklist，把命中项写入实时进度面板与会话快照。
     学生不直接看到分数，仅看到 checklist 进度，避免评分焦虑污染体验测量。
3. **对照学习 (Control, CT)**
   完全确定性脚本：把同一份病例切成 4 个**渐进披露**阶段
   （接诊 → 系统询问 → 深入追问 → 答案揭示），
   学生在每个阶段阅读披露内容并书面回答研究者预设的问题。
   不调用任何 LLM、不提供反馈，作为「**有结构但无 AI**」的对照基线。
4. **考试 (Exam)**
   学生与 AI-SP 自由对话，**过程中无任何反馈**；结束时由
   **总评智能体 (Final Evaluator)** 一次性给出 OSCE 4 维评分
   （病史完整性、医患沟通、临床推理、诊断准确性）、
   checklist 命中、诊断正误与定性反馈。Exam 同时承担**学习后测验**功能。

> 上述 4 种方法共享**同一份病例 YAML 与同一份 checklist rubric**，
> 仅「智能体协作策略」是自变量，确保方法间难度严格对齐。

### 2. 系统架构

平台采用前后端分离 + WebSocket 流式对话架构：

- **Frontend** (React 18 + Vite + TypeScript)：四个学习入口共享统一的
  对话 UI 与临床表单 (Worksheet) 组件；学习历史中显式标注本次会话所采用的方法
  (SA / MA / CT / Exam)。
- **Backend** (FastAPI + SQLAlchemy + asyncpg)：
  - 引入 **`SessionStrategy` 抽象基类**，为四种方法分别派生
    `SingleAgentSession` / `MultiAgentSession` / `ExamSession` / `ControlSession`，
    把「智能体调用链」与「持久化、对话历史维护」解耦。
  - 所有 LLM 调用统一经由 **Prompt Registry** 取出 prompt：
    YAML 提供 v1 默认值，DB `prompts` 表保存历史版本与激活状态；
    每条 `training_sessions` 在第一条学生消息时把当前 `prompt_versions_json`
    快照写入，**保证论文复现性**。
  - LLM 后端为通义千问 `qwen-max` (DashScope API)。
- **Data Layer**：PostgreSQL 15 持久化 `users`、`training_sessions`
  （含 `method` 字段索引）、`messages`、`evaluation_snapshots`、
  `final_evaluations`、`ct_steps`、`survey_responses`、`prompts`。

### 3. 实验流程

每位被试按研究者口头指引完成：
**Pre-Survey → SA / MA / CT 学习两轮 → Exam 后测一次 → Post-Survey (SUS + 开放题)**。
平台不强制顺序，只在每条会话上记录 `method`，便于后续按真实曝露顺序做分析。

### 4. 测量指标

- **行为指标**：每会话提问次数、对话总轮数、用时、checklist 命中率、
  导师介入次数（仅 MA）、SP 情绪轨迹。
- **学习成效**：Exam 模式由 Final Evaluator 输出
  - 14 项 history-taking checklist 命中（0/1）
  - OSCE 4 维评分 (1–5 Likert)
  - 主诊断正误与鉴别诊断列表
- **体验**：SUS-10（含反向计分）+ 6 道开放题。
- **过程数据**：所有学生消息、SP 回应、导师提示及响应延迟以 JSONL 导出，
  便于第三方编码者做定性分析。

### 5. 复现性与开放数据

- 所有 prompt 模板、病例 YAML、checklist 与 rubric 均纳入版本控制；
  会话级 `prompt_versions_json` 字段确保同一篇论文中报告的实验可被精确复跑。
- 平台提供 5 个论文级导出端点
  （`sessions.csv` / `messages.jsonl` / `checklist_matrix.csv` /
  `surveys.csv` / `ct_steps.jsonl`），输出字段含 `method` 标签，
  可直接导入 SPSS / R 做 SA-vs-MA、MA-vs-CT 等组间对比。

---

## English version (for international submission)

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
