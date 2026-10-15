"""G10 offline Challenger-versus-Champion comparison, NEVER a promoter.

Both books are synthetic, separate from Research and each other. The same
prospective public-shaped market events, quote/cost assumptions, and risk
policy are applied to two frozen models; G9's PAPER/REAL release remains
unconditionally prohibited. Lab recommendations are nonactionable.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from .learning_contract import canonical
from .paper_contract import (
    PaperPolicy,PaperQuote,PaperCosts,SignedLabProposal,PaperHold,
    LAB_GRADE,sha,dec)
from .paper_lab import ChampionLabPaperBook
from .research_journal import ResearchJournal,JournalHold

VERSION="NBOT_V5_1_G10_LAB_COMPARE_V1"
CHAMPION="CHAMPION_LAB_ONLY"
CHALLENGER="CHALLENGER_LAB_ONLY"
MAX_EVENTS=1000
REQUIRED_SETTLES=100
REQUIRED_FURTHER_ORIGINAL=2000


@dataclass(frozen=True)
class LabChallengerCohort:
    """A separate 2k *synthetic* testing population is not original science."""
    sample_count:int
    effective_btc_blocks:int
    first_ms:int
    last_ms:int
    evidence_sha256:str
    source_grade:str=LAB_GRADE
    independently_original_qualified:int=0
    scientific_challenger_authority:str="NONE"

    def validate(self):
        if (type(self.sample_count) is not int or
            not REQUIRED_FURTHER_ORIGINAL<=self.sample_count<=10000 or
            type(self.effective_btc_blocks) is not int or
            not 1<=self.effective_btc_blocks<=self.sample_count or
            type(self.first_ms) is not int or
            type(self.last_ms) is not int or
            not 0<=self.first_ms<self.last_ms or
            not sha(self.evidence_sha256) or
            self.source_grade!=LAB_GRADE or
            self.independently_original_qualified!=0 or
            self.scientific_challenger_authority!="NONE"):
            raise PaperHold("G10_CHALLENGER_COHORT_NOT_LAB_SAFE")
        return self


@dataclass(frozen=True)
class CompetitionProtocol:
    champion_sha256:str
    challenger_sha256:str
    policy_sha256:str
    cohort_sha256:str
    frozen_at_ms:int
    start_ms:int
    end_ms:int
    maximum_events:int=MAX_EVENTS
    minimum_common_market_events:int=100
    minimum_paper_settled_per_model:int=REQUIRED_SETTLES
    minimum_regimes:int=2
    max_drawdown_fraction:str="0.05"
    improvement_buffer_fraction:str="0.02"
    source_grade:str=LAB_GRADE
    paper_release_authority:str="NONE"
    route_change_authority:str="NONE"

    def validate(self,policy:PaperPolicy,cohort:LabChallengerCohort):
        policy.validate();cohort.validate()
        if (not all(sha(x) for x in (self.champion_sha256,
                self.challenger_sha256,self.policy_sha256,self.cohort_sha256))
            or self.champion_sha256==self.challenger_sha256
            or self.policy_sha256!=policy.digest()
            or self.cohort_sha256!=cohort.evidence_sha256
            or type(self.frozen_at_ms) is not int
            or type(self.start_ms) is not int
            or type(self.end_ms) is not int
            or not 0<=self.frozen_at_ms<self.start_ms<self.end_ms
            or self.frozen_at_ms<=cohort.last_ms
            or type(self.maximum_events) is not int
            or not 100<=self.maximum_events<=MAX_EVENTS
            or type(self.minimum_common_market_events) is not int
            or not 100<=self.minimum_common_market_events<=self.maximum_events
            or type(self.minimum_paper_settled_per_model) is not int
            or self.minimum_paper_settled_per_model!=REQUIRED_SETTLES
            or type(self.minimum_regimes) is not int
            or not 2<=self.minimum_regimes<=10
            or self.source_grade!=LAB_GRADE
            or self.paper_release_authority!="NONE"
            or self.route_change_authority!="NONE"):
            raise PaperHold("G10_COMPETITION_NOT_FROZEN_OR_RELEASE_CLAIM")
        drawdown=dec(self.max_drawdown_fraction,True)
        buffer=dec(self.improvement_buffer_fraction,True)
        if (drawdown>dec(policy.max_drawdown_fraction)
            or not Decimal("0.005")<=buffer<=Decimal(".20")):
            raise PaperHold("G10_COMPARISON_RISK_OR_BUFFER_WEAK")
        return self

    def digest(self):
        return sha256(canonical({"version":VERSION,"policy":self.__dict__})).hexdigest()


@dataclass(frozen=True)
class SharedLabEvent:
    event_sha256:str
    at_ms:int
    btc_regime:str
    market_regime:str
    quote:PaperQuote
    costs:PaperCosts
    champion:SignedLabProposal|None
    challenger:SignedLabProposal|None


@dataclass(frozen=True)
class EventAudit:
    event_sha256:str
    at_ms:int
    source_sha256:str
    source_grade:str
    btc_regime:str
    market_regime:str
    champion_result:str
    challenger_result:str
    champion_occupied:bool
    challenger_occupied:bool
    champion_cash:str
    challenger_cash:str
    authority:str="NONE"


@dataclass(frozen=True)
class CompetitionReview:
    version:str
    protocol_sha256:str
    shared_event_head_sha256:str
    common_events:int
    regimes:int
    champion_settled_lab:int
    challenger_settled_lab:int
    champion_abstained:int
    challenger_abstained:int
    champion_vetoed:int
    challenger_vetoed:int
    champion_censored:int
    challenger_censored:int
    champion_occupied:bool
    challenger_occupied:bool
    champion_net_cash_return:str
    challenger_net_cash_return:str
    champion_drawdown_fraction:str
    challenger_drawdown_fraction:str
    independent_original_outcomes:int=0
    genuine_paper_settlements:int=0
    scientific_challenger_approved:bool=False
    fair_real_paper_comparison:bool=False
    laboratory_diagnostic:str="LAB_HOLD"
    action:str="HOLD"
    active_champion_sha256:str=""
    financial_authority:str="NONE"


class DualBookCompetition:
    """Two separately journaled LAB books fed one deterministic event stream.

    Never shares cash/position or model keys. The shared audit journal is
    separately hashed and fsynced; replay is read-only, restart LOCKED.
    This is OFFLINE mock comparison, not an order-capable multi-model runner.
    """
    def __init__(self,*,champion_journal:ResearchJournal,
                 challenger_journal:ResearchJournal,review_journal:ResearchJournal,
                 policy:PaperPolicy,cohort:LabChallengerCohort,
                 protocol:CompetitionProtocol,champion_key:bytes,
                 challenger_key:bytes):
        protocol.validate(policy,cohort)
        if (not all(type(j) is ResearchJournal for j in
                (champion_journal,challenger_journal,review_journal)) or
            len({str(j.path) for j in
                (champion_journal,challenger_journal,review_journal)})!=3 or
            type(champion_key) is not bytes or len(champion_key)<32 or
            type(challenger_key) is not bytes or len(challenger_key)<32 or
            champion_key==challenger_key):
            raise PaperHold("G10_BOOKS_NOT_INDEPENDENT")
        self.policy=policy
        self.cohort=cohort
        self.protocol=protocol
        self.books={
          CHAMPION:ChampionLabPaperBook(champion_journal,
            policy=policy,model_sha256=protocol.champion_sha256,
            lab_key=champion_key,book_label=CHAMPION),
          CHALLENGER:ChampionLabPaperBook(challenger_journal,
            policy=policy,model_sha256=protocol.challenger_sha256,
            lab_key=challenger_key,book_label=CHALLENGER),
        }
        self.journal=review_journal
        self._rows,self.head=self.journal.replay()
        self.events=[]
        self.last_at_ms=-1
        # Never resume a running forward contest blindly. If another process
        # previously wrote review state or an open position exists, HOLD.
        self.restarted=bool(self._rows) or any(x.restart_hold for x in self.books.values())
        self._verify_reviews(self._rows)

    def _verify_reviews(self,rows):
        seen=set()
        last=-1
        for row in rows:
            p=row["payload"]
            if (row["action"]!="REVIEW" or
                p.get("schema")!=VERSION or
                p.get("protocol")!=self.protocol.digest() or
                p.get("grade")!=LAB_GRADE or
                p.get("authority")!="NONE" or
                not sha(p.get("event_sha256")) or
                p["event_sha256"] in seen or
                type(row["at_ms"]) is not int or
                row["at_ms"]<=last):
                raise PaperHold("G10_SHARED_JOURNAL_TAMPER_OR_CLOCK")
            seen.add(p["event_sha256"]);last=row["at_ms"]

    def _state(self,book):
        return self.books[book].state

    def step(self,event:SharedLabEvent):
        if self.restarted:
            raise PaperHold("G10_RESTART_LOCKED_NO_AUTOMATIC_COMPARISON")
        if type(event) is not SharedLabEvent:
            raise PaperHold("G10_EVENT_TYPE")
        p=self.protocol
        if (len(self.events)>=p.maximum_events or
            type(event.at_ms) is not int or
            not p.start_ms<=event.at_ms<p.end_ms or
            event.at_ms<=self.last_at_ms or
            not sha(event.event_sha256) or
            event.event_sha256 in {x.event_sha256 for x in self.events} or
            event.btc_regime not in ("UP","DOWN","RANGE","TRANSITION") or
            event.market_regime not in ("UP","DOWN","RANGE","TRANSITION") or
            type(event.quote) is not PaperQuote or
            type(event.costs) is not PaperCosts or
            event.quote.grade!=LAB_GRADE or event.costs.grade!=LAB_GRADE or
            event.quote.original_verified or event.costs.original_verified or
            not sha(event.quote.sha256) or
            event.costs.settled_through_ms<event.at_ms or
            event.costs.funding_from_ms is None or
            event.costs.funding_from_ms>event.at_ms):
            raise PaperHold("G10_UNSHARED_OR_UNVERIFIED_MARKET_EVENT")
        # Note: a real market-data feed would require a separate ORIGINAL
        # source attestation; this event SHA is only a LAB fixture identity.
        outcomes={}
        for label,recommendation in (
            (CHAMPION,event.champion),(CHALLENGER,event.challenger)):
            book=self.books[label]
            if book.state.occupied:
                mark=book.simulate_mark_or_exit(event.quote,event.costs,now_ms=event.at_ms)
                outcomes[label]=mark["status"]
            else:
                outcomes[label]="NO_TRADE"
            if recommendation is not None:
                # No proposal may be time-skewed or based on the other model.
                if (type(recommendation) is not SignedLabProposal or
                    recommendation.at_ms!=event.at_ms or
                    recommendation.source_sha256!=event.quote.sha256 or
                    recommendation.book!=label or
                    recommendation.model_sha256!=(
                       p.champion_sha256 if label==CHAMPION else p.challenger_sha256)):
                    raise PaperHold("G10_MODEL_SOURCE_OR_DECISION_MISMATCH")
                admission=book.simulate_entry(recommendation,event.quote,
                         event.costs,now_ms=event.at_ms)
                outcomes[label]=admission["status"]
        # Commit shared event AFTER both independent journal operations.
        # If interrupted between writes, next startup cannot silently
        # resume; independent ledgers remain audit/restart-held.
        payload={"schema":VERSION,"protocol":p.digest(),
                 "event_sha256":event.event_sha256,
                 "source_sha256":event.quote.sha256,
                 "grade":LAB_GRADE,"authority":"NONE",
                 "champion":outcomes[CHAMPION],
                 "challenger":outcomes[CHALLENGER],
                 "champion_head":self._state(CHAMPION).journal_head,
                 "challenger_head":self._state(CHALLENGER).journal_head,
                 "btc_regime":event.btc_regime,
                 "market_regime":event.market_regime}
        try:
            self.head=self.journal.append("REVIEW",event.at_ms,payload,
                                          expected_head=self.head)
        except (JournalHold,OSError):
            self.restarted=True
            raise
        item=EventAudit(event.event_sha256,event.at_ms,event.quote.sha256,
                 LAB_GRADE,event.btc_regime,event.market_regime,
                 outcomes[CHAMPION],outcomes[CHALLENGER],
                 self._state(CHAMPION).occupied,
                 self._state(CHALLENGER).occupied,
                 self._state(CHAMPION).cash,
                 self._state(CHALLENGER).cash)
        self.events.append(item);self.last_at_ms=event.at_ms
        return item

    def review(self):
        p=self.protocol
        self._verify_reviews(self.journal.replay()[0])
        total=len(self.events)
        if total!=len(self.journal.replay()[0]):
            raise PaperHold("G10_REVIEW_RESTART_OR_LOST_EVENT")
        settled=[self._state(x).settled for x in (CHAMPION,CHALLENGER)]
        censored=[self._state(x).censored for x in (CHAMPION,CHALLENGER)]
        abstained=[sum(getattr(e,("champion_result" if i==0 else
                     "challenger_result"))=="NO_TRADE" for e in self.events)
                    for i in (0,1)]
        vetoed=[sum(getattr(e,("champion_result" if i==0 else
                    "challenger_result"))=="LAB_VETO_NO_PAPER" for e in self.events)
                for i in (0,1)]
        regimes=len({(e.btc_regime,e.market_regime) for e in self.events})
        cash=[dec(self._state(x).cash) for x in (CHAMPION,CHALLENGER)]
        initial=dec(self.policy.capital)
        returns=[(v-initial)/initial for v in cash]
        dd=[dec(self._state(x).drawdown_fraction) for x in (CHAMPION,CHALLENGER)]
        diagnostic="LAB_HOLD"
        if (total>=p.minimum_common_market_events and
            min(settled)>=REQUIRED_SETTLES and
            regimes>=p.minimum_regimes and
            not any(self._state(x).occupied or self._state(x).held for x in
                    (CHAMPION,CHALLENGER)) and
            sum(censored)==0):
            if dd[1]>dec(p.max_drawdown_fraction) or dd[1]>dd[0]+Decimal(".01"):
                diagnostic="LAB_REJECT_RISK"
            elif returns[1]>returns[0]+dec(p.improvement_buffer_fraction):
                diagnostic="LAB_WOULD_RECOMMEND_PROMOTE_NOT_ACTIONABLE"
            elif returns[1]<=returns[0]:
                diagnostic="LAB_RETAIN_INCUMBENT"
            else:
                diagnostic="LAB_HOLD_INCONCLUSIVE"
        head=sha256(canonical([{"id":x.event_sha256,"ms":x.at_ms}
                              for x in self.events])).hexdigest()
        return CompetitionReview(VERSION,p.digest(),head,total,regimes,
             settled[0],settled[1],abstained[0],abstained[1],
             vetoed[0],vetoed[1],censored[0],censored[1],
             self._state(CHAMPION).occupied,self._state(CHALLENGER).occupied,
             str(returns[0]),str(returns[1]),str(dd[0]),str(dd[1]),
             laboratory_diagnostic=diagnostic,active_champion_sha256=p.champion_sha256)


def approve_model_promotion(*args,**kwargs):
    raise PaperHold("G10_GENUINE_TWO_MODEL_OWNER_PROMOTION_NOT_AUTHORIZED")


def authorize_challenger_paper(*args,**kwargs):
    raise PaperHold("G10_G7_NEW_2000_ORIGINAL_COHORT_AND_PAPER_RELEASE_MISSING")
