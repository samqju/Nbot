"""Independent READ-ONLY G4 raw forward-source integrity and coverage audit.

Never initializes SQLite, mutates any original live or G4 database, creates
economic labels or blesses collected frames as exchange fills. It rechecks
producer SHA chain and source frame contracts from immutable receipt bytes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from nbot.v5.g4_forward_stream_contract import verify_frame

VERSION="NBOT_V5_G4_FORWARD_INDEPENDENT_REPLAY_AUDIT_V1"
VAULT_VERSION="NBOT_V5_G4_FORWARD_RAW_SOURCE_V1"
ROUTES=frozenset(("market_aggtrade","public_bookticker","market_markprice"))
_ZERO="0"*64


def _json(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)


def _hash(v):
    return hashlib.sha256(_json(v).encode()).hexdigest()


def audit_forward_source_copy(*,db_path:str|Path) -> dict:
    path=Path(db_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("G4_AUDIT_SOURCE_MISSING_OR_SYMLINK")
    try:
        with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",
                             uri=True,timeout=10) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("G4_AUDIT_SQLITE_INTEGRITY_INVALID")
            cohorts=db.execute(
                "SELECT cohort_sha,symbols_json,contract "
                "FROM g4_forward_cohort").fetchall()
            if len(cohorts)!=1 or cohorts[0][2]!=VAULT_VERSION:
                raise ValueError("G4_AUDIT_FROZEN_COHORT_MISSING")
            cohort_sha,raw_symbols,version=cohorts[0]
            syms=json.loads(raw_symbols)
            if (not isinstance(syms,list) or not 1<=len(syms)<=50
                    or syms!=sorted(set(syms)) or "BTCUSDT" not in syms
                    or raw_symbols!=_json(syms) or
                    cohort_sha!=_hash({"symbols":syms,"version":VAULT_VERSION})):
                raise ValueError("G4_AUDIT_COHORT_CHANGED")
            count=0
            sha=_ZERO
            last_by_route={}
            opens={}
            sources={r:set() for r in ROUTES}
            holds=Counter()
            frame_counts=Counter()
            accepted=0
            held=0
            disconnects=0
            restarts=0
            for item in db.execute(
                "SELECT seq,route,epoch,kind,at_ms,symbol,evidence_state,"
                "reasons_json,raw_sha256,raw_frame,prior_sha256,chain_sha256 "
                "FROM g4_forward_receipts ORDER BY seq"):
                (seq,route,epoch,kind,at,symbol,state,reasons,raw_sha,
                 raw,previous,chain)=item
                count+=1
                if (seq!=count or route not in ROUTES or
                        type(epoch) is not int or epoch<1 or
                        type(at) is not int or at<1 or
                        not isinstance(raw,bytes) or
                        previous!=sha or hashlib.sha256(raw).hexdigest()!=raw_sha):
                    raise ValueError("G4_AUDIT_RAW_OR_SEQUENCE_TAMPERED")
                try:
                    reasons_decoded=json.loads(reasons)
                except (ValueError,TypeError):
                    raise ValueError("G4_AUDIT_REASONS_INVALID")
                if (not isinstance(reasons_decoded,list) or
                        reasons!=_json(reasons_decoded)):
                    raise ValueError("G4_AUDIT_REASONS_NOT_CANONICAL")
                fields={"contract":VAULT_VERSION,"route":route,"epoch":epoch,
                        "kind":kind,"at_ms":at,"symbol":symbol,"state":state,
                        "reasons_json":reasons,"raw_sha":raw_sha,"prior_sha":previous}
                if _hash(fields)!=chain:
                    raise ValueError("G4_AUDIT_CHAIN_TAMPERED")
                sha=chain
                previous_route=last_by_route.get(route)
                if previous_route is not None and at<previous_route[2]:
                    raise ValueError("G4_AUDIT_ROUTE_CLOCK_REWIND")
                if kind=="OPEN":
                    if (symbol is not None or raw or epoch!=(
                            previous_route[0]+1 if previous_route is not None else 1)):
                        raise ValueError("G4_AUDIT_EPOCH_INVALID")
                    opens[route]=epoch
                elif kind=="ABRUPT_RESTART_HOLD":
                    restarts+=1
                    if (previous_route is None or epoch!=previous_route[0]
                            or previous_route[1] not in ("OPEN","FRAME")
                            or state!="HOLD" or raw):
                        raise ValueError("G4_AUDIT_RESTART_MARKER_INVALID")
                elif kind=="CLOSED":
                    disconnects+=1
                    if (previous_route is None or epoch!=previous_route[0]
                            or previous_route[1] not in ("OPEN","FRAME")
                            or state!="HOLD" or raw):
                        raise ValueError("G4_AUDIT_DISCONNECT_MARKER_INVALID")
                elif kind=="FRAME":
                    if (previous_route is None or epoch!=previous_route[0]
                            or previous_route[1] not in ("OPEN","FRAME")
                            or not raw):
                        raise ValueError("G4_AUDIT_FRAME_EPOCH_INVALID")
                    frame_counts[route]+=1
                    if state=="SOURCE_RECORDED":
                        if reasons_decoded or symbol not in syms:
                            raise ValueError("G4_AUDIT_ACCEPTED_SOURCE_INVALID")
                        proof=verify_frame(route=route,raw=raw,
                                           received_at_ms=at,
                                           source_epoch=epoch,
                                           selected_symbols=syms)
                        if proof.state!="SOURCE_RECORDED" or proof.symbol!=symbol:
                            raise ValueError("G4_AUDIT_ACCEPTED_FRAME_NOT_REPRODUCIBLE")
                        sources[route].add(symbol)
                        accepted+=1
                    elif state=="HOLD":
                        held+=1
                        if not reasons_decoded:
                            raise ValueError("G4_AUDIT_HELD_FRAME_WITHOUT_REASON")
                        holds.update(reasons_decoded)
                    else:
                        raise ValueError("G4_AUDIT_FRAME_STATE_INVALID")
                else:
                    raise ValueError("G4_AUDIT_RECEIPT_KIND_INVALID")
                last_by_route[route]=(epoch,kind,at)
            return {
                "integrity_audit":"PASS","audit_contract":VERSION,
                "source_grade":"ORIGINAL_LOCAL_WSS_RECEIPTS_NOT_EXCHANGE_SIGNED",
                "frozen_cohort_size":len(syms),
                "records_verified":count,
                "head_sha256":sha,
                "source_recorded_frames":accepted,
                "held_frames":held,
                "unclean_restart_events":restarts,
                "socket_closed_events":disconnects,
                "frames_per_route":dict(sorted(frame_counts.items())),
                "distinct_recorded_symbols_per_route":{
                    r:len(sources[r]) for r in sorted(ROUTES)},
                "top_hold_reasons":holds.most_common(10),
                "continuous_quote_trade_funding_coverage_proven":False,
                "qualified_economic_outcomes":0,
                "g4_scientific_accepted":False,
                "order_authority":"NONE",
                "training_authority":"NONE",
            }
    except (sqlite3.DatabaseError,TypeError,OverflowError,KeyError) as exc:
        raise ValueError("G4_AUDIT_SOURCE_DB_UNVERIFIABLE") from exc


def main():
    import argparse
    p=argparse.ArgumentParser(description="Independent read-only G4 raw source replay")
    p.add_argument("--db",required=True)
    a=p.parse_args()
    try:
        print(_json(audit_forward_source_copy(db_path=a.db)))
        return 0
    except ValueError as exc:
        print(_json({"integrity_audit":"HOLD","reason":str(exc),
                     "order_authority":"NONE"}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
