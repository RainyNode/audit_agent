"""演示用最小 Web 应用：仅供主循环与检索工具联调。

这不是真实漏洞验证对象；正式调试案例由 D 固定 Starlette 版本后另行准备。
"""

from multipart import parse_form
from limits import within_count_limit

UPLOAD_DIR = "uploads"


def handle_upload(request):
    """上传入口：外部输入进入程序的位置。"""
    fields, files = parse_form(request.body)
    if not within_count_limit(len(files), limit=50):
        return {"status": 413, "error": "too many files"}
    saved = []
    for item in files:
        item.write_to(UPLOAD_DIR)
        saved.append(item.filename)
    return {"status": 200, "saved": saved}


def handle_login(request):
    """登录入口：同样经过表单解析。"""
    fields, _ = parse_form(request.body)
    return check_password(fields.get("username", ""), fields.get("password", ""))


def check_password(username, password):
    stored = load_user(username)
    return {"status": 200} if stored == password else {"status": 401}


def load_user(username):
    db = {"alice": "wonderland"}
    return db.get(username)
