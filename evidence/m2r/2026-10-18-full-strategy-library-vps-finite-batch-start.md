# NBOT V6 — owner-authorized native full strategy-library VPS batch (2026-10-18)

**Current verified state as of 2026-10-18 03:58 UTC:** finite server-side historical research **ACTIVELY RUNNING** on isolated V6 8GB/2CPU VPS via `nbot-v6-library-20261018.service`; this is NOT a recurring ChatGPT automation, production trading service, or a profitability claim. The owner explicitly requested to leave a finite offline research batch working on the VPS and review it later.

## Why this work was started

The completed 30/60/90/180-day tests of the ORIGINAL LightGBM breakout/pullback strategy all lost money, even on matched dates, and NO TRADE=0 won. The owner requested thorough evaluation of **all eight new GitHub strategy families**, non-AI native backtests, aftercost and independent historical comparisons, FreqAI LightGBM, Hyperopt, no-trade regime selection, and reinforcement learning, using a finite VPS background job after original research finished. The owner also noticed the old V1–V5 trading approach used **trailing stop-loss**, while original V6 strategy and new library had `trailing_stop=False`. Trailing is a **hypothesis**, not proven to have caused previous losses. Exact earlier V1–V5 trailing parameters were not recovered from this V6 research branch, so the new variant is an **explicit new fixed experiment**, not a claim to recreate V5.

## VERIFIED deployment and actual native preflights

