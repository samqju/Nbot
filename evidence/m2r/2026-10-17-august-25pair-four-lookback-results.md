# October 17, 2026 — FIRST actual native 25-market 30/60/90/180-day FreqAI historical comparison

**Experiment:** Completed the pre-declared [August one-week operational pilot](2026-10-17-august-fourwindow-pilot-protocol.md), using the pre-registered August Block D as an **exploratory seven-day subset**, not final blind full-month evidence. On authorized V6-only VPS (`8GB-Observation`, root V6 source checkout), `prototype/v6-freqtrade-freqai-20261016` GitHub research branch, Freqtrade **2026.9** pinned Docker image `sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535`. **No paper trading or real-money trading was started.**

## What was actually executed

The native `freqtrade backtesting` engine loaded the independently audited public Jan 1–Oct 16 2026 25-market four-feed historical archive and ran four separate full-engine backtests on **the identical period, August 1 at 00:00 UTC through August 8 at 00:00 UTC, 2026**. All runs used:

- **25 identical** Binance USDT-M futures markets, FreqAI `NbotV6TradeOutcomeFundingResearch` after-cost, funding-event target model with `NbotV6PurgedLightGBMRegressor`, original feature/entry/exit thresholds, FreqAI LightGBM settings, BTC context, 12×5m outcome horizon and chronological internal training split; no tuned or chosen markets based on backtest results.
- **One maximum global simulated trade**, 1× leverage, 1,000 USDT stake and 100,000 USDT virtual wallet; full engine fee **0.05% per side** and its modelled historical funding. The same research label economic assumption (**~21bps net label cost** with assumed fee/slippage/funding handling) was not changed.
- `backtest_period_days=7`, one fresh as-of August 1 model training cutoff per market. Only `train_period_days = 30 / 60 / 90 / 180` and research-only distinct `freqai.identifier` / bot name differ between config overlays. Exactly **four independent FreqAI model identifiers** in separate research-only result roots, zero order credentials, API/Telegram off, `dry_run=true`, no paper flag and original production V6 `NbotV6` untouched.
- The **native FreqAI research-only internal 12-candle/60min label-boundary purge** ran **25 times for each lookback: 100/100 model fit logs reported `boundary_violations=0`; 100/100 joblib fitted models saved; four distinct complete ZIP engine result archives**. The 180-day run trained from approximately **Feb 2, 2026**, with hourly feature warmup from approximately **Jan 24**, so existing January stage made it eligible. Each one-shot Docker used `--memory=6g --cpus=2`, one at a time, completed exit 0 and stopped. Disk/ram and 100 history files passed earlier audit.
- A small **BTC+ETH Aug 1–3 30-day smoke**, run before this pilot's full scoring, created two valid models and **zero trades**. August has also been used in earlier model warmup; neither pilot week nor August full month can be advertised as a pristine untouched blind selection test. Pre-registered May–August complete blocks remain unexecuted.

## Results — **ALL FOUR MODELS LOST MONEY**

All PnLs below are from the *actual Freqtrade simulated portfolio trade records* inside four native ZIP archives, **NOT** overlapping hypothetical opportunities. Fees and simulated funding are already included before the what-if extra execution charge.

| Trained on preceding | Saved native model fits | Completed simulated trades | Winners | Freqtrade PnL (USDT) | Maximum drawdown (USDT) | Extra +10bp round-trip | Extra +15bp | Extra +25bp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **30 days** | 25 | **28** | 8 | **−39.976652** | 62.157147 | −67.968091 | −81.963811 | −109.955250 |
| **60 days** | 25 | **27** | 13 | **−21.427845** | 43.229269 | −48.422179 | −61.919346 | −88.913681 |
| **90 days** | 25 | **23** | 4 | **−79.701474** | 79.701474 | −102.694240 | −114.190623 | −137.183390 |
| **180 days** | 25 | **10** | 4 | **−19.463025** | 28.045541 | −29.460547 | −34.459309 | −44.456832 |
| **NO TRADE** | 0 | 0 | 0 | **0** | 0 | 0 | 0 | 0 |

**Result:** Among these four variants, 180 days lost the least *absolute* USDT but also generated just 10 trades; 60 days reduced drawdown versus 30 days but still lost; 90 days performed worse. **Not enough data to choose a winning lookback** and **NONE beat NO TRADE (zero PnL)**. Their trading frequencies are unequal, so smaller loss alone is not evidence of improved per-trade expectancy or a statistically significant AI advantage. No longer model is promoted. Adding even *hypothetical* modest execution penalties makes every result materially worse. Actual book quotes, bid/ask, stop-market fills and venue settlement receipts remain **UNVERIFIED**. The stock Freqtrade `lookahead-analysis has_bias=Yes` remains unmodified; the prior fixed-model *decision-only* isolation from 3 trades supports bounded causal consistency, not overall leakage clearance.

## Reproducibility and raw evidence integrity

- **Source overlays**: `user_data/config.m2r-aug2026-{30,60,90,180}day-funded-purged.json`; automated [config parity test](../../tests/test_m2r_august_lookback_configs.py) **CI success** (all safeguards identical, only training window and model identifier different).
- **Exact independent native ZIP model/market/date/trade/cost audit**: [`scripts/m2r_august_fourwindow_compare.py`](../../scripts/m2r_august_fourwindow_compare.py) **exit 0**, confirming 25 markets, 25 fitted model joblibs, Aug1–Aug8 dates, exact 1× stake exposure, 0.05%/side engine trading fees, one position, no missing 25 market bundle and native PnL sum equivalence for all four; reports explicitly `NO TRADE`.
- **Full source-protected original archive and training logs, outside git** under V6-only `/root/nbot-v6-m1-20261016/multiwindow-aug-20261017/w{30,60,90,180}/` (each has independent `models/`, `backtest_results/*.zip` and `aug25-w*.log`).
- **Machine-readable consolidated JSON** at `/root/nbot-v6-m1-20261016/multiwindow-aug-20261017/aug-four-lookbacks-comparison.json`, SHA-256 **`ce082600c7539c879372bdd2b394e546a08624ed669aef692ba6e16adb5e1807`**. Full per-model ZIP SHA digests embedded in this JSON; no raw proprietary account info, user credentials or model binaries uploaded to GitHub.

## Implications and next experiment

**This was a meaningful first executed 4-way longer-history comparison, but not the complete May–August monthly walk-forward evaluation the owner approved.** The *next* scientifically necessary work is to complete the pre-registered calendar-block comparisons on independently designated full May/June/July/August chronology, with eligible 30/60/90/180-day windows (May/June 180 NOT eligible), native original price AI, breakout/pullback/combined after-cost AI, matched no-AI and NO TRADE, costs/wallet accounting identical, weekly model refits, and independent cost stress. Do not retrofit entry threshold/lookback to make Aug week look good, because August pilot outcomes are now inspected.

**Gate:** **M2 NO-GO, formal M3 unstarted, PAPER TRADING EXPLICITLY ON HOLD, M5A not built, M7 locked.** No paper daemon, owner live authorization, API keys or orders. Draft PR #50 remains unmerged, V5 unaffected.
