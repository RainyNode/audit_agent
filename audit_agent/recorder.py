# -*- coding: utf-8 -*-
"""运行记录：每个 run 一个目录，原始记录只追加、不修改（开题报告第十节）。

runs/<run_id>/
    events.jsonl   逐轮事件（模型请求/响应、工具请求/结果、异常、起止）
    raw/           模型原始响应（保留归档，由适配器提供）
    report.md      最终审计报告
    summary.json   一次运行的汇总（E 的记录表以它为数据源）
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import datetime
from pathlib import Path


def make_run_id(task_id: str, repeat_index: int) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{task_id}-r{repeat_index:02d}-{timestamp}-{secrets.token_hex(2)}"


class Recorder:
    def __init__(self, runs_dir, run_id: str):
        self.run_id = run_id
        self.dir = Path(runs_dir) / run_id
        (self.dir / "raw").mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / "events.jsonl"

    def event(self, event_type: str, **fields) -> None:
        record = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "type": event_type,
            **fields,
        }
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def save_raw(self, filename: str, obj) -> None:
        path = self.dir / "raw" / filename
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def save_report(self, text: str) -> str:
        path = self.dir / "report.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def save_summary(self, summary: dict) -> None:
        path = self.dir / "summary.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
