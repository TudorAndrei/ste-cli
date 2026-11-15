#!/usr/bin/env bash
# Build a Python wheel and source archive with checksums.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -n "${1:-}" ]; then
  uv run python - "$1" <<'PY'
import sys
import tomllib
from pathlib import Path
version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
if sys.argv[1].removeprefix("v") != version:
    raise SystemExit("The tag must agree with the version in pyproject.toml")
PY
fi
uv build --clear
uv run python - <<'PY'
import hashlib
from pathlib import Path
files = sorted(p for p in Path("dist").iterdir() if p.suffix == ".whl" or p.name.endswith(".tar.gz"))
with Path("dist/checksums.txt").open("w") as stream:
    for path in files:
        stream.write(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
PY
