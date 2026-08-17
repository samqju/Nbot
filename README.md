# NBOT V2

NBOT V2 is a research-first rebuild.

The active V2.1 runtime has one responsibility: collect and preserve unbiased, time-safe LIVE Binance USD-M Futures market evidence in one SQLite database.

It deliberately has **no strategy, model, champion, recommendation authority, paper execution, Testnet execution, or real execution**.

## V2.1 evidence rules

- complete 5-minute live events are atomic;
- failed/partial captures are recorded as attempts, not accepted as research events;
- live universe membership and spread/liquidity context are preserved point-in-time;
- missed events may recover canonical historical candles, but unrecoverable historical bid/ask and ranking context are never fabricated;
- recovered candle-only events are explicitly context-incomplete and cannot silently enter later decision-time training data;
- exact timestamped funding history is stored separately from current premium-index funding context;
- source timing, gap, integrity, coverage and storage-growth metrics are auditable;
- local/Binance clock skew above 5 seconds fails closed;
- live decision-time context captured more than 30 seconds after candle close is rejected rather than mislabeled as point-in-time evidence.

## Commands

```bash
python3 nbot_admin.py init
python3 nbot_admin.py check-live
python3 nbot_admin.py collect-once
python3 nbot_admin.py status
python3 nbot_admin.py audit
python3 nbot_admin.py recover-gaps
python3 nbot_admin.py sync-funding
python3 nbot_admin.py checkpoint
python3 nbot_admin.py backup
python3 -m unittest discover -s tests -v
python3 run_observation.py
```

Runtime data is written to `data/observer.db` and is not committed.

The rebuild plan is in `docs/NBOT_V2_REBUILD_ROADMAP.md`.

## V2.2 canonical research layer

V2.2 derives versioned features and transparent research-signal annotations
from the canonical V2.1 evidence database. It does not change which raw market
snapshots exist, does not place orders, and does not give any signal authority.

```bash
python3 nbot_admin.py research-build
python3 nbot_admin.py research-status
python3 nbot_admin.py research-audit
```

`CANONICAL_FEATURES_V1` uses only the target event and earlier canonical
candles. Every research-ready point-in-time snapshot receives a feature row,
even when long lookback history is incomplete. Every feature row receives all
three initial signal annotations; inactive/no-signal annotations are retained.

Initial annotations are research baselines only:

- `CSM_RANK_1H_4H_V1`
- `TSMOM_4H_VOL_ADJ_V1`
- `INTRADAY_CONDITIONAL_MOM_REV_V1`

They are not champions, recommendations, or execution instructions.


## V2.3 future-path / outcome layer

V2.3 records what happened *after* each mature V2.2 feature row. Future data is
label/evaluation evidence only and is never a decision-time feature.

```bash
python3 nbot_admin.py sync-funding
python3 nbot_admin.py outcome-build
python3 nbot_admin.py outcome-status
python3 nbot_admin.py outcome-audit
```

`FUTURE_PATH_4H_V1` stores forward returns at 5m/15m/30m/1h/2h/4h, long and
short MFE/MAE and timing, future volatility, research-R barrier sequencing,
exact funding events crossed, explicit after-cost return proxies, and favorable
continuation after frozen hypothetical exit horizons. Missing future candles for
symbols that leave the observation universe are cached separately as label-only
historical klines; V2.2 features never read that cache.

## V2.4 exit-policy / profit-capture laboratory

V2.4 compares exit behavior on the same V2.3 future paths. It is research-only:
it cannot select an entry, promote itself, recommend a trade, or place an order.
Every policy starts with the exact same V2.3 ATR14 1R initial risk and may never
loosen below that initial stop.

```bash
python3 nbot_admin.py policy-build
python3 nbot_admin.py policy-status
python3 nbot_admin.py policy-report
python3 nbot_admin.py policy-audit
```

The frozen V1 catalog contains one control and seven challenger families:

- `INTEGER_R_STEP_CONTROL`
- `CONTINUOUS_R_GIVEBACK_V1`
- `ATR_VOLATILITY_TRAIL_V1`
- `CHANDELIER_TRAIL_V1`
- `STRUCTURE_TRAIL_V1`
- `RUNNER_POLICY_V1`
- `STAGNATION_TIME_EXIT_V1`
- `EXHAUSTION_TIGHTENING_V1`

