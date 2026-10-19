# NBOT V6 — finite recovery of seven interrupted library jobs

**Verified VPS time:** 2026-10-18 15:25:00 UTC (20:55 IST). **This is proof of running recovery, NOT a claim of recovery completion.**

## Why the queue stopped
The original `nbot-v6-library-20261018.service` completed its coordinator on 2026-10-18 14:36:20 UTC with status `complete_with_individual_failures_if_any`, but 7 research jobs had not succeeded: stochastic / ATR / volume Hyperopt (3), EMA / volume LightGBM (2), adaptive selector (1), PPO (1). The Stochastic Reversal Hyperopt was forcibly terminated with `EXIT_CODE=-9` after the original **four-hour** timeout; subsequent candidate jobs refused because its Docker container was still busy while teardown completed. The profit successor exited `BLOCKED: DOCKER_BUSY_AFTER_PREDECESSOR_STOPPED`, and global AI successor correctly exited `PROFIT_PROTECTION_STOPPED_WITHOUT_COMPLETE_EVIDENCE=MISSING`. At a later check Docker was empty; the original failed Hyperopt output still existed.

The already-successful work was **not repeated**: original baseline 3/3, native 8-strategy 24/24, trailing comparison 24/24 and 5/8 independent Hyperopt jobs = 56/63 stage1 successful. There were 51 official economic audit ZIPs and the original completion report remains immutable. Stage2 had 0/120 and Stage3 had 0/12.

## Recovery execution actually verified
- A [seven-job finite recovery coordinator](../../scripts/m2r_v6_library_failure_recovery.py) was committed on branch `prototype/v6-freqtrade-freqai-20261016` with [five safety/unit tests](../../tests/test_m2r_v6_library_recovery.py); GitHub Actions [39140260652](https://github.com/samqju/Nbot/actions/runs/39140260652) **passed both offline-unit-tests and official Freqtrade strategy discovery**.
- Fresh recovery results go to `/root/nbot-v6-m1-20261016/library-20261018-recovery`; the 4h terminated attempt and all 56 previously successful jobs remain in their original directories.
- Original model/strategy code frozen at exactly `aa97a32c9af73ae63503f5dbff63d98a7fe32200`; exchange credentials empty, one native simulated global position, no live/paper, candidate approval false. Sequentially run only missing `hyperopt/stochastic_reversal`, `hyperopt/atr_breakout`, `hyperopt/volume_trend`, `lgbm/ema_cross`, `lgbm/volume_trend`, `adaptive/ema_cross`, `rl/ema_cross` on the original scheduled periods.
- The per-job maximum timeout is 36,000 seconds (10 hours), specifically to avoid incorrectly classifying a still-progressing 60-epoch Hyperopt as a failure after 4 hours. If a job fails again or its actual native ZIP/fee/funding/one-slot evidence cannot be verified, recovery STOPS; no fabricated 'completed' signals.
- Persistent units installed under `/etc/systemd/system/` for `nbot-v6-library-recovery-20261018.service` and `nbot-v6-profit-protection-next-20261018.service`; the persistent `nbot-v6-global-20261018.service` was retained. Recovery enables/rearms Stage2 and Stage3 only when its seven tests complete and no Docker is active.
- **Actually observed:** at 2026-10-18 15:25 UTC `nbot-v6-library-recovery-20261018.service` was `active (running)`, main PID `158595`, with Docker running `NbotV6StochasticResearch` Hyperopt 60 epochs in `.../library-20261018-recovery/hyperopt/stochastic_reversal/tuning_may_june`. Recovery status showed `running, completed=0, failed=0, total=7`; Stage2 and Stage3 inactive as required. No second Docker research job started.

## Read-only PuTTY checks
```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_library_failure_recovery.py --status
systemctl status nbot-v6-library-recovery-20261018.service --no-pager
journalctl -u nbot-v6-library-recovery-20261018.service --no-pager -n 15
```

The user's existing `m2r_v6_all_research_status.py` shows the **original** 56/63 successful jobs; it does not automatically include the separate recovery progress, so the additional recovery command above is needed until the stage1 recovery completes.

## Pending
Actual economic results remain to be proven in Stage2 and Stage3. Stage2 profit-protection 120 native experiments, and Stage3 12 AI candidate/global portfolio runs are not started; both must remain inactive while Stage1 recovery Docker is running. A host restart during any in-flight job may require manual review of the partially written new recovery directory; do NOT delete it or repeat completed jobs blindly.
