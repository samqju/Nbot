# NBOT V6 — Stage 1 Final Research Report

**Report date:** 19 October 2026  
**Study:** First-stage eight-strategy library, original baseline, trailing stop A/B, Hyperopt, selected LightGBM/adaptive/PPO diagnostics  
**Conclusion:** **Research completed; NO-GO for trading promotion.** This report is evidence of historical tests, not evidence of profitable future execution.

## Executive summary

All **63 planned first-stage jobs** eventually completed successfully: 56 in the original run and 7 in an isolated, fully audited recovery completed 18 October 2026 at 22:38 UTC. The first run had stopped on a four-hour Hyperopt timeout and temporarily occupied Docker; the recovery used the exact original strategy code commit `aa97a32c9af73ae63503f5dbff63d98a7fe32200`, preserved the failed attempt and earlier successful files, and did not enable paper/live trading.

A read-only report script re-opened the archived economic audits and validated SHA-256 hashes of **all 51 original native Freqtrade ZIP outputs**: 3 original baseline, 24 native eight-strategy, and 24 trailing-stop. All counts and figures below are from those saved backtests. The eight native strategies and the original trailing policy were **negative for all eight families** over July–September, both at native reported costs and after the specified additional **25 basis points (0.25%) round-trip hypothetical execution-cost stress**. **NO TRADE** (+0 USDT PnL) beats every three-month standalone result under the stressed assumptions.

The best *relative* standalone result by aftercost stress was **EMA Cross**, at **−5,814.72 USDT** over three separate monthly native backtests; this is still a substantial historical loss, not a trading candidate. No automatic keep/drop or strategy promotion is justified. Only Stage 2 and global Stage 3 can test whether exit modifications or cost-aware selection improve the economics.

## Protocol and accounting

- Original fixed universe: **25 Binance USDT perpetual futures pairs**, 5-minute entry timeframe.
- Three separate monthly tests: **July, August and September 2026**. These periods have already been inspected and are **not blind market holdouts**.
- Historical model/strategy training also used earlier predeclared windows and May–June Hyperopt training, but **the table below is strictly the July–September isolated native backtest comparison**; it is not the net result of all model-fitting exercises.
- Each native backtest used an initial **100,000 USDT simulated wallet**, a **1,000 USDT nominal position**, **one global position at a time**, **1× leverage**, initial **−2% stop** and **+5% ROI**, with a **60-minute time exit**, Freqtrade cooldown/stoploss/drawdown protections, and the same 25-pair universe.
- Base native fees: **0.05% each way**. Additional modeled **0.25% round-trip** represents an execution-cost stress **not an observed historical bid–ask spread or guaranteed slippage**. Avoid double-counting it when comparing with actual fees.
- Trailing variant compared in Stage 1: **starts after +2% gross movement, with 1% trail**; this does **not** mean 1% net profit always executes. Same initial stop, target and time exit.
- Each row's three-month total is the **arithmetic sum of three independently backtested months for that ONE family and ONE exit variant**. Family totals are **not** a combined, executable eight-strategy global portfolio. Trade counts overlap in time across families, so they must never be summed into a deployable performance claim.

## Eight-strategy native results (July–September)

All amounts are USDT. “Native net” includes the fees applied by the Freqtrade backtest; “Stressed net” additionally subtracts 25bp round-trip. The same trading policy was evaluated separately for each strategy.

| Strategy family | Native net (3 monthly tests) | Stressed net (+25bp) | Trades | Win rate |
|---|---:|---:|---:|---:|
| EMA Cross | −1,458.22 | **−5,814.72** | 1,747 | 39.38% |
| Donchian Breakout | −1,544.03 | −6,643.09 | 2,050 | 36.83% |
| Bollinger Reversion | −1,949.04 | −7,017.46 | 2,037 | 43.20% |
| RSI Reversion | −2,153.93 | −7,254.23 | 2,049 | 42.26% |
| MACD Momentum | −2,450.21 | −7,111.96 | 1,871 | 37.25% |
| Stochastic Reversal | −2,534.64 | −8,050.81 | 2,223 | 38.64% |
| ATR Breakout | −2,166.99 | −7,355.37 | 2,084 | 37.57% |
| Volume Trend | −2,013.61 | −6,793.37 | 1,921 | 36.75% |

**Native fixed exits:** 0/8 families earned positive native net over the three monthly backtests; 0/8 earned positive stressed net.

### Native stressed results by individual month

| Strategy | July | August | September |
|---|---:|---:|---:|
| EMA Cross | −1,847.04 | −2,036.37 | −1,931.32 |
| Donchian Breakout | −2,302.71 | −2,397.21 | −1,943.18 |
| Bollinger Reversion | −2,236.62 | −2,321.59 | −2,459.24 |
| RSI Reversion | −2,475.00 | −2,272.28 | −2,506.95 |
| MACD Momentum | −2,371.55 | −2,272.97 | −2,467.43 |
| Stochastic Reversal | −2,665.40 | −2,420.30 | −2,965.11 |
| ATR Breakout | −2,637.86 | −2,461.82 | −2,255.69 |
| Volume Trend | −2,305.54 | −2,214.36 | −2,273.47 |

**Every individual family-month stressed result is negative** (24/24). This is a stronger observation than merely a negative summed family result.

## Trailing-stop A/B: did it protect profits?

