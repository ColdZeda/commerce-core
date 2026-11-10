"""检查垃圾注释与注释密度。规则见 AGENTS.md §6。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED = [
    (re.compile(r"^\s*#\s*\d+[.、]\s*"), "步骤旁白"),
    (re.compile(r"#\s*(然后|接下来|下面|首先|接着|最后)"), "步骤旁白"),
    (re.compile(r"#\s*(TODO|FIXME|XXX)"), "空头待办"),
    (re.compile(r"#\s*(简单处理|暂时不处理|以后优化)"), "自我免责"),
    (re.compile(r"^\s*#\s*[=\-#]{4,}"), "分区横幅"),
]

SKIP_DIRS = {"migrations", "node_modules", ".venv", "venv", "__pycache__", ".git", "build", "dist"}
DENSITY_LIMIT = 0.05


def iter_py(root: Path):
    for path in sorted(root.rglob("*.py")):
        if SKIP_DIRS & set(path.parts):
            continue
        yield path


def scan(path: Path):
    code = 0
    comment = 0
    hits = []
    in_doc = False
    for no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if line.startswith(('"""', "'''")):
            quote = line[:3]
            if len(line) > 3 and line.rstrip().endswith(quote):
                continue
            in_doc = not in_doc
            continue
        if in_doc or not line:
            continue
        if line.startswith("#"):
            comment += 1
            for pattern, reason in BANNED:
                if pattern.search(raw):
                    hits.append((no, reason, line[:70]))
                    break
        else:
            code += 1
    return hits, code, comment


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    total_code = 0
    total_comment = 0
    problems: list[str] = []

    for path in iter_py(root):
        hits, code, comment = scan(path)
        total_code += code
        total_comment += comment
        for no, reason, text in hits:
            problems.append(f"{path}:{no} [{reason}] {text}")

    total = total_code + total_comment
    ratio = total_comment / total if total else 0.0

    for item in problems:
        print(item)
    print(f"\n注释行 {total_comment} / 代码行 {total_code}，占比 {ratio:.1%}（上限 {DENSITY_LIMIT:.0%}）")

    if problems:
        print(f"FAIL: {len(problems)} 处禁用注释")
        return 1
    if ratio > DENSITY_LIMIT:
        print("FAIL: 注释密度超标")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
