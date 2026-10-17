# M2: Full September 2026 backtest — 25 coins, honest results

**Run date:** October 17, 2026. **Research-only** on the owner-authorized 8GB-Observation VPS.  
**Window:** **September 1, 2026 00:00 UTC to October 1, 2026 00:00 UTC** (30 complete days).  
**Decision:** **Both versions lost money. M2 remains NO-GO; M3/persistent M4/real trading NOT authorized.**

This test answers the owner's request to test an **entire month instead of relying on the profitable-looking first week of October**. We did **not** change the 25 market candidates, fit returns, risk rules, thresholds, or strategy code to make results look better.

## Results — September versus earlier October test


| Official Freqtrade historical outcome | **Sep 1–30 (30 days)** | Oct 1–7 (7 days; prior M2 evidence) |
|---|---:|---:|
| **AI V6 net P&L**, 0.05% fee per side | **−444.980 USDT** | −135.640 USDT |
| AI closed trades | **137** | 34 |
| AI wins / losses | **43 / 94** (31.4% wins) | 9 / 25 |
| AI max historical drawdown | **446.755 USDT** | 165.156 USDT |
| **No-ML baseline net P&L**, 0.05% fee per side | **−242.894 USDT** | **+169.849 USDT** |
| No-ML closed trades | **163** | 31 |
| No-ML wins / losses | **42 / 121** (25.8% wins) | 14 / 17 |
| No-ML max historical drawdown | **306.942 USDT** | 48.006 USDT |
| **NO TRADE** | **0 trades / 0 USDT** | 0 trades / 0 USDT |

The no-ML strategy beat AI by **202.086 USDT** in September, but **both lost**. Its positive October week did **not** generalize to September. This does **not** prove that an AI-less model would be better in every regime, that September represents all market regimes, or that we should buy/sell whichever coin happened to perform best in September.

## Verified method — September is NOT used as the initial training window

- Official **Freqtrade 2026.9** Docker image with FreqAI **LightGBMRegressor**, strategy `NbotV6`, original 30-day rolling training / seven-day historical backtest periods, original 5m/1h features and BTC correlation. The independent [September overlay](../../user_data/config.m2-september.json) makes a separate model folder so original M1/October results remain untouched.
- Previously downloaded real Binance public futures 5m/1h OHLCV, hourly mark and funding files for all **25** original candidates were **prepended back to July 15, 2026** using the official `download-data --prepend` command. The initial September training uses **August**, with earlier July data for the required 1h indicator warmup. Later historical retraining may train on completed earlier September candles available *as of that point*, not on future September candles.
- **25/25** candidates passed date continuity, missing candle/mark/funding availability and basic OHLCV checks for the entire period plus training warmup. [Dated machine audit](2026-10-17-september-25pair-data-audit.json).
- The official FreqAI log recorded **125 complete 30-day model fits** = **25 symbols × 5 historical weekly training windows**, with **zero error log lines** and backtesting exit code **0**.
- Both strategies: **100,000 simulated USDT starting wallet**, **1,000 USDT stake**, **one maximum simultaneous virtual position**, **1× leverage**. No Binance order credentials. The no-ML benchmark used the same frozen EMA20/EMA50 breakout/pullback strategy as October; no feature optimization.
- Official engine used **0.05% fee on entry and on exit**. Native Freqtrade funding accounting was retained; actual historical fills, best bid/ask at every timestamp, queue priority and stop slippage remain unproven, just as in the [original M2 assessment](../../M2_EVIDENCE.md).

## Fee and hypothetical additional-cost checks

A new full September backtest was run **for both versions** with the fee doubled to **0.10% per side**, rather than simply subtracting a fixed amount from the existing 0.05% results.

| Official Freqtrade version | 0.05% each side | 0.10% each side |
|---|---:|---:|
| AI V6 | **−444.980 USDT, 137 trades** | **−576.688 USDT, 137 trades** |
| No-ML | **−242.894 USDT, 163 trades** | **−388.318 USDT, 166 trades** |

Different fees can change orders and exit timing; the non-ML count changed from **163** to **166**.

For completeness, an **additional hypothetical** per-trade, total-roundtrip execution penalty of **10 basis points** (beyond the 0.05%-per-side baseline) changes net P&L to **−581.880 USDT for AI** and **−404.842 USDT for non-ML**. These are **fixed-trade estimates**, not observed bid/ask spreads or real fills; [machine-readable fee/coin/side/position-stress report](2026-10-17-september-30day-comparison.json) has +10/+25/+50/+100 basis-point scenarios. No additional-cost assumption turns either September strategy profitable.

