# -*- coding: utf-8 -*-
"""共用 Agent 主循环（组长负责，全组共用的骨架）。

对应开题报告第四节的运行流程：
    加载任务 -> 组装提示 -> 循环{模型响应 -> 工具请求校验 -> 执行 -> 回填}
    -> 正常结束或预算耗尽时收尾 -> 按 run_id 保存全过程。

原则（开题报告第五节）：
- 模型只提出工具请求；参数校验、预算扣减、执行与记录由本程序完成；
- 只允许调用登记的只读工具；
- 预算耗尽时仍要求模型输出已完成分析与证据不足处；
- 接口异常至多自动重试一次，重试同样消耗请求预算并保留事件。
"""

from __future__ import annotations

import json
import time

from . import PROMPT_VERSION
from .budget import Budget
from .tools.base import ToolResult
from .version import get_program_version

SYSTEM_PROMPT = """你是一名源码安全审计助手。你只能通过登记的只读工具查看源码，不得假设未读到的内容。

规则：
1. 结论必须有代码依据，引用文件名与行号；
2. 先检索、后判断；关键路径上被调用或发起调用的函数应继续查看；
3. 区分已确认事实与推测，证据不足处明确说明；
4. 未发现可确认问题时，列出已检查范围与局限；
5. 分析完成后直接输出最终 Markdown 报告，不再调用工具。

报告中对每项发现说明：文件和行号、输入到达关键处理的路径、问题原因、必要条件、可能影响、修复建议。"""

USER_PROMPT_TEMPLATE = """审计任务（task_id: {task_id}，重复编号: {repeat}）：
{scope}

工具说明：调用 retrieve_code 时用空格分隔多个关键词；每次返回的代码计入总字符预算，请规划检索。"""

FINALIZE_PROMPT = (
    "运行预算已耗尽（{reason}）。请立即基于已获得的全部信息输出最终审计报告，"
    "未完成的部分说明证据不足；不要再提出新的检索请求。"
)

REASON_ZH = {
    "budget_time": "总时限",
    "budget_model_requests": "模型请求次数",
    "adapter_error": "模型接口异常",
    "empty_response": "模型返回为空",
    "completed": "模型输出最终报告",
    "completed_finalize": "预算耗尽后收尾输出",
}


