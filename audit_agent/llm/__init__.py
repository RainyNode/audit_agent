# -*- coding: utf-8 -*-
"""模型适配器工厂。

GLM、DeepSeek 的内置接口地址写在这里；如官方地址变更，
由对应负责人（A / B）核实后修改，并把变更写进联调记录。
"""

from __future__ import annotations

import os

from .base import BaseModelAdapter
from .mock import MockAdapter
from .openai_compat import OpenAICompatAdapter

PROVIDER_BASE_URLS = {
    "glm": "https://open.bigmodel.cn/api/paas/v4/",
    "deepseek": "https://api.deepseek.com/v1",
}


def build_adapter(cfg) -> BaseModelAdapter:
    if cfg.adapter == "mock":
        return MockAdapter()
    if cfg.adapter in PROVIDER_BASE_URLS:
        base_url = cfg.base_url or PROVIDER_BASE_URLS[cfg.adapter]
        api_key = os.environ.get(cfg.api_key_env, "")
        if not api_key:
            raise SystemExit(
                f"未设置环境变量 {cfg.api_key_env}，无法调用 {cfg.adapter}。"
                f"密钥只放环境变量，不要写进配置或记录文件。"
            )
        return OpenAICompatAdapter(
            name=cfg.adapter,
            model_name=cfg.model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=cfg.temperature,
        )
    raise SystemExit(f"未知适配器: {cfg.adapter}（可选 mock / glm / deepseek）")
