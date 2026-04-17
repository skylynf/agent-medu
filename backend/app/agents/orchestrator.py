import asyncio
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.cases import load_case
from app.evaluation.checklist import create_empty_checklist, compute_score, update_checklist
from app.agents.sp_agent import generate_sp_response
from app.agents.tutor_agent import evaluate_need_for_intervention
from app.agents.evaluator_agent import evaluate_exchange
from app.models.session import TrainingSession
from app.models.message import Message
from app.models.evaluation import EvaluationSnapshot


class SessionOrchestrator:
    """Orchestrates the three agents for a single training session."""

    TUTOR_COOLDOWN_MESSAGES = 4
    TUTOR_MAX_INTERVENTIONS = 4
    TUTOR_MIN_MESSAGES_BEFORE_FIRST = 5

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        self.session_id = session_id
        self.case_id = case_id
        self.user_id = user_id
        self.case_data = load_case(case_id)
        self.checklist = create_empty_checklist()
        self.conversation_history: list[dict] = []
        self.current_emotion = "baseline"
        self.student_message_count = 0
        self.tutor_intervention_count = 0
        self.last_student_message_time: float | None = None
        self._already_checked: list[str] = []
        self._last_intervention_at_msg: int = 0

    async def get_opening(self) -> dict:
        """Generate the SP's opening statement."""
        voluntary = self.case_data["information_layers"]["voluntary"]
        opening = "，".join(voluntary)

        self.conversation_history.append({
            "role": "patient",
            "content": opening,
            "timestamp": time.time(),
        })

        score, completion_rate, _ = compute_score(self.checklist)

        return {
            "type": "patient_response",
            "content": opening,
            "emotion": self.current_emotion,
            "eval_update": {
                "checklist": self.checklist,
                "completion_rate": completion_rate,
                "score": score,
            },
        }

    async def process_student_message(
        self, content: str, db: AsyncSession, send_fn=None,
    ) -> list[dict]:
        """
        Process student message through all three agents.

        New flow:
        1. Send typing indicator immediately
        2. Generate SP response (what the student is waiting for)
        3. Send SP response
        4. Evaluate Q&A pair + tutor check concurrently (in background)
        5. Send eval_update and optional tutor hint

        If send_fn is provided, responses are streamed immediately;
        otherwise they are collected and returned as a list.
        """
        responses = []

        async def emit(msg: dict):
            if send_fn:
                await send_fn(msg)
            responses.append(msg)

        now = time.time()
        latency_ms = None
        if self.last_student_message_time is not None:
            latency_ms = int((now - self.last_student_message_time) * 1000)
        self.last_student_message_time = now
        self.student_message_count += 1

        self.conversation_history.append({
            "role": "student",
            "content": content,
            "timestamp": now,
        })

        student_msg = Message(
            session_id=self.session_id,
            role="student",
            content=content,
            response_latency_ms=latency_ms,
        )
        db.add(student_msg)
        await db.flush()

        # --- Phase 1: Generate SP response (student is waiting for this) ---
        await emit({"type": "typing", "content": ""})

        sp_response, new_emotion = await generate_sp_response(
            case_data=self.case_data,
            conversation_history=self.conversation_history,
            current_emotion=self.current_emotion,
        )
        self.current_emotion = new_emotion

        self.conversation_history.append({
            "role": "patient",
            "content": sp_response,
            "timestamp": time.time(),
        })

        patient_msg = Message(
            session_id=self.session_id,
            role="patient",
            content=sp_response,
            emotion=new_emotion,
        )
        db.add(patient_msg)

        await emit({
            "type": "patient_response",
            "content": sp_response,
            "emotion": new_emotion,
        })

        # --- Phase 2: Evaluate full Q&A exchange + tutor check concurrently ---
        eval_task = evaluate_exchange(
            student_message=content,
            patient_response=sp_response,
            conversation_history=self.conversation_history,
            already_checked=self._already_checked,
        )

        should_check_tutor = self._should_check_tutor()
        if should_check_tutor:
            tutor_task = evaluate_need_for_intervention(
                case_data=self.case_data,
                conversation_history=self.conversation_history,
                checklist_state=self.checklist,
                completion_rate=compute_score(self.checklist)[1],
                last_student_message_time=self.last_student_message_time,
                student_message_count=self.student_message_count,
            )
            eval_result, tutor_result = await asyncio.gather(eval_task, tutor_task)
        else:
            eval_result = await eval_task
            tutor_result = {"should_intervene": False}

        # Update checklist
        newly_checked = eval_result.get("checked_items", [])
        delta = {}
        if newly_checked:
            delta = update_checklist(self.checklist, newly_checked)
            self._already_checked.extend(newly_checked)

        score, completion_rate, missed_critical = compute_score(self.checklist)

        student_msg.evaluator_delta_json = {
            "checked_items": newly_checked,
            "reasoning": eval_result.get("reasoning", ""),
        }

        snapshot = EvaluationSnapshot(
            session_id=self.session_id,
            message_id=student_msg.id,
            checklist_state_json=self.checklist,
            completion_rate=completion_rate,
        )
        db.add(snapshot)

        await emit({
            "type": "eval_update",
            "checklist": self.checklist,
            "completion_rate": completion_rate,
            "score": score,
            "delta": delta,
        })

        # Tutor intervention (only if allowed)
        if tutor_result.get("should_intervene"):
            self.tutor_intervention_count += 1
            self._last_intervention_at_msg = self.student_message_count
            hint_content = tutor_result.get("hint_content", "")

            self.conversation_history.append({
                "role": "tutor",
                "content": hint_content,
                "timestamp": time.time(),
            })

            tutor_msg = Message(
                session_id=self.session_id,
                role="tutor",
                content=hint_content,
            )
            db.add(tutor_msg)

            await emit({
                "type": "tutor_hint",
                "content": hint_content,
                "hint_level": tutor_result.get("hint_level", "moderate"),
                "intervention_type": tutor_result.get("intervention_type"),
            })

        session = await db.get(TrainingSession, self.session_id)
        if session:
            session.total_messages = len(self.conversation_history)
            session.student_messages = self.student_message_count
            session.tutor_interventions_count = self.tutor_intervention_count
            session.checklist_json = self.checklist

        await db.flush()
        return responses

    def _should_check_tutor(self) -> bool:
        """Decide whether to even ask the tutor LLM this turn."""
        if self.student_message_count < self.TUTOR_MIN_MESSAGES_BEFORE_FIRST:
            return False
        if self.tutor_intervention_count >= self.TUTOR_MAX_INTERVENTIONS:
            return False
        msgs_since_last = self.student_message_count - self._last_intervention_at_msg
        if self._last_intervention_at_msg > 0 and msgs_since_last < self.TUTOR_COOLDOWN_MESSAGES:
            return False
        return True

    async def end_session(self, db: AsyncSession) -> dict:
        """End the training session and generate summary."""
        score, completion_rate, missed_critical = compute_score(self.checklist)

        session = await db.get(TrainingSession, self.session_id)
        if session:
            session.ended_at = datetime.now(timezone.utc)
            session.final_score = score
            session.checklist_json = self.checklist
            await db.flush()

        strengths = []
        improvements = []
        for cat_key, cat_data in self.checklist.items():
            cat_checked = sum(1 for i in cat_data["items"].values() if i["checked"])
            cat_total = len(cat_data["items"])
            cat_rate = cat_checked / cat_total if cat_total > 0 else 0
            display = cat_data["display_name"]
            if cat_rate >= 0.8:
                strengths.append(f"{display}覆盖充分")
            elif cat_rate < 0.5:
                improvements.append(f"{display}需要加强")

        if not missed_critical:
            strengths.append("所有关键项目均已覆盖")
        else:
            improvements.append(f"遗漏关键项: {', '.join(missed_critical)}")

        started = session.started_at if session else datetime.now(timezone.utc)
        ended = session.ended_at if session and session.ended_at else datetime.now(timezone.utc)
        duration = int((ended - started).total_seconds())

        return {
            "type": "session_summary",
            "session_id": str(self.session_id),
            "case_id": self.case_id,
            "final_score": score,
            "completion_rate": completion_rate,
            "total_messages": len(self.conversation_history),
            "student_messages": self.student_message_count,
            "tutor_interventions_count": self.tutor_intervention_count,
            "duration_seconds": duration,
            "checklist": self.checklist,
            "critical_missed": missed_critical,
            "strengths": strengths,
            "improvements": improvements,
        }
