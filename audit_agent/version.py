# -*- coding: utf-8 -*-
"""程序版本标识：优先返回 git 短提交号，满足"运行记录关联程序版本"的要求。

zip 分发或未安装 git 时自动回退到固定版本号，不影响运行。
"""

from pathlib import Path

from . import PROGRAM_VERSION

_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_program_version() -> str:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"{PROGRAM_VERSION}+{result.stdout.strip()}"
    except Exception:
        pass
    return PROGRAM_VERSION
