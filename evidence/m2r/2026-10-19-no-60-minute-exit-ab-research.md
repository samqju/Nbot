# Nbot V6 — Remove the 60-minute time exit: frozen native Freqtrade A/B research

**Owner requested:** 19 October 2026. **Status at launch:** Real offline study running on the VPS, not a completed economic finding.

## Hypothesis and scope

The original eight independent strategy families were normally exited when the native +5% ROI was hit, the initial −2% protective stop was hit, the trailing stop was triggered (trailing arm), **or the trade was closed at a forced 60-minute expiration**. Previous archived trade-ledger audits showed that 15,295/15,982 fixed-exit trades and 15,033/16,274 original trailing-exit trades reached the 60-minute time exit. The user explicitly requested removing that time limit and determining whether allowing trades to continue until +5%, −2% or activated trailing would improve Freqtrade economic outcomes.

### Frozen comparison parameters

- **Only strategy change:** `custom_exit(...)` returns `None` in new isolated subclasses; there is **no 60-minute custom exit**. Original technical entry functions, indicators, eight strategy family mapping and protection methods are inherited without any modification. Verified `git diff` against original frozen source `aa97a32c9af73ae63503f5dbff63d98a7fe32200` returned unchanged for `NbotV6LibraryResearch.py`.
- **Fixed arm:** +5% native Freqtrade ROI and −2% initial stop. No exit signal; no time closure.
- **Trailing arm:** same +5% ROI and −2% initial stop; original +2% favorable movement activation and 1% gap trailing stop. No time closure.
- All positions **1× leverage**, 1,000 USDT stake, one global open position, 100,000 USDT paper-equity **backtest-only** wallet, 25 original Binance USDT futures pairs, five-minute candles, cooldown/stop-loss/drawdown protections, native 0.05% fees each side. Additional hypothetical **25bps roundtrip** turnover stress in independent economic audit.
- Historical periods: **July 1–August 1, August 1–September 1, September 1–October 1**, and separately **continuous July 1–October 1**; exactly eight families × two policy arms × four history periods = **64 new native Freqtrade studies**. Monthly A/B compares the same original monthly 60-minute archive; continuous A/B is supplementary for month-boundary artifacts.
- **Inescapable finite-horizon caveat:** Freqtrade *must* mark/force-close open positions at the final candle of each backtest. Such `force_exit` is **not** an added trading rule; count it explicitly in each native audit, report mean/median/90th percentile holding times and how often the one-slot portfolio remained locked in an open position. Monthly boundaries artificially end some long trades; continuous three-month comparisons mitigate but do not eliminate end-of-data risk.
- **Existing July–September periods are repeatedly inspected**, and results are exploratory, not untouched market holdout, alpha proof, or trading approval. Keeping trades open means fewer new entries can execute. Difference in total P&L mixes exit effect and subsequent one-slot opportunity cost; it is NOT per-trade paired causal exit difference.

### Isolation and safety

- Source research-only strategy subclasses: [NbotV6NoTimeLimitResearch.py](../../user_data/strategies/NbotV6NoTimeLimitResearch.py).
- Finite guarded owner-opt-in coordinator: [m2r_v6_no_time_exit_batch.py](../../scripts/m2r_v6_no_time_exit_batch.py).
- Persistent sequential one-Docker-at-a-time service: [nbot-v6-no-time-exit-20261019.service](../../deploy/nbot-v6-no-time-exit-20261019.service); requires official Freqtrade Docker image, no live/paper authorization, original historical data read-only, git branch and original entry implementation verified, service error blocks. **No retry of partial/incomplete output, no overwrite of any earlier 63/120/12 studies.** New isolated VPS path: `/root/nbot-v6-m1-20261016/no-time-exit-20261019/`.
- Current pinned VPS source at launch: `0a954bea03e2f65a023d44da00fde7a68df2895b`; **do NOT pull/update the active `global-next-source` checkout while this batch executes**. GitHub branch documentation/test changes committed later are not part of already-running Freqtrade source.
- Each native result must pass ZIP SHA-256 and internal trade ledger reconciliation, exactly 25 pairs, one 1,000-USDT global slot, 1× leverage, native 0.05% each-side fees, no unexpected `v6_library_60m_exit`, recorded exit reason counts and explicit historical-end forced position closures.
- Four new unit tests passed on VPS; initial CI failed because test wrongly assumed the GitHub runner runs as root (test-harness-only bug fixed on branch after launch). Do not interpret the initial failed CI run as a failed native research job.

### Preliminary first actual experiment (not project conclusion)

On 2026-10-19 around 05:13 UTC, the first new native Freqtrade ZIP for EMA Cross July fixed exit succeeded:
- Original 60min policy: **594 trades**, −1,847.04 USDT net after hypothetical additional 25bp.
- Unlimited fixed native policy: **9 trades**, +118.38 USDT net after same stress (original native fees also included), one forced exit at the July backtest end.
- This is a **dramatic portfolio-occupancy difference**; longer-holding trades exclude many subsequent entries. Do not infer from this one positive monthly run that the full three-month strategy is profitable.
- Subsequent trials were active at the time of the record; final figures must come from full 64-run `final-comparison.json` only.

### Read-only VPS status

```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_no_time_exit_batch.py --status
systemctl status nbot-v6-no-time-exit-20261019.service --no-pager
```

**Owner decision:** NO promotion, paper/live remains disabled, retain every losing result, investigate economic effect of holding longer before changing the learned selector's exit targets or training labels.
