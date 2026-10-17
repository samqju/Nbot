#!/usr/bin/env bash
# NBOT V6: execute ONE next native historical research backtest, never live.
# Read-only status is allowed. --execute requires correct isolated V6 branch,
# no other running Docker jobs, dry-run config and no exchange keys.
set -euo pipefail
mode="$1"
[[ "$mode" == "--execute" || "$mode" == "--status" ]] || { echo "INVALID_MODE"; exit 2; }
ROOT="/root/nbot-v6-m1-20261016"
cd "$ROOT/source"
[[ "$(git branch --show-current)" == "prototype/v6-freqtrade-freqai-20261016" ]] || { echo WRONG_BRANCH; exit 2; }
[[ -z "$(git status --porcelain=v1)" ]] || { echo DIRTY_REPO; exit 2; }
ROOTDATA="$ROOT/jansep-20261017"
for w in 30 60 90 180; do
  case "$w" in
    30) from=20260215 ;;
    60) from=20260315 ;;
    90) from=20260415 ;;
    180) from=20260715 ;;
  esac
  expected=$(python3 - "$from" <<'PY'
from datetime import datetime
import sys, math
start=datetime.strptime(sys.argv[1],'%Y%m%d')
end=datetime.strptime('20261001','%Y%m%d')
print(math.ceil((end-start).days/7)*25)
PY
)
  folder="$ROOTDATA/w$w"
  state="$folder/run-state.txt"
  identity="nbot-v6-m2r-jansep2026-$w""d-20261017"
  models="$folder/models/$identity"
  zips="$folder/backtest_results"
  # Missing output directories are normal for not-yet-started 60/90/180d windows.
  # With pipefail enabled, "find" on absent directory exits nonzero even
  # though wc prints zero, so explicitly check existence first.
  if [[ -d "$zips" ]]; then
    zipcount=$(find "$zips" -name '*.zip' -type f | wc -l)
  else
    zipcount=0
  fi
  if [[ -d "$models" ]]; then
    modelcount=$(find "$models" -name '*_model.joblib' -type f | wc -l)
  else
    modelcount=0
  fi
  if [[ "$zipcount" == 1 && "$modelcount" == "$expected" ]]; then
    # A complete native archive may survive its interactive SSH launcher.
    # Validate actual native Freqtrade fields; do not invent EXIT_CODE=0.
    python3 - "$folder" "$w" "$from" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import json,sys
folder=Path(sys.argv[1])
w=int(sys.argv[2]); dt=sys.argv[3]
archives=list((folder/"backtest_results").glob("*.zip"))
assert len(archives)==1
with ZipFile(archives[0]) as z:
    assert z.testzip() is None
    candidates=[p for p in z.namelist() if p.endswith(".json") and not p.endswith("_config.json")]
    assert len(candidates)==1
    result=json.loads(z.read(candidates[0]))