## How much time was each approach taking market risk?

Directly reconciled all official closed-trade open/close timestamps across **720 hours** of September, including Freqtrade's valid **zero-minute** closes and checking that no two global positions overlapped.

| Measure | AI V6 | No-ML |
|---|---:|---:|
| Time with a position open | **292.583 hours** | **717.417 hours** |
| Share of month at risk | **40.637%** | **99.641%** |
| Time flat | **427.417 hours** | **2.583 hours** |
| Overlapping global positions | 0 | 0 |

**The non-ML strategy was in the market practically 24/7** and still lost money over September. It may be especially exposed to trend reversals and volatility. A win rate by itself does not measure the risk/reward of an AI selection gate.

## Independent public Binance funding check — with two exceptions

Queried Binance public USD-M historical funding events and independently calculated signed funding per exported trade by timestamp, direction, amount, mark price and funding rate.

- AI: **137 trades / 45 actual funding settlement events**. External event total **−0.103678 USDT** versus Freqtrade funding-field total **−0.172038 USDT**.
- No-ML: **163 trades / 89 actual settlement events**. External total **−1.101568 USDT** versus Freqtrade **−1.202064 USDT**.
- **One trade in each strategy failed the 0.05-USDT per-trade difference screen:** AI **ATOM** trade (September 30 23:20 → October 1 00:00), **0 actual settlement events / −0.100345 USDT engine funding**; and no-ML **INJ** trade (September 30 21:35 → October 1 00:00), **0 actual events / −0.100433 USDT engine funding**. Both trades were closed by the backtest at **the test-window boundary**. Other trade-level differences were at most five cents.

These are **not silently counted as fully reconciled**. There may be an engine's synthetic period-end funding assumption, closing-boundary accounting issue, or another explanation. We retain the original Freqtrade net P&L and flag the exceptions for investigation. They are ~0.1 USDT each, not enough to reverse losses of hundreds of USDT.

## Why the result matters

1. **September changed the conclusion about the simple strategy:** winning one October week is not enough; it lost in the entire previous month.
2. **AI still underperformed:** its trend/return filter reduced exposure, but the chosen trades were net negative in both studied periods. The target currently learns next-12-candle price returns, not actual after-cost trading outcomes.
3. **NO TRADE wins this September comparison** by avoiding negative trading outcomes altogether.
4. **A smart universe selector or changing strategy could help in principle**, but we cannot claim it does without later, *predefined and out-of-sample* tests. Selecting winners using hindsight from September would give a falsely profitable answer.
5. The official FreqAI lookahead-analysis warning and missing exact 2026 historical bid/ask/fill prices documented in [M2_EVIDENCE.md](../../M2_EVIDENCE.md) **remain unresolved**. An additional losing month does not fix those acceptance blockers.

**M2 research: September full-month extension PASSED its execution and audit checks; economic/release gate remains NO-GO. M3 NOT STARTED.** No persistent paper trading, 20-position service, active 8-hour selector, real orders, credentials, or changes to the V5 servers.

## How to repeat the tests (research only)

On an isolated V6 source checkout after Docker setup, download the earlier market history:

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai download-data --config /freqtrade/user_data/config.json --trading-mode futures --timeframes 5m 1h --timerange 20260715-20261001 --prepend
```

Check history for all 25:

```bash
docker run --rm --entrypoint python -v "$PWD:/freqtrade/work" freqtradeorg/freqtrade:stable_freqai /freqtrade/work/scripts/m1_audit_history.py --backtest-start 20260901 --backtest-end 20261001
```

Run September AI, with **prior-history training**:

```bash
docker run --rm --memory=6g --cpus=2 -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m2-september.json --strategy NbotV6 --freqaimodel LightGBMRegressor --timerange 20260901-20261001 --fee 0.0005 --cache none --export trades
```

Run September no-ML control:

```bash
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m2-nonml.json --strategy NbotV6NoML --timerange 20260901-20261001 --fee 0.0005 --cache none --export trades
```

For doubled fees, repeat with `--fee 0.001`. Save the four resulting ZIP archives, the FreqAI fit log and output audits privately. [Official-archive report generator](../../scripts/m2_september_summary.py) validates the exact results, original matching 25 pairs and 125 historical model fits, and outputs the compact JSON linked above. Do **not** overwrite the October-only model identifier or use trade mode.
