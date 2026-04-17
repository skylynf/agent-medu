"""命令行入口：

    python -m evaluate run                 # 跑全部分析
    python -m evaluate run --section exam  # 仅指定模块（可重复）
    python -m evaluate dump                # 仅把数据库快照成 CSV
    python -m evaluate inspect             # 打印每个表行数 + 样例
"""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluate import report as r
from evaluate.analyses import REGISTRY
from evaluate.build_dataset import build
from evaluate.config import get_settings
from evaluate.loader import load_all
from evaluate.printers import PRINTERS


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m evaluate", description="Medu-SPAgent 论文级分析")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="跑分析")
    run.add_argument("--section", "-s", action="append",
                     choices=list(REGISTRY.keys()),
                     help="只跑指定 section，可重复。默认全部。")
    run.add_argument("--no-write", action="store_true", help="不写 output/ 文件")
    run.add_argument("--max-rows", type=int, default=100, help="每张表最大打印行数")

    dump = sub.add_parser("dump", help="把数据库表快照为 CSV")
    dump.add_argument("--out", default=None, help="输出目录（默认 OUTPUT_DIR/raw/）")

    sub.add_parser("inspect", help="打印每张表的行数与字段")

    return p


def cmd_run(args) -> int:
    settings = get_settings()
    out_dir = settings.ensure_output()

    r.section("Medu-SPAgent — paper-grade evaluation pipeline",
              subtitle=f"Postgres: {_redact(settings.database_url)}  ALPHA={settings.alpha}")

    raw = load_all()
    r.kv(raw.info(), title="Raw row counts")

    ds = build(raw)
    r.kv({
        "n_students": len(ds.students),
        "n_learning_sessions": len(ds.learning),
        "n_exam_sessions": len(ds.exams),
        "checklist_long_rows": len(ds.checklist_long),
        "surveys_wide_rows": len(ds.surveys_wide),
    }, title="Dataset summary")

    sections = args.section or list(REGISTRY.keys())
    for name in sections:
        mod = REGISTRY[name]
        try:
            res = mod.analyze(ds, settings)
        except Exception as e:  # 不让单个 section 崩掉整个 pipeline
            r.section(f"{name}: FAILED")
            r.kv({"error": repr(e)})
            continue
        printer = PRINTERS.get(name)
        if printer:
            printer(res)
        else:
            r.section(name)
            r.kv({"keys": list(res.keys())})
        if not args.no_write:
            r.write_outputs(name, res, out_dir)

    if not args.no_write:
        # 同时把构建出来的关键宽表也落盘
        ds.students.to_csv(out_dir / "ds_students.csv", index=False)
        ds.learning.to_csv(out_dir / "ds_learning.csv", index=False)
        ds.exams.to_csv(out_dir / "ds_exams.csv", index=False)
        ds.checklist_long.to_csv(out_dir / "ds_checklist_long.csv", index=False)
        ds.surveys_wide.to_csv(out_dir / "ds_surveys_wide.csv", index=False)
        r.section("Output files written")
        r.kv({"output_dir": str(out_dir.resolve())})

    return 0


def cmd_dump(args) -> int:
    settings = get_settings()
    out = Path(args.out or (settings.output_dir / "raw"))
    raw = load_all()
    paths = raw.dump_csv(out)
    r.section("Raw tables dumped to CSV")
    for k, p in paths.items():
        print(f"  {k:>22}  {p}")
    return 0


def cmd_inspect(_args) -> int:
    raw = load_all()
    info = raw.info()
    r.section("Row counts")
    r.kv(info)
    for tbl in ("users", "training_sessions", "messages", "final_evaluations", "survey_responses"):
        df = getattr(raw, _alias(tbl))
        r.section(f"{tbl} — schema")
        r.kv({c: str(df[c].dtype) for c in df.columns})
        if not df.empty:
            r.df(df.head(3), title=f"{tbl} sample (head 3)")
    return 0


def _alias(t: str) -> str:
    return {
        "users": "users",
        "training_sessions": "sessions",
        "messages": "messages",
        "evaluation_snapshots": "snapshots",
        "final_evaluations": "finals",
        "ct_steps": "ct_steps",
        "survey_responses": "surveys",
        "prompts": "prompts",
    }[t]


def _redact(url: str) -> str:
    if not url or "://" not in url:
        return url
    head, tail = url.split("://", 1)
    if "@" in tail:
        creds, host = tail.split("@", 1)
        return f"{head}://***@{host}"
    return url


def main(argv=None) -> int:
    args = _make_parser().parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "dump":
        return cmd_dump(args)
    if args.cmd == "inspect":
        return cmd_inspect(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
