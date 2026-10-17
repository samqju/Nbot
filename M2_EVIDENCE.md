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

Freqtrade exports already include fees and a `funding_fees` field: the reconstructed sums of the recorded funding field in the *original* archives were **-0.722 USDT for AI** and **+0.368 USDT for non-ML**. These values are *part of the engine backtest records*, not separately reconciled against actual Binance settlement per position. The cost script does **not** double-charge them. Before acceptance, independently verify the funding convention and the exact event timestamps for futures markets.

### Lookahead/bias checking

**Official Freqtrade `lookahead-analysis` on frozen non-ML:** completed exit **0**, **30 tested signals**, `has_bias=No`, `biased_entry_signals=0`, `biased_exit_signals=0`. The lookahead tool deliberately overrides stake, maximum open trades and order types to test the signal path; **those tool-internal values are NOT the comparison backtest's risk settings**. Official documentation warns that no bias found in sampled signals is **not a proof of all-signal causality**.

**AI V6 lookahead tool:** not accepted yet. Freqtrade's analysis forcibly sets unlimited open positions, and our core V6 guard correctly refused it with `NBOT_V6_REQUIRES_ONE_GLOBAL_POSITION`. We chose **not** to loosen the primary AI strategy's paper/owner safety protections just to run this diagnostic. Separately audit FreqAI label isolation and devise an isolated safe, test-only method before declaring the AI path free of leakage. `set_freqai_targets` intentionally uses future close only for `&-forward_return` labels, while `feature_engineering_*` columns are past-only; this is a *source review observation*, not an accepted full independent audit.

## M2 acceptance checklist and remaining tasks

- [x] Freeze non-ML EMA20/EMA50 + prior 20-candle breakout/pullback benchmark without fitting an ML model.
- [x] Run the non-ML and **NO TRADE** comparators for the exact same 25 candidates, seven days, 1× and one-position risk.
- [x] Compare actual official Freqtrade fee-inclusive trades and exits to the M1 FreqAI result.
- [x] Rerun both strategies in Freqtrade with an explicitly doubled fee per side.
- [x] Publish trade-level per-coin/long-short summaries and *hypothetical* additional execution cost stresses, with all assumptions labeled.
- [x] Run official lookahead-analysis on the 30 tested non-ML signals (no bias detected).
- [ ] Obtain **observed**, timestamped bid/ask, depth and plausible maker/taker/slippage bands at the historical decision time, not merely present-day quotes.
- [ ] Independently reconcile funding fees against exchange historical settlement events and audit the treatment of fee tiers / order types.
- [ ] Complete FreqAI prediction-label isolation and no-leakage verification without disabling live/paper safety rules.
- [ ] Validate eligible signal counts/abstentions and exposure metrics across both models for the same period, and inspect the full trade distributions.
- [ ] Establish a defensible, repeatable base-cost and high-cost methodology beyond simple additive fixed-fill stresses. **M2 gate remains OPEN**.
- [ ] Extend comparisons through independent periods and regimes in **M3**; avoid optimizing solely on the first week.

**Decision:** Keep M2 **IN PROGRESS**; the non-ML comparator is a useful control but **not approved for deployment**. Next review cost-model fidelity and FreqAI/no-ML attribution; then M3 multiple chronological held-out windows. In parallel only offline M5A selector design/research is allowed; its eight-hour live scanner/rotation is **NOT built**, and the separate **up-to-20-position dry-run paper configuration remains intact but NOT commissioned**.

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
