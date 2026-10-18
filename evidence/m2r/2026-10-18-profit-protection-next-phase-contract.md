# NBOT V6 — owner-ordered NEXT native profit-protection exit research phase (2026-10-18)

**ACTUALLY QUEUED ON OWNER'S ISOLATED V6 VPS AT 2026-10-18T04:23:02Z (09:53 IST).** GitHub native unit / exact 40 strategy class discovery CI [39096771429](https://github.com/samqju/Nbot/actions/runs/39096771429) PASSED, including 5 pre-registered exit policies × 8 Freqtrade native classes and source syntax. An immutable, root-only **once-only VPS successor wait script**, mirrored from [scripts/m2r_v6_profit_protection_successor_wait.sh](../../scripts/m2r_v6_profit_protection_successor_wait.sh), was saved outside the active Git checkout as `/root/nbot-v6-m1-20261016/library-20261018/v6-profit-protection-successor-wait-once.sh`, syntax checked, SHA256 `89f5a1762c8bcfa03ecae646cda2344b4364a63fc0a361e9c2fc092443684b72`. Explicitly started finite VPS systemd transient **`nbot-v6-profit-protection-next-20261018.service`** at **04:23:02 UTC**, independently verified **active/running PID 148502**, with log line `WAIT_FOR_FINITE_RESEARCH_ONLY_STUDY_COMPLETION: nbot-v6-library-20261018.service`. The **original batch remains active/running PID 142873 at launch**, source checkout still frozen at `aa97a32`; no new native Docker was started, no Git pull or prior research modification, no paper/live activities or keys.

The successor's wait loop checks the original service once per minute **for at most 24 hours** (not a repeating ChatGPT automation), then ONLY after the original service stops **and** its saved status says `complete_with_individual_failures_if_any` and its actual native summary exists and Docker is idle does it perform `git pull --ff-only` on the SAME V6 research branch. The new coordinator independently requires **all 24 original fixed + 24 original trailing real native ZIP economic audits and all three NoML baseline audits**, and refuses partial/inconsistent portfolios. Then and only then will it execute the conservative OHLCV loss-path diagnostic and **120 one-at-a-time** new native exit backtests. A premature/blocked original batch, dirty branch, missing archive, another Docker, source/syntax failure, job timeout/reboot or code audit error **halts the successor without claiming completion**. **The follow-up does NOT survive VPS reboot**. It is **QUEUED, NOT YET EXECUTING EXIT TRIALS**, as of 04:23:02 UTC. VPS status:
```bash
systemctl status nbot-v6-profit-protection-next-20261018.service --no-pager
tail -n 15 /root/nbot-v6-m1-20261016/library-20261018/v6-profit-protection-successor-wait-once.log
cat /root/nbot-v6-m1-20261016/library-20261018/profit-protection-next-phase/status.json
```
The last command returns missing until the previous batch completes and the successor actually starts; that is expected. Owner's previously deleted ChatGPT scheduler was NOT recreated.


**Owner direction:** “the changes in research priorities you just suggested should be tested next once current run of things is completed.” This is a real execution directive to study profit protection and smaller reasonable gain targets **after** the currently active eight-family native strategy, trailing-stop, Hyperopt, LightGBM, regime NO_TRADE, PPO research batch completes.

## Strictly after the ongoing batch

- Existing **`nbot-v6-library-20261018.service`** must finish; do not pull or rewrite its GitHub checkout or run another native Docker container while it is active.
- Before any next-phase native job, require `library-20261018/v6-library-research-status.json` to declare `stage=complete` and `status=complete_with_individual_failures_if_any`, with a saved final first-batch summary and **verified real native ZIP + economic audit for all 24 baseline fixed and 24 current trailing monthly strategy backtests**, plus the three original NoML baselines. A failed original group **blocks the successor** until investigated, regardless of the rest of the batch appearing complete.
- Original original 30/60/90/180 model archives remain untouched. Paper trading and real trading remain disabled, no market orders, credentials empty, owner hook locked, no model / hyperparameter automatic promotion, main/V5 untouched.

## Frozen owner-preferred exit-policy alternatives

Each new class uses **the exact same standalone eight native strategy family indicators, long/short entry signals, pairlist, 5-minute candles, global 1× USDT 1000 initial position, native protections, fee 0.0005 per side, initial -2% loss stop, 60-minute duration limit, 100,000 USDT simulated wallet**. Only ROI/trailing exit parameters differ.

