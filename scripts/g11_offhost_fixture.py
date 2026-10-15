"""G11 original-shaped SYNTHETIC cross-VPS custody probe.

On Observation: make /tmp/isolated-dir (private, no services).
Copy sealed/ to Execution via approved SSH keys.
On Execution: verify /tmp/isolated-dir/sealed by independent SHA replay.
This does NOT qualify actual original Binance market evidence.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_v5_1_g2 import manifest, END_OPEN, END_DECISION
from test_v5_1_g4_source import frame, NOW
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.deep_segments import DeepSegmentRecorder
from nbot_v5_1.archive_custody import seal_archive, verify_archive

CYCLES = 8


def symbols():
    broad = manifest()
    book = ObservationBook(broad)
    g3 = explore_event(book, FiveMinuteEvent(END_OPEN,END_DECISION),
                       capacity_slots=0)
    deep = choose_deep(broad,g3)
    if len(deep.symbols) != 20 or "BTCUSDT" not in deep.symbols:
        raise RuntimeError("G11_ARCHIVE_WRONG_DEEP_COHORT")
    return deep.symbols


def fingerprint(folder):
    d = sha256()
    entries = 0
    size = 0
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("G11_OFFHOST_PATH_UNSAFE")
        raw = p.read_bytes()
        d.update(p.name.encode() + b"\0" + sha256(raw).digest())
        entries += 1
        size += len(raw)
    return d.hexdigest(),entries,size


def run(operation: str, destination: Path):
    if (not destination.is_absolute() or destination.is_symlink()
            or str(destination).startswith("/home/")):
        raise RuntimeError("G11_ONLY_PRIVATE_TEMP_LOCATION")
    deep = symbols()
    if operation == "produce":
        destination.mkdir(mode=0o700)
        source = destination / "raw"
        sealed = destination / "sealed"
        source.mkdir(mode=0o700)
        sealed.mkdir(mode=0o700)
        rec = DeepSegmentRecorder(source,symbols=deep)
        for i in range(CYCLES):
            at=NOW+i*2000
            for symbol in deep:
                for kind in ("TRADE","QUOTE","MARK"):
                    result=rec.append(kind=kind,raw=frame(
                        kind,symbol=symbol,id=i+8,received=at),
                        received_at_ms=at,epoch=1)
                    if result.state == "HOLD":
                        raise RuntimeError("G11_SOURCE_SYNTHETIC_INPUT_HELD")
            rec.flush()
        seal_archive(source=source,destination=sealed,symbols=deep)
    elif operation != "verify":
        raise RuntimeError("G11_UNKNOWN_OPERATION")
    sealed = destination / "sealed"
    verified = verify_archive(root=sealed,symbols=deep)
    if (verified["frames"] != CYCLES*20*3
            or verified["segments"] != CYCLES):
        raise RuntimeError("G11_CROSSHOST_SOURCE_REPLAY_MISMATCH")
    digest, files, bytes_used = fingerprint(sealed)
    output = {"schema":"NBOT_V5_1_G11_CROSS_VPS_SYNTHETIC_V1",
              "mode":operation,"source_grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
              "archive_sha256":digest,"archive_file_count":files,
              "sealed_bytes":bytes_used,
              "frames":verified["frames"],"segments":verified["segments"],
              "markets":len(deep),"order_authority":"NONE",
              "actual_original_offhost_qualified":False,
              "passed":True}
    print(json.dumps(output,sort_keys=True),flush=True)


if __name__ == "__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: g11_offhost_fixture.py produce|verify /tmp/NAME")
    run(sys.argv[1],Path(sys.argv[2]))
