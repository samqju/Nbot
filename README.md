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
