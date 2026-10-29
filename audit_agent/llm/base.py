# -*- coding: utf-8 -*-
"""模型适配层接口。A（GLM）与 B（DeepSeek）的接入都实现这一个接口。

主循环只依赖本文件的数据结构与 BaseModelAdapter，不关心供应商差异。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    """模型发出的一次工具请求。"""

    call_id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """一次模型响应的统一表示。

    raw 保存供应商原始响应（A/B 的适配器负责提供），供归档核查；
    usage_reported 为 False 表示供应商未返回用量字段，费用计算时须注明。
    """

    text: str = ""
    tool_calls: list = field(default_factory=list)
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    usage_reported: bool = False
    raw: Optional[dict] = None


class BaseModelAdapter(abc.ABC):
    """模型适配器接口：接收 OpenAI 风格的 messages 与 tools 定义，返回 LLMResponse。"""

    name: str = "base"
    model_name: str = "unknown"

    @abc.abstractmethod
    def chat(self, messages: list, tools_spec: list) -> LLMResponse:
        raise NotImplementedError
