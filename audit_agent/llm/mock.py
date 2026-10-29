# -*- coding: utf-8 -*-
"""流水线自测适配器：不需要密钥、不消耗费用。

行为固定：第一次请求返回一次 retrieve_code 调用，之后返回模拟报告。
用于在接入真实模型前验证主循环、预算扣减与记录链路是否正常。
"""

from __future__ import annotations

from .base import BaseModelAdapter, LLMResponse, ToolCall


class MockAdapter(BaseModelAdapter):
    name = "mock"
    model_name = "mock-1"

    def __init__(self, keyword: str = "form parse limit"):
        self.keyword = keyword

    def chat(self, messages: list, tools_spec: list) -> LLMResponse:
        already_answered = any(m.get("role") == "assistant" for m in messages)
        if not already_answered:
            return LLMResponse(
                text="",
                tool_calls=[ToolCall(
                    call_id="mock-call-1",
                    name="retrieve_code",
                    arguments={"query": self.keyword, "max_chars": 3000},
                )],
                finish_reason="tool_calls",
            )

        report = (
            "## 模拟审计报告（Mock，不代表模型真实结论）\n\n"
            "- 本报告由 MockAdapter 生成，仅用于验证主循环、工具调用与记录链路。\n"
            "- 实际检索返回内容见 events.jsonl 与 raw/ 目录。\n\n"
            "### 结论\n"
            "证据不足，无法给出可确认的审计结论（模拟输出）。"
        )
        return LLMResponse(text=report, finish_reason="stop")
