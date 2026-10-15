"""V4-inspired O(1)-memory G4 price-path evaluation of original V5 segments.

Consumes every immutable compressed segment through independent SHA-chain
replay, but retains no per-tick raw list and opens no per-frame SQLite table.
This is counterfactual price-only proof: never a fill, cost, training sample
or permission to order. Unknown source epochs/IDs lead to HOLD, not a win.
"""
from __future__ import annotations
import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext

from nbot.v5.g4_segmented_source import read_segments
from nbot.v5.g4_forward_stream_contract import verify_frame
from nbot.v5.g4_price_path import PathReplay, PATH_CONTRACT_VERSION


def _positive(v):
    if type(v) is not str or len(v)>80:
        return None
    try:
        n=Decimal(v)
    except (InvalidOperation,ValueError):
        return None
    return n if n.is_finite() and n>0 else None


def original_segment_price_path(*, segment_dir, candidate, policy,
                                 audit_at_ms):
    """Sequential, constant-space, independently re-verified original path.

    Returns the established V5 PathReplay shape, with financial authority NONE.
    The head SHA is derived only after auditing the *whole* archive. Underlying
    trade ID gaps, held frames, restarts and missing forward coverage all HOLD.
    """
    if (not isinstance(candidate,dict) or not isinstance(policy,dict)
            or type(audit_at_ms) is not int or audit_at_ms<=0):
        raise ValueError("G4_INCREMENTAL_INPUT_INVALID")
    did=candidate.get("decision_id")
    side=candidate.get("side")
    symbol=candidate.get("symbol")
    decision=candidate.get("decision_at_ms")
    horizon=policy.get("horizon_ms")
    declared=policy.get("declared_at_ms")
    if (not isinstance(did,str) or len(did)!=64
            or not all(c in "0123456789abcdef" for c in did)
            or side not in ("LONG","SHORT")
            or type(symbol) is not str or not symbol.endswith("USDT")
            or candidate.get("status")!="OBSERVED"
            or type(decision) is not int or decision<=0
            or type(horizon) is not int or horizon<=0
            or type(declared) is not int or declared>decision
            or type(policy.get("policy_sha256")) is not str
            or len(policy["policy_sha256"])!=64):
        raise ValueError("G4_INCREMENTAL_POLICY_OR_CANDIDATE_INVALID")
    entry=_positive(policy.get("entry_reference_price"))
    stop=_positive(policy.get("stop_price"))
    target=_positive(policy.get("target_price"))
    if (entry is None or stop is None or target is None
            or (side=="LONG" and not stop<entry<target)
            or (side=="SHORT" and not target<entry<stop)):
        return PathReplay("HOLD",("G4_INCREMENTAL_GEOMETRY_INVALID",),did,None,None)

    maturity=decision+horizon
    if audit_at_ms<decision:
        return PathReplay("PENDING",("DECISION_NOT_YET_REACHED",),did,None,None)
    direction=Decimal(1) if side=="LONG" else Decimal(-1)
    risk=abs(entry-stop)

    head=None
    last_epoch=None
    last_symbol=None
    last_pre=None
    first=None
    prior_agg=None
    prior_last=None
    last_time=None
    count=0
    digest=hashlib.sha256()
    selected=None
    last_inside=None
    after_horizon=False
    reasons=set()
    # Track original route continuity and initial symbol cursor.
    active=False
    in_window=False
    source_closed=False

    def record_row(row):
        nonlocal count,first,prior_agg,prior_last,last_time
        encoded=json.dumps(row,sort_keys=True,separators=(",",":"),
                           ensure_ascii=True,allow_nan=False).encode()
        if count==0:
            digest.update(b"[")
            first=row["a"]
        else:
            digest.update(b",")
        digest.update(encoded)
        count+=1
        prior_agg,prior_last,last_time=row["a"],row["l"],row["T"]

    for rec,raw in read_segments(segment_dir):
        head=rec["chain_sha"]
        if rec["route"]!="market_aggtrade":
            continue
        kind=rec["kind"]
        if kind=="OPEN":
            if in_window and selected is None and not after_horizon:
                reasons.add("G4_INCREMENTAL_SOURCE_RESTART")
            active=True
            if last_epoch is not None and rec["epoch"]!=last_epoch:
                last_symbol=None
                last_pre=None
            last_epoch=rec["epoch"]
            continue
        if kind in ("CLOSED","ABRUPT_RESTART_HOLD"):
            if in_window and selected is None and not after_horizon:
                reasons.add("G4_INCREMENTAL_SOURCE_INTERRUPTED")
            active=False
            continue
        if kind!="FRAME" or rec["symbol"]!=symbol:
            continue
        if not active or rec["epoch"]!=last_epoch:
            reasons.add("G4_INCREMENTAL_UNOPENED_EPOCH")
            continue
        if rec["at_ms"]>audit_at_ms:
            continue
        if rec["state"]!="SOURCE_RECORDED":
            if rec["at_ms"]>=decision-5000 and not after_horizon and selected is None:
                reasons.add("G4_INCREMENTAL_HELD_SOURCE_FRAME")
            continue
        previous=last_symbol
        try:
            valid=verify_frame(route="market_aggtrade",raw=raw,
                               received_at_ms=rec["at_ms"],
                               source_epoch=rec["epoch"],
                               selected_symbols=(symbol,),
                               prior_agg_id=(previous["a"] if previous else None),
                               prior_last_trade_id=(previous["l"] if previous else None))
            row=json.loads(raw)["data"]
            row={k:row[k] for k in ("a","f","l","T","p","q","m")}
        except (KeyError,TypeError,ValueError,UnicodeError):
            reasons.add("G4_INCREMENTAL_RAW_FRAME_INVALID")
            continue
        if valid.state!="SOURCE_RECORDED":
            reasons.add("G4_INCREMENTAL_INDEPENDENT_FRAME_MISMATCH")
            continue
        if previous and row["T"]<previous["T"]:
            reasons.add("G4_INCREMENTAL_TRADE_TIME_REORDER")
        last_symbol=row
        at=row["T"]
        if at<decision:
            last_pre=row
            continue
        if at>maturity:
            after_horizon=True
            continue
        if not in_window:
            if last_pre is None or decision-last_pre["T"]>5000:
                reasons.add("G4_INCREMENTAL_PREDECISION_TRADE_MISSING")
            else:
                record_row(last_pre)
            in_window=True
        if (prior_agg is not None and
                (row["a"]!=prior_agg+1 or row["f"]!=prior_last+1)):
            reasons.add("G4_INCREMENTAL_SEQUENCE_GAP")
        record_row(row)
        last_inside=(at,_positive(row["p"]))
        if selected is None:
            price=_positive(row["p"])
            if price is None:
                reasons.add("G4_INCREMENTAL_TRADE_PRICE_INVALID")
            elif direction*(price-entry)<=-risk:
                selected=("STOP_PRICE_CROSSED",at,price)
            elif direction*(price-target)>=0:
                selected=("TARGET_PRICE_CROSSED",at,price)
    # All original segments are independently audited before any result.
    if count:
        digest.update(b"]")
    if head is None or count<2:
        reasons.add("G4_INCREMENTAL_SOURCE_OR_PATH_MISSING")
    if in_window and selected is None and audit_at_ms>=maturity and not after_horizon:
        reasons.add("G4_INCREMENTAL_FULL_HORIZON_NOT_PROVEN")
    if reasons:
        return PathReplay("HOLD",tuple(sorted(reasons)),did,head,
                          digest.hexdigest() if count else None)
    if selected is None and audit_at_ms<maturity:
        return PathReplay("PENDING",("HORIZON_NOT_MATURE",),did,head,
                          digest.hexdigest() if count else None)
    if selected is None:
        if last_time is None:
            return PathReplay("HOLD",("G4_INCREMENTAL_EXIT_MISSING",),did,head,None)
        # A stop/target was never hit. The final trade inside the horizon
        # is the last verified price. Keep only bounded state, never rows.
        selected=("HORIZON_LAST_TRADE",*(last_inside or (None,None)))
    why,when,price=selected
    if price is None:
        return PathReplay("HOLD",("G4_INCREMENTAL_EXIT_INVALID",),did,head,None)
    with localcontext() as ctx:
        ctx.prec=34
        gross=direction*(price-entry)/risk
    return PathReplay(
        state="PATH_REPLAYED",reasons=(),candidate_id=did,
        archive_sha256=head,raw_rows_sha256=digest.hexdigest(),
        path_start_trade_id=first,path_end_trade_id=prior_agg,
        path_trade_count=count,exit_reason=why,exit_at_ms=when,
        exit_trade_price=str(price),gross_path_r=str(gross))
