# NBOT V6 — Global 25×8 Stage 3 prelaunch safety audit

**Audit date:** 19 October 2026 (VPS preflight on the research branch). **Stage 3 is queued, not executed as a full portfolio backtest.** No live/dry-run trading permissions changed.

## Why this audit matters

Stage 2 initially failed on non-root Freqtrade Docker reading source files made root-only by Git-pull `umask 077`. We diagnosed and archived the failure, fixed source permissions, restarted Stage 2 and recovered native results. The owner asked that Stage 3 not repeat these mistakes.

The Stage 3 native coordinator had **an additional independent version of that same issue**: it created `exact-overlay.json` as root, without making the file world-readable. This was corrected before Stage 3 starts; the automated test now exercises real overlay creation and asserts the Docker-required nonroot read bit. The file contains **no exchange credentials** and no live/paper authorization.

## Changes committed on the V6 research branch

1. **Non-root readable native overlay:** [Global coordinator](../../scripts/m2r_v6_global_batch.py) writes each exact native Freqtrade overlay, explicitly `chmod 0644`, asserts the non-root read bit, and requires every candidate forecast ledger and shared hashed dataset. Native backtesting uses `--cache none`, Freqtrade's risk protections, 1,000 USDT stake, max one position, and 1× leverage.
2. **Python source permission audit:** the coordinator rejects any unreadable Python module under `scripts`, `user_data/strategies` or `user_data/freqaimodels`; it does not silently assume root can read a file that Docker uid1000 cannot.
3. **Static readiness verifier:** new read-only [readiness check](../../scripts/m2r_v6_global_readiness.py) checks 25 unique eligible configured pairs, all 25×{5m futures OHLCV, 1h funding, 1h mark} = **75 nonempty market files**, strategy/model sources, source read permissions and required offline/no-keys/one-slot settings. The shared base configuration can omit `nbot_live_mode` and `nbot_paper_research_mode` because the locked Stage 3 overlay explicitly sets both to **false**. An explicit unsafe true value still blocks.
4. **Persistent Stage 3 handoff:** [successor waiter](../../scripts/m2r_v6_global_successor_wait.sh) remains active but waits until the finite 120-run Stage 2 produces its expected verified completion evidence and stops. It fetches only the V6 research branch after Stage 2, restores harmless Python readability (`umask 022`, `chmod a+r`), checks syntax and tests, and runs the strict static readiness check. No new Stage 3 Docker while Stage 2 is running.
5. **Official non-root Docker runtime smoke:** after Stage 2 finishes and Docker is idle, the Stage 3 handoff runs a small, **offline** `stable_freqai` import check for LightGBM, scikit-learn, PyArrow, the eight-family candidate generator, pure global ranker, and both native Freqtrade adapter classes. Failure blocks the Stage 3 job **before** expensive training.
6. **Automated tests:** [global batch contract tests](../../tests/test_m2r_v6_global_batch_contract.py) now assert the actual native overlay has the Docker-readable bit and locked paper/live/fee/slot settings. [Stage 3 readiness tests](../../tests/test_m2r_v6_global_readiness.py) simulate 25 synthetic coin histories, root-only 0600 source, missing funding data and unsafe configuration. These tests use isolated temporary fixtures and do **not** launch VPS research.

## Direct VPS verification

- The static readiness check returned `static_readiness_ok: true`, `errors: []`, `pair_count: 25`, `market_inputs_expected: 75`, `market_input_missing: []`. It reported its expected limitation: file existence and static checks alone do **not** prove no historical candle gaps, usable model labels, complete runtime economics, or positive returns.
- The original selected Freqtrade dataset and the separate global research checkout have readable Python files, and the complete original Stage 1 archive/report stayed unchanged.
- The global batch contract/selector unittest command on VPS passed **20 tests** after the latest overlay patch, with three FreqAI-dependent tests **skipped on the host**, as expected. Official FreqAI-image CI also independently executes dependency-dependent tests.
- The latest verified regular GitHub CI at the time of this audit (workflow [39184055512](https://github.com/samqju/Nbot/actions/runs/39184055512)) passed offline unit tests and official Freqtrade strategy discovery. Subsequent commits are independently subject to CI.

## Known residual risks — NO unfounded guarantees

- No actual 25-coin historical ML forecast generation or one-slot native portfolio backtest has been executed yet. Those full end-to-end jobs are queued by the VPS handoff and can still encounter unforeseen data gaps, RAM/CPU constraints, native-schema mismatches or poor economics. Any such failure **must block**, preserve logs and require investigation, not silently mark the model successful.
- Training targets use historical 5m OHLCV approximations and explicitly priced fee assumptions, **not measured live orderbook depth, actual slippage or certain intrabar stop-fill paths**.
- Historical July–September 2026 has already been inspected. Positive net outcomes from these windows alone would not pass untouched future-market proof.
- This work **does not delete losing models, change existing 120 Stage 2 experiments, enable live/paper trading, or promote a chosen strategy**.

## One-command user audit

Read-only status while Stage 2 runs:

```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_global_readiness.py --strict
```

Original first-stage report: [Stage 1 Final Research Report](2026-10-19-stage1-final-research-report.md).  
Actual stage 2 recovery: [Permission fix and resumed profit protection](2026-10-19-profit-protection-permission-recovery.md).

**Decision:** Stage 3 source and queue can remain armed **conditionally**. Full training must start only when Stage 2 has finished its 120 native studies and the Stage 3 readiness, official-image import, no-concurrent-Docker and source-immutability checks all pass. Do not claim Stage 3 economic results until native archives are independently audited.
