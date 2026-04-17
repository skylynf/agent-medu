"""把分析结果格式化打印到命令行，并把可序列化的部分写到 output/。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def section(title: str, subtitle: str | None = None) -> None:
    console.rule(f"[bold cyan]{title}")
    if subtitle:
        console.print(f"[dim]{subtitle}[/dim]")


def kv(d: dict, *, title: str | None = None) -> None:
    t = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1))
    t.add_column("k", style="bold")
    t.add_column("v")
    for k, v in d.items():
        t.add_row(str(k), _fmt(v))
    if title:
        console.print(Panel(t, title=title, border_style="dim"))
    else:
        console.print(t)


def df(df_: pd.DataFrame, *, title: str | None = None, max_rows: int = 100) -> None:
    if df_ is None or len(df_) == 0:
        if title:
            console.print(f"[yellow]{title}: (空)[/yellow]")
        return
    show = df_.head(max_rows)
    table = Table(title=title, header_style="bold magenta", show_lines=False)
    for c in show.columns:
        table.add_column(str(c))
    for _, row in show.iterrows():
        table.add_row(*[_fmt(v) for v in row.tolist()])
    console.print(table)
    if len(df_) > max_rows:
        console.print(f"[dim]…(共 {len(df_)} 行，已截断到 {max_rows} 行)[/dim]")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if pd.isna(v):
            return "—"
        if abs(v) >= 10000 or (abs(v) < 0.01 and v != 0):
            return f"{v:.4g}"
        return f"{v:.4f}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)[:80]
    return str(v)


def to_json_safe(obj: Any) -> Any:
    """把含 DataFrame 的 dict 转成可 json.dump 的结构。"""
    if isinstance(obj, pd.DataFrame):
        # 单元格可能是 DB 读出的 UUID 等，需再走一遍清洗
        return to_json_safe(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return to_json_safe(obj.to_dict())
    if isinstance(obj, dict):
        # json 仅接受 str 键；分析结果里 groupby 标签常为 UUID / 非 str
        return {
            (k if isinstance(k, str) else str(k)): to_json_safe(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def write_outputs(name: str, payload: dict, out_dir: Path) -> None:
    """把分析结果写到 output/{name}.json，且把每个 DataFrame 字段单独落 csv。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{name}.json"
    json_path.write_text(json.dumps(to_json_safe(payload), ensure_ascii=False, indent=2),
                         encoding="utf-8")
    for k, v in _walk_dataframes(payload, prefix=name):
        v.to_csv(out_dir / f"{k}.csv", index=False)


def _walk_dataframes(obj: Any, *, prefix: str):
    if isinstance(obj, pd.DataFrame):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_dataframes(v, prefix=f"{prefix}__{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk_dataframes(v, prefix=f"{prefix}__{i}")
