"""V7 offline broad-market outcome laboratory; CSV/ZIP -> source-hashed SQLite.

No private API, orders, wallet credentials, live execution or real-fill claims.
"""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from .data import BAR_MS, Bar, contract_registry, discover, load_bars, discover_funding, load_funding
from .features import HISTORY, market_features, proposals, btc_regime

FEE_EACH = .0005
SLIPPAGE_EACH = .0001
STOP_FRACTION = .02
TAKE_FRACTION = .03
HORIZON_BARS = 12
REVIEW_MS = 8 * 60 * 60 * 1000
LABEL_POLICY = "V7_5M_STOP_FIRST_2STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_V1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunity(
 decision_ms INTEGER NOT NULL,
 label_available_ms INTEGER NOT NULL,
 symbol TEXT NOT NULL,
 side TEXT NOT NULL,
 family TEXT NOT NULL,
 regime TEXT NOT NULL,
 features TEXT NOT NULL,
 net REAL NOT NULL,
 mfe_pct REAL NOT NULL,
 mae_pct REAL NOT NULL,
 exit_ms INTEGER NOT NULL,
 exit_reason TEXT NOT NULL,
 quality TEXT NOT NULL,
 source_hash TEXT NOT NULL,
 PRIMARY KEY (decision_ms,symbol,side,family)
);
CREATE INDEX IF NOT EXISTS opp_by_symbol ON opportunity(symbol,decision_ms);
CREATE INDEX IF NOT EXISTS opp_by_time ON opportunity(decision_ms);
CREATE TABLE IF NOT EXISTS watch(
 review_ms INTEGER NOT NULL,
 label_available_ms INTEGER NOT NULL,
 symbol TEXT NOT NULL,
 regime TEXT NOT NULL,
 features TEXT NOT NULL,
 target_net REAL NOT NULL,
 signal_count INTEGER NOT NULL,
 source_hash TEXT NOT NULL,
 PRIMARY KEY(review_ms,symbol)
);
CREATE INDEX IF NOT EXISTS watch_by_time ON watch(review_ms);
CREATE TABLE IF NOT EXISTS outcome_context(
 decision_ms INTEGER NOT NULL,
 symbol TEXT NOT NULL,
 side TEXT NOT NULL,
 family TEXT NOT NULL,
 mfe_bar_close_ms INTEGER,
 mae_bar_close_ms INTEGER,
 btc_return_to_exit REAL,
 future_btc_status TEXT NOT NULL,
 funding_status TEXT NOT NULL,
 funding_net_fraction REAL,
 mfe_mae_time_quality TEXT NOT NULL,
 PRIMARY KEY(decision_ms,symbol,side,family)
);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""

