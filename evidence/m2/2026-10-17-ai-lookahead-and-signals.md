# M2 AI FreqAI lookahead and signal accounting — October 17, 2026

**Scope:** Owner-authorized private 8GB-Observation VPS, official Freqtrade/FreqAI **2026.9**, Binance public 25-pair history Oct 1–8 2026. Research-only Docker runs; no exchange keys, real orders or persistent paper daemon.

## Why a separate audit strategy is needed

Official Freqtrade `lookahead-analysis` intentionally overrides `max_open_trades` to **-1/unlimited** and uses market orders and enlarged stakes. The main `NbotV6` safety check refuses this in its bot startup; **we did not modify or weaken the main AI strategy**.

Created `NbotV6M2Audit`, a separate historical-only subclass that **inherits the identical indicators, FreqAI model targets, signals and exits**, and permits the official diagnostic override only when `sys.argv` names `lookahead-analysis`, `nbot_m2_audit_only=true`, `dry_run=true`, no exchange API credentials, no Telegram/API server, and max-open-trades=-1. It rejects live execution completely. Config/model artifacts use a separate `user_data/config.m2-ai-lookahead.json` overlay and `nbot-v6-m2-ai-lookahead-20261017` model identifier.

## Actual FreqAI lookahead-analysis outcome

- Method: `freqtrade lookahead-analysis`, 25 candidates, original full 30-day model parameters, **Oct 1–8**, base fee `0.0005`, minimum signals **8**, targeted signals **8**.
- Exit status **0**: the diagnostic completed, using ~102 seconds. **Exit status 0 does not mean bias-free.**
- Official output row: `has_bias = Yes`; `total_signals = 8`; `biased_entry_signals = 0`; `biased_exit_signals = 0`.
- `biased_indicators` contained: `&-forward_return`, `&-forward_return_mean`, `&-forward_return_std`, `do_predict`, `DI_values`, `exit_long`, `exit_short`, `enter_tag`, `enter_long`.
- Freqtrade documentation identifies the `&-` target indicators as potentially **expected false positives**, because targets deliberately contain future training labels. **That does not explain away changes to `do_predict`, entry/exit indicators or model filter values**. FreqAI's retraining and pairlist slicing may change predictions between lookahead sub-runs; this is a hypothesis, **not a verified finding**.
- **Interpretation: M2 AI leakage/invariance gate FAILED/UNRESOLVED.** Even though the eight sampled entry/exit signals showed zero explicit bias counts, the reported changed prediction/entry/exit columns prohibit a blanket "no lookahead" claim. Investigate with frozen-as-of prediction artifacts, separately controlled retraining, feature-prefix tests and additional signal coverage. Do not use this diagnostic as a normal strategy backtest or trading deployment.

Official documentation: https://www.freqtrade.io/en/2026.9/lookahead-analysis/ .

## Separate causal-source and offline checks

- A prefix-causality test compares FreqAI price/EMA/volatility/volume-ratio/momentum and candle-body `%-` features calculated on a full series versus a shorter prefix, ensuring appended future candles do not change prior features. Uses indicator periods 14 and 28.
- The intentionally forward `&-forward_return` target is a 12-candle **training label** only, is not a `%-` feature and is undefined over the final 12 rows. This does **not** by itself prove that trained predictions and FreqAI data processing are fully safe.
- The audit strategy's dry-run/no-credentials/CLI-only override has dedicated unit tests. Primary `NbotV6` and future owner-only live entry guards are unchanged.

## Exact seven-day exported signal accounting

Ran full official `--export signals --cache none` for both strategies with all 25 candidate pairs and **0.05% per-side fee**. Net results match the prior audited backtests.

| Metric from official ZIP signal exports | AI V6 | Frozen non-ML |
|---|---:|---:|
| Closed simulated trades | **34** | **31** |
| Entered-signal rows in `_signals.pkl` | **34** | **31** |
| Rejected-signal rows in `_rejected.pkl` | **68** | **6,531** |
| Exited-signal rows in `_exited.pkl` | **34** | **31** |
| Net historical P&L | **-135.640 USDT** | **+169.849 USDT** |

**Important interpretation:** The 6,531 baseline rejected signals are Freqtrade signal records, **not 6,531 distinct observed trade failures or independent opportunities**. Many signals may occur while the single global trade slot is occupied. The AI's 68 rejections likewise do not directly measure model abstention. We must **separately** account for all candidate candles, technical setups, `do_predict` gating, costs, concurrent positions and unavailable or out-of-distribution predictions, before computing valid ML adoption rates. One global position was deliberately used for apples-to-apples M2; **the separate up-to-20-slot M4 paper-research config is still intact and disabled**.

## Status

- [x] Completed real historical **non-ML** 30-signal official lookahead check with **no detected bias**.
- [x] Ran actual **AI lookahead diagnostic** without modifying production safety; identified concrete changed model/entry/exit indicator columns.
- [x] Added causal feature-prefix/target-separation source tests.
- [x] Verified exact historical **entered/rejected/exited** Freqtrade signal record counts for both strategies.
- [ ] Resolve AI prediction/input invariance and independently distinguish expected target false positives from any real decision-time future leakage.
- [ ] Reconcile setup/eligible/model `do_predict` abstention counts, not just exported trade signals.

**M2 is NOT complete. M3 may not begin.** Keep real money locked and continuous paper service off.
