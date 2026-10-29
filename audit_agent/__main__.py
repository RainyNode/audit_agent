# -*- coding: utf-8 -*-
"""命令行入口：python -m audit_agent --task tasks/demo_starlette.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_task
from .llm import build_adapter
from .loop import AgentLoop
from .recorder import Recorder, make_run_id
from .tools import ToolRegistry
from .tools.retrieve_v1 import build_v1_tool
from .version import get_program_version


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="审计 Agent 主循环（骨架版）")
    parser.add_argument("--task", required=True, help="任务配置 JSON 路径")
    parser.add_argument("--runs-dir", default=None, help="运行记录目录，默认为任务文件上上级目录下的 runs/")
    parser.add_argument("--adapter", choices=["mock", "glm", "deepseek"], help="覆盖任务配置中的模型适配器")
    parser.add_argument("--model", help="覆盖精确模型名")
    parser.add_argument("--base-url", help="覆盖接口地址")
    parser.add_argument("--repeat-index", type=int, help="覆盖重复编号")
    args = parser.parse_args(argv)

    task_path = Path(args.task).resolve()
    task = load_task(task_path)
    if args.adapter:
        task.model.adapter = args.adapter
    if args.model:
        task.model.model_name = args.model
    if args.base_url:
        task.model.base_url = args.base_url
    if args.repeat_index is not None:
        task.repeat_index = args.repeat_index

    repo = Path(task.repo_path)
    if not repo.is_absolute():
        repo = (task_path.parent / repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"源码目录不存在: {repo}")

    runs_dir = Path(args.runs_dir) if args.runs_dir else task_path.parent.parent / "runs"

    adapter = build_adapter(task.model)
    registry = ToolRegistry()
    registry.register(build_v1_tool(repo))

    run_id = make_run_id(task.task_id, task.repeat_index)
    recorder = Recorder(runs_dir, run_id)
    print(f"[audit_agent {get_program_version()}] run_id = {run_id}")

    summary = AgentLoop(task, adapter, registry, recorder).run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
