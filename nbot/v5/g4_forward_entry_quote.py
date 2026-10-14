"""Independent, read-only G4 original forward book quote at candidate decision.

Requires an independently SHA-chained G4 source vault, as-of receipt, correct
WSS socket epoch and real original quote payload. It cannot prove an executed
fill or provide arbitrary future exit-time evidence. Fail closed on gaps.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from nbot.v5.g4_forward_independent_audit import audit_forward_source_copy
from nbot.v5.g4_forward_stream_contract import verify_frame


class IndependentSourceAudit:
    """One independent prefix replay per bounded event batch.

    Quote queries cannot consume any row beyond the audited prefix. Immutable
    receipts are still verified individually; source custody is never inferred.
    """
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.proof = audit_forward_source_copy(db_path=path)

@dataclass(frozen=True)
class OriginalEntryQuote:
    state: str                  # LOCAL_SOURCE_QUOTE / HOLD
    reasons: tuple[str,...]
    symbol: str
    at_ms: int
    bid: str | None = None
    ask: str | None = None
    receipt_sha256: str | None = None
    source_epoch: int | None = None
    chain_head_sha256: str | None = None
    source_grade: str = "PUBLIC_TLS_WSS_LOCALLY_HASHED_NOT_EXCHANGE_SIGNED"
    fills: int = 0
    scored_outcomes: int = 0
    order_authority: str = "NONE"


def independent_asof_entry_quote(*,vault_db:str|Path,
                                 symbol:str,decision_at_ms:int,
                                 max_age_ms:int=1000,
                                 audit_cache:IndependentSourceAudit|None=None) -> OriginalEntryQuote:
    if (not isinstance(symbol,str) or not symbol.endswith("USDT")
            or type(decision_at_ms) is not int or decision_at_ms<=0
            or type(max_age_ms) is not int or not 0<=max_age_ms<=5000):
        raise ValueError("G4_ENTRY_QUOTE_CALL_INVALID")
    def held(reason):
        return OriginalEntryQuote("HOLD",(reason,),symbol,decision_at_ms)
    # Independent integrity replay of EVERY retained row, not only selected
    # symbol. The producer's self-audit alone is not sufficient.
    try:
        if audit_cache is not None:
            if not isinstance(audit_cache, IndependentSourceAudit) or audit_cache.path != Path(vault_db).resolve():
                return held("G4_ENTRY_VAULT_INTEGRITY_UNVERIFIED")
            proof=audit_cache.proof
        else:
            proof=audit_forward_source_copy(db_path=vault_db)
    except (ValueError,sqlite3.DatabaseError):
        return held("G4_ENTRY_VAULT_INTEGRITY_UNVERIFIED")
    if proof["integrity_audit"]!="PASS":
        return held("G4_ENTRY_VAULT_INTEGRITY_UNVERIFIED")
    with closing(sqlite3.connect(Path(vault_db).resolve().as_uri()+"?mode=ro",
                         uri=True,timeout=10)) as db:
        db.execute("BEGIN")
        raw_symbols=db.execute("SELECT symbols_json FROM g4_forward_cohort").fetchone()[0]
        if symbol not in json.loads(raw_symbols):
            return held("G4_ENTRY_SYMBOL_NOT_FROZEN")
        quote=db.execute(
            "SELECT seq,epoch,at_ms,raw_frame,raw_sha256,chain_sha256 "
            "FROM g4_forward_receipts WHERE route='public_bookticker' "
            "AND symbol=? AND kind='FRAME' AND evidence_state='SOURCE_RECORDED' "
            "AND at_ms BETWEEN ? AND ? AND seq<=? ORDER BY at_ms DESC,seq DESC LIMIT 1",
            (symbol,decision_at_ms-max_age_ms,decision_at_ms,proof["records_verified"])).fetchone()
        if quote is None:
            return held("G4_ENTRY_FRESH_QUOTE_MISSING")
        seq,epoch,seen,raw,raw_sha,chain=quote
        # There must be an active, known local WSS socket epoch before this
        # observation. A quote after a close/restart cannot be backdated.
        initial=db.execute(
            "SELECT seq,at_ms FROM g4_forward_receipts "
            "WHERE route='public_bookticker' AND epoch=? AND kind='OPEN' "
            "ORDER BY seq LIMIT 1",(epoch,)).fetchone()
        if initial is None or initial[0]>=seq or initial[1]>seen:
            return held("G4_ENTRY_EPOCH_NOT_OPEN")
        between=db.execute(
            "SELECT kind,evidence_state,symbol FROM g4_forward_receipts "
            "WHERE route='public_bookticker' AND seq>? AND seq<=?",
            (initial[0],seq)).fetchall()
        # No CLOSE or restart inside a supposedly active epoch, and no
        # candidate-symbol HOLD between epoch open and chosen quote. A single
        # bad receipt taints that symbol's epoch (no recovery by later price).
        if any(kind in ("CLOSED","ABRUPT_RESTART_HOLD") or
               (kind=="FRAME" and state=="HOLD" and sym==symbol)
               for kind,state,sym in between):
            return held("G4_ENTRY_SOURCE_EPOCH_WITH_HELD_FRAME")
        if hashlib.sha256(raw).hexdigest()!=raw_sha:
            return held("G4_ENTRY_RAW_BYTES_CHANGED")
        try:
            local=verify_frame(route="public_bookticker",raw=raw,
                               received_at_ms=seen,source_epoch=epoch,
                               selected_symbols=(symbol,))
            value=json.loads(raw)["data"]
        except (TypeError,ValueError,KeyError):
            return held("G4_ENTRY_BOOK_FRAME_INVALID")
        if local.state!="SOURCE_RECORDED" or local.symbol!=symbol:
            return held("G4_ENTRY_BOOK_FRAME_INVALID")
    return OriginalEntryQuote(
        "LOCAL_SOURCE_QUOTE",(),symbol,seen,
        bid=value["b"],ask=value["a"],
        receipt_sha256=raw_sha,source_epoch=epoch,
        chain_head_sha256=proof["head_sha256"])


def policy_quote_mapping(quote:OriginalEntryQuote) -> dict[str,Any]:
    """G4 pure geometry adapter; truthful locally verified, never a fill."""
    return {
        "symbol":quote.symbol,"sampled_at_ms":quote.at_ms,
        "bid":quote.bid,"ask":quote.ask,
        "source_verified":quote.state=="LOCAL_SOURCE_QUOTE",
        "receipt_sha256":quote.receipt_sha256,
        "provenance_grade":quote.source_grade,
        "financial_authority":"NONE",
    }
