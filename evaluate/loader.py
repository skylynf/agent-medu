"""把 Postgres 中所有相关表读入 pandas。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from evaluate.db import make_engine

_TABLES = {
    "users": "SELECT * FROM users",
    "training_sessions": "SELECT * FROM training_sessions",
    "messages": "SELECT * FROM messages",
    "evaluation_snapshots": "SELECT * FROM evaluation_snapshots",
    "final_evaluations": "SELECT * FROM final_evaluations",
    "ct_steps": "SELECT * FROM ct_steps",
    "survey_responses": "SELECT * FROM survey_responses",
    "prompts": "SELECT * FROM prompts",
}


@dataclass
class RawData:
    users: pd.DataFrame
    sessions: pd.DataFrame
    messages: pd.DataFrame
    snapshots: pd.DataFrame
    finals: pd.DataFrame
    ct_steps: pd.DataFrame
    surveys: pd.DataFrame
    prompts: pd.DataFrame

    def info(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "training_sessions": len(self.sessions),
            "messages": len(self.messages),
            "evaluation_snapshots": len(self.snapshots),
            "final_evaluations": len(self.finals),
            "ct_steps": len(self.ct_steps),
            "survey_responses": len(self.surveys),
            "prompts": len(self.prompts),
        }

    def dump_csv(self, out_dir: Path) -> dict[str, Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        out: dict[str, Path] = {}
        for k, df in self.__dict__.items():
            p = out_dir / f"raw_{k}.csv"
            df.to_csv(p, index=False)
            out[k] = p
        return out


def load_all(engine: Engine | None = None) -> RawData:
    eng = engine or make_engine()
    frames: dict[str, pd.DataFrame] = {}
    with eng.connect() as conn:
        for name, sql in _TABLES.items():
            try:
                frames[name] = pd.read_sql(sql, conn)
            except Exception as e:
                # 缺表（例如还没运行迁移）→ 给空 DF 占位，让分析模块自行判断
                print(f"[loader] WARN: 表 {name} 读取失败：{e}")
                frames[name] = pd.DataFrame()
    return RawData(
        users=frames["users"],
        sessions=frames["training_sessions"],
        messages=frames["messages"],
        snapshots=frames["evaluation_snapshots"],
        finals=frames["final_evaluations"],
        ct_steps=frames["ct_steps"],
        surveys=frames["survey_responses"],
        prompts=frames["prompts"],
    )
