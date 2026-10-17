# NBOT V6 — M2 first after-fee baseline and stress evaluation

**Date:** October 17, 2026 (UTC)
**Status:** **M2 PARTIALLY COMPLETE — NOT ACCEPTED; DO NOT DEPLOY**.
**Market:** fixed 25 Binance USDT-M futures, 5m candles, historical **2026-10-01 through 2026-10-08**.
**Risk parity:** both backtest variants used **max_open_trades=1**, 1×, roughly **1,000 USDT fixed stake**, the same fixed 25-pair whitelist, **100,000 USDT simulated wallet**, initial stop **2%** and ROI target **5%**. Futures funding handling remains native Freqtrade; no exchange credentials or real orders were used.

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

## M2 acceptance checklist and remaining tasks

- [x] Freeze non-ML EMA20/EMA50 + prior 20-candle breakout/pullback benchmark without fitting an ML model.
- [x] Run the non-ML and **NO TRADE** comparators for the exact same 25 candidates, seven days, 1× and one-position risk.
- [x] Compare actual official Freqtrade fee-inclusive trades and exits to the M1 FreqAI result.
- [x] Rerun both strategies in Freqtrade with an explicitly doubled fee per side.
- [x] Publish trade-level per-coin/long-short summaries and *hypothetical* additional execution cost stresses, with all assumptions labeled.
- [x] Run official lookahead-analysis on the 30 tested non-ML signals (no bias detected).
- [ ] Obtain **observed**, timestamped bid/ask, depth and plausible maker/taker/slippage bands at the historical decision time, not merely present-day quotes.
- [x] Independently reconcile **actual Binance historical funding events** to both exported strategies, including sign, mark price and settlement time: **65/65 trades within five cents**; fee-tier/order-type fills remain [ ] separately unverified.
- [ ] Resolve the **actual flagged AI lookahead differences** after running the historical-only audit subclass. Offline prefix feature-causality and label separation pass, but model `do_predict` / entry/exit columns changed. NO M2 clearance.
- [x] Reproduce exact official exported **entry / rejected / exit record counts** and trade-level pair/side/time summaries across both strategies (AI: 34/68/34, no-ML: 31/6531/31).
- [ ] Complete raw eligible setup / FreqAI `do_predict` abstention / slot occupancy / exposure reconciliation (exported signal records alone are insufficient).
- [ ] Establish a defensible, repeatable base-cost and high-cost methodology beyond simple additive fixed-fill stresses. **M2 gate remains OPEN**.
- [ ] Extend comparisons through independent periods and regimes in **M3**; avoid optimizing solely on the first week.

**Decision:** Keep M2 **IN PROGRESS**; true historical Binance funding has now been checked, but unverified historical bid/ask/slippage and the **positive AI lookahead indicator-difference flag** explicitly BLOCK the acceptance gate. The non-ML comparator is a useful control but **not approved for deployment**. Next review cost-model fidelity and FreqAI/no-ML attribution; then M3 multiple chronological held-out windows. In parallel only offline M5A selector design/research is allowed; its eight-hour live scanner/rotation is **NOT built**, and the separate **up-to-20-position dry-run paper configuration remains intact but NOT commissioned**.

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