Stops for a future 5-minute bar are decided only from information available
through the previous completed bar. The lab records after-cost net R, gross R,
full-path MFE/MAE, winner capture ratio, peak giveback, holding time,
post-exit favorable movement, missed extension, exit reason, compact stop-change
history, and deterministic lineage back to the V2.3 future path.

V2.4 does not auto-promote a policy. Promotion requires later unseen
chronological evidence as defined by the rebuild roadmap.


## V2.7 execution capital boundary

V2.7 reintroduces the execution side as a clean, separate capital boundary.
It does not import the V2 research/selection/champion stack and it has no
approved entry authority by default. Real Binance order adapters are deferred
to the V2.8 Testnet mechanical canary.

```bash
python3 run_execution.py --self-check
```

The self-check must report `entry_authority=NONE`, no approved exit policies,
and `order_adapter=NONE_UNTIL_V2_8`. Execution state is separate from
`data/observer.db` and is stored atomically in `data/execution_v2_state.json`
when an execution adapter is used.



## V2.8 Binance Testnet mechanical canary

V2.8 connects the V2.7 capital boundary to Binance USD-M Futures Testnet for
**mechanical validation only**. `TESTNET_MECHANICAL_CANARY_V1` is a manual,
Testnet-only canary authority; it is not a research champion and its outcomes
are explicitly stored as `TESTNET_MECHANICAL_ONLY`, never research evidence.

The real credential file is intentionally outside Git and exists only on the
Execution VPS:

```text
/home/ubuntu/.config/nbot/.env
```

The tracked template is `deploy/v2/execution.env.example`. Execution-owned
mutable state is stored under `/var/lib/nbot-execution/`, separate from the
Observer database. The default self-check remains fail-closed and places no
orders:

```bash
python3 run_execution.py --self-check
```

### V2.8.1 execution safety hardening

V2.8.1 keeps the V2.8 mechanical Testnet trading behavior unchanged while
hardening two operator/runtime boundaries discovered during the first physical
canary:

- Testnet session-entry counts are persisted in
  `/var/lib/nbot-execution/testnet_trading_guard.json` before an entry order can
  be submitted, so restarting Python does not reset the session limit. Removing
  and recreating the valid arm file starts a new explicit Testnet session. A
  missing/corrupt guard state while already armed fails closed.
- Capital-mutating/reconciliation actions hold the kernel-backed single-instance
  lock `/var/lib/nbot-execution/execution_v2.lock`. Read-only `--testnet-preflight`
  remains available from a second terminal while a canary is running.

These controls do not change strategy, risk sizing, leverage, exit policy, or
Binance order endpoints.

### V2.8.2 exchange-close recovery and proven execution mechanics

V2.8.2 restores the useful V1 reconciliation rule that **exchange truth wins**
without restoring V1's learning coupling. If Execution restarts with a durable
local position but Binance is already flat, it now settles that close from
Binance account trade history instead of stopping permanently at
`LOCAL_POSITION_MISSING_ON_EXCHANGE`.

The recovery path is deliberately stricter than V1:

- `GET /fapi/v1/userTrades` is used to reconstruct the exact closing fill
  quantity, weighted exit price, realized PnL and close timestamp;
- same-direction post-entry fills or ambiguous quantities fail closed instead
  of guessing which trade belongs to the position;
- protective algo identity is persisted with the position and Binance algo
  history is matched to the actual closing order ID before labeling a close
  `PROTECTIVE_STOP_TRIGGERED`; otherwise the conservative reason
  `EXCHANGE_FLAT_RECOVERED_AFTER_RESTART` is used;
- the recovered outcome ID is deterministic from the immutable entry identity,
  so crash/retry cannot create a second outcome for the same execution;
- queueing the outcome and clearing `open_position` happen in one atomic
  execution-state replacement;
- incomplete close evidence fails closed. V2 never substitutes an invented
  zero exit price or zero PnL;
- stop writes retain V1's no-blind-retry principle: an ambiguous conditional
  order is recovered by `clientAlgoId`, and stop replacement verifies the new
  stop before removing older protection;
