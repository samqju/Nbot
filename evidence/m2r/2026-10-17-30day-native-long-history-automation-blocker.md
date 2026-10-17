# NBOT V6 Oct 17 2026 — 30-day native historical ZIP and failed sequential launcher diagnosis

## Verified original 30-day historical backtest output

Last successfully accessed authorized isolated V6-only VPS at **2026-10-17 15:47 UTC**; native original experiment under `/root/nbot-v6-m1-20261016/jansep-20261017/w30/`.

- **825 / 825 saved fitted FreqAI models**, 25 original fixed Binance USDT-M perpetual pairs × 33 weekly 30-day model windows. Native Freqtrade backtest ZIP `backtest_results/backtest-result-2026-10-17_15-23-00.zip` exists, approximately 1.5MB and `zipfile.ZipFile.testzip()` returned `None` (no ZIP CRC errors).
- The ZIP strategy key is **`NbotV6TradeOutcomeFundingResearch`**, model identifier **`nbot-v6-m2r-jansep2026-30d-20261017`**, Freqtrade backtest range **2026-02-15 00:00:00 UTC to 2026-10-01 00:00:00 UTC exclusive**, 25 markets, one `max_open_trades`, 1,000 USDT stake, 100,000 USDT nominal starting wallet.
- Real native engine historical simulation result fields read directly from ZIP: **1,930 simulated closed trades**, **−2,311.5943346 USDT** total reported simulated net PnL, **2,346.17921763 USDT** maximum native equity drawdown. **NO TRADE = 0**. These are simulation results **NOT real exchange trades or fills**; historical execution/signed funding/stops and extra 10/15/25bps stress still need independent audit. This long period is partially previously viewed (Aug/Sept); do not claim pristine blind acceptance.
- The original laptop/SSH launcher exited/disconnected **without writing EXIT_CODE** even though Freqtrade Docker subsequently finished and wrote ZIP. `w30/run-state.txt` therefore contains ONLY `STARTED_UTC=2026-10-17T11:57:25Z`. **A missing exit marker does not negate the native ZIP, but must not be misrepresented as `EXIT_CODE=0`.** The original stdout log stopped prematurely at 15th coin around 2026-10-17 13:57 UTC, and contained **493 logged `boundary_violations=0` purge checks**, not all 825. Other 332 model-purge log entries are **not independently observed**; separate model artifacts do not prove log parity. Auditing code now explicitly reports this limitation rather than incorrectly asserting 825 verified purge logs.
- All 60-/90-/180-day LONG-PERIOD portfolios **NOT started** at last check, no native results, model count zero. Stage2 historical wider-universe selection **NOT executed**.

## Why remaining windows did not start

Owner had deleted scheduled ChatGPT checking task, so a separate safe **finite offline historical-only VPS systemd transient unit `nbot-v6-jansep26-historical.service`** was installed at 14:02 UTC to wait for the original 30d run, then advance research without a chat or PuTTY client. At **2026-10-17 15:23:12 UTC** this unit **FAILED with exit status 2** during the VPS bootstrap's `bash -n` source check. Root cause from its actual `vps-research-bootstrap.log`:

```
scripts/m2r_jansep_research_runner.sh: line 30: syntax error near unexpected token 'fi'
```

Inspection showed a previous GitHub string replacement had damaged and duplicated shell-script text: runner lines cut off mid quoted Bash grep, coordinator similarly contained malformed conditions. This was a **real code error**, NOT a profitability finding or data/training-model failure. Bootstrap failed closed **before starting 60d, 90d, 180d or a competing Docker**, leaving original 825 saved models/ZIP intact. `docker ps` showed no active containers at the last VPS check.

## Repair made on the V6 research branch, NOT yet deployed on VPS

