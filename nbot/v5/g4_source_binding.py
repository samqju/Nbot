"""Read-only point-in-time G1/G2/G3 witness binder for OFFLINE G4 research.

The binder proves internal snapshot identity, clocks, 100-direction denominator,
source-witness membership and feature digest from an external SQLite COPY.
Local WSS/REST witness data are NOT exchange-signed; this function cannot prove
historical fills, after-cost outcomes, archive authenticity or trading viability.

No schema modifications, network access, financial authority or synthetic labels.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Mapping

from nbot.v5.observation_contract import INTERVAL_MS, PATTERN_IDS


@dataclass(frozen=True)
class BindingAudit:
    state: str                      # SOURCE_BOUND / HOLD
    reasons: tuple[str, ...]
    event_open_ms: int
    symbol: str
    side: str
    candidate_id: str | None = None
    candidate_source_sha256: str | None = None
    g2_witness_sha256: str | None = None
    g3_context_sha256: str | None = None
    g3_feature_sha256: str | None = None
    eligible_population: int = 0
    candidate_population: int = 0
    source_grade: str = "LOCAL_WSS_REST_WITNESS_NOT_EXCHANGE_SIGNED"
    scored_outcomes: int = 0
    model_training_authority: str = "NONE"
    recommendation_authority: str = "NONE"
    order_authority: str = "NONE"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf8")).hexdigest()


def _hold(event: int, symbol: str, side: str, issues: set[str]) -> BindingAudit:
    return BindingAudit("HOLD", tuple(sorted(issues)), event, symbol, side)


def bind_from_frozen_observation_copy(*, db_path: str | Path, event_open_ms: int,
                                      symbol: str, side: str) -> BindingAudit:
    """Strict evidence preflight on a *copy*; never attach/modify operational DB.

    A SOURCE_BOUND row is only an internally consistent original G1/G2/G3
    candidate. No G4 matured path, quote at EXIT, funding or actual fill exists
    merely because the row has been bound.
    """
    if type(event_open_ms) is not int or event_open_ms < 0 or event_open_ms % INTERVAL_MS:
        raise ValueError("G4_BIND_EVENT_CLOCK_INVALID")
    if type(symbol) is not str or side not in ("LONG", "SHORT"):
        raise ValueError("G4_BIND_IDENTITY_INVALID")
    if not symbol.isalnum() or symbol.upper() != symbol:
        raise ValueError("G4_BIND_SYMBOL_INVALID")
    path = Path(db_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("G4_BIND_SNAPSHOT_NOT_REGULAR_FILE")
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro",
                             uri=True, timeout=8) as db:
            return _check(db, event_open_ms, symbol, side)
    except (sqlite3.Error, TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return _hold(event_open_ms, symbol, side, {"G4_BIND_SQLITE_OR_EVIDENCE_INVALID"})


def _check(db: sqlite3.Connection, event: int, symbol: str, side: str) -> BindingAudit:
    issues: set[str] = set()
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        return _hold(event, symbol, side, {"G4_BIND_SQLITE_INTEGRITY_FAILED"})
    cohort = db.execute(
        "SELECT cohort_digest,symbols_json FROM g1f_universe_snapshots"
    ).fetchall()
    if len(cohort) != 1:
        return _hold(event, symbol, side, {"G4_BIND_UNIQUE_COHORT_MISSING"})
    cohort_sha, selected_raw = cohort[0]
    selected = json.loads(selected_raw)
    if (not isinstance(selected, list) or len(selected) != 50
            or len(set(selected)) != 50 or selected != sorted(selected)
            or "BTCUSDT" not in selected or symbol not in selected):
        return _hold(event, symbol, side, {"G4_BIND_FROZEN_TOP50_MISMATCH"})
    if _canonical(selected) != selected_raw:
        issues.add("G4_BIND_COHORT_RECORD_NOT_CANONICAL")
    if _sha(_canonical({
        "selection_version": "USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
        "symbols": selected,
    })) != cohort_sha:
        issues.add("G4_BIND_COHORT_DIGEST_MISMATCH")
    original = db.execute(
        "SELECT payload_json,payload_sha FROM g2_cohort_witness "
        "WHERE cohort_digest=?", (cohort_sha,)
    ).fetchone()
    if original is None or _sha(original[0]) != original[1]:
        issues.add("G4_BIND_ORIGINAL_G2_COHORT_MISSING")
    else:
        co = json.loads(original[0])
        if (co.get("cohort_digest") != cohort_sha
                or sorted(co.get("ranked_selected", [])) != selected):
            issues.add("G4_BIND_ORIGINAL_G2_SELECTION_MISMATCH")
    manifests = db.execute(
        "SELECT cohort_digest,committed_ms,state,verification_json,verification_sha "
        "FROM g1f_event_manifest WHERE event_open_ms=?", (event,)
    ).fetchall()
    if len(manifests) != 1:
        return _hold(event, symbol, side, {"G4_BIND_ORIGINAL_EVENT_NOT_PRESENT"})
    cohort_id, committed, state, manifest_raw, manifest_sha = manifests[0]
    if _sha(manifest_raw) != manifest_sha or cohort_id != cohort_sha or state != "OBSERVE_ONLY":
        issues.add("G4_BIND_EVENT_MANIFEST_INVALID")
    if type(committed) is not int or not event + INTERVAL_MS <= committed < event + 2*INTERVAL_MS:
        issues.add("G4_BIND_DECISION_CLOCK_INVALID")
    # Independently verify all 100 candidate IDs and source JSON digests,
    # not merely the requested side (otherwise a truncated denominator passes).
    candidates = db.execute(
        "SELECT decision_id,symbol,direction,status,record_json,record_sha "
        "FROM g1f_candidate_events WHERE event_open_ms=?", (event,)
    ).fetchall()
    identities = set()
    requested = None
    for did, sym, direction, rowstatus, raw, digest in candidates:
        identity = (sym, direction)
        if (identity in identities or sym not in selected or direction not in ("LONG", "SHORT")):
            issues.add("G4_BIND_DIRECTIONAL_DENOMINATOR_INVALID")
        identities.add(identity)
        if _sha(raw) != digest:
            issues.add("G4_BIND_CANDIDATE_DIGEST_MISMATCH")
        payload = json.loads(raw)
        if (payload.get("decision_id") != did or payload.get("symbol") != sym
                or payload.get("side") != direction or payload.get("status") != rowstatus
                or payload.get("event_open_ms") != event
                or payload.get("universe_digest") is None
                or payload.get("order_authority") != "NONE"):
            issues.add("G4_BIND_CANDIDATE_IDENTITY_INVALID")
        if identity == (symbol, side):
            requested = (did, rowstatus, payload, digest)
    if identities != {(s, d) for s in selected for d in ("LONG", "SHORT")}:
        issues.add("G4_BIND_DIRECTIONAL_DENOMINATOR_INVALID")
    if requested is None:
        issues.add("G4_BIND_SELECTED_SIDE_MISSING")
    elif (requested[1] != "OBSERVED"
          or requested[2].get("reason_codes")
          or set(requested[2].get("patterns", {})) != set(PATTERN_IDS)
          or "UNAVAILABLE" in requested[2].get("patterns", {}).values()):
        issues.add("G4_BIND_SELECTED_SIDE_NOT_QUALIFIED")

    # Every G2 coin's local at-decision receipt must still be present and
    # content-consistent; it proves *entry source*, NOT exit execution.
    witnesses = db.execute(
        "SELECT symbol,asof_ms,payload_json,payload_sha "
        "FROM g2_quote_witness WHERE event_open_ms=?", (event,)
    ).fetchall()
    if len(witnesses) != len(selected) or {x[0] for x in witnesses} != set(selected):
        issues.add("G4_BIND_G2_FULL_WITNESS_DENOMINATOR_MISSING")
    chosen_witness_sha = None
    for sym, asof, raw, digest in witnesses:
        if _sha(raw) != digest:
            issues.add("G4_BIND_G2_WITNESS_DIGEST_MISMATCH")
            continue
        row = json.loads(raw)
        if (row.get("event_open_ms") != event or row.get("symbol") != sym
                or row.get("cohort_digest") != cohort_sha
                or row.get("asof_ms") != asof or type(asof) is not int
                or asof < event + INTERVAL_MS or asof > committed
                or row.get("status") != "SOURCE_RECORDED"
                or row.get("hold_reasons") or row.get("order_authority") != "NONE"
                or row.get("paper_fill_grade") != "UNVERIFIED"):
            issues.add("G4_BIND_G2_WITNESS_HELD_OR_INVALID")
        source = row.get("source")
        if (not isinstance(source, dict)
                or source.get("market_connected") is not True
                or source.get("public_connected") is not True):
            issues.add("G4_BIND_G2_SOURCE_NOT_CONNECTED")
        else:
            quote_at = source.get("quote_received_ms")
            trade_at = source.get("trade_received_ms")
            if (type(quote_at) is not int or type(trade_at) is not int
                    or not 0 <= asof - quote_at <= 5000
                    or not 0 <= asof - trade_at <= 15000):
                issues.add("G4_BIND_G2_RECEIPT_CLOCK_INVALID")
        if sym == symbol:
            chosen_witness_sha = digest
    g3 = db.execute(
        "SELECT payload_json,payload_sha FROM g3_event_context "
        "WHERE event_open_ms=?", (event,)
    ).fetchall()
    chosen_g3_sha = feature_sha = None
    if len(g3) != 1 or _sha(g3[0][0]) != g3[0][1]:
        issues.add("G4_BIND_G3_CONTEXT_DIGEST_MISSING")
    else:
        chosen_g3_sha = g3[0][1]
        g = json.loads(g3[0][0])
        feat = g.get("feature_evidence")
        if (g.get("event_open_ms") != event
                or g.get("valid_from_ms") != committed
                or g.get("status") != "OBSERVE_ONLY"
                or g.get("order_authority") != "NONE"
                or g.get("recommendation_authority") != "NONE"
                or not isinstance(feat, dict)):
            issues.add("G4_BIND_G3_CONTEXT_UNQUALIFIED")
        else:
            feature_sha = feat.get("feature_sha256")
            without = {k: v for k, v in feat.items() if k != "feature_sha256"}
            if (_sha(_canonical(without)) != feature_sha
                    or feat.get("event_open_ms") != event
                    or feat.get("valid_from_ms") != committed
                    or feat.get("candidate_cohort_size") != 50
                    or feat.get("unknown_coin_count") != 0
                    or feat.get("btc", {}).get("valid") is not True
                    or feat.get("coins", {}).get(symbol, {}).get("state") != "AVAILABLE"):
                issues.add("G4_BIND_G3_FEATURE_NOT_REPRODUCIBLE")
    if issues:
        return _hold(event, symbol, side, issues)
    return BindingAudit(
        "SOURCE_BOUND", (), event, symbol, side,
        candidate_id=requested[0],
        candidate_source_sha256=requested[3],
        g2_witness_sha256=chosen_witness_sha,
        g3_context_sha256=chosen_g3_sha,
        g3_feature_sha256=feature_sha,
        eligible_population=50,
        candidate_population=100,
    )


def main():
    """Read-only scientific inspection of a frozen original G1/G2/G3 copy."""
    import argparse
    from dataclasses import asdict
    p=argparse.ArgumentParser(description="Read-only G4 candidate original-source binding")
    p.add_argument("--db",required=True)
    p.add_argument("--event",required=True,type=int)
    p.add_argument("--symbol",required=True)
    p.add_argument("--side",choices=("LONG","SHORT"),required=True)
    args=p.parse_args()
    try:
        audit=bind_from_frozen_observation_copy(
            db_path=args.db,event_open_ms=args.event,
            symbol=args.symbol,side=args.side)
        print(json.dumps(asdict(audit),sort_keys=True))
        return 0 if audit.state=="SOURCE_BOUND" else 2
    except (OSError,ValueError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "scored_outcomes":0,"order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
