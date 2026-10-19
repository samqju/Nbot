#!/usr/bin/env bash
# Persistent fail-closed VPS-only third-stage queue. NO trading, no duplicate.
# Does not compete with currently running library / profit protection.
set -euo pipefail
umask 022
ROOT=/root/nbot-v6-m1-20261016
SRC="$ROOT/global-next-source"
OUT="$ROOT/library-20261018"
BRANCH=prototype/v6-freqtrade-freqai-20261016
LIB=nbot-v6-library-20261018.service
PROFIT=nbot-v6-profit-protection-next-20261018.service
log() { echo "$(date -u +%FT%TZ) GLOBAL_V6_QUEUE $*"; }
fatal() { log "BLOCKED $*"; exit 3; }
[[ "$(id -u)" == 0 ]] || fatal ROOT_REQUIRED
[[ -d "$SRC/.git" ]] || fatal ISOLATED_RESEARCH_CHECKOUT_MISSING

# Wait indefinitely for success, but NEVER wait forever if an earlier job
# has failed / vanished without verifiable complete outputs. Survives reboot
# as an ordinary explicitly enabled systemd service.
while true; do
  lib=$(python3 - "$OUT/v6-library-research-status.json" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1]))
 print(d.get("status","MISSING"))
except (OSError,ValueError):print("MISSING")
PY
)
  profit=$(python3 - "$OUT/profit-protection-next-phase/status.json" <<'PY'
import json,sys
try:
 d=json.load(open(sys.argv[1]))
 print(d.get("status","MISSING"))
except (OSError,ValueError):print("MISSING")
PY
)
  [[ "$lib" != "blocked" && "$profit" != "blocked" ]] || fatal PREDECESSOR_BLOCKED
  lib_active=0; systemctl is-active --quiet "$LIB" && lib_active=1 || true
  profit_active=0; systemctl is-active --quiet "$PROFIT" && profit_active=1 || true
  if [[ $lib_active == 0 && "$lib" != "complete_with_individual_failures_if_any" ]]; then
      fatal "LIBRARY_STOPPED_WITHOUT_COMPLETE_EVIDENCE=$lib"
  fi
  if [[ $profit_active == 0 && "$profit" != "complete_offline_not_release_ready" ]]; then
      fatal "PROFIT_PROTECTION_STOPPED_WITHOUT_COMPLETE_EVIDENCE=$profit"
  fi
  if [[ $lib_active == 0 && $profit_active == 0
       && "$lib" == "complete_with_individual_failures_if_any"
       && "$profit" == "complete_offline_not_release_ready" ]]; then
      log "PRIOR_TWO_BATCHES_COMPLETED; validation begins"
      break
  fi
  log "WAITING library=$lib active=$lib_active profit=$profit active=$profit_active"
  sleep 300
done

[[ -z "$(docker ps -q)" ]] || fatal OTHER_DOCKER_CONTAINER_RUNNING
[[ "$(git -C "$SRC" branch --show-current)" == "$BRANCH" ]] || fatal WRONG_BRANCH
[[ -z "$(git -C "$SRC" status --porcelain=v1)" ]] || fatal DIRTY_SOURCE
git -C "$SRC" fetch origin "$BRANCH" || fatal SOURCE_FETCH_FAILED
git -C "$SRC" merge --ff-only FETCH_HEAD || fatal NONFASTFORWARD_CODE_BLOCKED
find "$SRC/scripts" "$SRC/user_data/strategies" "$SRC/user_data/freqaimodels" -type f -name "*.py" -exec chmod a+r {} + || fatal GLOBAL_CODE_UNREADABLE
[[ -z "$(git -C "$SRC" status --porcelain=v1)" ]] || fatal SOURCE_DIRTY_AFTER_PULL
[[ -f "$SRC/V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md" ]] || fatal MISSING_APPROVED_SPEC
[[ -f "$SRC/scripts/m2r_v6_global_batch.py" ]] || fatal INCOMPLETE_RUNNER
python3 -m py_compile \
  "$SRC/scripts/m2r_v6_global_dataset.py" \
  "$SRC/scripts/m2r_v6_global_batch.py" \
  "$SRC/user_data/strategies/NbotV6GlobalOfflineResearch.py" || fatal CODE_SYNTAX_FAILURE
(cd "$SRC" && python3 -m unittest tests.test_m2r_v6_global_batch_contract \
   tests.test_m2r_v6_global_opportunity_ranker) || fatal REQUIRED_UNIT_TEST_FAILURE
[[ -z "$(docker ps -q)" ]] || fatal DOCKER_BECAME_BUSY
[[ ! -e "$ROOT/global-25x8-20261018/owner-comparison.json" ]] || fatal ALREADY_COMPLETED
log "OWNER_AUTHORIZED_OFFLINE_ONLY_START; NO PAPER NO LIVE; source=$(git -C "$SRC" rev-parse HEAD)"
export NBOT_V6_GLOBAL_RESEARCH=OWNER_AUTHORIZED_OFFLINE_GLOBAL_V6_RESEARCH_ONLY
exec /usr/bin/python3 "$SRC/scripts/m2r_v6_global_batch.py" --execute
