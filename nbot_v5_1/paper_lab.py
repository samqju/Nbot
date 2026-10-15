"""G9 Champion-FIRST offline paper-like SIMULATOR, never enabled PAPER mode.

Uses G5 fsynced SHA-chain journal only in a separate G9 LAB file. Every
state transition has LAB_SIMULATION_ONLY, financial_authority=NONE, zero
exchange orders. Restart is LOCKED; unfinished synthetic position is
RESTART_HOLD, not an assumed flat book. No auto-start or network imports.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from decimal import Decimal
from pathlib import Path

from .paper_contract import (
    PaperPolicy,SignedLabProposal,PaperQuote,PaperCosts,PaperHold,
    assess_lab_proposal,dec,LAB_GRADE,sha,LAB_BOOKS)
from .research_journal import ResearchJournal,JournalHold

VERSION="NBOT_V5_1_G9_CHAMPION_LAB_BOOK_V1"
LAB_ONLY="CHAMPION_LAB_ONLY"
ACTIONS=frozenset({"ADMIT","TRAIL_CHECKPOINT","TERMINAL","PATH_HOLD"})
_ZERO=Decimal(0)


@dataclass(frozen=True)
class LabPaperState:
    status:str
    cash:str
    realized_net:str
    fees:str
    funding:str
    drawdown_fraction:str
    occupied:bool
    held:bool
    position:dict|None
    settled:int
    censored:int
    journal_head:str
    financial_authority:str="NONE"
    paper_authority:str="NONE"
    exchange_orders:int=0


class ChampionLabPaperBook:
    def __init__(self,journal:ResearchJournal,*,policy:PaperPolicy,
                 model_sha256:str,lab_key:bytes,
                 book_label:str="CHAMPION_LAB_ONLY"):
        if (type(journal) is not ResearchJournal or type(policy) is not PaperPolicy
                or not sha(model_sha256) or type(lab_key) is not bytes
                or len(lab_key)<32 or book_label not in LAB_BOOKS):
            raise PaperHold("G9_BOOK_CONFIG_INVALID")
        self.journal=journal
        self.policy=policy.validate()
        self.model_sha256=model_sha256
        self.lab_key=lab_key
        self.book_label=book_label
        rows,head=self.journal.replay()
        self.head=head
        self._rows=rows
        self._seen={}
        self.state=self._project(rows,head)
        # A lab constructor never grants a paper release; even a clean
        # process restart must begin LOCKED. Fresh empty lab is test-only.
        self.restart_hold=bool(self.state.occupied)

    def _project(self,rows,head):
        cash=dec(self.policy.capital,True);start=cash;peak=cash
        realized=_ZERO;fees=_ZERO;funding=_ZERO;pos=None;held=False
        settled=censored=0
        decisions=set();last_ms=-1
        for item in rows:
            action=item["action"];body=item["payload"]
            if (action not in ACTIONS or
                body.get("schema")!=VERSION or
                body.get("model_sha256")!=self.model_sha256 or
                body.get("policy_sha256")!=self.policy.digest() or
                body.get("grade")!=LAB_GRADE or
                body.get("authority")!="NONE" or
                body.get("book")!=self.book_label or
                item["at_ms"]<last_ms):
                raise PaperHold("G9_LEDGER_SCHEMA_OR_CLOCK_OR_AUTHORITY")
            last_ms=item["at_ms"]
            try:
                if action=="ADMIT":
                    if pos is not None:raise PaperHold("G9_DUPLICATE_OCCUPANCY")
                    if body["decision_id"] in decisions:
                        raise PaperHold("G9_DECISION_REPLAY")
                    decisions.add(body["decision_id"])
                    for key in ("entry","qty","entry_fee","stop","target","initial_stop"):
                        dec(body[key],True)
                    if not sha(body["decision_id"]) or body["side"] not in ("LONG","SHORT"):
                        raise PaperHold("G9_BAD_ADMISSION")
                    entry=dec(body["entry"]);qty=dec(body["qty"])
                    fee=dec(body["entry_fee"])
                    if dec(body["initial_stop"])!=dec(body["stop"]):
                        raise PaperHold("G9_ADMISSION_STOP_REWRITTEN")
                    risk=abs(entry-dec(body["stop"]))*qty
                    exposure=entry*qty
                    if (risk<=0 or
                        risk>cash*dec(self.policy.max_open_risk) or
                        exposure>cash*dec(self.policy.max_exposure_multiple) or
                        fee>cash):
                        raise PaperHold("G9_LEDGER_RISK_VIOLATION")
                    fees+=fee
                    cash=start+realized-fee
                    pos=dict(body)
                elif action=="TRAIL_CHECKPOINT":
                    if pos is None or held or body.get("decision_id")!=pos["decision_id"]:
                        raise PaperHold("G9_TRAILING_ORPHAN_OR_HELD")
                    new=dec(body["stop"],True);old=dec(pos["stop"])
                    if ((pos["side"]=="LONG" and new<old) or
                        (pos["side"]=="SHORT" and new>old)):
                        raise PaperHold("G9_TRAIL_LOOSENING")
                    pos["stop"]=str(new)
                elif action=="PATH_HOLD":
                    if pos is None or body.get("decision_id")!=pos["decision_id"]:
                        raise PaperHold("G9_HOLD_ORPHAN")
                    held=True
                elif action=="TERMINAL":
                    if pos is None or body.get("decision_id")!=pos["decision_id"]:
                        raise PaperHold("G9_ORPHAN_OR_DUPLICATE_TERMINAL")
                    if body.get("result")=="LAB_CENSORED":
                        # No invented exit/outcome; the entry fee remains
                        # a debit in the audited LAB cash reconciliation.
                        realized-=dec(pos["entry_fee"])
                        cash=start+realized
                        censored+=1
                    elif body.get("result")=="LAB_SIMULATED_SETTLEMENT":
                        if held:raise PaperHold("G9_HELD_POSITION_FALSE_SETTLEMENT")
                        qty=dec(pos["qty"]);exitp=dec(body["exit"],True)
                        closefee=dec(body["exit_fee"])
                        fund=dec(body["funding"])
                        side=Decimal(1 if pos["side"]=="LONG" else -1)
                        gross=(exitp-dec(pos["entry"]))*qty*side
                        net=gross-closefee-fund-dec(pos["entry_fee"])
                        if (gross!=dec(body["gross"]) or net!=dec(body["net"])
                                or body.get("reason") not in ("STOP","TARGET","HORIZON")):
                            raise PaperHold("G9_LEDGER_GROSS_NET_RECONCILE")
                        fees+=closefee;funding+=fund;realized+=net
                        cash=start+realized
                        settled+=1
                        peak=max(peak,cash)
                    else:raise PaperHold("G9_TERMINAL_TYPE")
                    pos=None;held=False
            except (KeyError,TypeError,ValueError) as e:
                if isinstance(e,PaperHold):raise
                raise PaperHold("G9_MALFORMED_LEDGER_RECORD") from e
        if cash!=start+realized-(dec(pos["entry_fee"]) if pos is not None else _ZERO):
            raise PaperHold("G9_CASH_LEDGER_ACCOUNTING_MISMATCH")
        dd=max(_ZERO,(peak-cash)/peak)
        return LabPaperState("LOCKED_RESTART_HOLD" if pos is not None
                             else "LAB_LOCKED_NO_PAPER_RELEASE",
             str(cash),str(realized),str(fees),str(funding),str(dd),
             pos is not None,held or pos is not None,
             pos,settled,censored,head)

    def _append(self,action,at_ms,body):
        # Validate next state first only when the journal append has succeeded;
        # a disk error MUST never silently update RAM balances/capacity.
        payload={"schema":VERSION,"book":self.book_label,
                 "model_sha256":self.model_sha256,
                 "policy_sha256":self.policy.digest(),
                 "grade":LAB_GRADE,"authority":"NONE",**body}
        try:
            self.head=self.journal.append(action,at_ms,payload,
                                          expected_head=self.head)
            rows,head=self.journal.replay()
            state=self._project(rows,head)
            self._rows=rows
            self.state=state
            return state
        except (JournalHold,OSError,ValueError):
            # Partial/torn write means reopening must fail closed.
            self.restart_hold=True
            raise

    def simulate_entry(self,proposal:SignedLabProposal,quote:PaperQuote,
                       costs:PaperCosts,*,now_ms:int):
        if self.restart_hold:
            raise PaperHold("G9_RESTART_ISOLATION_HOLD")
        veto=assess_lab_proposal(proposal=proposal,quote=quote,costs=costs,
             policy=self.policy,known_model_sha256=self.model_sha256,
             lab_key=self.lab_key,now_ms=now_ms,
             expected_book=self.book_label,
             occupied=self.state.occupied,
             halted=dec(self.state.drawdown_fraction)>=dec(
                     self.policy.max_drawdown_fraction))
        if veto.reasons:
            return {"status":"LAB_VETO_NO_PAPER","reasons":veto.reasons,
                    "exchange_orders":0}
        if proposal.decision_id in {r["payload"].get("decision_id")
                for r in self._rows if r["action"]=="ADMIT"}:
            return {"status":"LAB_VETO_NO_PAPER","reasons":("DECISION_REPLAY",),
                    "exchange_orders":0}
        slip=dec(costs.slippage_rate)
        entry=(dec(quote.ask)*(1+slip) if proposal.side=="LONG"
               else dec(quote.bid)*(1-slip))
        stop=dec(proposal.stop)
        direction=1 if proposal.side=="LONG" else -1
        per_unit=(entry-stop)*direction
        if per_unit<=0:
            raise PaperHold("G9_GEOMETRY_INVALID")
        cash=dec(self.state.cash)
        risk=cash*dec(self.policy.risk_fraction)
        qty=min(risk/per_unit,cash*dec(self.policy.max_exposure_multiple)/entry)
        if qty<=0:raise PaperHold("G9_ZERO_SIZE")
        fee=qty*entry*dec(costs.fee_rate)
        if fee>=cash:raise PaperHold("G9_FEE_EXCEEDS_CASH")
        self._append("ADMIT",now_ms,{
             "decision_id":proposal.decision_id,"symbol":proposal.symbol,
             "side":proposal.side,"entry":str(entry),"qty":str(qty),
             "stop":str(stop),"initial_stop":str(stop),
             "target":str(dec(proposal.target)),
             "entry_fee":str(fee),"entered_ms":now_ms,
             "quote_sha256":quote.sha256,
             "cost_sha256":costs.fee_sha256,
             "source_sha256":proposal.source_sha256})
        return {"status":"SYNTHETIC_LAB_OPEN_NOT_PAPER",
                "occupied":True,"exchange_orders":0}

    def simulate_mark_or_exit(self,quote:PaperQuote,costs:PaperCosts,
                              *,now_ms:int,trailing_stop:str|None=None):
        if self.restart_hold:
            raise PaperHold("G9_RESTART_HOLD_NO_AUTOMATIC_EXIT")
        pos=self.state.position
        if pos is None:raise PaperHold("G9_NO_ACTIVE_LAB_POSITION")
        if type(now_ms) is not int or now_ms<=pos["entered_ms"]:
            raise PaperHold("G9_MARK_NOT_FORWARD")
        reasons=assess_lab_proposal(proposal=None,quote=None,costs=costs,
              policy=self.policy,known_model_sha256=self.model_sha256,
              lab_key=self.lab_key,now_ms=now_ms).reasons
        reasons=tuple(x for x in reasons if x not in
                      ("PROPOSAL_MISSING_OR_MALFORMED","QUOTE_MISSING"))
        if (type(quote) is not PaperQuote or
            quote.symbol!=pos["symbol"] or quote.grade!=LAB_GRADE or
            quote.original_verified or not sha(quote.sha256) or
            type(quote.at_ms) is not int or
            not 0<=now_ms-quote.at_ms<=self.policy.max_quote_age_ms):
            reasons+=("EXIT_QUOTE_UNQUALIFIED",)
        try:
            bid,ask=dec(quote.bid,True),dec(quote.ask,True)
            if bid>=ask or (ask-bid)/bid>dec(self.policy.max_spread_fraction):
                reasons+=("EXIT_SPREAD_BAD",)
        except (PaperHold,AttributeError):
            reasons+=("EXIT_QUOTE_INVALID",)
        if (type(costs) is PaperCosts and
                (type(costs.funding_from_ms) is not int or
                 costs.funding_from_ms>pos["entered_ms"])):
            reasons+=("FUNDING_HOLDING_PERIOD_NOT_COVERED",)
        if reasons:
            self._append("PATH_HOLD",now_ms,{"decision_id":pos["decision_id"],
                  "reasons":list(sorted(set(reasons)))})
            self.restart_hold=True
            return {"status":"SOURCE_OR_COST_HOLD", "exchange_orders":0}
        side=Decimal(1 if pos["side"]=="LONG" else -1)
        mark=bid if side==1 else ask
        stop=dec(pos["stop"]);target=dec(pos["target"])
        hit_stop=(mark-stop)*side<=0
        hit_target=(mark-target)*side>=0
        if hit_stop and hit_target:
            self._append("PATH_HOLD",now_ms,{"decision_id":pos["decision_id"],
                   "reasons":["G9_AMBIGUOUS_EXIT"]})
            self.restart_hold=True
            return {"status":"SOURCE_OR_COST_HOLD","exchange_orders":0}
        reason=("STOP" if hit_stop else "TARGET" if hit_target else
             "HORIZON" if now_ms-pos["entered_ms"]>=self.policy.max_duration_ms
             else None)
        if reason is None:
            if trailing_stop is not None:
                new=dec(trailing_stop,True)
                if (side==1 and new<stop) or (side==-1 and new>stop):
                    raise PaperHold("G9_TRAIL_CANNOT_LOOSEN")
                if new!=stop:
                    self._append("TRAIL_CHECKPOINT",now_ms,
                       {"decision_id":pos["decision_id"],"stop":str(new)})
            return {"status":"LAB_STILL_OCCUPIED","exchange_orders":0}
        slip=dec(costs.slippage_rate)
        exit_price=(bid*(1-slip) if side==1 else ask*(1+slip))
        qty=dec(pos["qty"])
        gross=(exit_price-dec(pos["entry"]))*qty*side
        fee=exit_price*qty*dec(costs.fee_rate)
        funding=dec(costs.funding_cash_quote)
        net=gross-fee-funding-dec(pos["entry_fee"])
        self._append("TERMINAL",now_ms,{
            "decision_id":pos["decision_id"],
            "result":"LAB_SIMULATED_SETTLEMENT","reason":reason,
            "exit":str(exit_price),"gross":str(gross),"exit_fee":str(fee),
            "funding":str(funding),"net":str(net),
            "quote_sha256":quote.sha256,
            "cost_sha256":costs.fee_sha256})
        return {"status":"LAB_SIMULATED_SETTLEMENT_NOT_PAPER",
                "net_quote":str(net),"reason":reason,"exchange_orders":0}

    def censor_held_lab(self,*,now_ms:int,reason:str):
        if (not self.state.occupied or not self.restart_hold or
                type(now_ms) is not int or not 0<=now_ms or
                type(reason) is not str or not reason.isupper() or
                len(reason)>72):
            raise PaperHold("G9_CENSOR_NOT_ALLOWED")
        self._append("TERMINAL",now_ms,{"decision_id":
             self.state.position["decision_id"],"result":"LAB_CENSORED",
             "reason":reason})
        # Even after censure, a reopened instance must not imply paper
        # authority. New LAB trial may resume only with new instance.
        return {"status":"LAB_CENSORED_UNQUALIFIED","exchange_orders":0}

def real_paper_entry(*args,**kwargs):
    raise PaperHold("G9_OWNER_APPROVED_CHAMPION_PAPER_RELEASE_NOT_AVAILABLE")
