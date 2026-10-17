# October 17, 2026 — Resumed V6 native 25-market matched controls and cost stress

**Owner-authorized V6-only research; measured from real Freqtrade historical backtest ZIP archives. No network orders, no paper/live service, no branch merge.** Checked correct VPS via root/PuTTY `8GB-Observation`; branch `prototype/v6-freqtrade-freqai-20261016`; idle Docker and clean checkout prior to data analysis.

## Previously unfinished run verified

The pre-existing separate `original-unpurged-control25.log` now contains the COMPLETE native full-engine strategy summary for October 8–9 (two days; ending October 10 UTC): **13 trades, −33.762866 USDT**, one global 1× nominal ~1000 USDT position; an actual Freqtrade ZIP exists `original-unpurged-control25-2026-10-17_08-46-04.zip`. This completion had **not** been confirmed in the earlier handoff because SSH connectivity was interrupted; it is now verified. No new trading simulation was necessary to establish this.

## Actual three-way matching + hypothetical execution-cost stress

Read-only existing `scripts/m2r_native_fullengine_cost_comparison.py` read **three verified native engine historical backtest ZIP archives** and calculated actual saved-trade result, stake-weighted extra *hypothetical* fees/slippage deductions. Exit 0.

| Variant | Native engine trades | Engine historical USDT result | Extra +10bps cost | Extra +15bps | Extra +20bps | Extra +25bps |
|---|---:|---:|---:|---:|---:|---:|
| Original price AI, existing unpurged | **13** | **−33.762866** | −46.762233 | −53.261917 | −59.761600 | −66.261283 |
| Original price AI, research-only 12-candle internal purged | **7** | **−28.799423** | −35.799121 | −39.298971 | −42.798820 | −46.298669 |
| Event-funding-aware trade-outcome AI, native purged | **24** | **+39.085015** | +15.099813 | +3.107212 | **−8.885390** | **−20.877991** |
| No trade | **0** | **0** | 0 | 0 | 0 | 0 |

Fee assumption: Freqtrade historical backtests already model **0.05% per side and engine's funding**, and +bps values are **additional roundtrip execution penalties** against the *actual saved Freqtrade trades*, not book-observed fills. Funding-aware candidate break-even extra cost **16.2955 basis points round trip**. These are small, **previously inspected two-day historical windows** and do NOT imply a stable economic edge. The purged vs unpurged AI are *different fits/portfolio executions*, not randomized controlled trading conditions. All three models are research alternatives, not production promotion candidates.

**Cost gate:** We have explicitly improved hypothetical labels with signed funding events and last fully closed historical 1h mark proxy, and compared loss under a range of slippage penalties. **We still do not possess measured bid/ask spreads/order book fill paths, actual exchange funding billing for those hypothetical positions, or actual stop-market execution.** It would be misleading to claim step 3 fully certified or that conservative reserve bps are actual measured trading costs. The real-fill/fee-settlement gate stays OPEN and M2 remains **NO-GO**.

## Reproduce from existing authorized V6 VPS (read-only, no trading)

```bash
cd /root/nbot-v6-m1-20261016/source
python3 scripts/m2r_native_fullengine_cost_comparison.py \
  --unpurged-original /root/nbot-v6-m1-20261016/native-purged-validation-20261017/original-unpurged-control25-2026-10-17_08-46-04.zip \
  --purged-original /root/nbot-v6-m1-20261016/native-purged-validation-20261017/full25_backtest-2026-10-17_08-25-55.zip \
  --funding-aware-purged /root/nbot-v6-m1-20261016/native-purged-validation-20261017/funded-purged-all25-2026-10-17_08-44-36.zip \
  --output /root/nbot-v6-m1-20261016/native-purged-validation-20261017/native-fullengine-three-way-cost-comparison.json
```

Full output remains **on V6 VPS, outside Git checkout**, at `/root/nbot-v6-m1-20261016/native-purged-validation-20261017/native-fullengine-three-way-cost-comparison.json`, SHA-256 `f7338e55ed74a328c64cbc084f09289c0bd2523002b87c7655e3dd949f8459e0`. Source files and base tests remain in [preceding native research report](2026-10-17-native-saved-model-purge-event-funded-research.md).

**Step 1:** 25 native saved model weight hashes and 7,200 overlapping frozen model predictions passed, but original Freqtrade official `lookahead-analysis` `has_bias=Yes` still not independently cleared due deletion/refit behavior and unclosed paths. **Step 2:** Native research-only 12-candle/1-hour internal split purge passes (300 dense original samples) but not silently promoted. **Step 3:** Historical event-funding model and bounded sensitivity completed, **actual spread/slippage/stop/settlement remains UNVERIFIED**. No paper/live, no owner release approval. M2 NO-GO; May–Aug 30/60/90/180-day research not run; M3/M4/M5A/M7 locked.
