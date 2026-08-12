# Phase 7.5A - Observation Learning Visibility

## Goal

Give the operator a safe `/learning` Telegram view of the autonomous Phase-7
learning loop without moving learning code or learning state into the Execution
Worker.

## Boundary

Observation remains the owner of model registry, training status, shadow
evidence, promotion state, and the human-readable learning report. Execution
keeps the single Telegram listener and acts only as a read-only proxy for the
operator command.

The flow is:

```text
Telegram /learning
  -> Execution operator listener
  -> ObservationClient.request_learning_status()
  -> authenticated POST /learning-status over the existing control tunnel
  -> Observation builds read-only learning status
  -> formatted status returned to Telegram
```

No strategy, learning, dataset, model registry, promotion, or training module is
imported by `workers/execution_worker.py`.

## Safety properties

- `/learning` cannot enable or disable trading.
- `/learning` cannot change paper routing or model authority.
- `/learning` cannot submit an order.
- Observation reports `order_authority=NONE` and the client rejects any other
  authority value.
- If Observation is unavailable, `/learning` reports unavailable and Execution
  continues unchanged.
- There is still exactly one Telegram `getUpdates` listener, on Execution, so
  operator commands cannot be consumed unpredictably by two VPSs.
- The endpoint uses the same authenticated Observation control boundary already
  used for proposals and outcomes.
- Learning status is served from the HTTP handler thread, not the Execution
  position-management hot path.

## Phase-7 operator view

The report prefers the automatic trainer's own qualified cohort rather than
rescanning the full historical candidate files. It displays:

- current champion
- current challenger and stage
- Phase 7.4 training status
- qualified outcomes versus required outcomes
- independent market events versus required events
- Phase 7.5 comparison status
- matched outcomes versus required outcomes
- independent comparison events versus required events
- disagreement events versus required events
- eligible broad-market regimes versus required regimes
- champion average after-cost R
- challenger average after-cost R
- challenger lift over champion
- current governance verdict and plain-English reason
- paper activation state
- real-order execution safety state
- next automatic action

`PHASE7_PAPER_PROMOTION_LOCKED` is rendered explicitly as success of the Phase-7
forward gates while preserving the Phase-8 paper-authority boundary.