- **REPLACED** broken runner `scripts/m2r_jansep_research_runner.sh` with fresh short guarded source, per-window expected fits (30d 825, 60d 725, 90d 625, 180d 300), checks for 25-pair native archive strategy/model id, exact dates, one 1× $1,000 position, clean V6 Git branch, idle Docker, dry-run, blank exchange keys, weekly 7d fitting. It only runs ONE native long-window backtest per call; safely recognizes completed 30d original archive without falsely writing an exit code; preserves model cache on timeout.
- **REPLACED** corrupted `scripts/m2r_jansep_vps_sequential_coordinator.sh` with finite bounded one-job-at-a-time flow: 30d verified or safely resumed; 60d, 90d, 180d sequential; then native economic auditor; then read-only historical S3 ever-archived USDT contract-month inventory and 25-only as-of 8h ranking diagnostics. True all-exchange historically rotated 25-vs-fixed 25 PnL remains **NOT IMPLEMENTED / NEEDS ALT-MARKET POINT-IN-TIME ELIGIBILITY AND COST DATA**.
- Updated `scripts/m2r_jansep_native_rolling_audit.py`: requires expected model artifact count and exact native trade ledger, reports **observed** 493/825 original embargo/purge log coverage, retains 0 violations only for observed records, never claims all 825 boundary checks passed.
- Added `tests/test_m2r_jansep_runner_syntax.py` with Bash syntax checks for both scripts and safety contract. CI run **39046880409 passed** for the first corrected source version. Additional restart-script CI must be separately confirmed.
- Added fail-closed **MANUAL finite VPS recovery entrypoint** `scripts/m2r_jansep_vps_safe_restart_once.sh`: checks root, branch, idle Docker, no active previous/transient coordinator, clean git, FF pull, Bash/Python syntax, verifies native 30d archive via the runner, runs actual native 30d economic/purge-coverage audit, and starts a distinct new *finite* transient systemd research-only service. It is **NOT a periodic task** and does NOT touch V5/main, paper daemon, live money or keys.

**IMPORTANT:** after the GitHub code repair, the authorized Desktop Commander laptop relay stopped responding (timeouts) although its device catalog still showed stale online. The repair commits are **in GitHub but NOT verified pulled/deployed on V6 VPS**. No claim the new safe service has started; as of last verifiable VPS read the original systemd unit was FAILED. Explicit fresh SSH/VPS access required for recovery. Do not blindly run jobs or assert result until logged. The owner explicitly **deleted ChatGPT scheduled monitoring**, so **do not recreate that automation**.

## Restart/recovery instructions once authorized VPS SSH returns

On owner-authorized **V6-only** PuTTY session `8GB-Observation`, login root, first check `docker ps -q`, `systemctl status nbot-v6-jansep26-historical.service --no-pager`, and `git -C /root/nbot-v6-m1-20261016/source status --porcelain=v1`. If **no active Docker**, no active research coordinator, correct V6 branch, and clean checkout, the guarded (owner-authorized offline-only) restart is:

```bash
cd /root/nbot-v6-m1-20261016/source
git pull --ff-only origin prototype/v6-freqtrade-freqai-20261016
bash scripts/m2r_jansep_vps_safe_restart_once.sh
```

If ANY command fails, halt and inspect without deleting models or starting a second container. New finite unit if successful: `nbot-v6-jansep26-retryonce-20261017.service` (a different name because the original transient unit is FAILED). The guarded recovery **first verifies and audits the completed 30d native archive**, then starts later 60d/90d/180d automatically one at a time on the VPS even when laptop/chat disconnects. Does NOT survive VPS reboot. Run `systemctl status nbot-v6-jansep26-retryonce-20261017.service --no-pager`, `docker ps --format '{{.Names}}'` and `tail -n 30 /root/nbot-v6-m1-20261016/jansep-20261017/vps-research-coordinator.log` to monitor.

**M2 gate NO-GO. Paper trading ON HOLD. M7 real orders LOCKED. Original PR #50 DRAFT/UNMERGED. V5 and main unchanged.**