s=result["strategy"]["NbotV6TradeOutcomeFundingResearch"]
assert s["freqai_identifier"]==f"nbot-v6-m2r-jansep2026-{w}d-20261017"
assert s["backtest_start"]==f"{dt[:4]}-{dt[4:6]}-{dt[6:]} 00:00:00"
assert s["backtest_end"]=="2026-10-01 00:00:00"
assert len(s["pairlist"])==25 and s["max_open_trades"]==1
assert float(s["stake_amount"])==1000 and float(s["starting_balance"])==100000
assert s["trading_mode"]=="futures" and s["timeframe"]=="5m"
assert len(s["trades"])==s["total_trades"]
PY
    if [[ ! -f "$state" ]]; then
      echo "SAFE_VALIDATED_ARCHIVE_BUT_NO_STATE_w$w"; exit 2
    fi
    if ! grep -q '^EXIT_CODE=0$' "$state" &&
       ! grep -q '^NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1$' "$state"; then
      printf 'NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1\n' >> "$state"
      echo "RECOVERED_NATIVE_ZIP_NO_ORIGINAL_EXIT_MARKER_w$w"
    fi
    echo "VALIDATED_OFFLINE_WINDOW=$w MODELS=$modelcount EXPECTED=$expected"
    continue
  fi
  if [[ "$zipcount" != 0 ]]; then
    echo "HALT_INCOMPLETE_OR_CONFLICTING_NATIVE_ZIP_w$w zips=$zipcount models=$modelcount expected=$expected"
    exit 2
  fi
  if [[ "$modelcount" -gt "$expected" ]]; then
    echo "HALT_TOO_MANY_FITTED_MODELS_w$w"
    exit 2
  fi
  [[ -z "$(docker ps -q)" ]] || { echo "HALT_OTHER_DOCKER_CONTAINER_RUNNING"; exit 2; }
  if [[ -f "$state" ]]; then
    if grep -q '^EXIT_CODE=' "$state" &&
       ! grep -q '^EXIT_CODE=124$' "$state"; then
      echo "HALT_PREVIOUS_ERROR_NOT_AUTOMATICALLY_RETRIED_w$w"
      exit 2
    fi
    # Missing exit marker only accepted if launch died while preserving models.
    if ! grep -q '^EXIT_CODE=' "$state" &&
       ! grep -q '^RESEARCH_RESUME_APPROVED_AFTER_ORPHAN=1$' "$state"; then
      echo "HALT_UNEXPLAINED_MISSING_EXIT_MARKER_w$w"
      exit 2
    fi
  fi
  echo "NEXT_OFFLINE_WINDOW=$w MODELS=$modelcount EXPECTED=$expected"
  [[ "$mode" == "--execute" ]] || exit 0
  conf="$ROOT/source/user_data/config.m2r-jansep2026-$w""day-offline.json"
  python3 - "$conf" "$w" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));w=int(sys.argv[2])
assert d["dry_run"] is True and d["nbot_m2r_research_only"] is True
assert d["nbot_m2r_purge_internal"] is True and d["nbot_m2r_event_funding_labels"] is True
assert d["nbot_live_mode"] is False and d["nbot_paper_research_mode"] is False
assert d["max_open_trades"]==1 and d["force_entry_enable"] is False
assert d["exchange"]=={"key":"","secret":""}
assert d["telegram"]["enabled"] is False and d["api_server"]["enabled"] is False
assert d["freqai"]["train_period_days"]==w and d["freqai"]["backtest_period_days"]==7
assert d["freqai"]["identifier"]==f"nbot-v6-m2r-jansep2026-{w}d-20261017"
assert d["freqai"]["data_split_parameters"]=={"test_size":.2,"shuffle":False}
PY
  mkdir -p "$folder"
  attempt=1
  while [[ -e "$folder/attempt-$attempt.log" ]]; do attempt=$((attempt+1)); done
  if [[ -f "$state" ]]; then cp "$state" "$folder/prior-state-attempt-$attempt.txt"; fi
  printf 'STARTED_UTC=%s\nWINDOW_DAYS=%s\nATTEMPT=%s\n' "$(date -u +%FT%TZ)" "$w" "$attempt" > "$state"
  echo "RUNNING_WINDOW=$w ATTEMPT=$attempt BEGIN_UTC=$(date -u +%FT%TZ)"
  set +e
  timeout -s TERM -k 60 18000 docker run --rm --name "nbot-v6-jansep-w$w-offline" \
    --network bridge --memory=6g --cpus=2 \
    -v "$ROOT/source:/research:ro" \
    -v "$ROOT/january-2026-public-history-stage:/history:ro" \
    -v "$folder:/results" \
    --entrypoint freqtrade freqtradeorg/freqtrade:stable_freqai backtesting \
    -c /research/user_data/config.json \
    -c "/research/user_data/config.m2r-jansep2026-$w""day-offline.json" \
    --userdir /results --datadir /history \
    --strategy NbotV6TradeOutcomeFundingResearch \
    --strategy-path /research/user_data/strategies \
    --freqaimodel NbotV6PurgedLightGBMRegressor \
    --freqaimodel-path /research/user_data/freqaimodels \
    --timerange "$from-20261001" --fee 0.0005 --cache none --export trades \
    > "$folder/attempt-$attempt.log" 2>&1
  rc=$?
  set -e
  printf 'EXIT_CODE=%s\nSTOPPED_UTC=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$state"
  echo "ENDED_OFFLINE_WINDOW=$w NATIVE_RETURN_CODE=$rc"
  exit "$rc"
done
echo "ALL_FOUR_WINDOWS_HAVE_NATIVE_ARCHIVES_BUT_AUDIT_STILL_REQUIRED"
