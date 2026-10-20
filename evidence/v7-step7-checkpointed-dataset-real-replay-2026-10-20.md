# NBOT V7 Step 7 — Checkpointed Disk-Bounded Historical Dataset Builder

**Recorded:** 2026-10-20 IST/UTC  
**Scope:** Isolated `V7` branch and previously downloaded BTCUSDT/ETHUSDT/SOLUSDT monthly public Binance archives.  
**Status:** **ENGINEERING TEST PASSED**; full 876-symbol archive-observed universe ingestion has **NOT** run or been validated; economic/production claims remain NO-GO.

## Why this was needed

The original three-coin nine-month label database occupied approximately **344 MiB**. Scaling the same uncompressed, per-signal SQLite structure to 876 archive-observed symbols on a 96 GiB VPS risks out-of-space, an aborted build being misinterpreted as complete and expensive repeated processing after interruption. Archive object presence is **not** proof the contract was trading at that date. The next full-market phase therefore needs a bounded, restartable ingestion foundation.

## Exact code changes

- `nbot_v7/lab.py`: new `build_progress` receipt table, transactionally committed with each symbol's original conditional labels and source hashes. Only after every symbol is validated does `meta.build_complete` change to `true`; incomplete/corrupt builds are rejected by the nine-month experiment.
- `--resume`: explicit opt-in for a partially built dataset. Matches label policy, UTC date interval, requested months, source-symbol set, registry file SHA256, BTC bundle and for each resumed symbol **re-hashes its full current source bundle** before reusing any previous label rows. A completed dataset cannot be resumed/overwritten.
- `_build_budget`: checks SQLite database and WAL/SHM total against a supplied disk quota and checks remaining filesystem free capacity **before and after each symbol**. SQLite WAL is checkpointed after every completed symbol to keep growth bounded. Budget violation aborts the build with an explicit **incomplete** status. There can still be a *single symbol's transaction-size* overshoot before the check, so the operator must retain a substantial free-disk reserve.
- `nbot_v7/cli.py`: `build --max-db-gib 12 --min-free-gib 8` defaults for command-line VPS builds and `build --resume` for incomplete saved checkpoints; no overwrite-by-default.
- `tests_v7/test_archive_system.py`: deliberate second-symbol exception confirms first symbol's exact progress persists and resumes once without duplicate candidates; completed/mismatched source resumes are refused. Deliberately tiny storage quota proves `build_complete=false` remains.
- No changes to exchange execution permissions, trading policy, model-selection objective, data label economics, historical BTC context or real-money authorization.

Source commits, sequential on active V7:
- `1e2dfc92b6150734a5073349bb845a7e3bb7ca26` — checkpoint/resume/budget database implementation
- `4a91b00b15b4c7418e1b8e3ea7857565cae4215d` — CLI guards
- `24475a212b09cd48b113ad4001e437c9cc7460f2` — crash/restart budget tests

## Actual Linux results (VPS)

After GitHub fast-forward `V7`, **36/36 V7 tests PASS**, using real LightGBM in isolated `/opt/nbot-v7-20261020/venv`. Test transcript SHA256:
`cc2a2b19af39fc0c53a36b3bdf977e096ea650c60e9fc39f8f06c17e2f7ecd06`
(`/opt/nbot-v7-20261020/runs/step7-dataset-checkpoint-tests.txt`).

**Deliberate bounded-failure rehearsal using original nine-month BTC/ETH/SOL archives, no redownload:**

1. New DB `runs/pilot-btc-eth-sol-2026/checkpoint-real.sqlite`, requested 0.08 GiB SQLite quota and 8 GiB free-space reserve.
2. Initial builder exits **1** with `RuntimeError: DATASET_DB_BUDGET_EXCEEDED_INCOMPLETE` after writing one atomic symbol checkpoint; it did **not** set `build_complete=true`.
3. Run `build ... --resume --max-db-gib 1 --min-free-gib 8` using the exact same source and registry. Resume exits **0**; reports **1 existing symbol checkpoint reused**, **3 symbols in completed registry**, **249,685 candidate labels**, **2,454 watch-review records**, funding source coverage for 3/3 pilot symbols.
4. Run all A/B1/B trained-brain experiments from the new resumed DB into its own new output folder. The replay exits **0**, all four model accounts remain marked complete, and the **C_A and C_B decision-chain JSONL files have byte-for-byte identical SHA256** to the earlier Step 6 corrected initial dataset:
   - A: `95ef4f80ea716eb629825101bd228cb0d087cfc8c8856cc5b5347c9e8de62099`
   - B adaptive: `2c57a65da51a6e8f4545b3e6d11387ded040ab1bd76d5c4a8190ad48adc82d26`
5. Resumed completed DB ~**344 MiB**, still only a three-coin engineering sample; VPS filesystem ~**94 GiB** free at check. The candidate/source model evidence remains **5m bar/funding proxy** and archive-observed, not certified historical active-contract status.
6. Resumed experiment summary SHA256 `40850278d4962039025e2aba00c07e49d3279579e6196e3461d83e69b98a08c8`. Original corrected output remains separate at `experiment-boundary-fixed/`, with no original result deletion or overwriting.

**Commands / how to reproduce safely:**

```bash
cd /opt/nbot-v7-20261020/code
/opt/nbot-v7-20261020/venv/bin/python -m unittest discover -s tests_v7 -v

# Use a NEW database and a complete approved archive/registry source set.
python -m nbot_v7 build --archive /path/to/archives --registry /path/to/registry.csv \
  --db /path/to/new.sqlite --start-month 2026-01 \
  --max-db-gib 12 --min-free-gib 8

# Only on that SAME, incomplete, source-compatible database:
python -m nbot_v7 build --archive /path/to/archives --registry /path/to/registry.csv \
  --db /path/to/new.sqlite --start-month 2026-01 \
  --max-db-gib 12 --min-free-gib 8 --resume
```

For archived but *not independently lifecycle-verified* symbols, add `--allow-archive-observed-universe` and mark results **EXPLORATORY ONLY**.

## Still not solved

- This does not make the current SQLite label schema efficiently compact for an entire 900-directory all-market experiment. Need source-quality registry and per-symbol/interval capacity planning; 344 MiB for three coins suggests **potential tens of GiB** for hundreds of symbols. Do not promise full 900-contract nine-month readiness before a bounded larger-cohort stress test.
- No historical listing/retirement/suspension audit, native Freqtrade or tick fill proof, order-book spread/queue confirmation, alternate strategy alpha, unbiased unseen holdout or positive learning evidence.
- The prior three-coin negative model result remains unchanged: A −340.6883, B1 −660.0041, B adaptive −953.6469 USDT on Jul–Sep separate 10,000-USDT sleeves; no model promotion.
- Risk/code architecture remains production-oriented with historical lab removable, but trading operation/paper/live remains **unapproved**.

**Next bounded step:** Profile a 20–50 symbol *source-qualified or explicitly proxy-graded* cohort using observed archive coverage and disk/CPU budgets, determine whether compact normalized feature storage is required for whole-universe 3+3+3, then scale historical acquisition only within approved disk quota; avoid forcing a 900-symbol download before eligibility and space planning. Record results and failures in `V7_CHAT_HANDOVER.md`.
