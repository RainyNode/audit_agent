# -*- coding: utf-8 -*-
"""任务配置：对应开题报告"最小接口约定"中的任务配置一行。

task_id、源码路径、审计范围（匿名、不含答案）、模型配置、策略、预算、重复编号。
repo_path 为相对路径时，以任务文件所在目录为基准解析。
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class BudgetConfig:
    time_minutes: int = 10        # 总时限
    model_requests: int = 12      # 模型请求次数
    retrieve_calls: int = 20      # 检索调用次数
    code_chars: int = 40000       # 累计返回代码字符数


@dataclass
class ModelConfig:
    adapter: str = "mock"                    # mock | glm | deepseek
    model_name: str = "mock-1"               # 精确模型名，随运行记录保存
    base_url: str = ""                       # 留空使用内置地址
    api_key_env: str = "AUDIT_LLM_API_KEY"   # 密钥只放环境变量，不进任何记录
    temperature: float = 0.3


@dataclass
class TaskConfig:
    task_id: str
    repo_path: str
    scope: str                     # 匿名审计任务描述
    strategy: str = "V1"
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    repeat_index: int = 1
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_task(path) -> TaskConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("task_id", "repo_path", "scope"):
        if not raw.get(key):
            raise SystemExit(f"任务配置缺少必填字段: {key}")
    return TaskConfig(
        task_id=str(raw["task_id"]),
        repo_path=str(raw["repo_path"]),
        scope=str(raw["scope"]),
        strategy=str(raw.get("strategy", "V1")),
        budget=BudgetConfig(**(raw.get("budget") or {})),
        model=ModelConfig(**(raw.get("model") or {})),
        repeat_index=int(raw.get("repeat_index", 1)),
        notes=str(raw.get("notes", "")),
    )
