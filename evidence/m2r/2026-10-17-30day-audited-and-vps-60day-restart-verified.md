# NBOT V6 — 2026-10-17 native 30-day audit and VERIFIED restart of sequential offline study

**Verified actual VPS research-only execution: 2026-10-17 16:26:49 UTC (21:56:49 IST).**

## Historical native 30-day result: actual verified Freqtrade portfolio output

- Research machine: existing authorized isolated V6-only `8GB-Observation` VPS; checkout `/root/nbot-v6-m1-20261016/source`, branch `prototype/v6-freqtrade-freqai-20261016`; raw native outputs under `/root/nbot-v6-m1-20261016/jansep-20261017/w30`. Original source log truncated by a disconnected SSH launcher but Freqtrade finished its full historical ZIP.
- Native Freqtrade 2026.9 research strategy `NbotV6TradeOutcomeFundingResearch`, chronological internally purged `NbotV6PurgedLightGBMRegressor`, **30-day train, 7-day rolling fits, 25 fixed USDT perpetual coins × 33 weekly cutoffs = 825 fitted native model artifacts**.
- **Historical trading simulation February 15–September 30 2026** (October 1 exclusive), 100,000 USDT nominal wallet, one portfolio trade at a time, 1,000 USDT 1× stake, no paper/live orders, nominal historical modeled 0.05% Binance Freqtrade fees per side plus engine funding. Not a live executable spread/stop fill claim. **30-day frozen candidate is not viable on this result**.
- Real saved and independently verified native Freqtrade ZIP: 25 markets, exact model identifier `nbot-v6-m2r-jansep2026-30d-20261017`, 1,930 actual engine **simulated** closed trades, **engine net PnL −2,311.594335 USDT**, **max equity drawdown 2,346.179218 USDT**, NO TRADE reference 0.
- The strict executable source auditor `scripts/m2r_jansep_native_rolling_audit.py --root /root/nbot-v6-m1-20261016/jansep-20261017 --output /root/nbot-v6-m1-20261016/jansep-20261017/jansep-native-30day-only-audit.json --completed-lookbacks 30` exited **0**, printed `CERTIFIED_NATIVE_LONG_HISTORY_JOBS [(30, 825, 1930, -2311.594335)]`. This audit examined the actual ZIP, strategy identifier/timeframe/backtest dates, model artifacts, actual 1930 trade objects, simulated fees 0.0005 each side, 1x stakes and PnL sum. Distinct cost sensitivity additional roundtrip execution stress, as **hypothetical** (not observed fills):

| Additional roundtrip cost beyond Freqtrade modeled fee/funding | 30d historical PnL (USDT) |
|---|---:|
| 0 bps | **−2,311.594335** |
| +10 bps | **−4,240.161941** |
| +15 bps | **−5,204.445743** |
| +25 bps | **−7,133.013349** |
| NO TRADE | **0** |

- **Incomplete training purge log provenance:** The original SSH stdout stops mid 15th coin, though 825 fitted models and native full backtest ZIP exist. Only **493/825** training cuts had visible `boundary_violations=0` records; **332 missing log entries remain unproved**. Repaired auditor reports `chronological_embargo_fit_checks_evidenced_in_logs=493`, `missing_embargo_fit_log_entries_due_to_disconnected_original_launcher=332`. Do **NOT** claim all 825 native internal boundary checks independently logged/verifiably passed, nor claim release integrity based solely on native ZIP.

## Original automated sequence failed and the specific second bug found and corrected

