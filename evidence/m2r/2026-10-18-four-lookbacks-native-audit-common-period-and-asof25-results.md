# NBOT V6 — 2026-10-18 morning VPS audit: all four Jan–Sep lookbacks complete, common Jul15–Sep30 comparison, Stage2 diagnostic recovered

**Observed via authorized owner laptop → PuTTY `8GB-Observation` → isolated NBOT V6 research VPS on 2026-10-18 03:22–03:28 UTC (08:52–08:58 IST).** The earlier Oct17 recovery systemd research job `nbot-v6-jansep26-retryonce-20261017.service` ended with status=3 on Oct18 00:53:36 UTC, **but not from model failure**: every native 30/60/90/180 Freqtrade training+portfolio run and the strict after-cost audit were successful before it stopped. The cause was file read permissions for the final non-ML Stage2 causal as-of diagnostic, which has now been separately corrected and completed. Nothing in this audit approves model deployment, paper or real trading.

## 1. Actual native Freqtrade train/portfolio runs: complete and audited

Original and **only** strategy tested in these four runs: `NbotV6TradeOutcomeFundingResearch` with `NbotV6PurgedLightGBMRegressor`. **NOT** the new eight strategy families added to GitHub the previous evening. Original 25 fixed USD-M futures pairs; 1× leverage, one global 1,000-USDT simulated stake, 100,000 simulated wallet, 5-minute candle decisions, 7-day rolling FreqAI retraining. Fee=0.0005 per side in engine; native historical modeled funding. These are hypothetical Freqtrade trades and costs, *not live exchange fills*, *not observed Binance order book/slippage*. All four native ZIPs, model counts, period boundaries, trade counts, trade-level 0.05% fees each side, 1× leverage and PnL aggregation **passed** `scripts/m2r_jansep_native_rolling_audit.py` at 2026-10-18 00:52 UTC. Audit path: `/root/nbot-v6-m1-20261016/jansep-20261017/jansep-native-four-window-audit.json`, SHA256 `8918a053e1ede7c5be8f8fb153a9a2071d6afb890a303938f3f23d169508f38e`.

| Lookback | Backtest trade start inclusive UTC | End exclusive UTC | Fitted models | Simulated trades | Native after-engine-cost PnL USDT | Extra **hypothetical** 25bp roundtrip PnL USDT | Native max drawdown USDT |
|---|---|---|---:|---:|---:|---:|---:|
| 30d | 2026-02-15 | 2026-10-01 | 825/825 | 1,930 | **−2,311.594335** | **−7,133.013349** | 2,346.179218 |
| 60d | 2026-03-15 | 2026-10-01 | 725/725 | 1,202 | **−1,540.263653** | **−4,542.779625** | 1,554.642130 |
| 90d | 2026-04-15 | 2026-10-01 | 625/625 | 829 | **−949.941697** | **−3,021.183262** | 998.687578 |
| 180d | 2026-07-15 | 2026-10-01 | 300/300 | 355 | **−201.647121** | **−1,088.545821** | 282.008053 |

**Original 30d client disconnected mid native run:** 825 saved model artifacts and native ZIP but only **493/825** chronological embargo/purge log messages survived, each observed message reporting `boundary_violations=0`; the other **332 split checks are unobserved**, not verified. For 60d/90d/180d, all **725/725, 625/625, 300/300** respective fitted-model boundary messages were preserved, zero violations recorded. The absence of original 30d last 332 training logs is a remaining provenance caveat for release-grade audit. All four actual native historical profitability figures are negative **even without extra slippage**.

Native archive SHA256 for 30/60/90/180 respectively:

- 30: `ac71714077c283f0de1b594dc66409d7a0e29f7439dfcde70eb4a7104c745ba2`
- 60: `c447d739c4bdf364c22e2fd7e572f186fcb004c84769f363660673722cd387a3`
- 90: `b4c2e7333c6bbd102295d042846ce5ce5b9c595d895cf9d6e9e03968624c5e87`
- 180: `762c6379e8f7a78c583525224b5e72deabee063179266e03af8943b5b08304a2`

## 2. Exact common-period PnL, generated from native ZIP trades (Jul15–Sep30)

The original full test periods differ. To prevent the misleading inference that 180d “wins” solely because it traded fewer months, a **new separate, read-only native ZIP trade ledger analysis** included only trades with native `open_date >= 2026-07-15T00:00 UTC` **and** `close_date < 2026-10-01T00:00 UTC`. All models therefore share the same elapsed evaluation period, starting wallet convention, native fee/funding settings, one-position cap and baseline `NO TRADE = 0`. Some models make different trades in that period: this is matched **calendar time**, not paired identical entry timestamps. All results derived from saved actual simulation trades, not labels.

Path: `/root/nbot-v6-m1-20261016/jansep-20261017/jansep-common-2026Jul15-Sep30-audit.json`; SHA256 `48371d3c4628d2021f4b70cbb6d6f2171bcbc7d6b4aca7c7719575484c95a6c8`.

| Lookback | Native simulated trades inside common dates | Net USDT incl. native modeled engine costs | Additional +10bps USDT | Additional +15bps USDT | Additional +25bps USDT |
|---|---:|---:|---:|---:|---:|
| 30d | 629 | **−761.106821** | −1,389.531427 | −1,703.743730 | −2,332.168335 |
| 60d | 491 | **−581.443320** | −1,072.072708 | −1,317.387402 | −1,808.016790 |
| 90d | 406 | **−287.027508** | −692.747819 | −895.607975 | −1,301.328286 |
| 180d | 355 | **−201.647121** | −556.406601 | −733.786341 | −1,088.545821 |
| **NO TRADE** | 0 | **0** | **0** | **0** | **0** |

