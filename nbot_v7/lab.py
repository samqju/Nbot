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
import shutil
import math
from .data import BAR_MS, Bar, contract_registry, discover, load_bars, discover_funding, load_funding
from .features import HISTORY, market_features, proposals, btc_regime, legacy_proposals
from .runtime.broker import PaperBroker
from .runtime.risk import RiskPolicy

FEE_EACH = .0005
SLIPPAGE_EACH = .0001
STOP_FRACTION = .02
TAKE_FRACTION = .03
HORIZON_BARS = 12
REVIEW_MS = 8 * 60 * 60 * 1000
LABEL_POLICY = "V7_5M_PAPER_BROKER_V6CONTROLS_2STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_V4"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate(
 decision_ms INTEGER NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
 family TEXT NOT NULL, regime TEXT NOT NULL, features TEXT NOT NULL,
 source_hash TEXT NOT NULL, PRIMARY KEY(decision_ms,symbol,side,family)
);
CREATE TABLE IF NOT EXISTS watch_candidate(
 review_ms INTEGER NOT NULL, symbol TEXT NOT NULL, regime TEXT NOT NULL,
 features TEXT NOT NULL, source_hash TEXT NOT NULL,
 PRIMARY KEY(review_ms,symbol)
);
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
CREATE TABLE IF NOT EXISTS build_progress(
 symbol TEXT PRIMARY KEY NOT NULL,
 source_sha256 TEXT NOT NULL,
 report_json TEXT NOT NULL
);
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
    if side not in ("LONG","SHORT"):raise ValueError("INVALID_SIDE")
    broker=PaperBroker()
    policy=RiskPolicy()
    position=broker.submit({"id":"HISTORICAL_SHADOW","symbol":"SHADOW",
                            "time_ms":bars[i+1].t,"side":side,"quote":bars[i+1].o},policy)
    polarity=1 if side == "LONG" else -1
    entry=position["entry_price"]
    stop=entry*(1-polarity*STOP_FRACTION)
    target=entry*(1+polarity*TAKE_FRACTION)
    mfe=0.0; mae=0.0
    exit_ms=bars[i+HORIZON_BARS].t+BAR_MS
    exit_price=bars[i+HORIZON_BARS].c
    reason="HORIZON"
    quality="COARSE_5M_OHLC_PATH_PROXY"
    for j in range(i+1,i+1+HORIZON_BARS):
        b=bars[j]
        fill,position=broker.on_bar(position,b,b.t+BAR_MS,policy)
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
            # A gap through a protective stop cannot fill at the better stop.
            exit_price=(min(stop,b.o) if polarity==1 else max(stop,b.o)) if stop_hit else target
            exit_ms=b.t+BAR_MS  # Conservative label availability, not a fill time.
            reason="STOP" if stop_hit else "TARGET"
            break
    if fill is None:raise RuntimeError("PAPER_PATH_DID_NOT_MATURE")
    net=fill["net_usdt"]/policy.notional_usdt
    exit_ms=fill["available_ms"]
    reason=fill["reason"].removesuffix("_AMBIGUOUS")
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
    bar_times=[b.t for b in bars]
    opportunities=[]
    funding=funding or []
    funding_times=[event[0] for event in funding]
    contexts=[]
    legacy=legacy_proposals(bars)
    # Only signals and features that were known when the completed candle closed.
    candidates=[]
    for i in range(HISTORY,len(bars)):
        b=bars[i]
        decision=b.t+BAR_MS
        if decision<start_ms or decision>=end_ms or not contract.eligible(decision):
            continue
        if bars[i-HISTORY].t!=b.t-HISTORY*BAR_MS:
            continue
        try:
            feats=market_features(bars,i,btc,times)
        except ValueError:
            continue
        f=json.dumps(feats,sort_keys=True,separators=(",",":"))
        regime=btc_regime(feats)
        if decision%REVIEW_MS==0:
            watch_data.append((decision,regime,f,feats))
            c.execute("INSERT INTO watch_candidate VALUES(?,?,?,?,?)",
                      (decision,symbol,regime,f,source_hash))
        for fam,side in proposals(bars,i,feats)+legacy.get(i,[]):
            candidates.append((decision,symbol,side,fam,regime,f,source_hash))
            # Future path completeness affects the outcome, never candidacy.
            if (i+HORIZON_BARS>=len(bars)
                or bars[i+HORIZON_BARS].t!=b.t+HORIZON_BARS*BAR_MS
                or not contract.eligible(bars[i+HORIZON_BARS].t+BAR_MS-1)):
                continue
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
    c.executemany("INSERT INTO candidate VALUES(?,?,?,?,?,?,?)",candidates)
    times=[r[0] for r in opportunities]
    for review,regime,f,_ in watch_data:
        # Watch labels need the entire future horizon. Missing future records
        # cannot be interpreted as zero opportunities or an ex-ante exclusion.
        begin=bisect_left(bar_times,review)
        required=REVIEW_MS//BAR_MS+HORIZON_BARS
        if (begin+required>len(bars)
            or bars[begin+required-1].t!=review+(required-1)*BAR_MS
            or not contract.eligible(review+required*BAR_MS-1)):
            continue
        j=bisect_left(times,review)
        k=bisect_left(times,review+REVIEW_MS)
        group=opportunities[j:k]
        # Universe training target is *future* opportunity potential; only for labels.
        v=max([x[7] for x in group],default=0.0)
        avail=review+REVIEW_MS+HORIZON_BARS*BAR_MS
        c.execute("INSERT INTO watch VALUES(?,?,?,?,?,?,?,?)",
                  (review,avail,symbol,regime,f,v,len(group),source_hash))
    return len(opportunities),len(watch_data)