| Exit policy ID | Trailing activation | Trail distance | Fixed profit target | Approximate protected *gross* gain when triggered |
|---|---:|---:|---:|---|
| `native` existing control | None | None | +5% | None |
| `trailing` current already-running control | +2% | 1% | +5% | +1% at activation; grows as favorable price rises |
| `protect_trail_1p0_gap_0p5` | +1% | 0.5% | +5% | ~+0.5% |
| `protect_trail_1p5_gap_0p5` | +1.5% | 0.5% | +5% | ~+1% |
| `protect_trail_2p0_gap_0p5` | +2% | 0.5% | +5% | ~+1.5% |
| `protect_take_profit_2p0` | No trailing | — | **+2%** | Gross +2% ROI if fill is simulated as achieved |
| `protect_take_profit_3p0` | No trailing | — | **+3%** | Gross +3% ROI if fill is simulated as achieved |

**Protected gross gain is NEVER guaranteed net cash P&L.** Freqtrade's five-minute OHLCV backtesting cannot reconstruct within-candle high/low sequence; stops can gap, fail or fill differently; actual exchange orders carry fees, modeled funding, bid/ask, execution overhead and adverse selection. The native backtests will use additional **hypothetical +25 basis points roundtrip cost stress** over the native fees/funding. See official [Freqtrade native backtesting limitations](https://docs.freqtrade.io/en/latest/backtesting/).

**No shotgun tuning of reward thresholds on September**: July and August (already inspected in previous research, so **not blind**) are descriptive selection windows for each family's provisional exit variation; September is a separate recorded replication check, not treated as an untouched future holdout. All seven native exit variants will be compared by family under identical dates, cost and risk settings. Changing exit rules may change future entry opportunities because freed global one-trade slots lead to different trade sequences. Do not compare just headline win rates.

## Actual next-phase work implemented on the V6 research branch

1. **Exact original 30-day historical LightGBM ZIP trade-path analysis**, reading historical actual Freqtrade *simulated closed trades*, identified coin's real stored 5-minute feather candles, and detecting losing trades that had reached +1%, +2%, +3% favorable gross price **strictly on candles ending before the actual exit candle**. It excludes the exit candle to avoid claiming a high definitely preceded a stop inside the same candle. Its counts are **diagnostics** and do not prove a counterfactual stop would have filled. [scripts/m2r_v6_profit_reversal_audit.py](../../scripts/m2r_v6_profit_reversal_audit.py).
2. All **five pre-specified additional exit choices × eight strategy families × three identical monthly historical periods July/August/September = 120 full native Freqtrade 25-pair portfolio backtests**, one Docker container at a time, no existing source or models overwritten. Classes [user_data/strategies/NbotV6ProfitProtectionResearch.py](../../user_data/strategies/NbotV6ProfitProtectionResearch.py); parameters not auto-Hyperoptimized. Uses original guarded [scripts/m2r_v6_library_native_job.py](../../scripts/m2r_v6_library_native_job.py) for official Freqtrade.
3. Each new native ZIP is independently checked for **one 1× $1000 slot, original 25 markets, correct test dates, trade PnL, 0.05% fees each side and consistency with trade ledger**; cost stress and saved per-job PnL/sha256. A native error HALTS rather than silently claiming success.
4. After all experiments succeed, compare original no-trailing +5%, existing +2%/1% trailing, and five new variants on each identical period. Rank only on July+August with positive after-extra-cost results and enough trades; if none qualify, **NO TRADE**. Evaluate selected policy in September separately, still not blind.
5. Save full per-policy original Freqtrade archives, native profit & aftercost JSON, chronological journal and `profit-protection-next-phase/seven_exit_policies-native-aftercost-comparison.json`. No strategy changes automatically applied to ML, RL, paper or live.

**Execution model:** A bounded, fail-closed **one-time VPS successor** should start only after the present full batch reports complete, all 48 old strategy/trailing ZIPs and economic audits exist and Docker is idle. No ChatGPT recurring automation should be created. The post-batch coordinator source is [scripts/m2r_v6_profit_protection_batch.py](../../scripts/m2r_v6_profit_protection_batch.py); code-level regression checks and official Freqtrade class discovery in CI. No profit or improved aftercost returns are yet established.

**No claim this will cure the original V6 losses or automatically yield +2% on a $1000 position.** Acceptance requires actual full-native positive net results, robustness to extra costs, a genuinely unseen chronological follow-up sample, and comparison to simply NOT TRADING. This remains M2 NO-GO and paper/live LOCKED.