**Conclusion:** Longer training windows had fewer trades and less-negative overall simulated results in these dates, but **all four still lose**, even before additional hypothetical execution-cost stress. The 180d model lost the least but **NO TRADE is superior**, and a statistically reliable monotonic improvement or strategy profit has **NOT** been established. Original full-year non-ML baseline and uniform-date independent nonAI/native strategy comparator have not yet been run. Do not promote any model based on these results.

## 3. Stage2 historical coin-selection work: finite diagnostic recovered, true whole-market comparison still BLOCKED

- The first stage finished four native ZIPs and the complete native aftercost audit at **2026-10-18 00:52:07 UTC**.
- Historical public Binance Vision 1h *directory metadata* inventory finished **00:53:36 UTC**: **895 ever-archived `*USDT` directory candidates**, **868 directory symbols having some monthly Jan–Sep 2026 1h ZIP metadata**, **0 metadata directory failures**. It is **not** a tradeable/inactive/delisted USDT-M point-in-time market list, validated 5m funding coverage, bid/ask spread history, or actual PnL trial. Source on VPS `jansep-20261017/binance-vision-2026-archived-usdt-symbol-months.json`, SHA256 `7b4f2b1e0cc34569c8c0ad515715a61222fbf7739aef4b156d707ceaba209a5c`.
- Original finite research unit failed after that because `/root/.../source/scripts/m2r_asof_25market_selector_diagnostic.py` was inadvertently mode **0600 root-only**, and `selector/` was root-owned **0700**, while `freqtradeorg/freqtrade:stable_freqai` runs as **`ftuser` UID/GID 1000**. Error: `python: can't open file '/research/scripts/m2r_asof_25market_selector_diagnostic.py': [Errno 13] Permission denied`. **NOT** a failure of model training or the native portfolio audit.
- On 2026-10-18 **03:25 UTC**, VPS was Docker-idle, correct `prototype/v6-freqtrade-freqai-20261016` branch, clean Git checkout. Repaired only the research diagnostic script mode `chmod 0644`; allowed **only** the isolated selector output folder UID1000 write access. Created a **finite once-only, no-restart/no-scheduler** VPS transient service `nbot-v6-jansep26-asof25-diagnostic.service`, using the same original Docker image with **`--network none`, no capabilities, `no-new-privileges`**, source/history read-only mounted, `/results` output mount and exact original script. The service exited **SUCCESS** at **03:25:45 UTC** (no Docker containers remain). Recovery command and logs persisted only on this isolated V6 VPS under `jansep-20261017/vps-stage2-asof25-recovery.{sh,log}`. No real/paper execution, no secret, no V5/main mutation.
- Fixed-25 *descriptive diagnostic* analyzed **684 as-of 8h reviews** from **2026-02-15 00:00Z to 2026-09-30 16:00Z**; **100% of reviews had all original 25 as-of histories ready**, confirmed all ranking/selection scores use only historical completed candles, BTC pinned, top10/bottom10 relative liquidity and forward volatility *evaluation only*. Output `jansep-20261017/selector/25-market-8h-asof-ranking.json`, SHA256 `46fd35195d2bfd9e02a1256b3e865d41563c43152ac5c77e8994a8c1e5317764`.
- Output explicitly sets `full_historical_25_of_entire_exchange_rotation_proven=false`, `real_strategy_pnl_comparison_completed=false`, `fixed25_to_top25_using_only_25_candidates_has_identical_membership_by_construction=true`. **It cannot be claimed the requested 8-hour historical 25-of-entire-Binance selector improved trading or changed 25-coin membership**: at the moment we only have actual audited full 5m/1h/funding histories for the 25 incumbent coins and no point-in-time eligibility/order-book cost data for outside symbols.

## 4. Clear next-stage decision and release gates

- **Stage 1 four full 30/60/90/180 FreqAI Jan–Sep native historical studies: COMPLETE, fully audited, NEGATIVE.** Their study's original native series all finished without runtime errors; the wrapper diagnostic glitch was fixed separately.
- **Stage 2A ever-archived symbols metadata inventory and fixed25 8h causal descriptive diagnostic: COMPLETE.**
- **Stage 2B genuine historically-eligible, exchange-wide 25-of-N rotating selector versus same-period fixed25 *economic Freqtrade portfolio* matched counterfactual: NOT DONE.** Need historically listed/active information, outside-25 5m/1h/funding and realistic costs, then a frozen chronological portfolio simulation and independent audit.
- **New eight-family open-indicator Freqtrade candidate/LightGBM/PPO library: only source/CI implemented on GitHub** by separate prior task; **none of the new eight native families has earned independent native profitability acceptance yet**. Last VPS source checkout remains old exact commit `1c264dc` because GitHub research library commits have **not** been pulled onto VPS; do not pull those or start heavy new experiments without safe protocol/owner instruction.
- **M2 NO-GO, M3 pending, M4 paper OFF, M5A full universe selector not approved, M7 LIVE LOCKED.** There was **no ChatGPT scheduled checking task recreated**. Current VPS is Docker-idle, both completed systemd jobs are inactive/failed-history, not a sign that model training still needs restarting. **Do NOT restart 30/60/90/180 training unnecessarily.**