class AgentLoop:
    def __init__(self, task, adapter, registry, recorder):
        self.task = task
        self.adapter = adapter
        self.registry = registry
        self.recorder = recorder
        self._usage = {"prompt": 0, "completion": 0, "reported": True}

    # ---- 对外入口 ----

    def run(self) -> dict:
        b = self.task.budget
        budget = Budget(b.time_minutes, b.model_requests, b.retrieve_calls, b.code_chars)
        self._usage = {"prompt": 0, "completion": 0, "reported": True}
        self.recorder.event(
            "run_start",
            task_id=self.task.task_id,
            repeat_index=self.task.repeat_index,
            model_adapter=self.adapter.name,
            model_name=self.adapter.model_name,
            strategy=self.task.strategy,
            program_version=get_program_version(),
            prompt_version=PROMPT_VERSION,
            config=self.task.to_dict(),
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                task_id=self.task.task_id, repeat=self.task.repeat_index, scope=self.task.scope)},
        ]
        tool_spec = self.registry.spec()

        finish_reason = None
        report = None

        while True:
            if budget.time_left() <= 0:
                finish_reason = "budget_time"
                break
            if not budget.can_model_request():
                finish_reason = "budget_model_requests"
                break

            resp = self._chat_with_retry(messages, tool_spec, budget)
            if resp is None:
                # 区分请求过程中预算耗尽，还是接口本身失败
                if budget.time_left() <= 0:
                    finish_reason = "budget_time"
                elif not budget.can_model_request():
                    finish_reason = "budget_model_requests"
                else:
                    finish_reason = "adapter_error"
                break

            if resp.tool_calls:
                messages.append(self._assistant_tool_message(resp))
                for tc in resp.tool_calls:
                    result = self._execute_tool(tc, budget)
                    messages.append({"role": "tool", "tool_call_id": tc.call_id, "content": result.content})
                continue

            if not resp.text.strip():
                finish_reason = "empty_response"
                break

            report = resp.text
            finish_reason = "completed"
            break

        # 预算耗尽 -> 收尾：还剩请求额度就要求基于已有证据出报告
        if finish_reason in ("budget_time", "budget_model_requests") and budget.can_model_request():
            self.recorder.event("finalize_request", trigger=finish_reason)
            messages.append({"role": "user", "content": FINALIZE_PROMPT.format(reason=REASON_ZH[finish_reason])})
            resp = self._chat_with_retry(messages, [], budget)
            if resp is not None:
                if resp.tool_calls:
                    self.recorder.event("finalize_tool_calls_ignored", count=len(resp.tool_calls))
                if resp.text.strip():
                    report = resp.text
                    finish_reason = "completed_finalize"

        totals = budget.totals()
        totals.update({
            "prompt_tokens": self._usage["prompt"],
            "completion_tokens": self._usage["completion"],
            "usage_reported": self._usage["reported"],
        })

        report_path = self.recorder.save_report(report) if report else None
        self.recorder.event("run_end", finish_reason=finish_reason, totals=totals, report_file=report_path)

        summary = {
            "run_id": self.recorder.run_id,
            "task_id": self.task.task_id,
            "repeat_index": self.task.repeat_index,
            "model": {"adapter": self.adapter.name, "model_name": self.adapter.model_name},
            "strategy": self.task.strategy,
            "prompt_version": PROMPT_VERSION,
            "program_version": get_program_version(),
            "finish_reason": finish_reason,
            "finish_reason_zh": REASON_ZH.get(finish_reason, finish_reason),
            "totals": totals,
            "report_file": report_path,
            "events_file": str(self.recorder.events_path),
        }
        self.recorder.save_summary(summary)
        return summary

    # ---- 内部步骤 ----

    def _chat_with_retry(self, messages, tool_spec, budget):
        """发起一次模型请求，失败至多自动重试一次。

        每次真实请求（含重试）都消耗请求预算并保留事件。
        """
        for attempt in (1, 2):
            if attempt == 2 and (budget.time_left() <= 0 or not budget.can_model_request()):
                self.recorder.event("model_retry_skipped", reason="预算已耗尽，不再重试")
                return None
            budget.consume_model_request()
            started = time.monotonic()
            try:
                resp = self.adapter.chat(messages, tool_spec)
            except Exception as exc:  # 供应商异常类型不一，统一记录后决定是否重试
                self.recorder.event("model_error", attempt=attempt, error=repr(exc))
                continue

            self._usage["prompt"] += resp.prompt_tokens
            self._usage["completion"] += resp.completion_tokens
            self._usage["reported"] = self._usage["reported"] and resp.usage_reported
            self.recorder.event(
                "model_response",
                attempt=attempt,
                finish_reason=resp.finish_reason,
                text_chars=len(resp.text),
                tool_calls=[{"name": t.name, "arguments": t.arguments} for t in resp.tool_calls],
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                usage_reported=resp.usage_reported,
                latency_ms=round((time.monotonic() - started) * 1000),
                message_count=len(messages),
            )
            if resp.raw is not None:
                self.recorder.save_raw(f"model-{budget.model_requests:02d}.json", resp.raw)
            return resp
        return None

    def _execute_tool(self, tc, budget) -> ToolResult:
        """工具请求校验 -> 预算检查 -> 执行 -> 记录。任何一步不通过都把错误回给模型。"""
        self.recorder.event("tool_request", name=tc.name, arguments=tc.arguments)
        if not self.registry.has(tc.name):
            return ToolResult(False, f"错误：工具 {tc.name} 未登记，只允许调用登记的只读检索工具。", 0)
        error = self.registry.validate(tc.name, tc.arguments)
        if error:
            return ToolResult(False, f"参数错误：{error}。可修正参数后在剩余预算内重试。", 0)
        if budget.retrieve_exhausted():
            return ToolResult(False, "检索次数预算已耗尽，请立即基于已有信息输出最终审计报告。", 0)
        if budget.code_chars_exhausted():
            return ToolResult(False, "代码字符预算已耗尽，请立即基于已有信息输出最终审计报告。", 0)

        budget.consume_retrieve()
        result = self.registry.execute(tc.name, tc.arguments)
        budget.add_code_chars(result.chars)
        self.recorder.event(
            "tool_result",
            name=tc.name,
            ok=result.ok,
            chars_returned=result.chars,
            code_chars_total=budget.code_chars,
        )
        return result

    @staticmethod
    def _assistant_tool_message(resp) -> dict:
        message = {
            "role": "assistant",
            "content": resp.text or None,
            "tool_calls": [
                {
                    "id": t.call_id,
                    "type": "function",
                    "function": {"name": t.name, "arguments": json.dumps(t.arguments, ensure_ascii=False)},
                }
                for t in resp.tool_calls
            ],
        }
        if resp.reasoning_content:
            message["reasoning_content"] = resp.reasoning_content
        return message
