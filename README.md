# NBOT V2

NBOT V2 is a research-first rebuild.

The active V2.0 runtime has exactly one responsibility: collect unbiased, point-in-time LIVE Binance USD-M Futures market evidence into one SQLite database.

It deliberately has **no strategy, model, champion, virtual-trade authority, recommendation API, paper execution, Testnet execution, or real execution**.

## V2.0 commands

```bash
python3 nbot_admin.py init
python3 nbot_admin.py check-live
python3 nbot_admin.py collect-once
python3 nbot_admin.py status
python3 -m unittest discover -s tests -v
python3 run_observation.py
```

Runtime data is written to `data/observer.db` and is not committed.

The rebuild plan is in `docs/NBOT_V2_REBUILD_ROADMAP.md`.