1. First finite offline VPS transient service `nbot-v6-jansep26-historical.service` failed 2026-10-17 15:23:12 UTC, because shell source was corrupted and `bash -n` found unexpected `fi`. GitHub replacement scripts and CI fixed that parser failure. The 30-day ZIP survives unchanged; the original launcher never wrote `EXIT_CODE=0`, but the runner stores honest recovered `NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1` after validating its true native ZIP.
2. Initial attempt at guarded `scripts/m2r_jansep_vps_safe_restart_once.sh` on 2026-10-17 16:24 UTC stopped with exit 1 **after correctly validating 30-day ZIP but before starting 60-day**, because `set -euo pipefail` turned a `find missing-output-dir | wc -l` pipeline into a failing command for the not-yet-created 60-day files. Investigated with read-only `bash -x scripts/m2r_jansep_research_runner.sh --status` and fixed **only** the missing-directory guard. No hidden model failure.
3. V6 GitHub research commit **`1c264dcf69eef7ff0a9783d90fd0f74224738be2`** adds `if [[ -d "$zips" ]]` and `if [[ -d "$models" ]]` before counts, distinguishing legitimately not-yet-started windows from failed or inconsistent native output. Pulled via `git pull --ff-only` on the **clean, idle, isolated V6 VPS**. All three `bash -n` checks and Python compilation passed. Dry-run `bash scripts/m2r_jansep_research_runner.sh --status` printed **`VALIDATED_OFFLINE_WINDOW=30 MODELS=825 EXPECTED=825`** and **`NEXT_OFFLINE_WINDOW=60 MODELS=0 EXPECTED=725`**, exit 0.
4. Executed original owner-approved **guarded** `bash scripts/m2r_jansep_vps_safe_restart_once.sh` from V6 checkout on **2026-10-17 16:26:17 UTC**, with clean branch/no other Docker. It independently rechecked same 30d native ZIP, reran 30d strict native portfolio audit (exit 0) and started isolated **finite VPS systemd transient** service `nbot-v6-jansep26-retryonce-20261017.service`. `systemd-run` returned success; `systemctl is-active` returned **active**.
5. **At 2026-10-17 16:26:49 UTC, separately verified** `systemctl show` returned `ActiveState=active, SubState=running, MainPID=102374`; `docker ps -q` showed exactly **one Docker container** `e8778f620d9e`; source `w60/run-state.txt` records `STARTED_UTC=2026-10-17T16:26:18Z`, `WINDOW_DAYS=60`, `ATTEMPT=1`. Its actual native Freqtrade log is training BTC 1/25, 2/29 rolling fits with verified first logged `boundary_violations=0`. VPS finite research coordinator log shows `START_FINITE_HISTORICAL_RESEARCH`, `VALIDATED_OFFLINE_WINDOW=30 MODELS=825 EXPECTED=825`, and `RUNNING_WINDOW=60 ATTEMPT=1`.
6. The VPS-side finite systemd unit, not a ChatGPT scheduled task, is designed to run 60d → 90d → 180d **one at a time** and then native four-window audit and stage 2 archived-symbol and 25-only causal ranking diagnostics. **The future stages have NOT been verified complete yet**. The unit is not guaranteed across VPS reboot and may halt on a genuine validation/data/compute failure; inspect the read-only commands below if needed.

## Essential status commands (read-only, on authorized V6 research VPS)

```bash
systemctl status nbot-v6-jansep26-retryonce-20261017.service --no-pager
docker ps -q
ROOT=/root/nbot-v6-m1-20261016/jansep-20261017
tail -n 30 "$ROOT/vps-research-coordinator.log"
for w in 30 60 90 180; do
  echo "W=$w"
  cat "$ROOT/w$w/run-state.txt" 2>/dev/null || true
  find "$ROOT/w$w/models" -name '*_model.joblib' 2>/dev/null | wc -l
  find "$ROOT/w$w/backtest_results" -name '*.zip' 2>/dev/null | wc -l
done
```

Do **not** launch additional training Docker while one is running. When new records arrive, verify stage dates/stakes/PnL with native files and the saved auditor before calling 60/90/180 finished. Stage 2 entire-exchange historical 25-vs-rotated25 economic replay is **not automatically done**; the prepared archival-symbol metadata and fixed-25 as-of diagnostics **are only preliminary Stage2**, not proof of dynamic selection profitability.

**Release unchanged: M2 NO-GO, M3 not accepted, M4 paper ON HOLD, M7 LIVE LOCKED. Original V5 and default/main never touched. PR #50 remains draft/unmerged. Owner deleted any ChatGPT hourly checking task; no replacement task created.**
