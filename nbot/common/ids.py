from __future__ import annotations

import re
import uuid

_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,31}-[0-9a-f]{32}$")


def new_id(prefix: str) -> str:
    normalized = str(prefix).strip().upper().replace("-", "_")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,31}", normalized):
        raise ValueError("NBOT_ID_PREFIX_INVALID")
    return f"{normalized}-{uuid.uuid4().hex}"


def is_valid_id(value: str) -> bool:
    return bool(_ID_RE.fullmatch(str(value)))
