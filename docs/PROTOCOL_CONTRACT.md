# NBOT V3 Control Protocol Contract

Status: **Frozen by V3.5**

Protocol namespace:

`NBOT_V3_EXECUTION_V1`

Proposal schema:

`NBOT_V3_EXECUTION_PROPOSAL_V1`

Outcome schema:

`NBOT_V3_EXECUTION_OUTCOME_V1`

The Python source of truth is `nbot/communication/contracts.py` plus the
runtime-independent validators in `nbot/communication/validation.py`.  Changing
wire meaning requires a new version; an evaluated version is never silently
mutated.

## Authority boundary

The control protocol carries advisory capital-boundary messages.  It never
carries Binance credentials and never grants Observation order authority.
Execution independently owns current market/account truth, sizing, entry,
protection, position management, reconciliation and emergency action.

V3.5 permits only the explicitly non-economic Testnet recommendation authority:

`TESTNET_OPERATIONAL_CANARY_V1`

It is labelled `TESTNET_OPERATIONAL_ONLY` and cannot become LIVE economic
research evidence.  V3.4.6 Research Champion evaluation and the V3.4.7
Continuous Learning Foundation are implemented and remain
`RESEARCH_ONLY_NO_EXECUTION`.  A valid evaluator result may still be no Research
Champion; the control path must never invent or infer one.  Until V3.8 supplies
a valid research-facing authority, or deliberately runs the roadmap-approved
non-promotional dry mode, `live-paper` readiness remains fail closed as
`NOT_READY`.  `live-trade` remote control remains forbidden before V3.10.

## Transport

Observation exposes only:

- `GET /health`
- `POST /trade-request`
- `POST /execution-outcome`

Every request requires a strong bearer token.  Plain HTTP is accepted only on
loopback for local validation; a non-loopback bind/client requires TLS.  Request
and response sizes and I/O time are bounded.  Handlers never perform training
or broad-market scanning.

## TradeRequest

A request is valid only while Execution is `FLAT` and includes protocol,
request/time identity, profile/environment/mode, execution instance, supported
proposal schema and Execution release SHA.  Optional previous-proposal veto
feedback is explicit and is never interpreted as a market loss.

Observation verifies profile/environment/release identity, freshness and
request-id idempotency.  A duplicate request ID with different payload is a
collision and fails closed.

## TradeResponse / ExecutionProposal

Response status is exactly one of:

- `PROPOSAL`
- `NO_TRADE`
- `NOT_READY`

Network/HTTP failure is never converted to `PROPOSAL`.

A proposal binds at least profile/environment/evidence lineage, symbol/side,
market event, data generation, feature/selector/authority/exit-policy versions,
reference price, rank/score, optional expected after-cost Net-R and immutable
source/model digests.  A proposal has generated/expiry timestamps and a unique
proposal ID.

Execution stores the complete validated proposal receipt durably before it can
be adapted into the local `EntryProposal`.  Reuse of one proposal ID with a
different payload fails closed.  Execution never falls back to a local strategy
or stale cached proposal when Observation is unavailable.

## ExecutionOutcome / ACK

Execution completes its local accounting first and persists the existing
Execution outbox before network delivery.  The remote client reconstructs the
wire outcome by joining that execution truth with the durable proposal receipt,
so the returned outcome preserves exact research/proposal lineage without
requiring Execution position code to own research state.

Observation accepts an outcome only when its proposal and request are known and
all immutable proposal metadata match.  Outcome IDs are idempotent: the same
outcome returns `ALREADY_RECORDED`; an ID collision or second distinct outcome
for one proposal fails closed.

ACK status is exactly:

- `RECORDED`
- `ALREADY_RECORDED`

Execution removes its local pending outcome only after a valid ACK for the
exact outcome ID.  Network failure, bad ACK, wrong profile/lineage or receiver
failure leaves the pending outcome intact and therefore blocks the normal next
trade-request ordering already enforced by Execution.

## Open-position rule

No normal V3 control request belongs in the open-position hot path.  V3.5 adds
only a local veto-feedback persistence hook after a flat-mode entry rejection;
it does not add an Observation network call while a position is open.
