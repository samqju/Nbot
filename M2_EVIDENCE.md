# NBOT V6 — M2 historical benchmarks: September full month and October first week

**Date:** October 17, 2026 (UTC)
**Status:** **M2 INVESTIGATION COMPLETED WITH A NO-GO DECISION. M2 RELEASE/ACCEPTANCE GATE FAILED. DO NOT DEPLOY OR ADVANCE TO M3.**
**Market:** fixed 25 Binance USDT-M futures, 5m candles, historical **2026-10-01 through 2026-10-08**.
**Risk parity:** both backtest variants used **max_open_trades=1**, 1×, roughly **1,000 USDT fixed stake**, the same fixed 25-pair whitelist, **100,000 USDT simulated wallet**, initial stop **2%** and ROI target **5%**. Futures funding handling remains native Freqtrade; no exchange credentials or real orders were used.

## New full-month September 2026 comparison (owner-requested extension)

**September 1–30 (30 complete days):** Public Binance history was extended back to **July 15**, with **25/25** candidate data audits passing. FreqAI trained **125 real LightGBM models** (25 coins × 5 sequential 30-day rolling training windows), with **zero errors**, and tested September only after training from earlier data. The static 25-coin universe, one global position, 1× leverage and 1,000-USDT stake remained unchanged.

| Official historical metric | AI V6 | Frozen non-ML | NO TRADE |
|---|---:|---:|---:|
| September net P&L, 0.05% fee per side | **−444.980 USDT** | **−242.894 USDT** | **0** |
| September closed trades | **137** | **163** | 0 |
| September wins / losses | **43 / 94** | **42 / 121** | 0 |
| September win rate | **31.4%** | **25.8%** | N/A |
| September maximum drawdown | **446.755 USDT** | **306.942 USDT** | 0 |
| September net P&L, 0.10% fee per side | **−576.688 USDT** (137 trades) | **−388.318 USDT** (166 trades) | **0** |
| Share of 720h in a trade (base fee) | **40.637%** | **99.641%** | 0 |

**Both strategies lost money during September.** The simple strategy's **+169.849 USDT October first-week result** was not representative of September. AI underperformed no-ML by **202.086 USDT** in September, while NO TRADE was the best of these three alternatives. Extra hypothetical spread/slippage cost deductions make both results worse, not better.

Independent September funding reconciliation found **one approximately 0.10-USDT discrepancy per strategy** on positions force-closed at exactly the October 1 backtest boundary (AI ATOM and non-ML INJ); **do not claim every September funding field reconciled precisely**. The discrepancies are small compared with the losses but remain logged as a check failure. Historical market fill/bid-ask data and the earlier FreqAI lookahead warning remain unresolved.

**Full reproducible September report:** [30-day analysis](evidence/m2/2026-10-17-september-full-month-analysis.md), [all-25 history audit](evidence/m2/2026-10-17-september-25pair-data-audit.json), [per-market/fee/funding/exposure machine evidence](evidence/m2/2026-10-17-september-30day-comparison.json), [report generator](scripts/m2_september_summary.py).

**M2 decision unchanged: research execution succeeded, but acceptance FAILED / NO-GO. M3 and persistent paper/live trading remain unapproved.**

## What was implemented

- [Frozen non-ML benchmark source](user_data/strategies/NbotV6NoML.py), with matching EMA20/EMA50 trend, prior-20-bar breakout / EMA pullback entries, plus trend-reversal exits. It uses no future price labels or FreqAI predictions; no model is trained. It is **dry-run only**, refuses exchange credentials and is not commissioned as a paper or live service.
- [Benchmark configuration](user_data/config.m2-nonml.json), which turns off FreqAI in a separate overlay but retains the fixed universe, wallet, global slot limit, leverage/stake and Binance futures settings. Original V6 strategy/config are unchanged.
- **NO TRADE benchmark:** explicitly 0 positions, 0 notional exposure, 0 realized trading P&L and 0 transaction costs. Cash yield/interest is not modeled.
- [Trade-by-trade reproducible after-cost script](scripts/m2_evaluate.py), reading official Freqtrade ZIP exports, checking matching dates, risk, wallet and whitelist, reconstructing published net P&L, then adding **illustrative incremental cost** stresses (not observed order book spreads or fill losses) and summarizing every trade by pair and long/short side.
- [Machine-readable first-week breakdown](evidence/m2/2026-10-17-first-week-cost-sensitivity.json). Full original trade ZIPs, downloaded market files and model artifacts remain privately on the owner's **8GB-Observation** VPS under `/root/nbot-v6-m1-20261016/source/user_data/backtest_results/`.

