# NBOT V6 — Native trailing-stop execution audit and critical AI design review

**Recorded:** 19 October 2026. **Source:** Actual original Stage1 native Freqtrade ZIP trade ledgers, saved Stage2 exit-policy comparison, Stage3 conserved forecast rejection parquet and [global dataset/ranker source](../../scripts/m2r_v6_global_dataset.py). **Read-only checks; no trade submitted or model promoted.**

## Verdict

It would be wrong to interpret the zero-trade global-AI result as evidence that AI cannot trade, that humans outperform AI, or that trailing stops failed because prices never advanced +2%. The existing research design has material target/exit alignment and policy-gate weaknesses that require correction and new unseen validation.

### Original Stage1 8 families × 3 months: actual native trade outcomes

All sums below aggregate **separate, independently simulated family-month portfolios**, not one deployable eight-strategy combined portfolio. Per-trade Freqtrade `max_rate/min_rate` records have candle-level sequencing limitations. Native P&L includes native modeled fees/funding; additional hypothetical 25bp stress is NOT included in the exit-category figures below.

| Native outcome | Fixed exit policy | Original +2% activation / 1% trailing gap |
|---|---:|---:|
| Total native trades | 15,982 | 16,274 |
| Recorded favorable excursion ≥+1% | 2,628 | 2,743 |
| Recorded favorable excursion ≥+2% | 755 | 821 |
| Recorded favorable excursion ≥+3% | 273 | 143 |
| Closed by +5% ROI | 56 | 22 |
| Closed by trailing stop | n/a | **583** |
| Closed by initial stop loss | 611 | 615 |
| Closed by fixed 60-minute time exit | **15,295 (95.7%)** | **15,033 (92.4%)** |

The native ZIPs explicitly show **583 `trailing_stop_loss` exits, and every one of those 583 exits is profitable after modeled native fees**, aggregating **+8,577.34 USDT** in these separate family-month backtests. Therefore the original trailing rule *did activate and secure gains*.

But **615 initial stop exits totaled −12,847.08 USDT**, and **15,033 60-minute expiry exits totaled −13,983.65 USDT**; even with +1,099.19 USDT from 22 ROI exits, the aggregate independent fixed trailing-policy studies had negative native net P&L (~−17,190.78 USDT; plus optional 25bp stress more negative). These exit-category totals are **descriptive and not causal counterfactuals**, since the portfolios take somewhat different trades after earlier exits.

Only **821/16,274 (~5.0%)** of original trailing-policy trades had a recorded favorable excursion of at least +2% at any point in their native trade record. A trailing stop that activates only at +2% therefore cannot protect the majority of 60-minute trades. A lower activation threshold might protect more trades but could also lose profitable followthrough or suffer cost drag; it needs genuinely prespecified aftercost native experiments rather than assumption.

**Important distinction:** Global Stage3 fixed/trailing native backtests each entered **zero positions** because every generated forecast was rejected. Its trailing A/B result of zero vs zero provides **no information** about whether trailing protects actual winning trades.

### Conservative earlier-profit-before-loss diagnostic

The originally failed Stage2 loss-path diagnostic (`REVERSE_DATE_IN_NATIVE_TRADE` on valid same-candle stops) was patched to treat equal entry and exit timestamps as inconclusive rather than invalid. An isolated **read-only** re-run on one original EMA Cross July 2026 native backtest using the original historical 25-pair 5m feathers succeeded:
- 594 native trades, 357 losing trades.
- Of 357 losing trades with complete pre-exit chronological candle history, 3 had reached **+1% favorable gross movement** on a previous complete candle; **none** had reached +2% or +3% by this especially conservative definition.
- This diagnostic **does not count** an ambiguous favorable high occurring within the eventual exit candle and is **not executable profit or guaranteed rescue**. It is only one strategy-month, not a universal statement for the other 23 strategy-month records.
- The original Stage2 `loss_path_diagnostic_failed=true` remains an accurate historical status for that run; this new separate successful check does not rewrite the earlier failed audit or claim all 120 exit comparisons were invalid.

