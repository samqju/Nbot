"""V5 G4 pure offline Binance aggTrade PRICE-PATH replay; never a fill.

Consumes independent frozen candidate/policy plus original archive-like raw rows.
No REST, WSS, SQLite, execution, fee inference, private keys, or training.
Even a complete replay yields gross *path* R, NOT executable net R.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re
from typing import Mapping, Sequence

PATH_CONTRACT_VERSION = "NBOT_V5_G4_AGG_PATH_V1"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
SIDES = ("LONG", "SHORT")


@dataclass(frozen=True)
class PathReplay:
    state: str                 # HOLD / PENDING / PATH_REPLAYED
    reasons: tuple[str, ...]
    candidate_id: str
    archive_sha256: str | None
    raw_rows_sha256: str | None
    path_start_trade_id: int | None = None
    path_end_trade_id: int | None = None
    path_trade_count: int = 0
    exit_reason: str | None = None
    exit_at_ms: int | None = None
    exit_trade_price: str | None = None
    gross_path_r: str | None = None
    net_r: None = None          # Explicit: G4 price replay has NO executable costs
    scored_outcomes: int = 0
    financial_authority: str = "NONE"
    contract_version: str = PATH_CONTRACT_VERSION


def _hex(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def _clock(value: object) -> bool:
    return type(value) is int and value >= 0


def _positive(v: object) -> Decimal | None:
    # Never silently accept floats as evidence of original quoted precision.
    if not isinstance(v, str) or len(v) > 80:
        return None
    try:
        d = Decimal(v)
        return d if d.is_finite() and d > 0 else None
    except InvalidOperation:
        return None


def _digest(rows: Sequence) -> str:
    return sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def replay_aggtrade_price_path(
    *, candidate: Mapping, policy: Mapping, original_rows: Sequence[Mapping],
    source_manifest: Mapping, audit_at_ms: int,
) -> PathReplay:
    """Fail closed on future policy, insufficient horizon or aggTrade ID gap.

    Raw record format is Binance public aggTrades {a,f,l,T,p,q,m}.
    The manifest must include an independently captured archive blob SHA and
    its canonical-record SHA. This function can verify only supplied bytes/IDs;
    an independent source-witness audit is still mandatory before real labels.
    """
    if not isinstance(candidate, Mapping) or not isinstance(policy, Mapping):
        raise ValueError("G4_PATH_CONTRACT_INVALID")
    did = candidate.get("decision_id")
    if not _hex(did):
        raise ValueError("G4_PATH_DECISION_ID_INVALID")
    if not _clock(audit_at_ms):
        raise ValueError("G4_PATH_AUDIT_TIME_INVALID")

    reasons: list[str] = []
    side = candidate.get("side")
    decision = candidate.get("decision_at_ms")
    horizon = policy.get("horizon_ms")
    declared = policy.get("declared_at_ms")
    if side not in SIDES or candidate.get("status") != "OBSERVED":
        reasons.append("CANDIDATE_NOT_QUALIFIED")
    if (not _clock(decision) or not _clock(horizon) or horizon <= 0
            or not _clock(declared) or declared > decision):
        reasons.append("POLICY_OR_DECISION_CLOCK_INVALID")
    if not _hex(policy.get("policy_sha256")):
        reasons.append("POLICY_SHA_UNFROZEN")
    entry = _positive(policy.get("entry_reference_price"))
    stop = _positive(policy.get("stop_price"))
    target = _positive(policy.get("target_price"))
    if entry is None or stop is None or target is None:
        reasons.append("ENTRY_STOP_TARGET_INVALID")
    elif side == "LONG" and not (stop < entry < target):
        reasons.append("LONG_RISK_GEOMETRY_INVALID")
    elif side == "SHORT" and not (target < entry < stop):
        reasons.append("SHORT_RISK_GEOMETRY_INVALID")
    if reasons:
        return PathReplay("HOLD",tuple(sorted(set(reasons))),did,None,None)
    maturity = decision + horizon
    if audit_at_ms < maturity:
        return PathReplay("PENDING",("HORIZON_NOT_MATURE",),did,None,None)
    archive_sha = source_manifest.get("archive_sha256") if isinstance(source_manifest,Mapping) else None
    rows_sha = source_manifest.get("rows_sha256") if isinstance(source_manifest,Mapping) else None
    if not _hex(archive_sha) or not _hex(rows_sha):
        reasons.append("ORIGINAL_ARCHIVE_MANIFEST_MISSING")
    if not isinstance(original_rows,(tuple,list)) or len(original_rows)<2:
        reasons.append("ORIGINAL_TRADE_ROWS_MISSING")
    if reasons:
        return PathReplay("HOLD",tuple(sorted(set(reasons))),did,archive_sha,rows_sha)
    try:
        if _digest(original_rows)!=rows_sha:
            reasons.append("ORIGINAL_ROWS_SHA_MISMATCH")
    except (TypeError, ValueError, OverflowError):
        reasons.append("ORIGINAL_ROWS_NOT_CANONICAL")
    if source_manifest.get("source_grade")!="ORIGINAL_BINANCE_PUBLIC_AGGTRADES":
        reasons.append("ORIGINAL_SOURCE_GRADE_UNVERIFIED")
    if source_manifest.get("symbol")!=candidate.get("symbol"):
        reasons.append("ORIGINAL_SYMBOL_MISMATCH")
    # Archive bytes and original download provenance must be audited separately.
    if source_manifest.get("original_archive_verified") is not True:
        reasons.append("ORIGINAL_ARCHIVE_AUTHENTICITY_UNVERIFIED")
    if reasons:
        return PathReplay("HOLD",tuple(sorted(set(reasons))),did,archive_sha,rows_sha)
    previous_agg=previous_last=None
    parsed=[]
    for raw in original_rows:
        if not isinstance(raw,Mapping):
            reasons.append("ORIGINAL_ROW_SHAPE_INVALID")
            break
        agg,first,last,at=(raw.get(k) for k in ("a","f","l","T"))
        price,qty=_positive(raw.get("p")),_positive(raw.get("q"))
        if (any(type(x) is not int or x<0 for x in (agg,first,last,at))
                or first>last or price is None or qty is None
                or type(raw.get("m")) is not bool):
            reasons.append("ORIGINAL_ROW_INVALID")
            break
        if previous_agg is not None:
            if agg!=previous_agg+1 or first!=previous_last+1:
                reasons.append("AGGTRADE_SEQUENCE_GAP_OR_REORDER")
            if at<parsed[-1][0]:
                reasons.append("TRADE_TIME_REORDER")
        parsed.append((at,price,agg,first,last))
        previous_agg,previous_last=agg,last
    if not parsed:
        reasons.append("ORIGINAL_ROW_INVALID")
    else:
        if parsed[0][0]>decision or parsed[-1][0]<maturity:
            reasons.append("ORIGINAL_PATH_BOUNDS_INCOMPLETE")
        if source_manifest.get("first_agg_id")!=parsed[0][2] or source_manifest.get("last_agg_id")!=parsed[-1][2]:
            reasons.append("ORIGINAL_AGG_ID_MANIFEST_MISMATCH")
    if reasons:
        return PathReplay("HOLD",tuple(sorted(set(reasons))),did,archive_sha,rows_sha)

    direction=Decimal(1) if side=="LONG" else Decimal(-1)
    risk=abs(entry-stop)
    selected=None
    last=None
    for at,price,agg,first,last_id in parsed:
        if at<decision:
            continue
        if at>maturity:
            break
        last=(at,price)
        if direction*(price-entry)<=-risk:
            selected=("STOP_PRICE_CROSSED",at,price)
            break
        if direction*(price-target)>=0:
            selected=("TARGET_PRICE_CROSSED",at,price)
            break
    if selected is None and last is not None:
        selected=("HORIZON_LAST_TRADE",*last)
    if selected is None:
        return PathReplay("HOLD",("NO_TRADE_ON_OR_AFTER_DECISION",),
                          did,archive_sha,rows_sha)
    why,when,exit_price=selected
    with localcontext() as ctx:
        ctx.prec=34
        gross=direction*(exit_price-entry)/risk
    return PathReplay(
        state="PATH_REPLAYED",reasons=(),candidate_id=did,
        archive_sha256=archive_sha,raw_rows_sha256=rows_sha,
        path_start_trade_id=parsed[0][2],path_end_trade_id=parsed[-1][2],
        path_trade_count=len(parsed),exit_reason=why,exit_at_ms=when,
        exit_trade_price=str(exit_price),gross_path_r=str(gross),
    )
