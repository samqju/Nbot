"""Accelerated source-complete synthetic laboratory, no network interfaces.

Uses real 24-pattern and causal G3 functions, persisted G1/G2 format, immutable
compressed raw paths, signed synthetic costs and the automatic G4 row builder.
"""
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from nbot.v5.pattern_adapter import build_observations_from_closed_candles
from nbot.v5.g3_market_context import classify_event
from nbot.v5.g4_segmented_source import SegmentedForwardSource
from nbot.v5.science import canonical, digest
from tests.test_v5_g4_source_binding import db_fixture, EVENT
from tests.test_v5_g4_forward_vault import quote, trade
from tests.test_v5_economic_handoff import evidence
from tests.test_v5_science import review


def build_lab(root, events=60):
    source=root/"g1g2g3.sqlite"
    db_fixture(source)
    db=sqlite3.connect(source)
    syms=json.loads(db.execute("SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0])
    cohort=db.execute("SELECT cohort_digest FROM g1f_universe_snapshots").fetchone()[0]
    for table in ("g1f_event_manifest","g1f_candidate_events","g2_quote_witness","g3_event_context"):
        db.execute("DELETE FROM "+table)  # disposable initial fixture only
    segments=root/"segments"; segments.mkdir(mode=0o700)
    archive=SegmentedForwardSource(segments,symbols=syms,max_pending_frames=512,
                                   max_pending_bytes=1048576,max_disk_bytes=64*1024*1024)
    archive.connect(route="market_aggtrade",at_ms=EVENT-1000)
    archive.connect(route="public_bookticker",at_ms=EVENT-1000)
    quotes={}
    regimes=set()
    for i in range(events):
        event=EVENT+i*8*3600000; at=event+301000
        candles={}
        witnesses={}
        for j,sym in enumerate(syms):
            slope=(.002,-.002,0)[i%3] if sym=="BTCUSDT" else .0005+j*.000002
            bars=[]
            for k in range(96):
                close=100*(1+slope*(k-95)) + (.01*math.sin(k) if slope==0 else 0)
                bars.append((event-(95-k)*300000,close-.01,close+.5,close-.5,close,1000+k))
            candles[sym]=bars
            src={"market_connected":True,"public_connected":True,"market_epoch":1,"public_epoch":1,
                 "quote_received_ms":at-100,"trade_received_ms":at-100,"bid":100.0,"ask":100.1}
            witness={"event_open_ms":event,"symbol":sym,"cohort_digest":cohort,
                     "asof_ms":at,"status":"SOURCE_RECORDED","hold_reasons":[],
                     "paper_fill_grade":"UNVERIFIED","order_authority":"NONE","source":src}
            witnesses[sym]={"sampled_at_ms":at,"source":src}
            db.execute("INSERT INTO g2_quote_witness VALUES (?,?,?,?,?)",
                       (event,sym,at,canonical(witness),digest(witness)))
        records=build_observations_from_closed_candles(
            event_open_ms=event,decision_at_ms=at,observed_at_ms=at,
            eligible_symbols=syms,candles_by_symbol=candles)
        if len(records)!=100 or any(r["status"]!="OBSERVED" for r in records):
            raise AssertionError("LAB_G1_FULL_POPULATION")
        for r in records:
            db.execute("INSERT INTO g1f_candidate_events VALUES (?,?,?,?,?,?,?)",
                       (event,r["decision_id"],r["symbol"],r["side"],r["status"],canonical(r),digest(r)))
        features=classify_event(event_open_ms=event,decision_at_ms=at,selected_symbols=syms,
                                candles=candles,witnesses=witnesses)
        regimes.add(features["btc"]["regime"])
        context={"event_open_ms":event,"valid_from_ms":at,"status":"OBSERVE_ONLY",
                 "order_authority":"NONE","recommendation_authority":"NONE","feature_evidence":features}
        db.execute("INSERT INTO g3_event_context VALUES (?,?,?)",(event,canonical(context),digest(context)))
        manifest={"event_open_ms":event,"committed_ms":at}
        db.execute("INSERT INTO g1f_event_manifest VALUES (?,?,?,?,?,?)",
                   (event,cohort,at,"OBSERVE_ONLY",canonical(manifest),digest(manifest)))
        # One predecision and two forward trades per symbol. Short stops
        # occur before the later Long targets; fees cannot turn a missing path
        # into either result. Global route receipt clocks are monotonic.
        for offset in (-100,200,400):
            for sym in syms:
                if offset==-100:
                    raw=quote(symbol=sym,bid="100.0",ask="100.1",at=at+offset)
                    archive.ingest(route="public_bookticker",at_ms=at+offset,raw=raw)
                    quotes[(sym,at+offset)]=(raw,"100.0","100.1")
                atr=features["coins"][sym]["features"]["atr14_fraction"]
                price=100 if offset==-100 else 100+100*atr*1.5*1.1 if offset==200 else 100.1+100.1*atr*1.5*2.1
                agg=100+i*3+(-100,200,400).index(offset)
                raw=json.loads(trade(symbol=sym,agg=agg,first=500+(agg-100)*3,
                                     last=502+(agg-100)*3,at=at+offset))
                raw["data"].update(p=str(price),T=at+offset,E=at+offset)
                archive.ingest(route="market_aggtrade",at_ms=at+offset,raw=canonical(raw).encode())
                if offset>0:
                    bid,ask=str(price-.01),str(price+.01)
                    raw=quote(symbol=sym,bid=bid,ask=ask,at=at+offset)
                    archive.ingest(route="public_bookticker",at_ms=at+offset,raw=raw)
                    quotes[(sym,at+offset)]=(raw,bid,ask)
        archive.flush()
    db.commit(); db.close()
    def provider(population,intent,path,now):
        package,_=evidence(population,intent,path,now)
        raw,bid,ask=quotes[(intent["symbol"],path["exit_at_ms"])]
        package["exit_quote"].update(bid=bid,ask=ask,receipt_sha256=hashlib.sha256(raw).hexdigest())
        return package,review(digest(package),"G4_ECONOMIC_EVIDENCE",now=now,grade="SYNTHETIC")
    return source,segments,provider,regimes,archive


def laboratory_reviewer(subject,purpose,context,now):
    return review(subject,purpose,now=now,grade="SYNTHETIC",role=context["role"],
                  g5_accepted=True,g6_accepted=True,holdout_source_audit_accepted=True,
                  qualified_training_outcomes=context["qualified_training_outcomes"],
                  additional_nonoverlapping_outcomes=context.get("additional_nonoverlapping_outcomes",0))
