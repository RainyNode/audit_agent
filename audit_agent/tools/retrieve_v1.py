# -*- coding: utf-8 -*-
"""V1 关键词检索（最小可运行版本，先由组长顶上，C 后续替换为索引版）。

规则：遍历仓库内 .py 文件 -> 关键词大小写不敏感匹配 -> 命中行上下扩窗并合并
-> 按本次 max_chars 依次返回，放不下的片段注明截断。
重复返回的代码照常计入总字符预算（开题报告第五节）。

C 替换为索引版（V2/V3 同理）时，保持 Tool(name="retrieve_code", ...) 接口不变，
主循环无需改动。
"""

from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolResult

CONTEXT_LINES = 3              # 命中行上下各带的行数
DEFAULT_MAX_CHARS = 4000       # 单次检索默认返回字符上限


def _merge_ranges(line_ids, context: int):
    """把命中行合并为连续区间 [start, end]（0 基，含端点）。"""
    ranges = []
    for i in sorted(line_ids):
        start, end = max(0, i - context), i + context
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    return ranges


def build_v1_tool(repo_root) -> Tool:
    root = Path(repo_root)

    def validate(args):
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return "query 必须为非空字符串（空格分隔多个关键词）"
        max_chars = args.get("max_chars", DEFAULT_MAX_CHARS)
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 200 <= max_chars <= 8000:
            return "max_chars 必须是 200-8000 的整数"
        return None

    def func(args) -> ToolResult:
        terms = [t for t in str(args["query"]).split() if t]
        max_chars = int(args.get("max_chars", DEFAULT_MAX_CHARS))

        py_files = sorted(p for p in root.rglob("*.py") if p.is_file())
        if not py_files:
            return ToolResult(True, f"源码目录 {root} 下没有 .py 文件。", 0)

        hits = {}   # 相对路径 -> 命中行号列表（0 基）
        for path in py_files:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines):
                lowered = line.lower()
                if any(term.lower() in lowered for term in terms):
                    hits.setdefault(path.relative_to(root).as_posix(), []).append(idx)

        if not hits:
            content = f"关键词 {' / '.join(terms)} 未命中任何 .py 文件，请更换关键词重试。"
            return ToolResult(True, content, len(content))

        total_matches = sum(len(v) for v in hits.values())
        header = f"检索词: {' / '.join(terms)}；命中 {len(hits)} 个文件、{total_matches} 处。\n\n"
        blocks = []
        used = len(header)
        truncated = 0
        for rel in sorted(hits):
            lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            last_line = max(0, len(lines) - 1)
            for start, end in _merge_ranges(hits[rel], CONTEXT_LINES):
                end = min(end, last_line)
                snippet = "\n".join(lines[start:end + 1])
                block = f"### 文件: {rel}（行 {start + 1}-{end + 1}）\n```python\n{snippet}\n```\n\n"
                if used + len(block) > max_chars:
                    truncated += 1
                    continue
                blocks.append(block)
                used += len(block)

        content = header + "".join(blocks)
        if truncated:
            content += f"（因本次 max_chars={max_chars} 限制，有 {truncated} 个片段未返回，可缩小关键词继续检索。）\n"
        return ToolResult(True, content, len(content))

    return Tool(
        name="retrieve_code",
        description="按关键词检索源码，返回带文件名与行号的代码片段（只读）。空格分隔多个关键词。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，例如：form multipart limit",
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"本次返回代码字符上限，默认 {DEFAULT_MAX_CHARS}，范围 200-8000",
                },
            },
            "required": ["query"],
        },
        func=func,
        validate=validate,
    )
