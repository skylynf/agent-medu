"""分析模块集合。每个 module 暴露一个 ``analyze(dataset, settings) -> dict`` 入口。"""

from . import (
    cohort,
    demographics,
    exam_outcomes,
    learning_process,
    learning_gain,
    checklist_items,
    surveys as surveys_mod,
    reliability,
    correlations,
    mixed_models,
    process_dialogue,
)

REGISTRY = {
    "cohort": cohort,
    "demographics": demographics,
    "exam": exam_outcomes,
    "learning_process": learning_process,
    "learning_gain": learning_gain,
    "checklist_items": checklist_items,
    "surveys": surveys_mod,
    "reliability": reliability,
    "correlations": correlations,
    "mixed_models": mixed_models,
    "dialogue": process_dialogue,
}