| Strategy | Original fixed-exit stressed net | +2%-offset / 1%-trail stressed net | Trailing improvement |
|---|---:|---:|---:|
| EMA Cross | −5,814.72 | −5,928.88 | −114.16 |
| Donchian Breakout | −6,643.09 | −7,452.68 | −809.59 |
| Bollinger Reversion | −7,017.46 | −6,951.77 | +65.69 |
| RSI Reversion | −7,254.23 | −7,002.59 | +251.64 |
| MACD Momentum | −7,111.96 | −7,285.19 | −173.23 |
| Stochastic Reversal | −8,050.81 | −8,045.21 | +5.60 |
| ATR Breakout | −7,355.37 | −7,551.88 | −196.51 |
| Volume Trend | −6,793.37 | −7,469.28 | −675.91 |

The initial trailing variant reduced stressed loss for **3/8** families and worsened it for **5/8**. **None** became profitable. The exits can free capital earlier, alter later trades, miss a subsequent +5% target, and still incur fees. A higher win rate by itself is insufficient.

**Next comparison (not part of Stage 1):** Stage 2's five separate new policies per family × three months (**120 native runs**), including tighter profit protection around +1%, +1.5%, +2%, and +2%/+3% fixed targets. Those results must be reported separately and must not be retroactively included here.

## Original No-ML historical baseline

The three archived original No-ML native reference runs, kept separate from the eight-strategy experiments:

| Period | Native net | Stressed net (+25bp) | Trades |
|---|---:|---:|---:|
| July 2026 | −119.46 | −513.36 | 158 |
| August 2026 | +108.41 | −328.94 | 176 |
| September 2026 | −242.89 | −647.76 | 163 |
| **Three-month arithmetic total** | **−253.95** | **−1,490.07** | **497** |

The baseline's small August native gain becomes negative under the execution-cost stress. **Do not compare sums of one strategy's independent backtests with a synthetic best-of-eight lookahead portfolio.** Every native result is a separate one-slot simulation.

## Hyperopt, FreqAI LightGBM, adaptive selection and PPO

Stage 1 ultimately completed its **eight scheduled Hyperopt training tasks** (5 originally plus 3 recovered), **two LightGBM diagnostic research runs**, **one eight-hour adaptive regime-selector run**, and **one PPO reinforcement-learning run**. The latter four were completed in the seven-job recovery; they have native run states and independently verified recovery evidence.

These are **research task completions**, not proof of improved or profitable market outcomes:

- **Hyperopt** optimizes on May–June training. Applying chosen settings to already-seen July–September without a frozen OOS protocol would risk data snooping. The Stage 1 fixed-policy table above does *not* substitute newly optimized parameter results.
- **LightGBM** diagnostic training/backtests do not establish calibrated cross-coin **25×8** opportunity selection or unseen positive net returns. Those must be assessed through Stage 3, if its infrastructure passes independent checks.
- **Adaptive regime selection** had to obey its causal evidence/NO TRADE gates and is not equivalent to the forthcoming every-5-minute across-all-families ranker.
- **PPO** run completion confirms an executable research attempt under the official FreqAI-RL image, **not** that policy learning outperformed the original baseline or NO TRADE. No auto-promotion took place.
- **Data leakage / selection warnings:** These periods have been examined repeatedly; native Freqtrade execution still has intra-candle sequencing and orderbook fill uncertainties, and hypothetical extra 25bp does not prove real-world spread/slippage.

The seven recovered jobs were exactly: `hyperopt/stochastic_reversal/tuning_may_june`, `hyperopt/atr_breakout/tuning_may_june`, `hyperopt/volume_trend/tuning_may_june`, `lgbm/ema_cross/replication_september`, `lgbm/volume_trend/replication_september`, `adaptive/ema_cross/replication_september`, and `rl/ema_cross/validation_july`.

## Implications and research decisions

1. **Do not enable paper/live trading or promote a Stage 1 candidate.** No family cleared after-cost economics versus NO TRADE, and the initial trail variant did not rescue any family.
2. **Keep all eight families in the research library for the controlled Stage 2 and Stage 3 comparisons.** This preserves evidence, not endorsement. Owner to decide what stays only after all comparative results.
3. **Stage 2:** compare 120 additional native exit-policy trials against original exits on identical monthly periods. Include more realistic cost stresses, drawdown, same-candle ambiguity and profitable exits that later reversed.
4. **Stage 3:** compare all 25 coins × eight family signals × eligible LONG/SHORT at the same completed 5-minute candle; calibrated cost/risk-aware forecasts must compete globally against NO TRADE in one true native portfolio, not a hindsight-picked stitched collection.
5. **Release/validation:** future untouched market holdout, walk-forward purging, actual exchange eligibility and realistic microstructure/fee/funding assumptions required before economic approval. No strategy automatically promoted on a backtest win.

## Provenance, audit procedure and regeneration

**Source files on VPS, read-only:** `/root/nbot-v6-m1-20261016/library-20261018/candidate-native-aftercost-summary.json`, 51 ZIP archives under `{baseline,native,trailing}/<family>/<period>/backtest_results`, `/root/nbot-v6-m1-20261016/library-20261018-recovery/recovery-progress.json`, and `/root/nbot-v6-m1-20261016/library-20261018-recovery/verified-all-seven-and-original-56.json`.

**Reproducible verifier (does not start trading or training):**

```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_stage1_report.py
```

The verifier refuses to print a success summary unless the original 51 archive hashes, native economic audit flags, expected family/month coverage and seven-job recovery completion all match. Amounts rounded to two decimals here; the saved JSON retains full native precision.

**Earlier reference design and comparisons:** [Strategy library](../../STRATEGY_LIBRARY_V6.md), [main roadmap](../../ROADMAP.md), [global selection design](../../V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md), [recovery proof](2026-10-18-seven-job-recovery-vps-restarted.md). *This is a Stage 1 results report only. Stage 2 and Stage 3 results are not incorporated.*
