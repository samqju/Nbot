"""Persistent one-slot trading coordinator; no historical-lab dependency."""
from dataclasses import asdict
from hashlib import sha256
import json
import math
from ..decision import watchlist,choose
from .broker import PaperBroker
from .risk import RiskPolicy


class TradingEngine:
    def __init__(self,memory,brain,broker=None,policy=None):
        self.memory=memory
        self.brain=brain
        self.broker=broker or PaperBroker()
        self.policy=policy or RiskPolicy()
        fingerprint=sha256(json.dumps(asdict(self.policy),sort_keys=True).encode()).hexdigest()
        state=memory.read()
        if "risk_sha256" in state and state["risk_sha256"]!=fingerprint:
            raise ValueError("RISK_POLICY_CHANGED_REQUIRE_RECONCILIATION")
        if "risk_sha256" not in state:
            memory.transition("RISK_FREEZE",lambda s:s.update(risk_sha256=fingerprint))
        self.memory.verify()

    def review(self,rows,review_ms,now_ms):
        if now_ms<review_ms or now_ms-review_ms>self.policy.max_age_ms:
            raise ValueError("STALE_UNIVERSE_REVIEW")
        if any(r["review_ms"]!=review_ms for r in rows):
            raise ValueError("UNSYNCHRONIZED_UNIVERSE")
        selected,predictions=watchlist(self.brain,rows)
        self.memory.transition("UNIVERSE_REVIEW",lambda s:s.update(watch=selected,watch_expires=review_ms+8*3600000),
                               {"time_ms":review_ms,"brain":self.brain.version,"scores":predictions})
        return selected

    def decide(self,rows,decision_ms,now_ms,quotes,source_ready=True):
        state=self.memory.read()
        if getattr(self.brain,"cutoff_ms",-1)>decision_ms:
            raise ValueError("MODEL_FIT_AFTER_DECISION")
        if decision_ms<=state["last_decision"]:return "DUPLICATE_DECISION"
        if any(r["decision_ms"]!=decision_ms for r in rows):raise ValueError("UNSYNCHRONIZED_CANDIDATES")
        def clock(s):
            if decision_ms<=s["last_decision"]:raise ValueError("DUPLICATE_DECISION")
            day=now_ms//86400000
            if day!=s["day"]:s.update(day=day,daily_net=0)
            s["last_decision"]=decision_ms
        state=self.memory.transition("DECISION_CLOCK",clock,{"time_ms":decision_ms})
        reason=self.policy.check(state,decision_ms,now_ms,source_ready)
        if reason is None and now_ms>=state["watch_expires"]:reason="STALE_WATCH"
        valid=[r for r in rows if r["symbol"] in state["watch"]]
        chosen=None
        scores=[]
        if reason is None:
            chosen,scores=choose(self.brain,valid)
            if chosen is None:reason="NO_TRADE"
        if reason:
            self.memory.transition("ABSTAIN",lambda s:None,{"reason":reason,"time_ms":decision_ms,"scores":scores})
            return reason
        row,prediction=chosen
        quote=quotes.get(row["symbol"])
        if quote is None or not math.isfinite(quote) or quote<=0:return "INVALID_QUOTE_HOLD"
        identity={k:row[k] for k in ("decision_ms","symbol","side","family")}
        if row["side"] not in ("LONG","SHORT"):raise ValueError("INVALID_ORDER_SIDE")
        intent={"id":sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),
                "time_ms":now_ms,"symbol":row["symbol"],"side":row["side"],"quote":quote,
                "family":row["family"],"brain":self.brain.version,"prediction":prediction}
        # Commit intent before any broker side effect; unresolved intent blocks entries.
        def reserve(s):
            hold=self.policy.check(s,decision_ms,now_ms,source_ready)
            if hold:raise ValueError(hold)
            s["pending"]=intent
        self.memory.transition("ORDER_INTENT",reserve,intent)
        try:
            position=self.broker.submit(intent,self.policy)
        except BaseException:
            self.memory.transition("BROKER_HOLD",lambda s:s.update(kill=True),{"intent_id":intent["id"]})
            raise
        self.memory.transition("ENTRY_ACK",lambda s:s.update(position=position,pending=None),{"intent_id":intent["id"]})
        return "ENTERED"

    def reconcile_paper(self):
        if self.broker.mode!="PAPER":raise PermissionError("VENUE_RECONCILIATION_REQUIRED")
        state=self.memory.read()
        if state["pending"]:
            position=self.broker.submit(state["pending"],self.policy)
            self.memory.transition("RECOVER_PAPER_INTENT",lambda s:s.update(position=position,pending=None))
        return self.memory.read()

    def on_bar(self,symbol,bar,close_ms,funding_rate=None):
        if self.broker.mode!="PAPER":raise PermissionError("LIVE_FILL_EVENTS_REQUIRE_VENUE_RECONCILIATION")
        state=self.memory.read()
        p=state["position"]
        if p is None or p["symbol"]!=symbol:return None
        if p["last_bar_ms"] is not None and bar.t>p["last_bar_ms"]+(close_ms-bar.t):
            self.kill("MISSING_POSITION_PATH_RECONCILIATION_REQUIRED")
            return None
        result,updated=self.broker.on_bar(p,bar,close_ms,self.policy,funding_rate)
        if result is None:
            self.memory.transition("PAPER_MARK",lambda s:s.update(position=updated))
            return None
        def settle(s):
            if s["position"] is None or s["position"]["id"]!=result["id"]:
                raise ValueError("POSITION_ALREADY_SETTLED")
            day=close_ms//86400000
            if s["day"]!=day:s.update(day=day,daily_net=0)
            s["equity"]+=result["net_usdt"]
            s["peak"]=max(s["peak"],s["equity"])
            s["daily_net"]+=result["net_usdt"]
            s["position"]=None
        self.memory.transition("EXIT_ACK",settle,result,outcome=(result["id"],close_ms,result))
        return result

    def kill(self,reason):
        self.memory.transition("KILL_SWITCH",lambda s:s.update(kill=True),{"reason":reason})

    def reconcile_venue(self):
        if self.broker.mode!="LIVE":raise ValueError("VENUE_BROKER_REQUIRED")
        report=self.broker.poll()
        for pending in report["pending_outcomes"]:
            payload=pending["payload"]
            identity=payload["proposal_id"]
            existing=self.memory.conn.execute("SELECT 1 FROM outcome WHERE id=?",("venue:"+pending["record_id"],)).fetchone()
            if not existing:
                state=self.memory.read()
                local=state["position"] or state["pending"]
                if local is None or local["id"]!=identity:
                    self.kill("UNMATCHED_VENUE_CLOSE_REQUIRES_OPERATOR_RECONCILIATION")
                    raise ValueError("VENUE_CLOSE_IDENTITY_MISMATCH")
                def settle(s):
                    day=payload["closed_timestamp_ms"]//86400000
                    if s["day"]!=day:s.update(day=day,daily_net=0)
                    s["equity"]+=payload["realized_pnl_usd"]
                    s["peak"]=max(s["peak"],s["equity"])
                    s["daily_net"]+=payload["realized_pnl_usd"]
                    s.update(position=None,pending=None)
                self.memory.transition("VENUE_CLOSE_ACK",settle,payload,
                    outcome=("venue:"+pending["record_id"],payload["closed_timestamp_ms"],payload))
            self.broker.transport.acknowledge(pending["record_id"])
        native=report["position"]
        state=self.memory.read()
        if native is not None:
            local=state["position"] or state["pending"]
            if local is None or local["id"]!=native.proposal_id:
                self.kill("UNMANAGED_OR_MISMATCHED_VENUE_POSITION")
                raise ValueError("VENUE_POSITION_IDENTITY_MISMATCH")
            recovered={**local,"entry_price":native.entry_price,"quantity":native.quantity,
                       "stop":native.stop_price,"target":native.entry_price*(1+(1 if native.side=="LONG" else -1)*self.policy.take_fraction),
                       "deadline_ms":native.entry_timestamp_ms+self.policy.max_hold_ms,"broker_mode":"VENUE"}
            self.memory.transition("VENUE_POSITION_RECONCILED",lambda s:s.update(position=recovered,pending=None))
        elif state["position"] is not None or state["pending"] is not None:
            self.kill("MISSING_AUTHORITATIVE_VENUE_ACCOUNTING")
            raise ValueError("UNRESOLVED_VENUE_ACCOUNTING")
        return report["status"]
