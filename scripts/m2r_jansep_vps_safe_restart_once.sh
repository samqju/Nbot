#!/usr/bin/env bash
# Owner-authorized safe MANUAL restart of the V6-only finite historical study
# after original transient unit FAILED on a GitHub bash syntax error.
# Never places paper/live orders, never uses credentials, never edits V5/main.
# This DOES NOT create an hourly scheduler or any ChatGPT automation.
set -euo pipefail
ROOT=/root/nbot-v6-m1-20261016
SOURCE="$ROOT/source"
BATCH="$ROOT/jansep-20261017"
BRANCH=prototype/v6-freqtrade-freqai-20261016
OLDUNIT=nbot-v6-jansep26-historical.service
NEWUNIT=nbot-v6-jansep26-retryonce-20261017.service
[[ "$(id -u)" == 0 ]] || { echo ROOT_REQUIRED; exit 2; }
[[ -d "$SOURCE/.git" ]] || { echo MISSING_ISOLATED_V6_SOURCE; exit 2; }
cd "$SOURCE"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || { echo WRONG_BRANCH; exit 2; }
[[ -z "$(git status --porcelain=v1)" ]] || { echo DIRTY_WORKTREE; exit 2; }
[[ -z "$(docker ps -q)" ]] || { echo ANOTHER_DOCKER_RUNNING_DO_NOT_START; exit 2; }
if systemctl is-active --quiet "$OLDUNIT" ||
   systemctl is-active --quiet "$NEWUNIT"; then
  echo PREVIOUS_COORDINATOR_ALREADY_ACTIVE_DO_NOT_DUPLICATE
  exit 2
fi
[[ -f "$BATCH/w30/run-state.txt" ]] || { echo ORIGINAL_W30_MARKER_MISSING; exit 2; }
[[ -f "$BATCH/vps-research-bootstrap.sh" ]] || { echo ORIGINAL_VPS_BOOTSTRAP_MISSING; exit 2; }
git pull --ff-only origin "$BRANCH"
bash -n "$SOURCE/scripts/m2r_jansep_research_runner.sh"
bash -n "$SOURCE/scripts/m2r_jansep_vps_sequential_coordinator.sh"
python3 -m py_compile \
  "$SOURCE/scripts/m2r_jansep_native_rolling_audit.py" \
  "$SOURCE/scripts/m2r_binance_historical_universe_inventory.py" \
  "$SOURCE/scripts/m2r_asof_25market_selector_diagnostic.py"
[[ -z "$(docker ps -q)" ]] || { echo DOCKER_BECAME_BUSY; exit 2; }
# Runner in --status mode validates ZIP and model count and records the
# orphaned SSH original's TRUE archive verification, not a fabricated exit.
bash "$SOURCE/scripts/m2r_jansep_research_runner.sh" --status
# Independently verify the completed 30-day native ZIP with actual portfolio
# economics before allowing later training to start. This audit explicitly
# reports missing trainer purge logs after the original laptop disconnected.
python3 "$SOURCE/scripts/m2r_jansep_native_rolling_audit.py" \
  --root "$BATCH" \
  --output "$BATCH/jansep-native-30day-only-audit.json" \
  --completed-lookbacks 30
# Reuse root-owned bootstrap. It waits for ongoing native jobs, uses this
# V6-only branch and eventually execs finite 4-window research coordinator.
systemd-run \
  --unit=nbot-v6-jansep26-retryonce-20261017 \
  --description="NBOT V6 finite historical offline research restart once; NO paper/live" \
  --property=Type=exec --property=Restart=no --property=User=root \
  /bin/bash "$BATCH/vps-research-bootstrap.sh"
systemctl is-active "$NEWUNIT"
echo "SAFE_OFFLINE_V6_FINITE_COORDINATOR_STARTED"
echo "FOLLOWUP_READONLY: systemctl status $NEWUNIT --no-pager"
echo "FOLLOWUP_READONLY: tail -n 25 $BATCH/vps-research-coordinator.log"