## The first 7-day results

| Metric | FreqAI V6 (as already validated in M1) | Frozen non-ML comparator | NO TRADE |
|---|---:|---:|---:|
| Simulated trades | 34 | 31 | 0 |
| Winners / losers | 9 / 25 | 14 / 17 | 0 / 0 |
| Win rate | 26.5% | 45.2% | N/A |
| Engine net P&L, **0.05% fee per side** | **-135.640 USDT** | **+169.849 USDT** | **0.000 USDT** |
| Official max drawdown | 165.156 USDT | 48.006 USDT | 0 |
| Difference in net P&L | Baseline better by **305.489 USDT** | — | — |

**This does NOT show reliable profitability or prove that the ML model caused the loss.** The non-ML strategy has its own exits (trend-reversal only), while V6 also has AI prediction-dependent exits and an AI threshold for entry. Thus these are *strategy variants* sharing the same technical setups, not a controlled single-variable model attribution experiment. A single week is too short to assess market regimes and statistical uncertainty.

### Engine rerun with higher fees

Official Freqtrade `--fee` is charged **on both entry and exit**. A second complete pair of official backtests used **0.10% per side** (`--fee 0.001`, double the original base fee). Since fee changes can affect trades/timing, this is better than simply assuming identical fills.

| Fee / strategy | Trades | Net simulated P&L |
|---|---:|---:|
| 0.05% each side, FreqAI | 34 | **-135.640 USDT** |
| 0.05% each side, non-ML | 31 | **+169.849 USDT** |
| 0.10% each side, FreqAI | 34 | **-169.555 USDT** |
| 0.10% each side, non-ML | 30 | **+138.554 USDT** |

Even at twice the base fee, the simple variant beat FreqAI *in this specific window*. The altered 30-vs-31 trade count for non-ML confirms that **different fee assumptions can change the trading path**.

### Extra hypothetical roundtrip spread/slippage/cost stress

These are applied **in addition to** the official engine's 0.05% per-side fee *on fixed exported original fills*. They **do not** recalculate order fills, execution priority, funding timing or stop-loss hits; not a replacement for a realistic exchange execution model.

| Additional *total roundtrip* bps | FreqAI adjusted P&L | Non-ML adjusted P&L |
|---:|---:|---:|
| 0 | -135.640 USDT | +169.849 USDT |
| 10 | -169.543 USDT | +139.044 USDT |
| 25 | -220.396 USDT | +92.837 USDT |
| 50 | -305.152 USDT | +15.825 USDT |
| 100 | -474.664 USDT | **-138.199 USDT** |

The non-ML baseline's **fixed-fill** hypothetical break-even additional cost is approximately **55.137 bps per round trip**; this is **not an observed market spread** or a reliable live break-even threshold.

Freqtrade exports include fees and a `funding_fees` field, and the cost-stress script **does not double-charge them**. **Independent funding-event reconciliation is now PASSED for these trade windows:** Using Binance's unauthenticated USD-M `/fapi/v1/fundingRate` response, per-trade position size, settlement mark, timestamp and long/short sign, the AI trades had **11 funding events**, expected **-0.721885 USDT** versus Freqtrade **-0.721893 USDT**; the non-ML trades had **21 events**, expected **+0.367678 USDT** versus Freqtrade **+0.367662 USDT**. **0/65 trades** differed by more than **0.05 USDT**, and the total absolute per-trade difference was **0.000008 AI / 0.000018 non-ML USDT**. See the [per-trade Binance evidence](evidence/m2/2026-10-17-public-binance-funding-reconciliation.json) and [reproducible tool](scripts/m2_funding_reconcile.py). This validates **the specific historical funding events and engine sign/amount**, not order-book fill quality, future fee tiers or all future market regimes.

