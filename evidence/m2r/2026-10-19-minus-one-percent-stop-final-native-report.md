# Nbot V6 — Final −1% versus −2% initial stop-loss study

**Completed:** 2026-10-19 05:58:19 UTC / 11:28:19 IST. **No live/paper trading. No automated promotion.** Source frozen at `fc1cd22d13081017932c64860836816a32e5da3a`.

## Verdict

On the identical **uninterrupted July–September 2026** historical windows, changing only the initial protective stop from **−2% to −1%** made **14 of 16** combinations worse and **2 of 16** combinations less negative after the additional hypothetical **25 basis points** round-trip execution-cost stress. **None of the 16 at −1% achieved positive stressed net returns.**

No-time-limit custom exit remained removed; +5% native ROI was unchanged; the original trailing policy of +2% activation/1% gap remained on in the trailing variant. Eight original frozen 5m technical entry families, 25 original Binance USDT futures pairs, 1×/$1,000 notional one global position, 100,000 USDT simulated wallet, official Freqtrade native fee 0.05% each way, existing funding and protections unchanged. Every finite period ends with one unavoidable forced historical-end exit.

Results were separately SHA256-reconciled by [independent 32-ZIP audit](../../scripts/m2r_v6_stop_one_final_audit.py), which also checked actual underlying ZIP strategy stoploss field, +5% ROI, one slot, original coin universe, native fees and source trade-ledger economics, and zero 60-minute exits.

## Full result table

All results are **USDT** for standalone native portfolios and include original Freqtrade fees **plus** extra hypothetical 0.25% roundtrip stress. Fixed = +5% ROI/stop only; trailing = identical ROI/stop plus original trailing rule. These are **NOT** combined executable portfolios.

| Strategy | Exit | −2% stop | −1% stop | Improvement with −1% |
|---|---|---:|---:|---:|
| EMA Cross | Fixed | −513.12 | −768.45 | −255.33 |
| EMA Cross | Trailing | −346.96 | −530.37 | −183.41 |
| Donchian Breakout | Fixed | −433.51 | −224.74 | **+208.77** |
| Donchian Breakout | Trailing | −189.60 | −1,082.49 | −892.89 |
| Bollinger Reversion | Fixed | −217.48 | −544.25 | −326.77 |
| Bollinger Reversion | Trailing | −424.55 | −976.30 | −551.75 |
| RSI Reversion | Fixed | −434.90 | −641.71 | −206.81 |
| RSI Reversion | Trailing | −64.26 | −1,383.89 | **−1,319.63** |
| MACD Momentum | Fixed | −39.63 | −154.41 | −114.78 |
| MACD Momentum | Trailing | −477.08 | −1,173.80 | −696.72 |
| Stochastic Reversal | Fixed | −134.99 | −662.11 | −527.12 |
| Stochastic Reversal | Trailing | −613.84 | −1,197.53 | −583.69 |
| ATR Breakout | Fixed | −453.26 | −184.67 | **+268.59** |
| ATR Breakout | Trailing | −526.61 | −1,238.06 | −711.45 |
| Volume Trend | Fixed | −61.24 | −407.18 | −345.94 |
| Volume Trend | Trailing | −175.40 | −645.81 | −470.41 |

**Mechanism:** A tighter stop increased the number of stops and opened the single capital slot sooner to execute more weak signals. For EMA Cross fixed, −2% stop yielded **68 trades, 52 initial stop-loss exits and 15 +5% ROI exits**; −1% stop yielded **126 trades, 110 stop-loss exits and 15 +5% ROI exits**. Stressed net worsened from **−513.12** to **−768.45 USDT**. These are separate backtests with differing entries after the first exit, not paired counterfactual P&L.

## Scientific conclusions

- **A hard −1% stop does bound the nominal initial adverse movement more tightly per trade but does not bound realized fill risk or cumulative portfolio losses.** More false stops, turnover and higher cost can worsen aggregate economic results.
- **Do not claim the eight technical setups have no information at all**: they have not been fairly compared under a properly calibrated exit-matched ML selection model on unseen market data. They are *not economically validated* under the studied policies.
- **40% of trades reaching +2% or +3% favorable price movement does not guarantee profit.** Need REALIZED exit rates and payoff distribution after native fees, additional stressed slippage/funding and time capital occupied. With 0.35% round-trip cost assumed, 40% average +2% winner and 60% −1% loser gives approximately **−0.15% net/trade**, while 40% average +3% winner and 60% −1% loser gives approximately **+0.25% net/trade**. With 60% losers at −2%, even +3% winners average to **−0.35% net/trade** at 40% win rate. These are arithmetic illustrations, not measured price probabilities.
- Under the frozen −2% no-time trailing EMA result, **65/121 winning trades (~53.7%)** still produced **−346.96 USDT** after the extra hypothetical cost stress. Under RSI trailing −2%, **66/121 (~54.5%)** winning trades still produced **−64.26 USDT** stressed. More than 50% positive trades can still lose money.
- The previous Global AI LightGBM research trained to the +5%/−2%/60-minute label, with a hard ≥50% positive-class gate, rather than jointly learning expected net payoff for the owner's +1/+2/+3% preferred exits and capital occupation. No trades were selected. Interpret this as *inadequate entry/exit-aligned model design*, not as "AI trading cannot work."

## Roadmap decision

**Stop tuning initial stops and trailing combinations on already inspected July–September data.** Prioritize the [predeclared edge-first exit-matched AI research plan](2026-10-19-proposed-edge-first-ai-research-plan.md): causal complete candle features, strategy/coin/regime-aware expected net-profit distributions (not just probability of a win), first-touch +1/+2/+3/+5% labels, adverse-excursion and trailing paths, realistic costs, time-in-position, standard lookahead/recursive audit, chronological purging, and a genuinely untouched post-September test. Compare all 25×8 eligible side×exit options against NO TRADE in **one** real one-slot native Freqtrade portfolio, with confidence intervals and minimum effective trade count. Do not change thresholds to fit known July–September.

**Evidence:** Official VPS job `nbot-v6-stop-one-20261019.service` exited cleanly (`ActiveState=inactive, Result=success`); no research Docker running after completion. `/root/nbot-v6-m1-20261016/stop-one-percent-20261019/status.json` `jobs_completed=16/16`, `status=complete_research_only`; 16 new native ZIPs and 16 original no-time −2% controls all SHA256 verified and economically reconciled, no other previous Stage 1/2/3 results overwritten. Study is exploratory on already examined dates; no validation of future profitability.
