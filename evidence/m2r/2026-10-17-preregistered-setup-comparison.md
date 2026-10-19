# Predeclared M2R setup-selection experiment — October 17, 2026

**Recorded before seeing October 8–16 out-of-sample trade results.** Research-only. No trades can occur outside short-lived Freqtrade historical backtest Docker containers.

## Main question
Does LightGBM trained on realistic **hypothetical after-cost complete trade labels** rank and select eligible breakout/pullback opportunities better than our fixed non-ML strategy, the previous price-only LightGBM and **NO TRADE**?

## Fixed conditions (no post-result tuning)

- Fixed original **25 Binance USDT-M** markets, static pair list (the 8-hour rotating M5A selector is **not** part of this test).
- Candidate families = breakout (long/short) and EMA pullback (long/short), as defined before this experiment in `nbot_trade_outcome.py`.
- Each FreqAI model fits prior **30 chronological days** with a 12-bar 5m completed-trade target and predicts for the next 7-day historical chunk; FreqAI's native leakage boundary is a research caveat.
- After-cost labels enter at **the next candle open**; 2% stop / 5% target / maximum 12 bars; intrabar ambiguities treated stop-first; assumed cost **0.05% exchange fee per side, 0.05% extra entry and exit slippage reserve per side, 0.01% funding reserve**.
- Minimum LightGBM predicted NET complete-trade return **strictly >0.004 (0.4%)** and `do_predict==1`, with no after-the-fact threshold changes.
- Official engine all comparisons = 1,000 USDT stake, 1× leverage, max **one simultaneous** historical position, original wallet 100,000 USDT, **0.05% engine fee per side**; model reserve is a training filter, not additional engine real fills. Real spread/slippage still unavailable.
- **Development replay (already inspected):** September 1–October 1 (30 days); combined after-cost Challenger vs original AI, non-ML and NO TRADE. September results must NOT be presented as untouched final validation.
- **Provisional held-out chronological check, preselected now:** October **8–16, 2026** (Oct 8 at 00:00 UTC inclusive, Oct 16 at 00:00 UTC exclusive), after FreqAI training ending before its first test candle. Original price AI, no-ML, combined after-cost model, breakout-only after-cost model, pullback-only after-cost model, and NO TRADE must all use the same exact 25 markets, slots, fee, wallet and dates.
- Unique FreqAI model identifier for every family and phase to avoid accidental reuse / overwriting. Core V6 and old model outputs remain unchanged.
- Primary outcome = **official Freqtrade NET USDT** after its base fees/funding; report win/loss, 1-slot exposure, trade count, drawdown and NO TRADE benchmark. Secondarily measure number of model-ready candidate signals and predictive calibration. Predictions are not executable orders until engine backtest validates them.
- **NO MODEL PROMOTION** if held-out NET <=0, insufficient sample size (<30 actual portfolio trades), unresolved lookahead, missing live fill calibration, or if performance is not superior to non-ML and NO TRADE. Even a positive single holdout is preliminary; multiple later independent time windows are required.

## Caveats frozen in advance

1. Original price-only AI and no-ML have **different exit rules** from the new 60-minute model; a raw PnL difference is a useful comparison but **not a pure measurement of the effect of AI**.
2. The original public historical best bid/ask fill data are missing, 2026 bookDepth snapshots have gaps, and two earlier period-end funding events differed slightly. Engine cost assumptions are not actual market execution.
3. FreqAI native lookahead-analysis reported `has_bias=Yes` on some indicators. Two-coin prediction-prefix checks passed but full all-pair leakage certification is NOT complete.
4. The 29,033 September training-label outcomes are overlapping counterfactual opportunities, not portfolio trades. DO NOT sum them into trade returns.
5. If the test produces NO SIGNALS, fails due scarce training labels, or loses money, report failure/abstention and keep NO TRADE as the default. Do not silently optimize after inspecting these dates.

**All findings remain on draft branch/PR. M2 release NO-GO; M3 not authorized; no paper or live trading.**