### Global AI research design mismatches found in source

1. **Forecast target vs actual desired exit:** [global dataset](../../scripts/m2r_v6_global_dataset.py) uses a **fixed +5% take-profit, −2% stop, 12×5m=60m horizon** proxy in training. Model/selection scoring and later fixed/trailing native comparison did **not** train separate exit-matched realized-target labels for the user's +1/+2/+3% protective exits. An AI trained on a mismatched target is not a clean test of whether it can choose the coin/strategy/exit configuration best suited to a given market.
2. **Arbitrary 50% win-probability gate:** the ranking loop explicitly excludes forecasts with `calibrated_positive_probability < 0.50`, regardless of positive expected risk-adjusted P&L. Positive expectancy is not equivalent to positive win probability above 50% when reward/loss sizes differ. This gate can exclude some profitable-payoff setups in principle; simply removing it after seeing July–Sep would be data snooping.
3. **Very high conservative penalties:** candidate score subtracts the empirical calibration absolute residual (75th percentile), an additional hypothetical 25bp cost, and a 0.25 downside-reserve penalty, then requires at least a 0.1% additional conservative positive edge, and checks regime direction/liquidity. Those are prudent research gates but collectively generated zero selections; they have not been calibrated against unseen profitable trade decisions.
4. **Simplified, not learned dynamic market regime:** trend-up/trend-down/range is assigned from one `trend` feature with fixed 0.003 cutoffs, and short trades in an uptrend / longs in a downtrend are categorically rejected. This is *not* the fully learned multi-strategy switching policy the user envisioned.
5. **Feature/model limitations:** LightGBM family and pair embeddings plus nine numeric indicators were trained to predict individual proxy outcomes, not separately measured actual portfolio opportunity cost, fee/funding/slippage, setup-dependent stop trajectories and true as-of orderbook liquidity. Although forecasts were generated for all strategies and 25 coins, choosing the highest conservative predicted score is not proof the model learned to rank profitable trade opportunities reliably.
6. **Viewed date range:** July–September 2026 had been repeatedly inspected during development; no untouched holdout exists for proving real economic edge. A human-versus-AI claim would require a controlled human benchmark, which was never run.

### Required next research, not authorized deployment

- Treat the eight candidate strategies as a **signal library**, not yet an economically validated standalone rule set. Revisit too-frequent entries and the 60m expiry vs realistic intraday signal horizon.
- Prespecify matching after-fee/funding outcome labels for +1%, +2%, +3% protective exits, fixed target, trailing activation/gap, and timed exit, with stop-first candle ambiguities explicitly conservative. Include *all* rejected opportunities in training evaluation.
- Learn conditional win distribution **and payoff magnitude**, compute properly calibrated *expected net USDT after costs, uncertainty and risk* for each coin×family×side×exit. Do not equate win probability >50% with positive expected P&L; do not relax historical thresholds purely to force an existing July–September result.
- Introduce explicitly measured as-of regimes and conditional strategy success, use chronological purging, honest unseen later time periods, and compare a predeclared suite of models/baselines including NO TRADE before trading approval.
- Compare global selection in one real native 25-pair, 1-position Freqtrade portfolio. Preserve exploratory no-trade outputs and native ZIP audit; no live/paper trading or automatic promotion.

### Reproduce

- [Read-only 48 archive native trade path and exit reason probe](../../scripts/m2r_v6_trade_execution_probe.py):
`python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_trade_execution_probe.py`
- [Read-only corrected conservative native lost-trade prior-candle audit](../../scripts/m2r_v6_profit_reversal_audit.py); tested against `native/ema_cross/validation_july` historical ZIP with the full immutable public 25-coin feather history.
- [Actual global zero-selection rejection counts](2026-10-19-global-25x8-native-recovery-final-report.md).