- a flat account must also be free of orphan protective stops before recovery
  is accepted.

The V1 paper-account ideas that remain useful (durable local paper balance and
position state, fee/slippage accounting, restart restoration, and applying the
same open-position market stream to simulated stops) are retained as design
inputs for V2.9 LIVE-market paper execution. They are intentionally not added
to the V2.8 Testnet adapter, so this recovery patch does not mix paper and
exchange execution modes.

A recovered close is settled/delivered first and **never opens a new canary in
the same CLI invocation**. A fresh entry always requires another explicit
operator action.

### V2.8.3 Testnet algo settlement fallback

V2.8.3 hardens V2.8.2 against a real USD-M Testnet behavior observed during
physical canary validation: a triggered reduce-only `STOP_MARKET` can appear as
`FINISHED` in algo history with a populated `actualOrderId`, while
`/fapi/v1/userTrades` returns no rows for either the position lifetime or that
actual order ID.

Recovery still prefers `userTrades`. If those fills are unavailable, V2.8.3
accepts the algo-order fallback only when all independent exchange facts agree:

- exactly one post-entry `FINISHED`, reduce-only `STOP_MARKET` matches the close
  direction and full local quantity;
- its `actualOrderId` resolves to a `FILLED`, reduce-only actual order with the
  same direction and full executed quantity;
- algo `actualPrice` and actual-order `avgPrice` agree within the symbol tick;
- algo and actual-order client identities agree when both are present;
- `REALIZED_PNL` income in the exact close second sums to the PnL independently
  implied by durable entry price, actual exit price and quantity;
- Binance is already flat and orphan protective stops can be removed/verified.

Any missing, duplicate or contradictory evidence remains fail-closed. This
fallback is Testnet execution accounting only and remains excluded from research
evidence.

### V2.8.4 execution consolidation

V2.8.4 is a deliberate consolidation after physical Testnet testing exposed
that the clean V2 Execution rewrite had discarded several mature V1 execution
behaviors. The governing rule is again simple: **Binance is authoritative for
exchange position, order, fill and realized-PnL truth; NBOT is authoritative
for permission, risk, protection policy, MAE/MFE, R-multiple, durable local
identity and audit.** A local theoretical PnL may be recorded as an audit
variance, but it can never veto an otherwise fully proven Binance close.

The patch keeps V2's stronger safety additions while restoring the useful V1
behavioral baseline:

- local `OPEN` + Binance `FLAT` is a normal reconciliation case, not a permanent
  dead end;
- close settlement prefers `userTrades`, then a proven conditional-algo child
  order, then generic Binance order history for manual/external closes;
- exchange `REALIZED_PNL` is stored as realized PnL. The simple local
  entry/exit arithmetic is retained only in `last_close_audit` as
  `theoretical_pnl_usd` and `pnl_variance_usd`;
- identity contradictions still fail closed: wrong symbol/side/quantity,
  hedge/multiple-position state, unexpected additional fills, ambiguous full
  close orders, missing authoritative accounting, or unresolved order identity;
- the complete entry proposal/plan/client-order identity is fsync'd as
  `entry_inflight` before the market-order call. A restart resolves that exact
  client order without submitting a second entry, then restores protection or
  settles an already-closed position;
- a crash before the entry ever reaches Binance is cleared only after repeated
  exact-order-missing plus exchange-flat evidence;
- execution state uses fsync + atomic replace and corrupt state fails closed;
- completed outcomes remain in a bounded local execution history even after the
  pending delivery copy is ACKed and removed;
- new-stop-before-old-stop removal, deterministic IDs, single-instance locking,
  persistent Testnet session guards, orphan-stop cleanup, and no Observation
  dependency while open are preserved.

V2.8.4 does **not** restore V1 learning writes, Strategy/Universe imports, or
V1's unsafe fallback that could settle an unknown close at zero price/PnL. It
also does not prematurely add the V2.9 LIVE-market paper adapter. The useful V1
paper mechanisms (durable one-position state, atomic persistence, immutable
trade history, exchange-like stop lifecycle and restart recovery) are now
represented in the common execution-state/reconciliation contract and remain
the baseline for V2.9.
