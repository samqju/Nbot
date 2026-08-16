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
