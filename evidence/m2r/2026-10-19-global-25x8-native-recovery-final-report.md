# Nbot V6 — Stage 3 Global 25×8 Research: Recovery, Full Execution and Final Native Audit

**Completed and independently verified:** 19 October 2026, **03:45:42 UTC / 09:15:42 IST**.

**Owner-requested research-only scope:** 25 eligible original Binance USDT perpetual-futures markets, eight frozen independent strategy families, eligible LONG/SHORT signals each fully closed five-minute candle, LightGBM forecasts trained on 30/60/90/180-day chronological windows, and one Freqtrade global-position slot. No orders, paper trading, live trading, automatic model promotion or main/V5 merge.

## Executive summary

Stage 3 **finished all 12/12 scheduled jobs**: 4/4 forecast windows, 8/8 true Freqtrade native portfolio backtests (fixed and trailing for each window), and **0/12 current job failures**. The three-stage programme is complete as research execution: Stage 1 **63/63**, Stage 2 **120/120**, Stage 3 **12/12**.

**Economic finding: the global AI selector made NO TRADE in every 30/60/90/180-day window.** All eight genuine after-fee Freqtrade native portfolios made **zero trades** and reported **0 USDT net profit and 0 USDT additional-25bp-stress P&L**, with no simulated drawdown from trades. **This is not evidence of positive AI alpha, accurate winning-trade selection or a profitable policy**; it is a correctly executed policy that declines every trade under the conservative frozen gates. The earlier standalone strategy families generally lost after costs, but a NO TRADE reference of 0 is not evidence that the model could profitably discriminate favorable trades.

The original historical candidate dataset contains **914,878** after-base-fee labeled candidate records spanning model lookbacks and evaluation. Each of the four chronological historical test-window variants produced **263,937 scored candidate forecast rows** over its shared July 15–September 30 evaluation period, with calibrated positive-outcome probabilities and aftercost expected return estimates, rejection reasons and full audit ledger preserved. The same number of test candidates in every window does **not** imply identical predictions; forecasts and rejections differ.

## Verified scientific results

| Historical lookback | Scored valid candidate opportunities | Above 50% forecast probability | Median positive probability | Median predicted net after modeled base fees | Global selections | Native fixed trades/P&L | Native trailing trades/P&L |
|---|---:|---:|---:|---:|---:|---:|---:|
| 30 days | 263,937 | 11,368 | 40.07% | −0.0990% | **0** | 0 / 0 USDT | 0 / 0 USDT |
| 60 days | 263,937 | 14,062 | 40.94% | −0.0989% | **0** | 0 / 0 USDT | 0 / 0 USDT |
| 90 days | 263,937 | 16,678 | 40.80% | −0.0998% | **0** | 0 / 0 USDT | 0 / 0 USDT |
| 180 days | 263,937 | 23,095 | 40.63% | −0.0995% | **0** | 0 / 0 USDT | 0 / 0 USDT |

### Why every opportunity was rejected

Below are **actual saved forecast-rejection ledger counts**, not invented explanation. Categories are mutually exclusive as recorded by the research ranker; the probability gate acts first.

| Rejection reason | 30d | 60d | 90d | 180d |
|---|---:|---:|---:|---:|
| Calibrated positive probability below 50% | 252,569 | 249,875 | 247,259 | 240,842 |
| Side disagreed with the simplified trend-regime gate | 6,056 | 9,566 | 10,746 | 13,881 |
| Excess uncertainty, downside, execution-cost or liquidity risk | 3,580 | 2,926 | 4,159 | 6,781 |
| Conservative net expected edge failed minimum threshold | 1,732 | 1,570 | 1,773 | 2,433 |
| **Selected** | **0** | **0** | **0** | **0** |

A **few rare** candidate forecasts had positive net expectancy after the raw risk adjustment but did not satisfy all qualification gates simultaneously. The number exceeding +0.1 percentage-point conservative edge *before other gates* was 9/2/12/11 for 30/60/90/180 days, respectively. Even with model forecasts occasionally positive, **no candidate satisfied the full selection policy.** Median predicted post-base-fee returns were slightly negative in all four variants (~−0.1%). The strategy is highly selective and/or poorly calibrated for realizable high-quality opportunities; one cannot distinguish genuine loss-avoidance skill from excessively restrictive gates on these results alone.

**Do not retroactively lower probability thresholds or fees on these same viewed historical months and present newly selected winners as out-of-sample proof.** Any threshold/horizon/exit policy challenger must be prespecified using earlier training material, then validated on untouched future periods and one true native Freqtrade capital-constrained portfolio with NO TRADE=0 reference.

## Actual Stage 3 infrastructure failure and recovery

**First attempt:** Stage 3 forecast windows ran successfully from 2026-10-19 **02:24–02:53 UTC** under source commit `8c458c8fda89da86355b5551688ad8cebef5c396` and produced the four immutable forecast/proxy-label datasets. The first native job, `w30/native-fixed`, stopped at **02:53:59 UTC** with `OFFLINE_DOCKER_JOB_FAILED_2`. Official Freqtrade native log confirmed the strategy resolved and loaded 25-market history but failed in `bot_start` with `GLOBAL_V6_NATIVE_BACKTEST_ONLY_NO_ORDERS`: the overly strict internal guard did not accept Freqtrade's normalized effective offline configuration. **Not a trading P&L error.**

**Diagnosis and controlled repair:**

