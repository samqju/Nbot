"""Bounded forward shadow accounts. No exchange, execution or order transport.

Decisions precede entry candles. Stops active at a bar's start win over favorable
extremes; newly raised stops apply only to the next bar. Not tick-equivalent fills.
"""
from __future__ import annotations
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3

from .candidate_setups import BY_ID, CATALOG_DIGEST, INTERVAL_MS, tie_key

VERSION = "SHADOW_CANDIDATE_ACCOUNTS_V1"
AUTHORITY = "SHADOW_ONLY_NO_EXECUTION"
MAX_POSITIONS = 10
SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_configurations (
 release_sha TEXT NOT NULL, profile TEXT NOT NULL,
 config_json TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(release_sha,profile)
);

CREATE TABLE IF NOT EXISTS shadow_positions (
 id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL UNIQUE,
 release_sha TEXT NOT NULL, profile TEXT NOT NULL,
 state_json TEXT NOT NULL, digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_results (
 id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, release_sha TEXT NOT NULL,
 profile TEXT NOT NULL, closed_ms INTEGER NOT NULL, eligible INTEGER NOT NULL,
 result_json TEXT NOT NULL, digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS shadow_results_cohort ON shadow_results(release_sha,profile,closed_ms);
CREATE TABLE IF NOT EXISTS shadow_daily (
 release_sha TEXT NOT NULL, profile TEXT NOT NULL, candidate_id TEXT NOT NULL,
 state_json TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(release_sha,profile,candidate_id)
);
CREATE TABLE IF NOT EXISTS shadow_batches (
 release_sha TEXT NOT NULL, profile TEXT NOT NULL, event_ms INTEGER NOT NULL,
 batch_json TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(release_sha,profile,event_ms)
);
"""


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def verified(raw, expected):
    value=json.loads(raw)
    if digest(value)!=expected:
        raise ValueError("SHADOW_STATE_DIGEST_MISMATCH")
    return value


def day(t):
    return datetime.fromtimestamp(t/1000,timezone.utc).date().isoformat()


@dataclass(frozen=True)
class ShadowConfig:
    starting_balance_usd: float = 10000.
    risk_usd: float = 10.
    notional_usd: float = 1000.
    slippage_pct: float = .02
    taker_fee_rate: float = .0005
    max_spread_pct: float = .25
    max_reference_drift_pct: float = .25
    daily_trigger_r: float = 100.
    normal_giveback_r: float = 95.
    profit_giveback_r: float = 3.

    def __post_init__(self):
        for name,value in asdict(self).items():
            if isinstance(value,bool) or not math.isfinite(value) or value<0:
                raise ValueError("SHADOW_CONFIG_INVALID:"+name)
        if (not 0<self.risk_usd<self.notional_usd<=self.starting_balance_usd or self.taker_fee_rate>=.1
                or self.slippage_pct>1 or self.max_spread_pct>5 or self.max_reference_drift_pct>5
                or min(self.daily_trigger_r,self.normal_giveback_r,self.profit_giveback_r)<=0):
            raise ValueError("SHADOW_CONFIG_INVALID")


def advance_bar(state, bar):
    """Pure transition on a complete post-decision bar; returns state, close reason."""
    p=dict(state)
    t,o,h,l,c=bar
    if (t!=p["next_bar_ms"] or not all(math.isfinite(x) for x in (o,h,l,c))
            or min(o,h,l,c)<=0 or h<max(o,c) or l>min(o,c) or l>h):
        raise ValueError("SHADOW_BAR_INVALID")
    cfg=p["config"]
    sign=1 if p["side"]=="LONG" else -1
    cost=p["spread_half_frac"]+cfg["slippage_pct"]/100
    if p["status"]=="PENDING":
        entry=o*(1+sign*cost)
        reference=(p["bid"]+p["ask"])/2
        if abs(entry-reference)/reference*100>cfg["max_reference_drift_pct"]:
            p["closed_ms"]=t
            return p,"ENTRY_DRIFT_REJECTED"
        quantity=cfg["notional_usd"]/entry
        distance=cfg["risk_usd"]/quantity
        p.update(status="OPEN",entered_ms=t,entry_price=entry,quantity=quantity,
                 distance=distance,stop=entry-sign*distance,peak_r=0.,bars=0,
                 entry_fee=cfg["notional_usd"]*cfg["taker_fee_rate"],ambiguous_bars=0)
    p["bars"]+=1
    p["next_bar_ms"]=t+INTERVAL_MS
    hit=l<=p["stop"] if sign==1 else h>=p["stop"]
    if hit:
        raw=min(o,p["stop"]) if sign==1 else max(o,p["stop"])
        exit_price=raw*(1-sign*cost)
        gross=sign*(exit_price-p["entry_price"])*p["quantity"]
        fees=p["entry_fee"]+exit_price*p["quantity"]*cfg["taker_fee_rate"]
        p.update(exit_price=exit_price,net_usd=gross-fees,net_r=(gross-fees)/cfg["risk_usd"],
                 closed_ms=t+INTERVAL_MS-1)
        return p,"STOP"
    favorable=h if sign==1 else l
    peak=max(p["peak_r"],sign*(favorable-p["entry_price"])/p["distance"])
    p["peak_r"]=peak
    if peak>=1:
        stop=p["entry_price"]+sign*(math.floor(peak)-1)*p["distance"]
        if sign*(stop-p["stop"])>0:
            if (l<=stop if sign==1 else h>=stop):
                p["ambiguous_bars"]+=1
            p["stop"]=stop
    return p,None


class ShadowBook:
    def __init__(self,database,*,release_sha,profile,config=None):
        if database.config.market_environment!="LIVE" or profile not in {"live-paper","live-trade"}:
            raise ValueError("SHADOW_LIVE_PROFILE_REQUIRED")
        self.database=database
        self.release_sha=release_sha
        self.profile=profile
        self.config=config or ShadowConfig()
        with database.connection() as conn:
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            value=asdict(self.config)
            conn.execute("INSERT OR IGNORE INTO shadow_configurations VALUES(?,?,?,?)",
                         (release_sha,profile,encode(value),digest(value)))
            saved=conn.execute("SELECT config_json,digest FROM shadow_configurations WHERE release_sha=? AND profile=?",
                               (release_sha,profile)).fetchone()
            if verified(*saved)!=value:
                raise ValueError("SHADOW_CONFIG_CHANGED_START_NEW_RELEASE_COHORT")

    def _daily(self,conn,candidate,t,*,release=None,profile=None,config=None,pnl=None):
        release=release or self.release_sha
        profile=profile or self.profile
        cfg=config or asdict(self.config)
        row=conn.execute("SELECT state_json,digest FROM shadow_daily WHERE release_sha=? AND profile=? AND candidate_id=?",
                         (release,profile,candidate)).fetchone()
        value=verified(*row) if row else {}
        if value.get("day")!=day(t):
            value={"day":day(t),"realized_usd":0.,"peak_usd":0.,"halted":False,
                   "balance_usd":value.get("balance_usd",cfg["starting_balance_usd"])}
        if pnl is not None:
            value["balance_usd"]+=pnl
            value["realized_usd"]+=pnl
            value["peak_usd"]=max(value["peak_usd"],value["realized_usd"])
        giveback=cfg["profit_giveback_r"] if value["peak_usd"]/cfg["risk_usd"]>=cfg["daily_trigger_r"] else cfg["normal_giveback_r"]
        value["floor_usd"]=value["peak_usd"]-giveback*cfg["risk_usd"]
        value["halted"]=value["halted"] or value["realized_usd"]<value["floor_usd"] or value["balance_usd"]<cfg["notional_usd"]
        conn.execute("INSERT OR REPLACE INTO shadow_daily VALUES(?,?,?,?,?)",
                     (release,profile,candidate,encode(value),digest(value)))
        return value

    def _finish(self,conn,p,reason,now,*,eligible=False):
        p=dict(p,reason=reason,eligible=eligible,available_ms=now,authority=AUTHORITY)
        p.setdefault("closed_ms",now)
        conn.execute("INSERT INTO shadow_results VALUES(?,?,?,?,?,?,?,?)",
                     (p["id"],p["candidate_id"],p["release_sha"],p["profile"],p["closed_ms"],
                      int(eligible),encode(p),digest(p)))
        conn.execute("DELETE FROM shadow_positions WHERE id=?",(p["id"],))
        if eligible:
            self._daily(conn,p["candidate_id"],p["closed_ms"],release=p["release_sha"],
                        profile=p["profile"],config=p["config"],pnl=p["net_usd"])

    def advance(self,*,now_ms):
        """Catch up at most 96 bars per position. Never fabricate missing prices."""
        with self.database.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            positions=conn.execute("SELECT state_json,digest FROM shadow_positions").fetchall()
            latest=conn.execute("SELECT MAX(event_open_ms) FROM market_events WHERE status='COMPLETE' AND event_close_ms<? AND captured_at_ms<=?",
                                (now_ms,now_ms)).fetchone()[0]
            if latest is None: return
            for row in positions:
                p=verified(*row)
                bars=conn.execute("""SELECT c.event_open_ms,c.open_price,c.high_price,c.low_price,c.close_price
                    FROM candles_5m c JOIN market_events e USING(event_open_ms)
                    WHERE c.symbol=? AND c.event_open_ms>=? AND c.event_open_ms<=?
                      AND e.status='COMPLETE' AND e.event_close_ms<? AND e.captured_at_ms<=?
                    ORDER BY c.event_open_ms LIMIT 96""",
                    (p["symbol"],p["next_bar_ms"],latest,now_ms,now_ms)).fetchall()
                finished=False
                for bar in bars:
                    if bar[0]!=p["next_bar_ms"]:
                        self._finish(conn,p,"DATA_GAP_UNSCORABLE",now_ms)
                        finished=True
                        break
                    if p["status"]=="PENDING" and self._daily(conn,p["candidate_id"],bar[0],
                            release=p["release_sha"],profile=p["profile"],config=p["config"])["halted"]:
                        self._finish(conn,p,"DAILY_OR_BALANCE_BLOCKED",now_ms)
                        finished=True
                        break
                    p,reason=advance_bar(p,tuple(bar))
                    if reason:
                        self._finish(conn,p,reason,now_ms,eligible=reason=="STOP")
                        finished=True
                        break
                if not finished:
                    if p["next_bar_ms"]<=latest and len(bars)<96:
                        self._finish(conn,p,"DATA_GAP_UNSCORABLE",now_ms)
                    else:
                        conn.execute("UPDATE shadow_positions SET state_json=?,digest=? WHERE id=?",
                                     (encode(p),digest(p),p["id"]))

    def offer(self,*,event_ms,now_ms,opportunities,excluded=()):
        """One atomic allocation per profile/event, at most 10 GLOBAL reserved slots."""
        if now_ms<event_ms+INTERVAL_MS or now_ms>event_ms+INTERVAL_MS+30000:
            return
        with self.database.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM shadow_batches WHERE release_sha=? AND profile=? AND event_ms=?",
                            (self.release_sha,self.profile,event_ms)).fetchone():
                return
            excluded=set(excluded)
            # A served main suggestion may have entered: conservatively reserve its
            # candidate until an outcome or veto proves it is no longer outstanding.
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='served_execution_proposals'").fetchone():
                unresolved = conn.execute("""SELECT p.proposal_json,p.proposal_digest FROM served_execution_proposals p
                    WHERE p.profile IN ('live-paper','live-trade') AND p.completed_outcome_id IS NULL
                    AND NOT EXISTS(SELECT 1 FROM execution_veto_feedback v WHERE v.proposal_id=p.proposal_id)
                    LIMIT 1001""").fetchall()
                if len(unresolved)>1000: raise ValueError("SHADOW_UNRESOLVED_MAIN_LIMIT")
                for raw,check in unresolved:
                    proposal=json.loads(raw)
                    if digest(proposal)!=check: raise ValueError("SHADOW_PROPOSAL_DIGEST_MISMATCH")
                    candidate=(proposal.get("experiment_context") or {}).get("shadow_main_candidate")
                    if candidate: excluded.add(candidate)
            active=conn.execute("SELECT state_json,digest FROM shadow_positions").fetchall()
            occupied=set()
            for row in active:
                p=verified(*row)
                if p["candidate_id"] in excluded:
                    self._finish(conn,p,"MAIN_CANDIDATE_RESERVED",now_ms)
                else:
                    occupied.add(p["candidate_id"])
            counts=Counter(dict(conn.execute("""SELECT candidate_id,COUNT(*) FROM shadow_results
                WHERE release_sha=? AND profile=? AND eligible=1 GROUP BY candidate_id""",
                (self.release_sha,self.profile)).fetchall()))
            best={}
            for item in opportunities:
                name=item["candidate_id"]
                if name not in BY_ID or name in excluded or name in occupied: continue
                score=float(item["score"])
                bid,ask=float(item["bid"]),float(item["ask"])
                if not all(math.isfinite(x) for x in (score,bid,ask)) or score<=0 or not 0<bid<=ask: continue
                if item["side"] not in {"LONG","SHORT"}: raise ValueError("SHADOW_SIDE_INVALID")
                spread=(ask-bid)/((bid+ask)/2)
                if spread*100>self.config.max_spread_pct: continue
                if self._daily(conn,name,now_ms)["halted"]: continue
                key=(-score,item["symbol"],item["side"])
                if name not in best or key<best[name][0]:
                    best[name]=(key,dict(item,spread_half_frac=spread/2))
            selected=sorted(best,key=lambda name:(counts[name],tie_key(event_ms,self.profile,"SHADOW",name)))
            opened=[]
            for name in selected[:max(0,MAX_POSITIONS-len(occupied))]:
                item=best[name][1]
                identity=f"{VERSION}|{self.release_sha}|{self.profile}|{event_ms}|{name}"
                p=dict(item,id=hashlib.sha256(identity.encode()).hexdigest(),release_sha=self.release_sha,
                       profile=self.profile,version=VERSION,authority=AUTHORITY,catalog_digest=CATALOG_DIGEST,
                       config=asdict(self.config),decision_ms=now_ms,event_ms=event_ms,status="PENDING",
                       next_bar_ms=(now_ms//INTERVAL_MS+1)*INTERVAL_MS)
                conn.execute("INSERT INTO shadow_positions VALUES(?,?,?,?,?,?)",
                             (p["id"],name,self.release_sha,self.profile,encode(p),digest(p)))
                opened.append(name)
            batch={"version":VERSION,"event_ms":event_ms,"decision_ms":now_ms,
                   "opened":opened,"excluded":sorted(excluded),"authority":AUTHORITY}
            conn.execute("INSERT INTO shadow_batches VALUES(?,?,?,?,?)",
                         (self.release_sha,self.profile,event_ms,encode(batch),digest(batch)))


def shadow_report(database,*,release_sha):
    lines=["# Shadow candidate report","",
           "Simulated only. No exchange order authority. Shadow results do not train the main learner.",
           "Up to 10 global pending/open slots. Candle-based fills are not equivalent to live tick fills.",
           "Fees, fixed slippage and decision-time spread included; funding/liquidity are not modelled.",""]
    if not database.path.exists(): return "\n".join(lines+["No shadow history yet."])+"\n"
    with closing(sqlite3.connect(database.path.resolve().as_uri()+"?mode=ro",uri=True)) as conn:
        conn.execute("BEGIN")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_positions'").fetchone():
            return "\n".join(lines+["No shadow history yet."])+"\n"
        active=[verified(*r) for r in conn.execute("SELECT state_json,digest FROM shadow_positions")]
        lines += [f"Global reserved slots: {len(active)} / 10"]
        for p in active:
            lines += [f"- {p['profile']} / {p['candidate_id']} / {p['symbol']} {p['side']}: {p['status']}"]
        for profile in ("live-paper","live-trade"):
            rows=conn.execute("SELECT result_json,digest FROM shadow_results WHERE release_sha=? AND profile=? ORDER BY closed_ms DESC LIMIT 10001",
                              (release_sha,profile)).fetchall()
            results=[verified(*r) for r in rows[:10000]]
            lines += ["",f"## Alongside {profile}",f"Release: {release_sha}",
                      "Latest 10,000 results shown; unfinished positions are excluded from PnL.",
                      "| Candidate | Closed scored | Net USD | Mean R | Unscorable/cancelled |",
                      "|---|---:|---:|---:|---:|"]
            for name in BY_ID:
                group=[p for p in results if p["candidate_id"]==name]
                scored=[p for p in group if p["eligible"]]
                mean=sum(p["net_r"] for p in scored)/len(scored) if scored else 0.
                lines += [f"| {name} | {len(scored)} | {sum(p['net_usd'] for p in scored):.4f} | {mean:.4f} | {len(group)-len(scored)} |"]
            daily_rows=conn.execute("SELECT candidate_id,state_json,digest FROM shadow_daily WHERE release_sha=? AND profile=?",
                                    (release_sha,profile)).fetchall()
            lines += ["", "| Candidate daily account | UTC day | Balance USD | Realized today | Floor USD | Halted |",
                      "|---|---|---:|---:|---:|---|"]
            for name,raw,check in sorted(daily_rows):
                d=verified(raw,check)
                lines += [f"| {name} | {d['day']} | {d['balance_usd']:.2f} | {d['realized_usd']:.2f} | {d['floor_usd']:.2f} | {d['halted']} |"]
            reasons=Counter(p["reason"] for p in results if not p["eligible"])
            lines += [f"Unscorable/cancelled reasons: {dict(reasons)}",
                      f"Ambiguous bars in scored trades: {sum(p.get('ambiguous_bars',0) for p in results if p['eligible'])}"]
    lines += ["","Correlated trades are not independent evidence. No profitability or automatic mainnet approval is claimed."]
    return "\n".join(lines)+"\n"
