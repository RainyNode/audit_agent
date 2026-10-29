# -*- coding: utf-8 -*-
"""GLM / DeepSeek 共用的 OpenAI 兼容适配器。

两家供应商都提供 OpenAI 兼容接口，因此共用一个适配器、按配置区分：
A、B 各自核实所负责型号的准确名称、参数支持情况与用量字段，
差异不要静默处理——如实记入运行事件，"不以同名接口推定行为一致"。
"""

from __future__ import annotations

import json

from .base import BaseModelAdapter, LLMResponse, ToolCall


class OpenAICompatAdapter(BaseModelAdapter):
    def __init__(self, name: str, model_name: str, base_url: str, api_key: str, temperature: float = 0.3):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise SystemExit("调用真实模型需要安装 openai 包：pip install -r requirements.txt") from exc
        self.name = name
        self.model_name = model_name
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: list, tools_spec: list) -> LLMResponse:
        kwargs = dict(model=self.model_name, messages=messages, temperature=self.temperature)
        if tools_spec:
            kwargs["tools"] = tools_spec
        resp = self.client.chat.completions.create(**kwargs)

        choice = resp.choices[0]
        message = choice.message
        tool_calls = []
        for tc in (message.tool_calls or []):
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                # 参数不是合法 JSON 时原样带回，由主循环校验后把错误回给模型
                arguments = {"_invalid_arguments": tc.function.arguments}
            tool_calls.append(ToolCall(call_id=tc.id, name=tc.function.name, arguments=arguments))

        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            usage_reported=usage is not None,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
