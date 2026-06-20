"""导出 OpenAPI schema 到 packages/shared/openapi.json。

这是前端类型 codegen 的输入。CI 会重新运行本脚本并 `git diff --exit-code`，
确保 committed 的 schema 与后端代码不漂移——后端改了模型却没重新生成 → CI 红。

输出保证确定性（sort_keys + 固定缩进 + 末尾换行），否则 diff 不稳定。

用法: uv run python -m app.export_openapi
"""

import json
from pathlib import Path

from app.main import app

# app/export_openapi.py -> app -> backend -> repo 根
_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT = _REPO_ROOT / "packages" / "shared" / "openapi.json"


def main() -> None:
    spec = app.openapi()
    _OUTPUT.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema 已写入 {_OUTPUT}")


if __name__ == "__main__":
    main()
