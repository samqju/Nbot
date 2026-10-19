#!/usr/bin/env bash
# This is a ONE-TIME finite stage handoff, NOT a recurrent ChatGPT automation.
# Safe to stage while the existing original library research Docker is active.
# It NEVER runs another Docker or changes the Git checkout until predecessor
# has FINISHED and vacated all containers. Does not restart a stopped study.
set -euo pipefail
umask 022

ROOT=/root/nbot-v6-m1-20261016
SOURCE="$ROOT/source"
OUT="$ROOT/library-20261018"
PREVIOUS=nbot-v6-library-20261018.service
NEXT=nbot-v6-profit-protection-next-20261018.service
BRANCH=prototype/v6-freqtrade-freqai-20261016
LOG="$OUT/v6-profit-protection-successor-wait-once.log"

[[ "$(id -u)" == 0 ]] || { echo "V6_OWNER_ROOT_REQUIRED"; exit 2; }
[[ -d "$SOURCE/.git" && -d "$OUT" ]] || { echo "ORIGINAL_V6_STUDY_MISSING"; exit 2; }
[[ "$(git -C "$SOURCE" branch --show-current)" == "$BRANCH" ]] ||
    { echo "WRONG_BRANCH"; exit 2; }
exec >> "$LOG" 2>&1
say() { printf '%s | %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { say "BLOCKED: $*"; exit 3; }
say "WAIT_FOR_FINITE_RESEARCH_ONLY_STUDY_COMPLETION: $PREVIOUS"

# HARD DEADLINE: once per minute maximum, 24 hours. This waiter is itself a
# finite VPS process, cannot survive a reboot, and never schedules another.
ready=0
for ((i=0; i<1440; i++)); do
  prior=$(python3 - "$OUT/v6-library-research-status.json" <<'PY'
import json,sys
try:
    a=json.load(open(sys.argv[1]))
    print(a.get("status","MISSING"))
except (OSError,ValueError) as e:
    print("MISSING")
PY
)
  active=$(systemctl show "$PREVIOUS" -p ActiveState --value 2>/dev/null || true)
  if [[ "$active" == "active" || "$active" == "activating" || "$active" == "deactivating" ]]; then
    if (( i%15==0 )); then say "STILL_RUNNING predecessor=$active status=$prior"; fi
    sleep 60
    continue
  fi
  if [[ "$prior" == "blocked" ]]; then fail "PREVIOUS_RESEARCH_BLOCKED_NO_AUTOSTART"; fi
  if [[ "$prior" != "complete_with_individual_failures_if_any" ]]; then
    fail "PREVIOUS_UNIT_STOPPED_WITHOUT_COMPLETE_EVIDENCE status=$prior"
  fi
  [[ -s "$OUT/candidate-native-aftercost-summary.json" ]] ||
     fail "PREDECESSOR_FINAL_NATIVE_AUDIT_MISSING"
  [[ -z "$(docker ps -q)" ]] ||
     fail "DOCKER_BUSY_AFTER_PREDECESSOR_STOPPED"
  ready=1
  break
done
[[ "$ready" == 1 ]] || fail "ORIGINAL_FINITE_BATCH_DID_NOT_FINISH_WITHIN_24H"
say "PREVIOUS_FINISHED_SAFELY; NOW_AUTHORIZED_TO_DEPLOY_NEXT_STAGE_ONLY"

# Never touch main or V5; do not merge, reset or cherry-pick anything.
[[ "$(git -C "$SOURCE" branch --show-current)" == "$BRANCH" ]] ||
   fail "RESEARCH_BRANCH_CHANGED"
[[ -z "$(git -C "$SOURCE" status --porcelain=v1)" ]] ||
   fail "RESEARCH_CHECKOUT_DIRTY_AFTER_OLD_BATCH"
[[ -z "$(docker ps -q)" ]] || fail "DOCKER_CONFLICT_BEFORE_FF_ONLY_PULL"
git -C "$SOURCE" pull --ff-only origin "$BRANCH" ||
   fail "CANNOT_FETCH_PINNED_V6_FOLLOWUP_CODE"
find "$SOURCE/scripts" "$SOURCE/user_data/strategies" "$SOURCE/user_data/freqaimodels" -type f -name "*.py" -exec chmod a+r {} + ||
   fail "FAILED_TO_RESTORE_OFFLINE_DOCKER_READ_ACCESS"
git -C "$SOURCE" merge-base --is-ancestor 06d89709b9245c16173bbd11bf208110dde8e85a HEAD ||
   fail "EXPECTED_PROFIT_PROTECTION_GITHUB_CODE_NOT_PRESENT"
[[ -z "$(git -C "$SOURCE" status --porcelain=v1)" ]] ||
   fail "PULL_PRODUCED_DIRTY_CHECKOUT"
python3 -m py_compile \
 "$SOURCE/scripts/m2r_v6_library_native_job.py" \
 "$SOURCE/scripts/m2r_v6_profit_protection_batch.py" \
 "$SOURCE/scripts/m2r_v6_profit_reversal_audit.py" \
 "$SOURCE/user_data/strategies/NbotV6ProfitProtectionResearch.py" ||
 fail "POSTPULL_SYNTAX_INVALID"
[[ ! -e "$OUT/profit-protection-next-phase/status.json" ]] ||
   fail "FOLLOWUP_ALREADY_STARTED_NO_DUPLICATE_ALLOWED"
[[ -z "$(docker ps -q)" ]] || fail "DOCKER_BUSY_BEFORE_NEXT_NATIVE_JOB"

say "NEXT_STAGE_START_COMMIT=$(git -C "$SOURCE" rev-parse HEAD)"
say "NEXT_STAGE_NONTRADING_COMMAND_OWNER_AUTHORIZED_FINITE_5x8x3_EXIT_RESEARCH"
export NBOT_V6_LIBRARY_OFFLINE_EXECUTION=OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY
# exec keeps one systemd unit alive as the actual successor coordinator and
# ensures the original native research remains immutable.
exec /usr/bin/python3 "$SOURCE/scripts/m2r_v6_profit_protection_batch.py" --execute
