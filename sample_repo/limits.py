"""演示用限制函数：作为跨文件检索的第二个目标。"""


def within_count_limit(count: int, limit: int) -> bool:
    """判断数量是否在限制内。"""
    return count <= limit


def max_body_bytes() -> int:
    """请求体大小上限（字节）。"""
    return 1 << 20