def _database_disk_bytes(path: Path) -> int:
    """Account for SQLite main, WAL and SHM files before/after a symbol checkpoint."""
    return sum(p.stat().st_size for p in
               (path,path.with_name(path.name+"-wal"),path.with_name(path.name+"-shm"))
               if p.exists())


def _build_budget(db_path: Path, max_db_gib: float, min_free_gib: float):
    """Fail closed on source-label DB size and filesystem headroom.

    A symbol transaction may add some bytes before the next check; the hard
    reserve must therefore be materially greater than one symbol's footprint.
    """
    max_bytes=int(max_db_gib*1024**3)
    if _database_disk_bytes(db_path)>max_bytes:
        raise RuntimeError("DATASET_DB_BUDGET_EXCEEDED_INCOMPLETE")
    if shutil.disk_usage(db_path.parent).free<int(min_free_gib*1024**3):
        raise RuntimeError("DATASET_FREE_SPACE_RESERVE_BREACHED_INCOMPLETE")


def build_archive_database(
    archive_root: Path, registry_path: Path, db_path: Path,
    start_ms: int, end_ms: int, months: set[str], *, allow_archive_observed: bool=False,
    resume: bool=False, max_db_gib: float=12.0, min_free_gib: float=0.25,
) -> dict:
    """Checkpoint each audited symbol atomically, with an explicit final build marker.

    Resuming a partial build requires the same dates, registry, symbol set,
    label policy and source-file byte hashes; never append changed-source
    samples to a previously trained dataset.
    """
    if not (math.isfinite(max_db_gib) and max_db_gib>0
            and math.isfinite(min_free_gib) and min_free_gib>=0):
        raise ValueError("INVALID_DATASET_RESOURCE_BUDGET")
    if not db_path.exists() and resume:
        raise FileNotFoundError("NO_PARTIAL_DATASET_TO_RESUME")
    if db_path.exists() and not resume:
        raise FileExistsError("REFUSE_EXISTING_DATABASE_TO_PREVENT_LEAKAGE_OR_MIXED_RUNS")
    registry=contract_registry(registry_path,allow_archive_observed=allow_archive_observed)
    files=discover(archive_root,months)
    funding_files=discover_funding(archive_root,months)
    if "BTCUSDT" not in files or "BTCUSDT" not in registry:
        raise ValueError("BTC_SOURCE_AND_REGISTRY_REQUIRED")
    btc,btc_digest=load_bars(files["BTCUSDT"],start_ms-51*BAR_MS,end_ms+HORIZON_BARS*BAR_MS)
    if len(btc)<HISTORY+HORIZON_BARS:
        raise ValueError("INSUFFICIENT_BTC_BARS")
    source_symbols=sorted(set(registry)&set(files))
    base_meta={
        "policy":LABEL_POLICY,
        "registry_sha256":sha256(registry_path.read_bytes()).hexdigest(),
        "start_ms":str(start_ms),
        "end_ms":str(end_ms),
        "source_symbols":json.dumps(source_symbols,separators=(",",":")),
        "requested_months":json.dumps(sorted(months),separators=(",",":")),
        "btc_sources":json.dumps(btc_digest,sort_keys=True),
        "authority":"OFFLINE_RESEARCH_UNVERIFIED_NATIVE_EXECUTION",
    }
    coverage={"missing_registry_symbols":sorted(set(files)-set(registry)),
              "registry_symbols_without_archives":sorted(set(registry)-set(files)),
              "registry_source_grades":dict(sorted(__import__('collections').Counter(x.source_grade for x in registry.values()).items())),
              "eligibility_mode":"ARCHIVE_OBSERVED_EXPLORATORY" if allow_archive_observed else "CALLER_ATTESTED_REQUIRES_INDEPENDENT_AUDIT",
              "historical_exchange_universe_verified":False}
    db_path.parent.mkdir(parents=True,exist_ok=True)
    c=con(db_path)
    counts={}
    resumed=0
    try:
        meta=dict(c.execute("SELECT k,v FROM meta"))
        if resume:
            if meta.get("build_complete")!="false" or any(meta.get(k)!=v for k,v in base_meta.items()):
                raise ValueError("PARTIAL_DATASET_SCOPE_OR_SOURCE_MANIFEST_MISMATCH")
            counts={row["symbol"]:json.loads(row["report_json"]) for row in
                    c.execute("SELECT symbol,report_json FROM build_progress")}
            if set(counts)-set(source_symbols):
                raise ValueError("CHECKPOINT_SYMBOLS_NOT_IN_CURRENT_SCOPE")
        else:
            if meta:
                raise ValueError("DATABASE_ALREADY_INITIALIZED")
            with c:
                c.execute("INSERT INTO meta VALUES(?,?)",("build_complete","false"))
                c.executemany("INSERT INTO meta VALUES(?,?)",base_meta.items())
        _build_budget(db_path,max_db_gib,min_free_gib)
        for symbol in source_symbols:
            # Checkpointed symbols still have all source ZIPs re-hashed:
            # resumption must not silently accept edited or swapped archives.
            bars,digests=(btc,btc_digest) if symbol=="BTCUSDT" else load_bars(
                files[symbol],start_ms-51*BAR_MS,end_ms+HORIZON_BARS*BAR_MS)
            funding_rows,funding_hashes=load_funding(funding_files.get(symbol,[]),start_ms,end_ms)
            kline_months={p.name[-11:-4] for p in files[symbol]}
            funding_months={p.name[-11:-4] for p in funding_files.get(symbol,[])}
            funding_covered=(bool(funding_rows) and kline_months==funding_months)
            bundle={"klines":{Path(k).name:v for k,v in digests.items()},
                    "funding":{Path(k).name:v for k,v in funding_hashes.items()},
                    "btc":{Path(k).name:v for k,v in btc_digest.items()},
                    "contract":asdict(registry[symbol]),"label_policy":LABEL_POLICY}
            src=sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest()
            if symbol in counts:
                if counts[symbol]["source_sha256"]!=src:
                    raise ValueError("RESUME_SYMBOL_SOURCE_HASH_CHANGED:"+symbol)
                resumed+=1
                continue
            _build_budget(db_path,max_db_gib,min_free_gib)
            contract=registry[symbol]
            lo=max(start_ms,contract.from_ms)
            hi=min(end_ms,contract.to_ms)
            expected=max(0,(hi+BAR_MS-1)//BAR_MS-(lo+BAR_MS-1)//BAR_MS)
            actual=sum(lo<=bar.t<hi for bar in bars)
            # Labels and progress receipt are ONE symbol-level transaction.
            with c:
                n,w=generate_symbol(c,symbol,bars,btc,contract,src,start_ms,end_ms,
                                    funding=funding_rows,funding_coverage=funding_covered)
                record={"candidate_labels":n,"universe_reviews":w,
                        "source_sha256":src,"source_bundle":bundle,
                        "funding_source_complete":funding_covered,
                        "expected_eligible_bars":expected,"observed_eligible_bars":actual,
                        "missing_eligible_bars":max(0,expected-actual)}
                c.execute("INSERT INTO build_progress VALUES(?,?,?)",
                          (symbol,src,json.dumps(record,sort_keys=True)))
            counts[symbol]=record
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _build_budget(db_path,max_db_gib,min_free_gib)
        coverage["symbols"]=counts
        # No "complete" marker until every source symbol has a verified
        # checkpoint and the disk-headroom guard has succeeded.
        with c:
            c.execute("INSERT INTO meta VALUES(?,?)",("symbol_manifest",json.dumps(counts,sort_keys=True)))
            c.execute("INSERT INTO meta VALUES(?,?)",("coverage",json.dumps(coverage,sort_keys=True)))
            c.execute("UPDATE meta SET v='true' WHERE k='build_complete'")
        db_path.with_suffix(".coverage.json").write_text(json.dumps(coverage,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        return {"symbols_scanned":len(counts),"symbols_reused_after_checkpoint":resumed,
                "candidate_labels":sum(x["candidate_labels"] for x in counts.values()),
                "universe_reviews":sum(x["universe_reviews"] for x in counts.values()),
                "source_authority":"OFFLINE_5M_PROXY_NOT_NATIVE_FILLS","label_policy":LABEL_POLICY,
                "funding_covered_symbols":sum(int(x["funding_source_complete"]) for x in counts.values())}
    finally:
        c.close()
