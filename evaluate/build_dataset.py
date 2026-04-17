"""把 RawData 变成可分析的宽表。

产出：
- ``students``    : 每个学生一行（人口学 + 派生：组别 / pipeline 完整性）
- ``learning``    : 每个学习会话一行（含 session_index 1/2、过程指标）
- ``exams``       : 每个考试会话一行（最终结局）
- ``checklist_long``: 每个 (session, item) 一行的 0/1（用于逐项 χ²）
- ``surveys_wide``: 每个学生一行的 SUS 与 UES 总分及分量表
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from evaluate.config import EXAM_METHOD, GROUP_LABELS, LEARNING_METHODS, OSCE_DIMENSIONS
from evaluate.loader import RawData
from evaluate.scoring import (
    checklist_item_meta,
    checklist_item_names,
    checklist_score,
    compute_sus,
    compute_ues,
    flatten_checklist_json,
    flatten_final_checklist,
    open_ended_ids,
    sus_item_ids,
    ues_item_ids,
    ues_subscale_map,
)


@dataclass
class Dataset:
    students: pd.DataFrame
    learning: pd.DataFrame
    exams: pd.DataFrame
    checklist_long: pd.DataFrame
    surveys_wide: pd.DataFrame


# --------------------------------------------------------------------- helpers
def _parse_dt(s):
    return pd.to_datetime(s, errors="coerce", utc=True)


def _safe_int(x, default=0):
    try:
        if pd.isna(x):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def _duration_seconds(started, ended):
    if pd.isna(started) or pd.isna(ended):
        return None
    return (ended - started).total_seconds()


# --------------------------------------------------------------------- build
def build(raw: RawData) -> Dataset:
    sessions = raw.sessions.copy()
    if sessions.empty:
        raise RuntimeError("training_sessions 为空，无可分析数据。")
    sessions["started_at"] = _parse_dt(sessions["started_at"])
    sessions["ended_at"] = _parse_dt(sessions["ended_at"])
    sessions["duration_seconds"] = sessions.apply(
        lambda r: _duration_seconds(r["started_at"], r["ended_at"]), axis=1
    )

    msgs = raw.messages.copy()
    if not msgs.empty:
        msgs["timestamp"] = _parse_dt(msgs["timestamp"])

    # ----------------------------------------------------------- students 表
    users = raw.users.copy()
    learning_sessions = sessions[sessions["method"].isin(LEARNING_METHODS)].copy()

    # 推断每个学生的"组别"=他/她的所有学习会话采用的方法（应当唯一）
    grp_per_user = (
        learning_sessions.groupby("user_id")["method"]
        .agg(lambda s: sorted(set(s)))
        .rename("learning_methods")
        .reset_index()
    )
    grp_per_user["group"] = grp_per_user["learning_methods"].apply(
        lambda lst: lst[0] if len(lst) == 1 else "MIXED"
    )
    grp_per_user["group_label"] = grp_per_user["group"].map(GROUP_LABELS).fillna("MIXED")

    n_learning = (
        learning_sessions.groupby("user_id").size().rename("n_learning_sessions").reset_index()
    )
    exam_sessions = sessions[sessions["method"] == EXAM_METHOD].copy()
    n_exam = exam_sessions.groupby("user_id").size().rename("n_exam_sessions").reset_index()

    students = users.merge(grp_per_user, left_on="id", right_on="user_id", how="left")
    students = students.merge(n_learning, left_on="id", right_on="user_id", how="left", suffixes=("", "_x"))
    students = students.merge(n_exam, left_on="id", right_on="user_id", how="left", suffixes=("", "_y"))
    drop_cols = [c for c in students.columns if c.startswith("user_id")]
    students = students.drop(columns=drop_cols)
    students["n_learning_sessions"] = students["n_learning_sessions"].fillna(0).astype(int)
    students["n_exam_sessions"] = students["n_exam_sessions"].fillna(0).astype(int)
    students["pipeline_complete"] = (students["n_learning_sessions"] >= 2) & (students["n_exam_sessions"] >= 1)
    students = students.rename(columns={"id": "user_id"})

    # ----------------------------------------------------------- learning 长表
    msg_counts_by_session = (
        msgs.groupby("session_id")
        .agg(
            n_messages=("id", "count"),
            n_student_msgs=("role", lambda s: int((s == "student").sum())),
            n_patient_msgs=("role", lambda s: int((s == "patient").sum())),
            n_tutor_msgs=("role", lambda s: int((s == "tutor").sum())),
            mean_latency_ms=("response_latency_ms", "mean"),
            median_latency_ms=("response_latency_ms", "median"),
            mean_student_chars=(
                "content",
                lambda s: float(s[s.index.isin(s.index)].str.len().mean()) if len(s) else None,
            ),
        )
        .reset_index()
        if not msgs.empty
        else pd.DataFrame(columns=["session_id"])
    )

    # 学生消息字符数（更精准）
    if not msgs.empty:
        sm = msgs[msgs["role"] == "student"]
        smchar = sm.groupby("session_id")["content"].apply(
            lambda s: s.str.len().mean()
        ).rename("mean_student_msg_chars").reset_index()
        msg_counts_by_session = msg_counts_by_session.drop(columns=["mean_student_chars"], errors="ignore").merge(
            smchar, on="session_id", how="left"
        )

    # snapshots → 每会话末尾 completion_rate
    snaps = raw.snapshots.copy()
    if not snaps.empty:
        snaps["timestamp"] = _parse_dt(snaps["timestamp"])
        snap_last = (
            snaps.sort_values("timestamp").groupby("session_id").tail(1)[["session_id", "completion_rate"]]
            .rename(columns={"completion_rate": "snap_final_completion"})
        )
    else:
        snap_last = pd.DataFrame(columns=["session_id", "snap_final_completion"])

    learning = learning_sessions.merge(msg_counts_by_session, left_on="id", right_on="session_id", how="left")
    learning = learning.merge(snap_last, left_on="id", right_on="session_id", how="left", suffixes=("", "_dup"))
    learning = learning.drop(columns=[c for c in learning.columns if c.endswith("_dup")])

    # checklist 评分 (MA 写入 training_sessions.checklist_json；CT 没有；SA 没有)
    cls_rows = learning["checklist_json"].apply(
        lambda j: pd.Series(checklist_score(flatten_checklist_json(j)))
    )
    learning = pd.concat([learning.reset_index(drop=True), cls_rows.reset_index(drop=True)], axis=1)

    # session_index：按时间排序的第几次（1 / 2）
    learning = learning.sort_values(["user_id", "started_at"])
    learning["session_index"] = learning.groupby("user_id").cumcount() + 1

    learning["group"] = learning["method"]
    learning["group_label"] = learning["method"].map(GROUP_LABELS)

    # CT 每会话的阶段答复数
    ct = raw.ct_steps.copy()
    if not ct.empty:
        ct_count = (
            ct.groupby("session_id")
            .agg(ct_stages_completed=("id", "count"),
                 ct_total_chars=("student_input", lambda s: int(s.fillna("").str.len().sum())))
            .reset_index()
        )
        learning = learning.merge(ct_count, left_on="id", right_on="session_id", how="left", suffixes=("", "_ct"))
        learning = learning.drop(columns=[c for c in learning.columns if c.endswith("_ct")])

    # ----------------------------------------------------------- exams 表
    finals = raw.finals.copy()
    exams = exam_sessions.merge(finals, left_on="id", right_on="session_id", how="left", suffixes=("", "_fe"))
    exams = exams.merge(msg_counts_by_session, left_on="id", right_on="session_id", how="left", suffixes=("", "_msg"))
    exams = exams.drop(columns=[c for c in exams.columns if c.endswith("_msg") and c != "session_id_msg"])

    # OSCE 4 维拆开
    def _osce(d):
        out = {f"osce_{k}": None for k in OSCE_DIMENSIONS}
        if isinstance(d, dict):
            for k in OSCE_DIMENSIONS:
                v = d.get(k)
                try:
                    out[f"osce_{k}"] = float(v) if v is not None else None
                except (TypeError, ValueError):
                    out[f"osce_{k}"] = None
        return pd.Series(out)

    osce_cols = exams["holistic_scores_json"].apply(_osce)
    exams = pd.concat([exams.reset_index(drop=True), osce_cols.reset_index(drop=True)], axis=1)
    exams["osce_total"] = exams[[f"osce_{k}" for k in OSCE_DIMENSIONS]].sum(axis=1, skipna=True)
    exams["osce_total"] = exams["osce_total"].where(
        exams[[f"osce_{k}" for k in OSCE_DIMENSIONS]].notna().all(axis=1), other=None
    )
    exams["osce_mean"] = exams[[f"osce_{k}" for k in OSCE_DIMENSIONS]].mean(axis=1, skipna=False)

    cls_exam_rows = exams["checklist_results_json"].apply(
        lambda j: pd.Series(checklist_score(flatten_final_checklist(j)))
    )
    exams = pd.concat([exams.reset_index(drop=True), cls_exam_rows.reset_index(drop=True)], axis=1)

    exams["n_differentials_given"] = exams["differentials_given_json"].apply(
        lambda lst: len(lst) if isinstance(lst, list) else 0
    )
    exams["worksheet_filled"] = exams["worksheet_json"].apply(
        lambda d: int(any(k for k, v in (d or {}).items() if k != "_updated_at" and v))
    )

    # 把 group（学生组别）合并进来
    exams = exams.merge(students[["user_id", "group", "group_label"]], on="user_id", how="left")
    learning = learning.merge(
        students[["user_id", "group", "group_label"]].rename(
            columns={"group": "user_group", "group_label": "user_group_label"}
        ),
        on="user_id",
        how="left",
    )

    # ----------------------------------------------------------- checklist_long
    items = checklist_item_names()
    meta = checklist_item_meta()

    long_rows = []
    # MA 学习会话
    for _, row in learning.iterrows():
        flags = flatten_checklist_json(row.get("checklist_json"))
        for it in items:
            long_rows.append({
                "scope": "learning",
                "session_id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "group": row["method"],
                "group_label": GROUP_LABELS.get(row["method"], row["method"]),
                "case_id": row["case_id"],
                "item": it,
                "category": meta[it]["category_display"],
                "critical": meta[it]["critical"],
                "checked": flags.get(it, 0),
            })
    # 考试
    for _, row in exams.iterrows():
        flags = flatten_final_checklist(row.get("checklist_results_json"))
        grp = row.get("group") or "UNKNOWN"
        for it in items:
            long_rows.append({
                "scope": "exam",
                "session_id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "group": grp,
                "group_label": GROUP_LABELS.get(grp, grp),
                "case_id": row["case_id"],
                "item": it,
                "category": meta[it]["category_display"],
                "critical": meta[it]["critical"],
                "checked": flags.get(it, 0),
            })
    checklist_long = pd.DataFrame(long_rows)

    # ----------------------------------------------------------- surveys_wide
    surv = raw.surveys.copy()
    sus_rows = surv[surv["instrument"] == "sus"]
    ues_rows = surv[surv["instrument"] == "ues"]
    open_rows = surv[surv["instrument"] == "open_ended"]

    sus_item = sus_item_ids()
    ues_item = ues_item_ids()
    open_item = open_ended_ids()

    sus_records = []
    for _, r in sus_rows.iterrows():
        resp = r["responses_json"] or {}
        scored = compute_sus(resp)
        rec = {"user_id": str(r["user_id"]), "sus_complete": int(scored["complete"]),
               "sus_total": scored.get("sus_score")}
        for q in sus_item:
            rec[f"sus_{q}"] = resp.get(q)
        sus_records.append(rec)
    sus_df = pd.DataFrame(sus_records)
    if not sus_df.empty:
        sus_df = sus_df.sort_values(["user_id", "sus_complete"], ascending=[True, False]).drop_duplicates("user_id")

    ues_records = []
    for _, r in ues_rows.iterrows():
        resp = r["responses_json"] or {}
        scored = compute_ues(resp)
        rec = {"user_id": str(r["user_id"]),
               "ues_complete": int(scored["complete"]),
               "ues_overall": scored.get("ues_overall"),
               "ues_fa_mean": scored.get("fa_mean"),
               "ues_pu_mean": scored.get("pu_mean"),
               "ues_ae_mean": scored.get("ae_mean"),
               "ues_rw_mean": scored.get("rw_mean")}
        for q in ues_item:
            rec[f"ues_{q}"] = resp.get(q)
        ues_records.append(rec)
    ues_df = pd.DataFrame(ues_records)
    if not ues_df.empty:
        ues_df = ues_df.sort_values(["user_id", "ues_complete"], ascending=[True, False]).drop_duplicates("user_id")

    open_records = []
    for _, r in open_rows.iterrows():
        resp = r["responses_json"] or {}
        rec = {"user_id": str(r["user_id"])}
        for q in open_item:
            rec[f"oe_{q}"] = resp.get(q, "")
        open_records.append(rec)
    open_df = pd.DataFrame(open_records)
    if not open_df.empty:
        open_df = open_df.drop_duplicates("user_id", keep="last")

    # 合并
    students["user_id_str"] = students["user_id"].astype(str)
    surveys_wide = students[["user_id_str", "group", "group_label"]].rename(columns={"user_id_str": "user_id"})
    for df in (sus_df, ues_df, open_df):
        if not df.empty:
            surveys_wide = surveys_wide.merge(df, on="user_id", how="left")

    return Dataset(
        students=students,
        learning=learning,
        exams=exams,
        checklist_long=checklist_long,
        surveys_wide=surveys_wide,
    )
