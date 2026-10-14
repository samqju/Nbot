"""Offline G4 archive replay bridge on bounded RAM-backed temporary SQLite.

The LIVE collector never inserts raw ticks into SQLite. A separate explicit
offline read-only analysis can materialize a verified, capped vault view into
/dev/shm, recompute old independent G4 audits, and destroy the view on exit.

Not a producer of exchange-signed data, economic labels or model eligibility.
"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from nbot.v5.g4_segmented_source import read_segments
from nbot.v5.g4_forward_vault import ForwardSourceVault
from nbot.v5.g4_forward_independent_audit import audit_forward_source_copy


@contextmanager
def verified_ram_vault(segment_dir, *, symbols, ram_parent="/dev/shm",
                       max_frames=100000, max_view_mib=128):
    """Return (ephemeral SQLite pathname, independent source audit) only.

    Never target the operational G1/G4 original database. Full compressed
    archive must verify BEFORE replay rows can qualify as source receipts.
    Holds stay holds; restart gaps are reproduced as ABRUPT_RESTART_HOLD.
    """
    if (type(max_frames) is not int or not 1<=max_frames<=100000
            or type(max_view_mib) is not int or not 1<=max_view_mib<=128):
        raise ValueError("G4_BRIDGE_RESOURCE_BOUNDS_INVALID")
    parent=Path(ram_parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("G4_BRIDGE_RAM_PARENT_INVALID")
    frozen=tuple(sorted(symbols))
    # Parsing and proving the source happens before any sqlite DB is opened.
    # Do not materialize part of a corrupt compressed chain as accepted.
    frame_count=bytes_seen=0
    for rec,raw in read_segments(segment_dir,frozen):
        if rec["kind"]=="FRAME":
            frame_count+=1
            bytes_seen+=len(raw)
            if (bytes_seen>max_view_mib*1024*1024
                    or frame_count>max_frames):
                raise ValueError("G4_BRIDGE_FRAME_OR_BYTES_CAP_HOLD")
    with TemporaryDirectory(prefix="nbot-g4-original-proof-",dir=str(parent)) as temp:
        target=Path(temp)/"g4_raw_source.sqlite"
        # The view is disposable RAM/tmpfs and is never re-used for capture.
        with sqlite3.connect(target) as db:
            db.execute("PRAGMA journal_mode=MEMORY")
            db.execute("PRAGMA synchronous=OFF")
            vault=ForwardSourceVault(db,symbols=frozen,batch_frames=64)
            abrupt_expected=0
            for rec,raw in read_segments(segment_dir,frozen):
                route,at,kind=rec["route"],rec["at_ms"],rec["kind"]
                if kind=="ABRUPT_RESTART_HOLD":
                    abrupt_expected+=1
                    continue
                if kind=="OPEN":
                    result=vault.connect(route=route,at_ms=at)
                elif kind=="CLOSED":
                    result=vault.disconnect(route=route,at_ms=at)
                else:
                    result=vault.ingest(route=route,at_ms=at,raw=raw)
                    if result.evidence_state!=rec["state"]:
                        raise ValueError("G4_BRIDGE_FRAME_CLASSIFICATION_CHANGED")
                if target.stat().st_size>max_view_mib*1024*1024:
                    raise ValueError("G4_BRIDGE_TEMP_DB_CAP_HOLD")
            vault.flush()
            audit=vault.audit()
            if audit["counts"]["ABRUPT_RESTART_HOLD"]!=abrupt_expected:
                raise ValueError("G4_BRIDGE_RESTART_EVIDENCE_CHANGED")
        independent=audit_forward_source_copy(db_path=target)
        if independent["integrity_audit"]!="PASS":
            raise ValueError("G4_BRIDGE_INDEPENDENT_REPLAY_HOLD")
        # Deliberately no G4 scientific acceptance, net outcome or fill.
        yield target, {
            "source_integrity":"PASS",
            "bridge":"RAM_ONLY_OFFLINE",
            "frames_replayed":audit["counts"]["SOURCE_RECORDED"]+audit["counts"]["HOLD"],
            "abrupt_restart_holds":abrupt_expected,
            "original_archive_integrity":"INDEPENDENT_SEGMENT_HASH_REPLAY",
            "original_vault_audit":independent,
            "score_authority":"NONE",
            "order_authority":"NONE"}
