from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


def parse_env_file(path: Path | str) -> dict[str, str]:
    values: dict[str, str] = {}
    source = Path(path)
    if not source.exists():
        return values
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"NBOT_ENV_LINE_INVALID:{source}:{line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or any(ch.isspace() for ch in key):
            raise ValueError(f"NBOT_ENV_KEY_INVALID:{source}:{line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def merged_environment(*files: Path | str, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in files:
        merged.update(parse_env_file(path))
    merged.update(dict(os.environ if environ is None else environ))
    return merged
