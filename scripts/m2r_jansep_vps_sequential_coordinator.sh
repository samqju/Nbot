#!/usr/bin/env bash
# NBOT V6: finite, recoverable, sequential OFFLINE historical research ONLY.
# No paper/live strategies, exchange credentials, model promotion or scheduler.
set -euo pipefail
umask 077
ROOT="/root/nbot-v6-m1-20261016"
SOURCE="$ROOT/source"
OUT="$ROOT/jansep-20261017"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
mkdir -p "$OUT"
exec 9>"$OUT/vps-research-coordinator.lock"
flock -n 9 || { echo "OTHER_V6_COORDINATOR_RUNNING"; exit 2; }
exec >> "$OUT/vps-research-coordinator.log" 2>&1
say() { printf '%s  %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { say "STOP_ERROR: $*"; exit 3; }
say "START_FINITE_HISTORICAL_RESEARCH"
cd "$SOURCE"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail WRONG_BRANCH
[[ -z "$(git status --porcelain=v1)" ]] || fail DIRTY_REPOSITORY
command -v docker >/dev/null || fail DOCKER_MISSING
command -v timeout >/dev/null || fail TIMEOUT_MISSING
command -v python3 >/dev/null || fail PYTHON_MISSING
[[ -z "$(docker ps -q)" ]] || fail EXISTING_OTHER_DOCKER_JOB

# Prior first 30-day laptop->SSH launcher finished the native backtest ZIP
# but its interactive client vanished before writing EXIT_CODE. Treat a saved
# complete native ZIP as recoverable ONLY after the strict per-window validation
# in the runner below (trade dates, fees, stake, identifier, 25 coins).
# With no ZIP, model cache remains untouched but only a known orphan job can
# be resumed, never an arbitrary failed native result.
prior="$OUT/w30/run-state.txt"
[[ -f "$prior" ]] || fail INITIAL_30DAY_RUN_MISSING
if ! grep -q '^EXIT_CODE=' "$prior"; then
  z=$(find "$OUT/w30/backtest_results" -name '*.zip' -type f 2>/dev/null | wc -l)
  m=$(find "$OUT/w30/models" -name '*_model.joblib' -type f 2>/dev/null | wc -l)
  if [[ "$z" == 1 && "$m" == 825 ]]; then
    say "ORIGINAL_30D_NATIVE_ZIP_PRESENT_WITH_825_MODELS_REQUIRES_RUNNER_VALIDATION"
  elif [[ "$z" == 0 ]]; then
    say "ORIGINAL_30D_NO_ZIP_PRESERVE_MODELS_COUNT=$m"
    grep -q '^RESEARCH_RESUME_APPROVED_AFTER_ORPHAN=1$' "$prior" ||
      printf 'RESEARCH_RESUME_APPROVED_AFTER_ORPHAN=1\n' >> "$prior"
  else
    fail "INCONSISTENT_ORIGINAL_NATIVE_30D_FILES zips=$z models=$m"
  fi
fi

for count in $(seq 1 16); do
  [[ -z "$(docker ps -q)" ]] || fail COMPETING_DOCKER_JOB
  say "START_ONE_OFFLINE_RESEARCH_WINDOW_ATTEMPT=$count"
  set +e
  bash "$SOURCE/scripts/m2r_jansep_research_runner.sh" --execute
  rc=$?
  set -e
  say "ENDED_ONE_RESEARCH_WINDOW_ATTEMPT=$count code=$rc"
  if [[ "$rc" == 124 ]]; then
    say "KNOWN_BOUNDED_TIMEOUT_RETAIN_MODELS_AND_RETRY"
    continue
  fi
  [[ "$rc" == 0 ]] || fail "NATIVE_RUNNER_STOPPED_OR_FAILED_$rc"
  done_count=0
  for w in 30 60 90 180; do
    file="$OUT/w$w/run-state.txt"
    if [[ -f "$file" ]] &&
       { grep -q '^EXIT_CODE=0$' "$file" ||
         grep -q '^NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1$' "$file"; }; then
      done_count=$((done_count+1))
    fi
  done
  say "CURRENT_VERIFIED_NATIVE_ARCHIVE_MARKERS=$done_count/4"
  if [[ "$done_count" == 4 ]]; then break; fi
done
for w in 30 60 90 180; do
  file="$OUT/w$w/run-state.txt"
  [[ -f "$file" ]] || fail "NATIVE_WINDOW_NOT_STARTED_w$w"
  if ! grep -q '^EXIT_CODE=0$' "$file" &&
     ! grep -q '^NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1$' "$file"; then
    fail "NATIVE_WINDOW_INCOMPLETE_w$w"
  fi
done
say "STAGE1_FOUR_NATIVE_ARCHIVES_EXIST_BEGIN_STRICT_TRADE_ECONOMICS_AUDIT"
python3 "$SOURCE/scripts/m2r_jansep_native_rolling_audit.py" \
  --root "$OUT" --output "$OUT/jansep-native-four-window-audit.json" \
  --completed-lookbacks 30 60 90 180 || fail NATIVE_PORTFOLIO_AUDIT_FAILED
say "STAGE1_ECONOMIC_AUDIT_SAVED"

# Stage2 limited to strictly historical PUBLIC archive metadata and causal
# fixed-25 ranks; never claim full all-Binance rotated25 PnL tested.
timeout -s TERM -k 15 2400 python3 \
  "$SOURCE/scripts/m2r_binance_historical_universe_inventory.py" \
  --out "$OUT/binance-vision-2026-archived-usdt-symbol-months.json" \
  --threads 8 || fail BINANCE_HISTORICAL_METADATA_FAILED
say "STAGE2_USDT_MONTHLY_ARCHIVE_SYMBOL_INVENTORY_SAVED"
[[ -z "$(docker ps -q)" ]] || fail OTHER_DOCKER_BEFORE_SELECTOR_DIAGNOSTIC
mkdir -p "$OUT/selector"
timeout -s TERM -k 15 1800 docker run --rm \
  --name nbot-v6-jansep-asof-symbol-diagnostic --network none --memory=1g --cpus=1 \
  -v "$SOURCE:/research:ro" \
  -v "$ROOT/january-2026-public-history-stage:/history:ro" \
  -v "$OUT/selector:/results" --entrypoint python \
  freqtradeorg/freqtrade:stable_freqai \
  /research/scripts/m2r_asof_25market_selector_diagnostic.py \
  --data /history/futures --config /research/user_data/config.json \
  --output /results/25-market-8h-asof-ranking.json ||
  fail STAGE2_HISTORICAL_25_ONLY_CAUSAL_DIAGNOSTIC_FAILED
say "STAGE2_25_ONLY_CAUSAL_RANKING_DIAGNOSTIC_SAVED"
say "COMPLETE_FINITE_OFFLINE_RESEARCH_STAGE1_AND_STAGE2_DIAGNOSTICS_ONLY"
say "BLOCKED_WHOLE_EXCHANGE_POINT_IN_TIME_ROTATED25_ECONOMIC_BACKTEST_STILL_NEEDS_ALTERNATIVE_HISTORICAL_ELIGIBILITY_AND_FILLCOST_EVIDENCE"
say "NO_PAPER_NO_LIVE_NO_KEY_NO_REAL_ORDER_NO_MODEL_PROMOTION"
