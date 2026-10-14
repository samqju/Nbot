"""Bounded original WSS price-path maturation, separately from economics.

No invented costs or labels. Independently verified recorded prefix is required;
all missing/gapped paths stay held, regardless of elapsed horizon.
"""
from dataclasses import asdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from nbot.v5.g4_price_path import replay_aggtrade_price_path
from nbot.v5.science import digest


def follow_original_path(*, vault, audit, candidate, policy, now_ms):
    if audit.path != Path(vault).resolve() or audit.proof.get("integrity_audit") != "PASS":
        raise ValueError("G4_PATH_INDEPENDENT_PREFIX_MISSING")
    decision=candidate["decision_at_ms"]
    end=min(now_ms,decision+policy["horizon_ms"]+5000)
    with closing(sqlite3.connect(Path(vault).resolve().as_uri()+"?mode=ro",uri=True)) as db:
        db.execute("BEGIN")
        start=db.execute("SELECT seq,epoch FROM g4_forward_receipts WHERE route='market_aggtrade' AND symbol=? AND kind='FRAME' AND at_ms<=? AND seq<=? ORDER BY seq DESC LIMIT 1",
                         (candidate["symbol"],decision,audit.proof["records_verified"])).fetchone()
        if start is None:return {"state":"HOLD","reasons":["G4_ORIGINAL_PATH_START_MISSING"]}
        frames=db.execute("SELECT seq,epoch,at_ms,evidence_state,raw_frame FROM g4_forward_receipts WHERE route='market_aggtrade' AND symbol=? AND kind='FRAME' AND seq>=? AND seq<=? AND at_ms<=? ORDER BY seq LIMIT 100001",
                          (candidate["symbol"],start[0],audit.proof["records_verified"],end)).fetchall()
        if len(frames)>100000:return {"state":"HOLD","reasons":["G4_PATH_BATCH_CAPACITY_HOLD"]}
        markers=db.execute("SELECT seq,kind FROM g4_forward_receipts WHERE route='market_aggtrade' AND seq>? AND seq<=? AND at_ms<=? AND kind!='FRAME' ORDER BY seq",
                           (start[0],audit.proof["records_verified"],end)).fetchall()
    rows=[];failure=None
    for seq,epoch,at,state,raw in frames:
        if epoch!=start[1] or state!='SOURCE_RECORDED' or any(mseq<=seq for mseq,kind in markers):
            failure="G4_ORIGINAL_PATH_EPOCH_OR_SOURCE_GAP";break
        item=json.loads(raw)["data"]
        rows.append({k:item[k] for k in ("a","f","l","T","p","q","m")})
    if len(rows)<2:return {"state":"HOLD","reasons":[failure or "G4_ORIGINAL_PATH_ROWS_MISSING"]}
    manifest={"archive_sha256":audit.proof["head_sha256"],"rows_sha256":digest(rows),
              "source_grade":"ORIGINAL_BINANCE_PUBLIC_WSS_AGGTRADES","symbol":candidate["symbol"],
              "original_vault_verified":True,"independent_vault_head_sha256":audit.proof["head_sha256"],
              "first_agg_id":rows[0]["a"],"last_agg_id":rows[-1]["a"]}
    result=asdict(replay_aggtrade_price_path(candidate=candidate,policy=policy,original_rows=rows,
                                          source_manifest=manifest,audit_at_ms=now_ms,allow_early_exit=True))
    if failure and result["state"]!='PATH_REPLAYED':
        result={"state":"HOLD","reasons":[failure]}
    return result
