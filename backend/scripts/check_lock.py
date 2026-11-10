"""比较 lock 文件与实际安装（pip freeze）是否一致，用于依赖锁定门槛。

带环境标记的条目按当前解释器求值：Windows 装 colorama、Linux 不装，两边都不该报不一致。
"""

import re
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
SPEC = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)", re.IGNORECASE)


def normalize(name: str) -> str:
    """PEP 503 归一化：pip freeze 会把 - 写成 _，两边要对齐才能比。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(paths: list[Path], environment: dict[str, str] | None = None) -> dict[str, str]:
    pins: dict[str, str] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("#"):
                continue
            requirement = Requirement(line)
            if requirement.marker is not None and not requirement.marker.evaluate(environment):
                continue
            match = SPEC.match(line)
            if match:
                pins[normalize(match.group(1))] = match.group(2)
    return pins


def freeze(python: Path) -> dict[str, str]:
    output = subprocess.run(
        [str(python), "-m", "pip", "freeze"], capture_output=True, text=True, check=True
    ).stdout
    pins = {}
    for line in output.splitlines():
        match = SPEC.match(line.strip())
        if match:
            pins[normalize(match.group(1))] = match.group(2)
    return pins


def main() -> int:
    python = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(sys.executable)
    locked = parse_lock([ROOT / "requirements.txt", ROOT / "requirements-dev.txt"])
    installed = freeze(python)

    missing = {name: ver for name, ver in locked.items() if installed.get(name) != ver}
    extra = {name: ver for name, ver in installed.items() if name not in locked}

    print(f"lock={len(locked)} installed={len(installed)}")
    if missing:
        print("锁定的包与已安装不一致：", missing)
    if extra:
        print("已安装但未锁定：", extra)
    if missing or extra:
        return 1
    print("lock 与 pip freeze 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