def con(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(str(db), timeout=60)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=60000")
    c.executescript(SCHEMA)
    return c

def outcome(bars: list[Bar], i: int, side: str):
    """Next 5m open, frozen 2% stop/3% take/60m horizon, adverse-first tied candle.

    MFE/MAE are OHLC path bounds, not verified pre-exit tick chronology.
    """
    polarity=1 if side == "LONG" else -1
    entry=bars[i+1].o
    stop=entry*(1-polarity*STOP_FRACTION)
    target=entry*(1+polarity*TAKE_FRACTION)
    mfe=0.0; mae=0.0
    exit_ms=bars[i+HORIZON_BARS].t+BAR_MS
    exit_price=bars[i+HORIZON_BARS].c
    reason="HORIZON"
    quality="COARSE_5M_OHLC_PATH_PROXY"
    for j in range(i+1,i+1+HORIZON_BARS):
        b=bars[j]
        favorable=(b.h/entry-1) if polarity==1 else (1-b.l/entry)
        adverse=(b.l/entry-1) if polarity==1 else (1-b.h/entry)
        stop_hit=b.l<=stop if polarity==1 else b.h>=stop
        target_hit=b.h>=target if polarity==1 else b.l<=target
        if stop_hit and target_hit:
            quality="AMBIGUOUS_5M_STOP_FIRST"
            # Do not award the same candle's favorable extreme before a stop.
            mae=min(mae,-STOP_FRACTION)
        else:
            mfe=max(mfe,favorable)
            mae=min(mae,adverse)
        if stop_hit or target_hit:
            exit_price=stop if stop_hit else target
            exit_ms=b.t+BAR_MS  # Conservative label availability, not a fill time.
            reason="STOP" if stop_hit else "TARGET"
            break
    net=polarity*(exit_price/entry-1)-2*(FEE_EACH+SLIPPAGE_EACH)
    return (net,mfe,mae,exit_ms,reason,quality)

def path_outcome_context(bars, i, side, exit_ms, btc, btc_times, decision, funding_status="FUNDING_UNVERIFIED_NOT_COUNTED", funding_net_fraction=None):
    """Future-only outcome diagnostics. Extremum timing is 5m bar-close, NOT tick time."""
    direction=1 if side=="LONG" else -1
    entry=bars[i+1].o
    path=[bar for bar in bars[i+1:i+1+HORIZON_BARS] if bar.t+BAR_MS<=exit_ms]
    if not path:
        return None,None,None,"UNKNOWN",funding_status,funding_net_fraction,"NO_PATH"
    fav=lambda bar:direction*(bar.h/entry-1) if direction==1 else 1-bar.l/entry
    adv=lambda bar:direction*(bar.l/entry-1) if direction==1 else 1-bar.h/entry
    maxbar=max(path,key=fav)
    minbar=min(path,key=lambda bar:adv(bar))
    ix0=bisect_left(btc_times,decision-BAR_MS)
    ix1=bisect_left(btc_times,exit_ms-BAR_MS)
    btc_change=None
    status="BTC_FUTURE_COVERAGE_UNKNOWN"
    if (ix0<len(btc_times) and ix1<len(btc_times)
        and btc_times[ix0]==decision-BAR_MS and btc_times[ix1]==exit_ms-BAR_MS
        and (btc_times[ix1]-btc_times[ix0])==(ix1-ix0)*BAR_MS):
        btc_change=btc[ix1].c/btc[ix0].c-1
        status="BTC_UP" if btc_change>.005 else "BTC_DOWN" if btc_change<-.005 else "BTC_RANGE"
    return (maxbar.t+BAR_MS,minbar.t+BAR_MS,btc_change,status,
            funding_status,funding_net_fraction,"5M_BAR_CLOSE_BOUNDS_NOT_INTRABAR")

def generate_symbol(
    c: sqlite3.Connection, symbol: str, bars: list[Bar], btc: list[Bar],
    contract, source_hash: str, start_ms: int, end_ms: int,
    funding: list[tuple[int,float]] | None = None, funding_coverage: bool = False,
):
    times=[x.t for x in btc]
    watch_data=[]
    opportunities=[]
    funding=funding or []
    funding_times=[event[0] for event in funding]
    contexts=[]
    # Only signals and features that were known when the completed candle closed.
    for i in range(HISTORY,len(bars)-HORIZON_BARS):
        b=bars[i]
        decision=b.t+BAR_MS
        if decision<start_ms or decision>=end_ms or not contract.eligible(decision):
            continue
        if bars[i-HISTORY].t!=b.t-HISTORY*BAR_MS:
            continue
        if bars[i+HORIZON_BARS].t!=b.t+HORIZON_BARS*BAR_MS:
            continue
        try:
            feats=market_features(bars,i,btc,times)
        except ValueError:
            continue
        f=json.dumps(feats,sort_keys=True,separators=(",",":"))
        regime=btc_regime(feats)
        if decision%REVIEW_MS==0 and decision+REVIEW_MS+HORIZON_BARS*BAR_MS<=end_ms:
            watch_data.append((decision,regime,f,feats))
        for fam,side in proposals(bars,i,feats):
            n,mfe,mae,ex,why,q=outcome(bars,i,side)
            sign=1 if side=="LONG" else -1
            start_funding=bisect_left(funding_times,bars[i+1].t)
            end_funding=bisect_left(funding_times,ex)
            # Signed funding approximation on fixed entry notional, not verified mark notional.
            funding_net_fraction=-sign*sum(rate for _,rate in funding[start_funding:end_funding])
            n+=funding_net_fraction
            funding_status=("MONTHLY_RATE_ARCHIVE_PROXY" if funding_coverage
                            else "MISSING_FUNDING_MONTH_SOURCE")
            opportunities.append((decision,ex,symbol,side,fam,regime,f,
                                  n,mfe,mae,ex,why,q,source_hash))
            extra=path_outcome_context(bars,i,side,ex,btc,times,decision,
                                       funding_status,funding_net_fraction if funding_coverage else None)
            contexts.append((decision,symbol,side,fam,*extra))
    if opportunities:
        c.executemany("INSERT INTO opportunity VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",opportunities)
        c.executemany("INSERT INTO outcome_context VALUES(?,?,?,?,?,?,?,?,?,?,?)",contexts)
    times=[r[0] for r in opportunities]
    for review,regime,f,_ in watch_data:
        j=bisect_left(times,review)
        k=bisect_left(times,review+REVIEW_MS)
        group=opportunities[j:k]
        # Universe training target is *future* opportunity potential; only for labels.
        v=max([x[7] for x in group],default=0.0)
        avail=review+REVIEW_MS+HORIZON_BARS*BAR_MS
        c.execute("INSERT INTO watch VALUES(?,?,?,?,?,?,?,?)",
                  (review,avail,symbol,regime,f,v,len(group),source_hash))
    return len(opportunities),len(watch_data)

def build_archive_database(
    archive_root: Path, registry_path: Path, db_path: Path,
    start_ms: int, end_ms: int, months: set[str]
) -> dict:
    if db_path.exists():
        raise FileExistsError("REFUSE_EXISTING_DATABASE_TO_PREVENT_LEAKAGE_OR_MIXED_RUNS")
    registry=contract_registry(registry_path)
    files=discover(archive_root,months)
    funding_files=discover_funding(archive_root,months)
    if "BTCUSDT" not in files or "BTCUSDT" not in registry:
        raise ValueError("BTC_SOURCE_AND_REGISTRY_REQUIRED")
    btc,btc_digest=load_bars(files["BTCUSDT"],start_ms-51*BAR_MS,end_ms+HORIZON_BARS*BAR_MS)
    if len(btc)<HISTORY+HORIZON_BARS:
        raise ValueError("INSUFFICIENT_BTC_BARS")
    counts={}
    c=con(db_path)
    try:
        c.execute("INSERT INTO meta VALUES(?,?)",("policy",LABEL_POLICY))
        c.execute("INSERT INTO meta VALUES(?,?)",("registry_sha256",sha256(registry_path.read_bytes()).hexdigest()))
        c.execute("INSERT INTO meta VALUES(?,?)",("start_ms",str(start_ms)))
        c.execute("INSERT INTO meta VALUES(?,?)",("end_ms",str(end_ms)))
        c.execute("INSERT INTO meta VALUES(?,?)",("authority","OFFLINE_RESEARCH_UNVERIFIED_NATIVE_EXECUTION"))
        c.execute("INSERT INTO meta VALUES(?,?)",("btc_sources",json.dumps(btc_digest,sort_keys=True)))
        for symbol in sorted(set(registry)&set(files)):
            bars, digests=(btc,btc_digest) if symbol=="BTCUSDT" else load_bars(
                files[symbol],start_ms-51*BAR_MS,end_ms+HORIZON_BARS*BAR_MS)
            funding_rows,funding_hashes=load_funding(funding_files.get(symbol,[]),start_ms,end_ms)
            kline_months={p.name[-11:-4] for p in files[symbol]}
            funding_months={p.name[-11:-4] for p in funding_files.get(symbol,[])}
            funding_covered=(bool(funding_rows) and kline_months==funding_months)
            bundle={"klines":digests,"funding":funding_hashes}
            src=sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest()
            with c:
                n,w=generate_symbol(c,symbol,bars,btc,registry[symbol],src,start_ms,end_ms,
                                    funding=funding_rows,funding_coverage=funding_covered)
            counts[symbol]={"candidate_labels":n,"universe_reviews":w,
                            "source_sha256":src,"funding_source_complete":funding_covered}
        with c:
            c.execute("INSERT INTO meta VALUES(?,?)",("symbol_manifest",json.dumps(counts,sort_keys=True)))
        return {"symbols_scanned":len(counts),"candidate_labels":sum(x["candidate_labels"] for x in counts.values()),
                "universe_reviews":sum(x["universe_reviews"] for x in counts.values()),
                "source_authority":"OFFLINE_5M_PROXY_NOT_NATIVE_FILLS","label_policy":LABEL_POLICY,
                "funding_covered_symbols":sum(int(x["funding_source_complete"]) for x in counts.values())}
    finally:
        c.close()
