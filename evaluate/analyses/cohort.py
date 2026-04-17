"""CONSORT 风格队列流，识别完整 / 不完整 pipeline。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import EXAM_METHOD, GROUP_LABELS, LEARNING_METHODS, Settings


TITLE = "Cohort flow & pipeline integrity"


def analyze(ds: Dataset, settings: Settings) -> dict:
    students = ds.students
    sessions_total = len(ds.learning) + len(ds.exams)

    n_students = len(students)
    n_with_consent = int(students["consent_given"].sum()) if "consent_given" in students.columns else None

    # 三组分布
    groups = (
        students.groupby(["group", "group_label"], dropna=False)
        .size().reset_index(name="n_students")
    )

    # pipeline 完整性
    completeness = students.groupby("group").agg(
        n_total=("user_id", "count"),
        n_pipeline_complete=("pipeline_complete", "sum"),
        mean_n_learning=("n_learning_sessions", "mean"),
        mean_n_exam=("n_exam_sessions", "mean"),
    ).reset_index()
    completeness["completeness_rate"] = (completeness["n_pipeline_complete"] /
                                         completeness["n_total"]).round(3)

    # 异常：学生方法>1 / 缺学习 / 缺考试
    flagged = students[
        (students["n_learning_sessions"] != 2) | (students["n_exam_sessions"] != 1)
        | (students["group"] == "MIXED")
    ][["user_id", "username", "full_name", "group_label",
       "n_learning_sessions", "n_exam_sessions"]]

    # 学习会话/case 分布
    learning_by_case = (
        ds.learning.groupby(["group_label", "case_id"]).size()
        .unstack(fill_value=0).reset_index()
    )
    exam_by_case = (
        ds.exams.groupby(["group_label", "case_id"]).size()
        .unstack(fill_value=0).reset_index()
    )

    return {
        "title": TITLE,
        "summary": {
            "n_students": n_students,
            "n_consent_given": n_with_consent,
            "n_sessions_total": sessions_total,
            "n_learning_sessions": len(ds.learning),
            "n_exam_sessions": len(ds.exams),
            "groups_supported": list(LEARNING_METHODS),
            "exam_method": EXAM_METHOD,
        },
        "groups": groups,
        "pipeline_completeness": completeness,
        "flagged_students": flagged,
        "learning_by_case": learning_by_case,
        "exam_by_case": exam_by_case,
    }