### Lookahead/bias checking

**Official Freqtrade `lookahead-analysis` on frozen non-ML:** completed exit **0**, **30 tested signals**, `has_bias=No`, `biased_entry_signals=0`, `biased_exit_signals=0`. The lookahead tool deliberately overrides stake, maximum open trades and order types to test the signal path; **those tool-internal values are NOT the comparison backtest's risk settings**. Official documentation warns that no bias found in sampled signals is **not a proof of all-signal causality**.

**AI V6 lookahead tool: executed via a dedicated NO-LIVE audit subclass, but flagged differences — NOT CLEAN.** A separate `NbotV6M2Audit` inherits the core strategy's exact indicators/signals; it allows Freqtrade's forcibly unlimited-slot lookahead simulation only with dry-run enabled, empty credentials, disabled API/Telegram, an explicit audit overlay and the literal `lookahead-analysis` CLI. **Production `NbotV6` is untouched.** Official 25-pair, 8-signal audit finished (exit code 0) with `has_bias=Yes`: `biased_entry_signals=0`, `biased_exit_signals=0`, but changed indicator values for `&-forward_return`, its mean/std, `do_predict`, `DI_values`, `enter_tag`, `enter_long`, `exit_long` and `exit_short`. Freqtrade documents expected FreqAI `&-` target false positives; **that does not automatically clear changing prediction/entry/exit fields**. Model retraining and pairlist slicing might contribute, but this is a hypothesis, not accepted evidence. [Full diagnostic record](evidence/m2/2026-10-17-ai-lookahead-and-signals.md). Dedicated offline tests confirm 14/28 EMA/volatility/momentum/volume feature columns are unchanged by appended future candles, while `&-` is a separate forward label, not a feature. **The AI leakage gate remains UNRESOLVED.**

### Independent trade/signal/rejection accounting

Re-ran the official 25-pair `backtesting --export signals --cache none` for both variants (base 0.05% fee per side). The historical P&L reproduced exactly. [Raw signal-summary evidence and interpretation](evidence/m2/2026-10-17-ai-lookahead-and-signals.md).

| Export | AI V6 | Frozen non-ML |
|---|---:|---:|
| Entered signal rows / closed trades | 34 / 34 | 31 / 31 |
| Rejected-entry signal rows | **68** | **6,531** |
| Exited signal rows | 34 | 31 |

These represent engine signal/rejection *records*, not 6,531 independently available trades; the one-global-position cap rejects repeat entries while the slot is occupied. AI `do_predict` abstentions and all potential raw EMA setups are **not** fully captured by this export, so total eligibility/abstention/exposure accounting is not yet complete. The separate **20-slot future paper mode remains configured but intentionally inactive**.

## M2 acceptance checklist — final October 17 review (technical work vs approval)

