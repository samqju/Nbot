"""Point-in-time, source-gated, bounded-memory Binance USD-M 5m archive reader.

Archive-directory presence does NOT certify listing dates or executable orderbook depth.
"""
from __future__ import annotations
import csv
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime, timezone
import re

BAR_MS = 300_000
FILE = re.compile(r"(?P<symbol>[A-Z0-9]+USDT)-5m-(?P<month>\d{4}-\d{2})\.(?:zip|csv)$")

@dataclass(frozen=True)
class Bar:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float

@dataclass(frozen=True)
class Contract:
    symbol: str
    from_ms: int
    to_ms: int
    evidence_sha256: str

    def eligible(self, decision_ms: int) -> bool:
        return self.from_ms <= decision_ms < self.to_ms

def utc_ms(s: str) -> int:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset().total_seconds() != 0:
        raise ValueError("REQUIRE_EXPLICIT_UTC")
    return int(d.timestamp() * 1000)

def contract_registry(path: Path) -> dict[str, Contract]:
    """Mandatory independently researched historical registry; no inferred eligibility."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("EMPTY_HISTORICAL_REGISTRY")
    out = {}
    for row in rows:
        symbol = row["symbol"].strip().upper()
        evidence = row["evidence_sha256"].strip().lower()
        if (not re.fullmatch(r"[A-Z0-9]+USDT", symbol)
            or not re.fullmatch(r"[a-f0-9]{64}", evidence)):
            raise ValueError("INVALID_REGISTRY_ID_OR_SOURCE_DIGEST")
        a, b = int(row["from_ms"]), int(row["to_ms"])
        if a >= b or symbol in out:
            raise ValueError("INVALID_REGISTRY_RANGE_OR_DUPLICATE")
        if row.get("source_grade", "").strip() != "SOURCE_ATTESTED":
            raise ValueError("UNATTESTED_HISTORICAL_ELIGIBILITY")
        out[symbol] = Contract(symbol, a, b, evidence)
    return out

def discover(root: Path, months: set[str]) -> dict[str, list[Path]]:
    if not root.exists():
        raise FileNotFoundError(root)
    grouped: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        m = FILE.fullmatch(path.name)
        if m and m["month"] in months:
            grouped.setdefault(m["symbol"], []).append(path)
    for paths in grouped.values():
        paths.sort(key=lambda p: p.name)
        if len({FILE.fullmatch(p.name)["month"] for p in paths}) != len(paths):
            raise ValueError("DUPLICATE_SYMBOL_MONTH_ARCHIVE")
    return grouped

def _time(v: str) -> int:
    n = int(v)
    # Binance archive timestamps in newer archives may be in microseconds.
    if n >= 10**15:
        n //= 1000
    return n

def load_bars(paths: list[Path], start_ms: int, end_ms: int) -> tuple[list[Bar], dict]:
    if not paths:
        return [], {}
    allbars = []
    digests = {}
    for path in sorted(paths):
        digests[str(path)] = sha256(path.read_bytes()).hexdigest()
        if path.suffix == ".zip":
            with ZipFile(path) as z:
                names = [n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")]
                if len(names) != 1:
                    raise ValueError("ARCHIVE_MUST_CONTAIN_EXACTLY_ONE_CSV")
                with z.open(names[0]) as stream:
                    import io
                    rows = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
                    allbars.extend(_parse(rows, start_ms, end_ms))
        else:
            with path.open(newline="", encoding="utf-8-sig") as f:
                allbars.extend(_parse(csv.reader(f), start_ms, end_ms))
    allbars.sort(key=lambda b: b.t)
    previous = None
    for b in allbars:
        if previous is not None and b.t <= previous:
            raise ValueError("DUPLICATED_OR_UNSORTED_BAR")
        previous = b.t
    return allbars, digests

def _parse(rows, start_ms: int, end_ms: int):
    ret = []
    for r in rows:
        if not r or not r[0].strip().isdigit():
            if r and r[0].strip().lower() not in ("open_time", "open time"):
                raise ValueError("INVALID_CANDLE_ROW")
            continue
        if len(r) < 6:
            raise ValueError("INSUFFICIENT_CANDLE_COLUMNS")
        t = _time(r[0])
        if not start_ms <= t < end_ms:
            continue
        o, h, l, c, v = map(float, r[1:6])
        import math
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0
            or v < 0 or h < max(o,c,l) or l > min(o,c,h) or t % BAR_MS):
            raise ValueError("INVALID_OHLCV")
        ret.append(Bar(t,o,h,l,c,v))
    return ret