1. The original research safety check was reorganized into individually named, strict, audited checks: backtest mode, research-only flag, paper/live off, dry-run, one global position, 1,000 USDT stake, futures/isolated, forced entries off, **no exchange credentials**, API/Telegram/FreqAI disabled. Equivalent safe false/empty values were accepted for empty exchange credentials; **the trading prohibitions were not disabled**. Failed guard check names would be reported if it failed again, never secret values.
2. Ran an **isolated official Freqtrade native diagnostic** against the unchanged 30d decisions CSV. It exited successfully with **zero trades, zero P&L**, and an actual official native ZIP, independent of the failed original folder. The saved `native_audit` verified this ZIP, original native schema, wallet/one-slot/fees and zero trade ledger.
3. Created and used [one-time fail-closed recovery script](../../scripts/m2r_v6_global_native_recovery.py) with **read-only preflight**. Required Stage 2 verified complete and Docker idle; verified the exact old blocked status and empty failed native ZIP folder; verified that the **LightGBM candidate generator, original eight-family technical strategy signals, and opportunity ranker source had NOT CHANGED at all** between the old and resumed source.
4. Verified immutable SHA256 for the shared candidate dataset and **16 preexisting per-window forecast/model ledger files**; the 4 original forecast jobs were **not retrained**, and the predictions, selected trades and risk thresholds were **not regenerated/modified**. Preserved the original blocked status at `global-25x8-20261018/pre-guard-fix-blocked-progress.json`, its exact SHA256, full recovery manifest at `native-guard-fix-recovery-manifest.json`, and the incomplete first native folder at `failed-first-native-pre-guard-fix/`.
5. Re-armed only the existing `nbot-v6-global-20261018.service`, which performed strict 25-pair/75-file readiness, original unit tests and official non-root FreqAI dependency import smoke. It reused all four forecast jobs and executed only the eight missing Freqtrade native portfolio backtests.
6. **Final VPS 2026-10-19 03:45:42 UTC:** systemd `ActiveState=inactive`, `Result=success`, completed count `12/12`, `jobs_failed=0`, eight `native-audit.json` files and official ZIPs present, owner-comparison present, Docker has zero active containers. Resumed-native source commit: `1a17ab62cac105c09aef039fa0e75f0f86161ad8` (the later reporting script commits do **not** alter saved modeling provenance).

## Independent after-the-fact audit

Ran the read-only [global final native auditor](../../scripts/m2r_v6_global_final_audit.py) on the VPS after job completion. It independently checked original failed progress SHA256, original vs resumed source SHA fields, the original SHA256-sealed shared candidate dataset, every forecast audit/CSV/forecast-rejection parquet file versus **pre-recovery manifest hashes**, all eight official Freqtrade ZIPs versus their native audit SHA256, all native fees/P&L/trade-count economics, and the final one-slot model comparison.

The verifier returned `state=all_twelve_jobs_completed_hash_verified`, `all_forecast_sha256s_preserved=true`, `eight_native_zip_sha256s_verified=true`. All model variants selected no trades, so **there is no observable profit-protection A/B effect in Stage 3** (both policies encountered an empty selected trade ledger). The Stage 2 standalone trailing and fixed exit policy evidence remains informative and is retained separately.

All (25 × 8 × eligible-side) candidate feature/signal tables, historical proxy outcomes, per-window as-of expected-return predictions, calibrated success probabilities and rejection reasons are kept. Later optional 10-family research or dynamic 25-of-N selection remains a separate unproven challenger, **not** part of this completed eight-family baseline.

## Technical limitations and owner decision

- The trained model used OHLCV *proxy* stop/ROI future outcomes for training rather than exact orderbook fills. Its cost and funding assumptions must not be described as guaranteed real-world execution.
- July–September 2026 periods have been studied and reused, **not pristine OOS**. Some temporal model leakage may be constrained by purging, but this report is not an independent model-quality certification.
- As-of expected net-return forecasts tended slightly negative, and confidence/uncertainty gates eliminated all entries. This result supports **NO TRADE under the frozen current policy** but does not measure conditional directional edge for unselected opportunities or prove whether risk gates are optimally set.
- Reject changing thresholds solely to force positive backtest trades. Plan independent prespecified ablation challengers comparing (a) probability-only gate, (b) calibrated conservative net edge, (c) regime-side gating on/off, (d) cost sensitivity, and (e) exit-matched trailing policies. Hold a **new truly untouched date range** for final claims. Run each through the native single-slot Freqtrade portfolio without selecting winners after seeing realized P&L.
- All 3 stages have finished their *scheduled* work; **Nbot V6 has NOT demonstrated economically profitable future trading. NO PAPER, NO LIVE, NO AUTO PROMOTION.** The owner will decide which research candidates to retain after reviewing all comparisons.

## Reproduce and inspect without starting research

```bash
# Full final native SHA256 + provenance verification
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_global_final_audit.py

# Status of the completed Stage3 service and research coordinator
systemctl status nbot-v6-global-20261018.service --no-pager
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_global_batch.py --status

# Rejection ledger across all four ML windows (read-only official image)
docker run --rm --network none \
 -v /root/nbot-v6-m1-20261016/global-next-source:/research:ro \
 -v /root/nbot-v6-m1-20261016/global-25x8-20261018:/results:ro \
 --entrypoint python freqtradeorg/freqtrade:stable_freqai \
 /research/scripts/m2r_v6_global_selection_summary.py --root /results
```

Other immutable evidence: [Stage 1 final report](2026-10-19-stage1-final-research-report.md), [Stage 2 startup recovery](2026-10-19-profit-protection-permission-recovery.md), and [Stage 3 prelaunch safety hardening](2026-10-19-global-stage3-prelaunch-hardening-report.md).