- [x] Freeze non-ML EMA20/EMA50 + prior 20-candle breakout/pullback benchmark without fitting an ML model.
- [x] Run the non-ML and **NO TRADE** comparators for the exact same 25 candidates, seven days, 1× and one-position risk.
- [x] Compare actual official Freqtrade fee-inclusive trades and exits to the M1 FreqAI result.
- [x] Rerun both strategies in Freqtrade with an explicitly doubled fee per side.
- [x] Publish trade-level per-coin/long-short summaries and *hypothetical* additional execution cost stresses, with all assumptions labeled.
- [x] Run official lookahead-analysis on the 30 tested non-ML signals (no bias detected).
- [x] Retrieve and timestamp-match **historical Binance Vision book-depth bands**, detecting missing/stale snapshots instead of inventing good fills. **57 of 59 archive files available; 113/130 entry/exit events have fresh depth; 17 missing/stale; 113/113 fresh events show >=40.22 times the $1k order notional inside the 0.2% band.**
- [ ] Exact 2026 historical best bid/ask spreads and order-level fill/queue/stop-slippage: **UNAVAILABLE/NOT PROVEN**. Binance's matching public 2026 bookTicker archive returned **HTTP 404**; depth-band snapshots cannot replace a full historical order book. Conservative stress analysis is reported, **not observed fill data**.
- [x] Independently reconcile **actual Binance historical funding events** to both exported strategies, including sign, mark price and settlement time: **65/65 trades within five cents**; fee-tier/order-type fills remain [ ] separately unverified.
- [x] Independent as-of / pair-context reproducibility: **BTC and ETH forecasts, their model statistics, do_predict and DI_values matched exactly** for **2,016 candles each** when trained against 25-coin versus single-pair contexts, and for a strict earlier **576-candle as-of prefix** against the complete 7-day future. This is strong evidence against simple future-data drift for these two coins.
- [ ] Resolve why official **FreqAI lookahead-analysis still flags `has_bias=Yes`** on eight sampled signals and changes to some prediction/decision columns. The BTC/ETH controlled tests do **not** automatically clear all 25 coins or the diagnostic warning; NO M2 AI leakage clearance.
- [x] Reproduce exact official exported **entry / rejected / exit record counts** and trade-level pair/side/time summaries across both strategies (AI: 34/68/34, no-ML: 31/6531/31).
- [x] Audit original 25 market prediction artifacts, reconstruct raw causal setups, `do_predict` abstentions and final AI eligibility for all **50,400** 5m market-candle decisions. Original **6,837** technical setups → **28** blocked by unavailable/outlier AI predictions → **6,661** rejected by model predicted-direction/return requirement → **148** eligible AI candidate signal rows. Official AI engine filled **34** and explicitly rejected **68**; **46** remaining candidates were not separately exported as rejected rows. Do not mislabel all raw candidates as available executable orders.
- [x] Verify actual closed-position exposure and one-slot constraint: **AI in market 78.583h/168h (46.776%); non-ML 167.667h/168h (99.802%)**, zero overlapping positions in both. This materially changes the economic interpretation of the first-week comparison.
- [x] Reproduce **historical depth-conditioned scenario stresses** using each trade's entry/exit timestamp, order notional and 30-second liquidity check, charging **additional** penalties for missing/stale events. Results, actual archival limitations and code are published. **This quantifies risk but is NOT an observed executed spread or stop-fill simulation.**
- [ ] Establish **true historical fill/queue/impact/stop execution certainty**, account-specific fee tier and independently observed bid/ask spread for every entry and exit. This is **not possible from the available 2026 public archives** alone. Therefore the M2 acceptance gate FAILS, rather than being marked passed.
- [ ] Extend comparisons through independent periods and regimes in **M3**; avoid optimizing solely on the first week.

**Decision:** Keep M2 **IN PROGRESS**; true historical Binance funding has now been checked, but unverified historical bid/ask/slippage and the **positive AI lookahead indicator-difference flag** explicitly BLOCK the acceptance gate. The non-ML comparator is a useful control but **not approved for deployment**. Next review cost-model fidelity and FreqAI/no-ML attribution; then M3 multiple chronological held-out windows. In parallel only offline M5A selector design/research is allowed; its eight-hour live scanner/rotation is **NOT built**, and the separate **up-to-20-position dry-run paper configuration remains intact but NOT commissioned**.

## Final M2 review — measured evidence, limitations and no-go decision

### Historical execution liquidity: measured as-of data, not guessed

Downloaded Binance Vision **30-second historical USD-M futures order-depth snapshots** at the specific entry/exit dates from the original **65** one-week trades; this is a reproducible archive with public URLs and ZIP SHA-256 hashes. Actual older USD-M `bookTicker` direct snapshot archive for the tested date returned **HTTP 404**. Binance has publicly documented suspension of that best-bid/best-ask archive. **Book-depth bands cannot reveal the exact spread, maker fill probability or intrasecond stop-market loss.**