- Authorized VPS research path `/root/nbot-v6-m1-20261016/source`, Git branch `prototype/v6-freqtrade-freqai-20261016`, clean working copy, fast-forwarded **only** research branch from old `1c264dc` to GitHub commit **`aa97a32c9af73ae63503f5dbff63d98a7fe32200`**. PR #50 remains **DRAFT/UNMERGED**. V5/main untouched, existing archived Jan–Sep four-window model ZIPs and results untouched.
- VPS confirmed 8GB RAM (~7.4GB available initially), ~85GB free disk, 25 original pair archive data, no competing Docker or active research unit at startup. Official Freqtrade Docker image `freqtradeorg/freqtrade:stable_freqai` already installed. Local Python compilation passed. GitHub CI for source **`aa97a32`** passed both real Freqtrade strategy discovery including 8 trailing variants and offline unit tests (workflow run [39095218107](https://github.com/samqju/Nbot/actions/runs/39095218107)).
- **Native OFFLINE three-day smoke test 2026-08-01–04** on all 25 original USDT futures pairs, 1× 1000 USDT one position, fee 0.0005 per side, existing isolated 100k historical virtual wallet, native Freqtrade protections: `NbotV6EmaCrossResearch`, **54 simulated trades, −31.720 USDT**. Exact native ZIP saved to `library-20261018/preflight/native-ema-cross-aug1-aug4/backtest_results/`.
- **Native three-day trailing A/B smoke test** same period/pairs/fee/portfolio: `NbotV6EmaCrossTrailingResearch`, **55 simulated trades, −32.859 USDT**. Exact native ZIP saved under `library-20261018/preflight/trailing-ema-cross-aug1-aug4/backtest_results/`. Both preflights EXIT_CODE=0. Short sample does NOT demonstrate trailing superiority (here slightly worse). Native A/B change is ONLY exit trailing logic, not signal entries.
- Trailing-stop variant implemented independently for all eight families in [NbotV6LibraryResearch.py](user_data/strategies/NbotV6LibraryResearch.py), original versions unchanged. Freqtrade initial stop −2%, trailing only activates after trade is +2% profitable, and then follows a 1% trailing stop (`trailing_stop_positive=.01`, `trailing_stop_positive_offset=.02`, `trailing_only_offset_is_reached=True`). 5% ROI, 60-minute timeout and all native portfolio protections unchanged. The choice is fixed for the study; any other trailing parameters would require May–June-only tuning and separately frozen out-of-sample validation.

## Running finite server-side unit and exact sequence

At **2026-10-18 03:57:46 UTC**, after no-Docker/clean-branch/CI/native smoke checks, invoked a distinct root-owned finite systemd transient service:

```
nbot-v6-library-20261018.service
```

**Independently verified at 03:58:10 UTC:** `ActiveState=active`, `SubState=running`, `MainPID=142873`, exactly one native Docker container named `nbot-v6-library-single-native-offline`, and root-owned JSON state `library-20261018/v6-library-research-status.json` says `status=running`, stage `original_no_ml_baseline`. Original non-AI breakout/pullback baseline **July** actually finished and passed native ZIP/fee/leverage/25-pair/model-free audit: **158 simulated trades, −119.462162 USDT**, with extra hypothetical +25bps roundtrip slippage **−513.358350 USDT**. **August baseline was actively running** at this verification. Additionally a full **July EMA crossover native strategy** ran before starting the service and passed trade-ledger audit: **594 simulated trades, −365.754904 USDT**, with +25bp additional roundtrip cost **−1847.038049 USDT**, saved in `library-20261018/native/ema_cross/validation_july/native-economic-audit.json` (native SHA256 `59f38f165703e44475403f1f62a61aec0ceb381581dacfe44ddadb11811f5a23`). The batch detects and reuses this existing verified ZIP, NEVER overwrites it.

Exact finite **sequential** plan implemented in [full batch coordinator](scripts/m2r_v6_library_full_batch.py), each job through guarded [single-native-job runner](scripts/m2r_v6_library_native_job.py):

1. Reproduce original non-AI EMA breakout/pullback baseline on **July, August, September 2026** (different exit rule from new library; identify this when comparing).
2. **All eight fixed-exit standalone native strategies**, one 25-coin full month for **each** of July, August and September, same simulated wallet/stake, stop/ROI, 0.05% per-side fee, funding (native Freqtrade), risk protections. Each produces native ZIP, exact trade-ledger arithmetic audit, additional hypothetical **+25bp roundtrip** trading cost stress. NO TRADE 0 reference.
3. All eight **trailing-stop variations**, same three months and same entry-signal code, isolated ZIP and cost-stressed results. This provides controlled identical-signal A/B of trailing versus fixed exit behavior (trades can differ after earliest exit).
4. Rank original candidate families using **July + August only**, before touching September results for family shortlisting. Positive independent **both** chronological windows after extra 25bps and 20+ trades in each is minimum to call a candidate preliminarily economically eligible. Since August has already been inspected in prior research, neither it nor September is a pristine untouched final external test. If *none* pass, select **up to two best-scoring** merely for **exploratory diagnostic**, explicitly mark **not qualified**, no strategy promotion.
5. Native Freqtrade **Hyperopt May–June 2026** entry parameters for each eight candidates, 60 bounded epochs, one CPU, native protections, no automatic parameter exports or aftertest parameter leakage. The optimization results are exploratory until separately frozen and repeated OOS.
6. If one/two are eligible or diagnostic-best, run family-specific, separate-identifier after-cost **FreqAI LightGBM** native month-length September simulations, with 7-day retraining and strict 12×5m label chronology embargo. No model enters paper/live, no “AI improvement” claim unless matching native nonAI and trailing economic audits agree on fair dates.
7. Run the **strict 8h causal regime-aware selector** with currently EMPTY externally certified candidate scorecard manifest. Expected **NO TRADE** (zero portfolio entries) unless independent lookahead+aftercost regime evidence was proven; no fabricated positive scores from this same test set. Historical native adapter only chooses among fixed non-ML family signal variants at present; *actual simultaneous eight ML models routing remains unbuilt*.
8. Independently test native **PPO FreqAI RL** (neutral/long/short/exit) on July historical data in dedicated `freqtradeorg/freqtrade:stable_freqairl` image. This Docker image may need download and FreqAI PPO experiments may fail due to config/missing native dataset; such failures are logged, **not a successful training/profitability claim**. RL reward environment differs from actual native engine order fills.
9. Save full per-job result ZIPs, `native-economic-audit.json`, `run-state.txt`, `native.log`, and a final `candidate-native-aftercost-summary.json` plus readable status and event log. One job at a time, time-bounded; errors recorded and **no skipped/failing candidate is called validated**. Critical contamination or safety failure stops entire finite batch.

*All new source and current native data are on the same V6 research branch; paper/live remains disabled and exchange keys blank. The service is independent of PuTTY/chat while VPS remains online, but does **not** automatically survive a VPS reboot. The previous ChatGPT hourly checking automation was deleted by the owner and has **NOT** been recreated.*

## Owner read-only status commands — on PuTTY VPS

```bash
systemctl status nbot-v6-library-20261018.service --no-pager
docker ps --format '{{.Names}} {{.Status}}'
ROOT=/root/nbot-v6-m1-20261016/library-20261018
cat "$ROOT/v6-library-research-status.json"
tail -n 15 "$ROOT/v6-library-research-events.jsonl"
find "$ROOT" -name native-economic-audit.json | wc -l
```

**Caution on final project goals:** This finite batch is a first complete *research verification pass*, not a live adaptive profitable bot. It runs genuine native historical comparisons for the eight new families, native exit trailing A/B, Hyperopt, a limited number of FreqAI challengers, and a fail-closed NO TRADE regime test and separate RL research. Full future never-inspected OOS windows, calibrated predictive policy tests, exact 2019–2026 order-book executable slippage, **actual eight simultaneous AI policies inside router**, and entire-exchange 25-of-N dynamic rotation economic testing remain separate validation and development gates. No model can automatically promote itself.

**As of this GitHub evidence writing, the finite service was verified ACTIVE. Do not claim every experiment has finished; check the VPS's actual persisted files. No background ChatGPT task is needed.**
