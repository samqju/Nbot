"""G4 genuine-source prospective risk geometry ADMISSION ONLY (no virtual fills).

Joins read-only frozen G1/G2/G3 100-directional original evidence, original
WSS bid/ask at as-of decision and a preregistered pre-event risk template.
Returns a local reference-risk geometry or explicit hold. NEVER SCORED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import closing, nullcontext
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from nbot.v5.g4_segment_quotes import VerifiedSegmentQuotes
from nbot.v5.g4_source_binding import bind_from_frozen_observation_copy, ReadOnlyBindingSession
from nbot.v5.g4_forward_entry_quote import (
    independent_asof_entry_quote,policy_quote_mapping,
)
from nbot.v5.g4_prospective_policy import freeze_template,bind_at_decision
from nbot.v5.observation_contract import INTERVAL_MS

@dataclass(frozen=True)
class RealResearchAdmission:
    state: str
    reasons: tuple[str,...]
    event_open_ms: int
    symbol: str
    side: str
    original_candidate_sha256: str | None = None
    original_g3_feature_sha256: str | None = None
    original_entry_quote_sha256: str | None = None
    policy_sha256: str | None = None
    policy_geometry: dict | None = None
    maturity_status: str = "NOT_MATURED_OR_COST_VERIFIED"
    original_source_authenticity: str = "LOCAL_WSS_TLS_RECEIPTS_NOT_EXCHANGE_SIGNED"
    funded_cost_proof: bool = False
    qualified_economic_outcomes: int = 0
    order_authority: str = "NONE"
    training_authority: str = "NONE"


def admit_research_entry(*,g1_snapshot: str|Path,raw_source_vault: str|Path,
                         registry_file: str|Path,event_open_ms:int,
                         symbol:str,side:str, audit_cache=None, source_audit_cache=None) -> RealResearchAdmission:
    if type(event_open_ms) is not int or event_open_ms<0 or event_open_ms%INTERVAL_MS:
        raise ValueError("G4_ADMISSION_EVENT_INVALID")
    if side not in ("LONG","SHORT") or not isinstance(symbol,str) or not symbol.endswith("USDT"):
        raise ValueError("G4_ADMISSION_SIDE_OR_SYMBOL_INVALID")
    def hold(*issues):
        return RealResearchAdmission(
            "HOLD",tuple(sorted(set(issues))),event_open_ms,symbol,side)
    registry=Path(registry_file)
    if registry.is_symlink() or not registry.is_file():
        return hold("PREDECLARED_POLICY_FILE_MISSING")
    try:
        saved=json.loads(registry.read_text(encoding="utf8"))
        if (saved.get("registry_version")!="NBOT_V5_G4_PREDECLARED_POLICY_REGISTRY_V1"
                or saved.get("research_only") is not True
                or saved.get("financial_authority")!="NONE"):
            return hold("POLICY_REGISTRY_NOT_ADMISSIBLE")
        frozen=freeze_template(saved["spec"])
        if frozen.policy_sha256!=saved.get("policy_sha256"):
            return hold("POLICY_REGISTRY_SHA_MISMATCH")
        if event_open_ms<frozen.spec["activates_at_ms"]:
            return hold("PREACTIVATION_EVENT_NOT_ELIGIBLE")
    except (OSError,ValueError,TypeError,KeyError):
        return hold("POLICY_REGISTRY_UNVERIFIABLE")

    if source_audit_cache is not None:
        if (not isinstance(source_audit_cache,ReadOnlyBindingSession)
                or source_audit_cache.path!=Path(g1_snapshot).resolve()):
            return hold("ORIGINAL_SOURCE_AUDIT_SESSION_INVALID")
        bound=source_audit_cache.bound(event_open_ms,symbol,side)
    else:
        bound=bind_from_frozen_observation_copy(
            db_path=g1_snapshot,event_open_ms=event_open_ms,
            symbol=symbol,side=side)
    if bound.state!="SOURCE_BOUND":
        return hold("ORIGINAL_G1_G2_G3_DENOMINATOR_HELD",*bound.reasons)
    try:
        path=Path(g1_snapshot)
        context=(nullcontext(source_audit_cache.db) if source_audit_cache is not None else
                 closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=10)))
        with context as db:
            if source_audit_cache is None: db.execute("BEGIN")
            old=db.execute(
                "SELECT record_json FROM g1f_candidate_events "
                "WHERE event_open_ms=? AND symbol=? AND direction=?",
                (event_open_ms,symbol,side)).fetchone()
            context=db.execute(
                "SELECT payload_json FROM g3_event_context WHERE event_open_ms=?",
                (event_open_ms,)).fetchone()
            original_g2=db.execute(
                "SELECT payload_json FROM g2_quote_witness "
                "WHERE event_open_ms=? AND symbol=?",(event_open_ms,symbol)).fetchone()
        if not old or not context or not original_g2:
            return hold("ORIGINAL_FROZEN_SOURCE_ROW_MISSING")
        candidate=json.loads(old[0])
        g3=json.loads(context[0])
        g2=json.loads(original_g2[0])
        decision=candidate["decision_at_ms"]
        if type(decision) is not int or decision < event_open_ms+INTERVAL_MS:
            return hold("CANDIDATE_DECISION_CLOCK_INVALID")
        # Original G2 source is captured BEFORE slower three-stage G1
        # REST finality; candidate commitment happens later. Exact equality
        # would reject every genuine event. Earlier G2 is causal source
        # context, NOT a fresh entry/executable quote at G4 decision:
        # the independent forward-WSS quote below must prove that.
        g2_at=g2.get("asof_ms")
        if (type(g2_at) is not int or
                not event_open_ms+INTERVAL_MS<=g2_at<=decision):
            return hold("G2_SOURCE_ASOF_FUTURE_OR_NOT_EVENT_CAUSAL")
        coin=g3["feature_evidence"]["coins"][symbol]
        atr=coin.get("features",{}).get("atr14_fraction")
        if type(atr) not in (int,float):
            return hold("ORIGINAL_G3_ATR_FRACTION_UNAVAILABLE")
        # Repr preserves the exact original IEEE754 value's roundtrip (and
        # provenance is the original G3 feature SHA, not this formatting).
        atr_text=repr(atr)
        if Decimal(atr_text)<=0:
            return hold("ORIGINAL_G3_ATR_NOT_POSITIVE")
        g3_input={
            "state":coin["state"],
            "reasons":coin.get("reasons",[]),
            "valid_from_ms":g3["valid_from_ms"],
            "feature_sha256":bound.g3_feature_sha256,
            "atr14_fraction":atr_text,
        }
    except (OSError,ValueError,sqlite3.Error,KeyError,TypeError,IndexError):
        return hold("ORIGINAL_SOURCE_ADMISSION_EXTRACTION_INVALID")
    if isinstance(audit_cache,VerifiedSegmentQuotes):
        # Direct 50-coin original source chain witness. Unlike the old
        # temporary SQLite view, this does not cap real capture at 100k ticks.
        quote=audit_cache.asof(
            symbol,decision,frozen.spec["max_quote_age_ms"])
    else:
        quote=independent_asof_entry_quote(
            vault_db=raw_source_vault,symbol=symbol,
            decision_at_ms=decision,
            max_age_ms=frozen.spec["max_quote_age_ms"],audit_cache=audit_cache)
    if quote.state!="LOCAL_SOURCE_QUOTE":
        return hold("INDEPENDENT_REAL_ENTRY_QUOTE_HELD",*quote.reasons)
    # This is a side-correct counterfactual reference; all costs, future
    # original path/exit/funding receipts and actual fill remain absent.
    candidate["source_digest"]=bound.candidate_source_sha256
    result=bind_at_decision(
        template=frozen,candidate=candidate,g3_coin=g3_input,
        quote=policy_quote_mapping(quote))
    if result.state!="GEOMETRY_RECORDED":
        return hold("PREDECLARED_RISK_GEOMETRY_HELD",*result.reasons)
    return RealResearchAdmission(
        "REFERENCE_GEOMETRY_RECORDED",(),event_open_ms,symbol,side,
        original_candidate_sha256=bound.candidate_source_sha256,
        original_g3_feature_sha256=bound.g3_feature_sha256,
        original_entry_quote_sha256=quote.receipt_sha256,
        policy_sha256=frozen.policy_sha256,
        policy_geometry=result.frozen_policy)


def main():
    import argparse
    p=argparse.ArgumentParser(description="G4 read-only original forward-entry reference geometry")
    p.add_argument("--g1-snapshot",required=True)
    p.add_argument("--raw-source-vault",required=True)
    p.add_argument("--registry-file",required=True)
    p.add_argument("--event",required=True,type=int)
    p.add_argument("--symbol",required=True)
    p.add_argument("--side",choices=("LONG","SHORT"),required=True)
    a=p.parse_args()
    try:
        record=admit_research_entry(
            g1_snapshot=a.g1_snapshot,raw_source_vault=a.raw_source_vault,
            registry_file=a.registry_file,event_open_ms=a.event,
            symbol=a.symbol,side=a.side)
        print(json.dumps(asdict(record),sort_keys=True))
        return 0 if record.state=="REFERENCE_GEOMETRY_RECORDED" else 2
    except (ValueError,OSError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "qualified_economic_outcomes":0,
                          "order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