- **59** pair/day archives requested, **57** available. The two missing were **OPUSDT and TRXUSDT for October 8**; the data collector reported their HTTP errors.
- **130** trade-side events audited: **113** matched a prior, non-suspect timestamped snapshot within **45 seconds**; **17** had stale or otherwise unverified snapshots (some gaps were many hours). These events must **not** be treated as free or frictionless.
- In those **113 matched events**, historical cumulative buy/sell side liquidity within **0.2%** of the mid/reference was at least **40.22× the position's notional** (median **380.61×**). This supports basic size feasibility when the snapshot is reliable, **not** promised cost, quote spread or guaranteed market impact.
- Detailed [per-event depth/quality evidence](evidence/m2/2026-10-17-historical-depth-trade-time-audit.json) and [historical depth audit script](scripts/m2_bookdepth_audit.py).

**Cost scenario with different penalties for verified versus stale snapshots**, charged in addition to the base historical 0.05% exchange fee *per side* and existing funding. These are **assumptions**, not actual historical fills:

| Extra assumed cost on each entry/exit | AI V6 adjusted P&L | Non-ML adjusted P&L |
|---|---:|---:|
| No additional cost | -135.640 USDT | +169.849 USDT |
| Matched 5 bps / stale 25 bps | -185.520 USDT | +121.191 USDT |
| Matched 10 bps / stale 50 bps | -235.400 USDT | +72.533 USDT |
| Matched 20 bps / stale 100 bps | -335.160 USDT | **-24.784 USDT** |
| Matched 40 bps / stale 200 bps | -534.681 USDT | -219.417 USDT |

[Per-event quality-adjusted scenario output](evidence/m2/2026-10-17-snapshot-quality-cost-stress.json) and [generator](scripts/m2_depth_cost_stress.py). This remains a **fixed-trade replay**: additional costs did NOT change actual entry selection, order fill conditions or holding times, so do not call these results realized returns.

### What the AI actually filtered — 50,400 original 5m decisions

Rebuilt the original exact causal EMA20/EMA50, prior-20-bar breakout and pullback setups from downloaded 5m candles for each of the 25 coins. Joined by **exact UTC candle timestamp** to the original full-universe **2016-per-coin** FreqAI prediction artifacts and applied the original **+/-0.006 predicted return** requirement.

| Decision stage | Count |
|---|---:|
| 25 coins × 2,016 completed 5m candles | **50,400** |
| Raw long/short technical setups | **6,837** (3,437 long; 3,400 short) |
| Technical setups blocked by `do_predict != 1` or invalid prediction | **28** |
| Technically valid/model-ready setups rejected by return threshold or direction | **6,661** |
| Original AI long/short candidate rows eligible before portfolio trade-slot constraints | **148** (128 long, 20 short) |
| Original Freqtrade AI entries / explicit rejected rows / exits | **34 / 68 / 34** |
| Raw eligible signal rows not reflected in those two engine categories | **46** |

The engine's no-entry/rejection handling does not enumerate these remaining 46 in the exported rejected rows; they may be suppressed by active same-pair positions or backtest engine timing. No claim that they were profitable missed trades. [Reconstructed per-pair decision-gate evidence](evidence/m2/2026-10-17-original-model-decision-gates.json) with [audit script](scripts/m2_decision_audit.py).

### The unusually high non-ML exposure explains why profits are not directly comparable

Official trade timestamps, independently audited, reveal **zero simultaneous overlapping trades** in either historical variant but wildly different exposure: AI occupied its single global trade slot for **78.583 hours of 168 (46.776%)**; the non-ML comparator occupied it for **167.667 hours (99.802%)**, with only **0.333 hours flat**. Non-ML was almost always at market risk! [Timestamped exposure evidence](evidence/m2/2026-10-17-original-risk-exposure.json) and [reproducible script](scripts/m2_exposure_audit.py). This is a strong reason **not to treat one winning week as a dependable profitable strategy**.

### Controlled checks of future-data invariance — helpful but not enough to override the official warning

