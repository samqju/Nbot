# NBOT V6 October 17, 2026 — autonomous *finite* Jan–Sep offline research handoff

## Owner instruction and distinction from ChatGPT reminders

On October 17 the owner asked to persist all work on GitHub in case the chat reaches its limit and explicitly said they **DELETED the scheduled ChatGPT checking task**. **Do not recreate that task without an explicit new user instruction.** The earlier owner instruction to run the *two historical research stages consecutively* is still valid. A **single, nonrecurring, server-side systemd transient service** has therefore been launched on the isolated V6 research VPS. This is a finite **offline historical study**, NOT paper/live trading, NOT a continuous market-scanning or trading process and NOT a ChatGPT task.

## Last physically verified VPS checkpoint

- Authorized V6-only server through existing saved PuTTY session `8GB-Observation` on owner laptop, login root. Research source branch `prototype/v6-freqtrade-freqai-20261016`. **Never use V5 or main**.
- The ORIGINAL 30-day Freqtrade native backtest was launched at **2026-10-17 11:57:25 UTC / 17:27:25 IST** as `nbot-v6-jansep-w30-offline`.
- As of **2026-10-17 14:01:10 UTC / 19:31:10 IST**, **510 actual saved 30-day trained model joblib artifacts** out of 25 markets × 33 weekly cutoffs = **825 planned fits**. **0 completed Freqtrade native portfolio ZIPs**, **no verified Jan–Sep economic result** yet. This is **only** 30-day training, NOT 510 of a project-wide total.
- IMPORTANT operational issue: the original Windows-to-SSH launch session was reported unavailable, while Docker `nbot-v6-jansep-w30-offline` kept running past the original foreground timeout and `w30/run-state.txt` still contained only `STARTED_UTC=2026-10-17T11:57:25Z`; no `EXIT_CODE` marker. **Never infer a successful/failed original shell exit without evidence. Do not delete saved models.**
- At **2026-10-17 14:02:05 UTC / 19:32:05 IST**, created and verified active isolated systemd transient unit:
  `nbot-v6-jansep26-historical.service`. **`systemctl is-active` returned `active`**, original main PID `92974`. A separate VPS-side bootstrap (root-only `0700`) is saved at
  `/root/nbot-v6-m1-20261016/jansep-20261017/vps-research-bootstrap.sh`,
  with log `vps-research-bootstrap.log`. On last inspection it was safely **WAITING for the existing 30-day Docker container**, not launching any parallel training or editing a source-mounted checkout.
- The transient systemd service survives this ChatGPT conversation or owner laptop/SSH disconnect **while VPS/systemd is alive**, but it is NOT enabled across VPS reboots. If the VPS restarts or service fails, inspect results and explicitly relaunch only the source-controlled guarded finite job after checking all safety boundaries. It has **no hourly timer** and there is **no ChatGPT monitoring automation**.

## Exactly what the VPS server-side finite job is configured to do

Bootstrap is intentionally outside source while existing 30-day Docker is training. After original Docker exits, bootstrap checks correct V6-only clean git branch, fast-forwards **only** `prototype/v6-freqtrade-freqai-20261016`, runs `bash -n` for scripts and Python source syntax checks, then executes:

`scripts/m2r_jansep_vps_sequential_coordinator.sh` (**committed**).

That server-side coordinator uses an OS `flock` singleton and fail-closed Docker checks; it preserves all existing model artifacts and distinguishes a completed original native 30d archive without a launcher exit marker from a partially interrupted original job needing an explicit cached-model retry. It **does not invent** an exit status or silently assume 30d backtest success. The safe one-job-per-call runner `scripts/m2r_jansep_research_runner.sh --execute` then executes the missing chronological windows **sequentially**, up to a bounded number of retry attempts, never two resource-intensive Docker jobs concurrently, never a trading daemon:

| Historical model lookback | Eligible simulated trade start UTC | End exclusive UTC | Max position |
|---|---|---|---|
| 30 days | Feb 15, 2026 | Oct 1, 2026 | 1 × 1,000 USDT, 1× |
| 60 days | Mar 15, 2026 | Oct 1, 2026 | same |
| 90 days | Apr 15, 2026 | Oct 1, 2026 | same |
| 180 days | Jul 15, 2026 | Oct 1, 2026 | same |

Original strategy/features/hyperparameters, 7d FreqAI re-training, separate model identities, 12-bar internal embargo, 25 original futures coins, no credentials, 0.05%/side fee + modeled funding, and +10/15/25bp *hypothetical* cost sensitivity unchanged. Common Jul15–Sep30 comparison needed because start dates differ. Original/other models and non-ML baselines **not automatically run by this initial four-window coordinator**; do not claim those comparisons complete. Once the four actual native ZIPs exist and the `scripts/m2r_jansep_native_rolling_audit.py` comprehensive offline archive inspection passes, finite coordinator attempts Stage 2 **read-only historical S3 symbol-directory-month inventory** plus a **non-tradable as-of 8-hour liquidity/volatility diagnostic of the original 25 histories**. Stage 2's genuine *whole historically eligible Binance futures universe vs fixed-25 portfolio economic test* is **NOT automatically implemented**; the historical non-incumbent/delisted symbols' 5m/1h/funding and executable bid/ask must be demonstrated first, or report **BLOCKED**, not successful. No future market data leak, no survivorship-biased claims.

## Exact status, recovery and evidence commands on authorized V6 VPS

```bash
systemctl status nbot-v6-jansep26-historical.service --no-pager
journalctl -u nbot-v6-jansep26-historical.service -n 40 --no-pager
docker ps --format '{{.Names}}'
ROOT=/root/nbot-v6-m1-20261016/jansep-20261017
tail -n 40 "$ROOT/vps-research-bootstrap.log"
tail -n 40 "$ROOT/vps-research-coordinator.log"  # appears after bootstrap
for w in 30 60 90 180; do
  echo "WINDOW=$w"
  cat "$ROOT/w$w/run-state.txt" 2>/dev/null || true
  find "$ROOT/w$w/models" -name '*_model.joblib' 2>/dev/null | wc -l
  find "$ROOT/w$w/backtest_results" -name '*.zip' 2>/dev/null | wc -l
done
ls -l "$ROOT/jansep-native-four-window-audit.json" \
      "$ROOT/binance-vision-2026-archived-usdt-symbol-months.json" \
      "$ROOT/selector/25-market-8h-asof-ranking.json" 2>/dev/null || true
```

**Do not start a second job or edit a mounted source repo while an existing Docker container is active.** If the one-shot service fails, diagnose log, branch, Docker state and existing ZIPs *before* any resumption; no blind restart. Do not publish PnL from partial jobs. Never infer full autonomous research is completed from the existence of the systemd service. After full native results are audited, publish the source-controlled results and hashes, update `NEW_CHAT_HANDOFF.md`, `ROADMAP.md`, `M2R_RESEARCH.md`, and draft PR #50, verify CI. Code and prior pilot outcomes remain research only. **M2 NO-GO, M3 not accepted, M4 PAPER STILL ON HOLD, M7 LIVE LOCKED.**
