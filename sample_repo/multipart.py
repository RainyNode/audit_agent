"""演示用表单解析模块：只实现足以联调检索的最小逻辑。"""

BOUNDARY_PREFIX = b"--"


def parse_form(body: bytes):
    """解析整个请求体，返回 (普通字段字典, 文件字段列表)。"""
    fields, files = {}, []
    for part in split_parts(body):
        name, value = read_part(part)
        if _is_file(name):
            files.append(FileItem(name, value))
        else:
            fields[name] = value.decode("utf-8", "replace")
    return fields, files


def split_parts(body: bytes):
    """按 multipart 边界把请求体切成若干段。"""
    boundary = _find_boundary(body)
    if boundary is None:
        return []
    segments = body.split(boundary)
    return [seg for seg in segments[1:-1] if seg.strip(b"\r\n-")]


def read_part(part: bytes):
    """返回 (字段名, 值)；文件字段与普通字段同样处理。"""
    raw_headers, _, payload = part.partition(b"\r\n\r\n")
    name = _header_name(raw_headers)
    return name, payload


def _find_boundary(body: bytes):
    head, _, rest = body.partition(b"\r\n\r\n")
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-type") and b"boundary=" in line:
            return BOUNDARY_PREFIX + line.split(b"boundary=")[-1].strip()
    return None


def _header_name(raw_headers: bytes) -> str:
    for line in raw_headers.split(b"\r\n"):
        if line.lower().startswith(b"content-disposition"):
            for token in line.split(b";"):
                token = token.strip()
                if token.startswith(b"name="):
                    return token[5:].strip(b'"').decode("utf-8", "replace")
    return ""


def _is_file(name: str) -> bool:
    return name.startswith("file")


class FileItem:
    def __init__(self, filename, payload):
        self.filename = filename
        self.payload = payload

    def write_to(self, directory):
        import os

        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, self.filename), "wb") as fh:
            fh.write(self.payload)
