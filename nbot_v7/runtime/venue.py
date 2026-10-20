"""V7 bridge to selectively ported, audited V3/V5 execution lifecycles.

No credentials are read and no connection is made during construction.
The injected exchange retains its own arm files, account preflight, order IDs,
protection and ambiguous-write recovery. V7 fixes its exit policy independently.
"""
from dataclasses import replace
from pathlib import Path
from nbot.execution.entry import EntryLifecycle,EntryLifecycleConfig,EntryProposal
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.reconciliation import ReconciliationLifecycle
from nbot.execution.risk import RiskConfig,RiskManager

AUTHORITY="NBOT_V7_FROZEN_REVIEWED_BRAIN"
EXIT_POLICY="NBOT_V7_FIXED_2STOP_3TAKE_60M_V1"


class AuditedVenueTransport:
    def __init__(self,exchange,workspace,profile,policy,clock):
        if profile not in ("live-paper","live-trade","testnet-trade"):
            raise ValueError("UNSUPPORTED_V7_EXECUTION_PROFILE")
        self.exchange=exchange
        self.profile=profile
        self.policy=policy
        self.clock=clock
        self.durable=ExecutionDurableStore(Path(workspace),profile=profile)
        self.risk=RiskManager(RiskConfig(risk_per_trade_usd=policy.notional_usdt*policy.stop_fraction,
                                        max_notional_usd=policy.notional_usdt,leverage=1))
        self.emergency=EmergencyFlattener(exchange=exchange)
        self.recovery=ReconciliationLifecycle(exchange=exchange,durable=self.durable,risk=self.risk,
                                              emergency=self.emergency,now_ms=clock)
        self.entry=EntryLifecycle(exchange=exchange,state=self.durable.state,risk=self.risk,
                                 emergency=self.emergency,now_ms=clock,
                                 config=EntryLifecycleConfig(profile=profile,
                                     market_environment=self.durable.state.market_environment,
                                     allowed_entry_authorities=frozenset({AUTHORITY}),
                                     allowed_exit_policies=frozenset({EXIT_POLICY})))

    def enable_after_review(self,approval_reference):
        if not approval_reference:raise PermissionError("EXPLICIT_ENTRY_REVIEW_REQUIRED")
        # Venue guard still requires its independent authorized arm/session.
        self.recovery.reconcile()
        self.durable.state.set_entries_enabled(True)

    def submit_protected_idempotent(self,intent,policy):
        if policy!=self.policy:raise ValueError("VENUE_RISK_ENVELOPE_MISMATCH")
        now=self.clock()
        if now<intent["time_ms"] or now-intent["time_ms"]>policy.max_age_ms:
            raise ValueError("STALE_VENUE_INTENT")
        self.recovery.reconcile()
        if self.durable.outbox.pending_count():raise ValueError("PENDING_OUTCOME_DELIVERY_HOLD")
        proposal=EntryProposal(proposal_id=intent["id"],generated_at_ms=now,
                expires_at_ms=now+min(policy.max_age_ms,30000),profile=self.profile,
                market_environment=self.durable.state.market_environment,symbol=intent["symbol"],side=intent["side"],
                reference_price=intent["quote"],entry_authority=AUTHORITY,exit_policy_version=EXIT_POLICY)
        position=self.entry.execute(proposal,now_ms=now)
        return {**intent,"entry_price":position.entry_price,"quantity":position.quantity,
                "stop":position.stop_price,"target":position.entry_price*(1+(1 if position.side=="LONG" else -1)*policy.take_fraction),
                "deadline_ms":position.entry_timestamp_ms+policy.max_hold_ms,"broker_mode":"VENUE",
                "entry_client_order_id":position.entry_client_order_id,"protective_stop_id":position.protective_stop.stop_id}

    def reconcile(self,client_id=None):
        result=self.recovery.reconcile()
        position=self.durable.state.open_position
        if client_id is not None and position is not None and position.proposal_id!=client_id:
            raise ValueError("RECONCILED_POSITION_IDENTITY_MISMATCH")
        return {"status":result.status,"position":position,"pending_outcomes":self.durable.outbox.pending()}

    def poll(self):
        self.recovery.reconcile()
        position=self.durable.state.open_position
        if position is not None:
            quote=self.exchange.quote(position.symbol)
            now=self.clock()
            self.risk.check_quote(quote,now_ms=now)
            if self.profile=="live-paper":
                self.exchange.on_market_tick(symbol=position.symbol,bid=quote.bid,ask=quote.ask,timestamp_ms=quote.timestamp_ms)
                self.recovery.reconcile()
                position=self.durable.state.open_position
            if position is not None:
                sign=1 if position.side=="LONG" else -1
                executable=quote.bid if sign==1 else quote.ask
                gross=sign*(executable/position.entry_price-1)
                current_r=sign*(executable-position.entry_price)*position.quantity/position.initial_risk_usd
                self.durable.state.update_open_position(replace(position,mfe_r=max(position.mfe_r,current_r),
                                                               mae_r=min(position.mae_r,current_r)))
                if gross>=self.policy.take_fraction or now>=position.entry_timestamp_ms+self.policy.max_hold_ms:
                    self.exchange.close_position(position.symbol,position.side,reason="V7_FIXED_TARGET" if gross>=self.policy.take_fraction else "V7_FIXED_HORIZON")
                    self.recovery.reconcile()
        return self.reconcile()

    def acknowledge(self,outcome_id):
        return self.durable.outbox.acknowledge(outcome_id)