We separately trained the unchanged FreqAI configuration for **BTC and ETH alone** and compared each 7-day forecast series to the respective coin's original 25-pair 7-day run: all **2,016 timestamps per coin** matched exactly for the predicted return, training-label mean/std, model filter (`do_predict`) and distance-index columns (`DI_values`). [Context evidence](evidence/m2/2026-10-17-prediction-invariance-btc-eth.json).

We also trained with only **October 1–3** available for the evaluation period, and compared those first **576 five-minute predictions per coin** against the original October 1–8 forecast. **All 576 BTC and 576 ETH rows matched exactly across every reported model output**; adding five later days had **zero measured effect** on those earlier forecasts. [Actual as-of/future-truncation evidence](evidence/m2/2026-10-17-asof-future-truncation-predictions.json). This supports causal behavior *on those two tested coins and that frozen training cutoff*, and the separate unit tests already show past-only feature prefixes and forward-only labels.

**However,** the official Freqtrade lookahead-analysis on eight tested AI entries/exits still reports `has_bias=Yes` and changed `do_predict`/indicator/decision columns. Model retraining or signal-sliced replay differences are plausible explanations, **not fully established**; the 2-coin checks cannot certify all 25 or every training/model-rotation scenario. We **explicitly refuse to wave away the warning**. The strategy may be safe under the controlled frozen cases and still have an unresolved test sensitivity. An independent all-market as-of/walk-forward protocol and explanation of the warning are needed before any M3-based adaptive model claim.

### M2 outcome: investigation finished, deployment gate FAILED (NO-GO)

The request to **complete M2 properly** results in an evidence-backed **NO-GO**, not a manufactured positive pass. We have run the non-ML/AI/NO TRADE controls, official doubled-fee reruns, real historical funding reconciliation, independent 30-second depth screen, several conservative cost scenarios, full AI prediction filters and risk-time audits, source-prefix causality checks and controlled BTC/ETH training-history tests.

**The remaining acceptance blockers are concrete:**
1. Exact historic spread/queue/fills/stop slippage and account-specific fee tier cannot be verified from the available public October 2026 data; 17/130 even lack timely depth-band coverage. Real future paper order-book snapshots can prospectively measure them before M4.
2. Official FreqAI lookahead-analysis still flags changed prediction/entry/exit columns; until reconciled, no claim that every AI entry is free of future-information or replay artifacts.
3. No evidence that AI improves on the simple strategy or NO TRADE; in the only validated first week, AI lost money. The simple strategy's apparent profit depends on very high market exposure and weakens under large (hypothetical) fill penalties.

**Decision:** M2 **RESEARCH ASSESSMENT COMPLETE; ACCEPTANCE FAILED / NO-GO.** This does **not** unlock M3, M4 persistent paper, M5A live selector or M7 real money. The blockers must be addressed or the architecture changed in an explicitly owner-reviewed new study. Do not force a roadmap checkbox to "pass" merely because the requested tests have been run.

## Reproduction on the owner-authorized V6 research VPS

From `/root/nbot-v6-m1-20261016/source` with the downloaded Binance data, no credentials and only short-lived official Docker test containers:

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m2-nonml.json --strategy NbotV6NoML --timerange 20261001-20261008 --fee 0.0005 --export trades
```

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m2-nonml.json --strategy NbotV6NoML --timerange 20261001-20261008 --fee 0.001 --cache none --export trades
```

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai lookahead-analysis --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m2-nonml.json --strategy NbotV6NoML --timerange 20261001-20261008 --minimum-trade-amount 10 --targeted-trade-amount 30 --fee 0.0005
```

To reproduce the fixed-export cost sensitivity exactly, see `python3 scripts/m2_evaluate.py --help` and supply the respective original official ZIP file paths to `--ai`, `--baseline`, and the ignored output JSON path.

Official Freqtrade references: [Backtesting and fee modeling](https://www.freqtrade.io/en/stable/backtesting/), [lookahead limitations](https://www.freqtrade.io/en/stable/lookahead-analysis/).
