# NBOT V6 — profit-protection failed handoff diagnosed and recovered

**Direct live VPS observations:** 2026-10-19 00:47–00:57 UTC (Asia/Kolkata +05:30). **NO live or paper trading was enabled.** This note records actual service and output evidence, not predictions or final economic results.

## Pre-repair investigation

- Seven missing eight-strategy recovery experiments finished successfully 2026-10-18 22:38:01 UTC. Recovery status `finished, completed=7, failed=0`; original successful library backtests, trailing A/B and historical audit archives remain unchanged. Stage 1: **63/63** jobs.
- The newly rearmed `nbot-v6-profit-protection-next-20261018.service` failed 2026-10-18 22:38:10 UTC (`ExecMainStatus=1`) on the first native run `protect_trail_1p0_gap_0p5/ema_cross/validation_july`; **0 of 120** native exit-policy studies completed at that time.
- Actual native output `.../library-20261018/protect_trail_1p0_gap_0p5/ema_cross/validation_july/native.log` showed **PermissionError: [Errno 13] Permission denied: '/research/user_data/strategies/NbotV6GlobalOfflineResearch.py'**. Freqtrade 2026.9 strategy discovery scans other Python files even when selecting the profit-protection family.
- The optional original-loss trajectory audit also had **Permission denied** importing `/research/scripts/m2r_v6_profit_reversal_audit.py`. `namei -l` on the host proved both source files were root-owned mode **0600** after the Stage2 Git pull (the old Stage2 successor script had `umask 077`); the research Docker runs under a non-root user.
- `nbot-v6-global-20261018.service` stopped at 22:43:01 UTC with `BLOCKED PREDECESSOR_BLOCKED`, correctly refusing to run AI research before Stage2. No global portfolio results existed.

## Safe repair actually performed

1. Patched and committed both future GitHub handoff scripts `scripts/m2r_v6_profit_protection_successor_wait.sh` and `scripts/m2r_v6_global_successor_wait.sh`: use `umask 022` for downloaded checkout files and normalize read permission on the specific research Python source trees after updating the V6 branch, before native/Docker work.
2. Fast-forwarded the **separate idle** `global-next-source` checkout to the patched V6 branch, validated both Bash files with `bash -n`, and copied the revised Stage2 waiter to the installed Stage2 entrypoint. Active study code was not modified while a research container was running.
3. Preserved the failed Stage2 status, events, diagnostic log and incomplete first trial in the private archive `/root/nbot-v6-m1-20261016/profit-protection-failed-attempt-20261019/` (no completed study overwritten). Original 63/63 first-stage evidence untouched.
4. Explicitly restored mode **0644** to Python source files in `source/scripts`, `source/user_data/strategies` and `source/user_data/freqaimodels`; original Git checkout remained clean. Verified **inside the official Docker image** that all three files involved in the permission problem were readable.
5. Restarted the existing offline-only Stage2 systemd service; it began new native trials, produced audited actual Freqtrade ZIP results and moved sequentially to subsequent periods. Re-armed the existing Stage3 global service **only as a waiting handoff**, preventing simultaneous Docker work.

## Last verified state — 2026-10-19 00:57:39 UTC / 06:27:39 IST

- **Stage 1:** 63/63 original and recovered experiments complete; no repeat jobs.
- **Stage 2:** `nbot-v6-profit-protection-next-20261018.service` **ACTIVE**, 3/120 official exit-rule portfolio experiments completed and audited, fourth job `protect_trail_1p0_gap_0p5/donchian_breakout/validation_july` STARTED. First EMA Cross early-trail variant (July/Aug/Sep) returned native after-base-cost results **negative in all three months**, and negative under additional hypothetical 25bp stress. No strategy has been promoted.
- **Stage 3:** `nbot-v6-global-20261018.service` **ACTIVE AS WAITER**; journal displayed `WAITING library=complete_with_individual_failures_if_any active=0 profit=running active=1`. No global 25×8 portfolio research yet started; no `global-25x8-20261018/progress.json` present.
- **Important secondary issue:** optional Stage2 loss-path diagnostic now fails with `REVERSE_DATE_IN_NATIVE_TRADE`, distinct from the fixed permission failure. The `m2r_v6_profit_reversal_audit.py` original code treated equal native open/close timestamps as invalid; Freqtrade can legitimately enter and exit within one candle. Patched and committed conservative handling for **equal timestamp = no earlier complete path**, retaining the error for genuinely reversed timestamps. This patch applies to a **separate future read-only diagnostic** only; the active Stage2 code was not interrupted, and `loss_path_diagnostic_failed=true` accurately remains in its current status. The corrected optional diagnostic has **not been rerun or verified against the old archive** yet. The 120 native backtests do not depend on that diagnostic.

## Read-only PuTTY commands

```bash
systemctl status nbot-v6-profit-protection-next-20261018.service --no-pager -l
python3 /root/nbot-v6-m1-20261016/source/scripts/m2r_v6_profit_protection_batch.py --status
journalctl -u nbot-v6-global-20261018.service --no-pager -n 10
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_global_batch.py --status
```

**Scientific guardrails:** Historical equity paths and calibrated models are not evidence of profitable future live trading. Preserve all native ZIPs (including negative results), compare strategies/exit policies and 25bp execution stress, await genuine unseen walk-forward economic evidence and owner acceptance. Fail-closed on any additional research error, rather than deleting outputs or re-running completed studies.
