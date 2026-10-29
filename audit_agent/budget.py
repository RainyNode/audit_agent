# -*- coding: utf-8 -*-
"""运行预算：总时限、模型请求次数、检索次数、累计返回代码字符数。

对应开题报告"拟定首轮统一预算"。重复返回的代码照常计入字符预算。
预算耗尽不删改任何已产生的记录；主循环据此决定何时进入收尾流程。
"""

import time


class Budget:
    def __init__(self, time_minutes: int, model_requests: int, retrieve_calls: int, code_chars: int):
        self.time_limit_sec = time_minutes * 60
        self.max_model_requests = model_requests
        self.max_retrieve_calls = retrieve_calls
        self.max_code_chars = code_chars

        self._start = time.monotonic()
        self.model_requests = 0
        self.retrieve_calls = 0
        self.code_chars = 0

    # ---- 查询 ----

    def elapsed_sec(self) -> float:
        return time.monotonic() - self._start

    def time_left(self) -> float:
        return self.time_limit_sec - self.elapsed_sec()

    def can_model_request(self) -> bool:
        return self.model_requests < self.max_model_requests and self.time_left() > 0

    def retrieve_exhausted(self) -> bool:
        return self.retrieve_calls >= self.max_retrieve_calls

    def code_chars_exhausted(self) -> bool:
        return self.code_chars >= self.max_code_chars

    # ---- 扣减 ----

    def consume_model_request(self) -> None:
        self.model_requests += 1

    def consume_retrieve(self) -> None:
        self.retrieve_calls += 1

    def add_code_chars(self, n: int) -> None:
        self.code_chars += n

    def totals(self) -> dict:
        return {
            "elapsed_sec": round(self.elapsed_sec(), 1),
            "model_requests": self.model_requests,
            "model_requests_max": self.max_model_requests,
            "retrieve_calls": self.retrieve_calls,
            "retrieve_calls_max": self.max_retrieve_calls,
            "code_chars": self.code_chars,
            "code_chars_max": self.max_code_chars,
        }
