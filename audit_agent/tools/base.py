# -*- coding: utf-8 -*-
"""工具层接口：模型只能调用在这里登记的只读工具（白名单）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolResult:
    ok: bool
    content: str
    chars: int = 0   # 计入代码字符预算的字符数；错误结果为 0


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, func, validate=None):
        self.name = name
        self.description = description
        self.parameters = parameters   # JSON Schema，随工具清单发给模型
        self.func = func
        self.validate = validate or (lambda args: None)


class ToolRegistry:
    """只读工具白名单：名字不在登记表里的调用一律拒绝。"""

    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重复登记: {tool.name}")
        self._tools[tool.name] = tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def validate(self, name: str, arguments: dict) -> Optional[str]:
        return self._tools[name].validate(arguments or {})

    def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools[name]
        try:
            return tool.func(dict(arguments or {}))
        except Exception as exc:  # 工具异常转成给模型的错误信息，模型可在剩余预算内修正重试
            return ToolResult(False, f"工具执行异常: {exc!r}", 0)

    def spec(self) -> list:
        """OpenAI 风格的工具定义，发给模型。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]
