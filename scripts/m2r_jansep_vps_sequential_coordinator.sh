#!/usr/bin/env bash
# NBOT V6 ONLY — unattended FINITE offline research batch (never a trading daemon).
# Owner approved Stage1 30/60/90/180 consecutive native historical tests
# and a Stage2 read-only archive / fixed-25 as-of-ranking diagnosis.
# NOT a ChatGPT automation, NOT paper trading, NOT live.
set -euo pipefail
umask 077

ROOT="/root/nbot-v6-m1-20261016"
SOURCE="$ROOT/source"
OUT="$ROOT/jansep-20261017"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
mkdir -p "$OUT"
exec 9>"$OUT/vps-research-coordinator.lock"
if ! flock -n 9; then echo "ANOTHER_V6_COORDINATOR_ALREADY_RUNNING"; exit 2; fi
exec >> "$OUT/vps-research-coordinator.log" 2>&1
stamp() { printf '%s  %s\n' "$(date -u +%FT%TZ)" "$*"; }
fail() { stamp "HALT_ERROR: $*"; exit 3; }
stamp "START finite owner-approved V6-only offline research coordinator"
test -d "$SOURCE/.git" || fail "MISSING_ISOLATED_V6_REPO"
cd "$SOURCE"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "WRONG_BRANCH"
[[ -z "$(git status --porcelain=v1)" ]] || fail "DIRTY_V6_CHECKOUT"
command -v docker >/dev/null || fail "NO_DOCKER"
command -v timeout >/dev/null || fail "NO_TIMEOUT"
command -v python3 >/dev/null || fail "NO_PYTHON"

# The first 30d native 25-market backtest was launched through an earlier
# interactive Windows->SSH client with its own 7200s timeout. Do not compete.
while [[ -n "$(docker ps -q)" ]]; do
  stamp "WAIT existing Freqtrade research Docker process; will not start another"
  sleep 45
done

# Existing foreground launcher may take a few seconds after Docker termination
# to write EXIT_CODE=124 or =0. No blind restart if process disappeared.
state="$OUT/w30/run-state.txt"
if [[ -f "$state" ]] && ! grep -q '^EXIT_CODE=' "$state"; then
  for i in $(seq 1 12); do
    grep -q '^EXIT_CODE=' "$state" && break
    sleep 10
  done
  grep -q '^EXIT_CODE=' "$state" || fail "PRIOR_30DAY_PROCESS_ENDED_WITHOUT_EXIT_MARKER; requires manual diagnosis"
fi
stamp "Existing historical run status: $(tr '\n' ' ' < "$state")"

# The coordinating client can now safely update only the authorized V6 branch.
[[ -z "$(docker ps -q)" ]] || fail "UNEXPECTED_DOCKER_BUSY_BEFORE_PULL"
git pull --ff-only origin "$BRANCH" || fail "V6_GIT_FAST_FORWARD_FAILED"
[[ -z "$(git status --porcelain=v1)" ]] || fail "REPO_DIRTY_AFTER_PULL"
stamp "Research checkout at $(git rev-parse HEAD); no V5/main changes"

for attempt in $(seq 1 12); do
  [[ -z "$(docker ps -q)" ]] || fail "OTHER_DOCKER_JOB_STARTED"
  stamp "EXECUTE_NEXT bounded one-window native historical research, attempt=$attempt"
  set +e
  bash "$SOURCE/scripts/m2r_jansep_research_runner.sh" --execute
  rc=$?
  set -e
  stamp "One-window bounded return code: $rc"
  if [[ "$rc" == 124 ]]; then
    stamp "Guarded timeout, retry with saved FreqAI models; NEVER delete cached model binaries"
    continue
  fi
  [[ "$rc" == 0 ]] || fail "ONE_WINDOW_OR_RESEARCH_CONFIG_FAILURE_RC=$rc"
  # Fail-closed complete/remaining enumeration.
  complete=0
  for w in 30 60 90 180; do
    f="$OUT/w$w/run-state.txt"
    if [[ -f "$f" ]] && grep -q '^EXIT_CODE=0$' "$f"; then
      complete=$((complete+1))
    fi
  done
  stamp "Validated-run-markers $complete/4 windows"
  if [[ "$complete" == 4 ]]; then break; fi
done
for w in 30 60 90 180; do
  f="$OUT/w$w/run-state.txt"
  [[ -f "$f" ]] && grep -q '^EXIT_CODE=0$' "$f" || fail "HISTORICAL_WINDOW_INCOMPLETE_w$w"
done
stamp "ALL FOUR NATIVE HISTORICAL RUNS MARKED SUCCESS; now audit actual Freqtrade archives"

python3 "$SOURCE/scripts/m2r_jansep_native_rolling_audit.py" \
  --root "$OUT" \
  --output "$OUT/jansep-native-four-window-audit.json" \
  --completed-lookbacks 30 60 90 180 || fail "FULL_NATIVE_ARCHIVE_AUDIT_FAILED"
stamp "Stage1 native archive audit PASSED (do not imply original non-AI baseline was executed)"

# Stage 2: Metadata-only broader-universe discovery. This reads public index
# keys but does NOT assume 2026 as-of listing/tradability or live spreads.
timeout -s TERM -k 10 2400 python3 \
  "$SOURCE/scripts/m2r_binance_historical_universe_inventory.py" \
  --out "$OUT/binance-vision-2026-archived-usdt-symbol-months.json" \
  --threads 8 || fail "HISTORIC_EXCHANGE_METADATA_INVENTORY_FAILED"
stamp "Stage2 broader-market archive metadata inventory saved; no as-of contract eligibility certified"

# Strictly as-of 8h 25-symbol liquidity/range DIAGNOSTIC.
[[ -z "$(docker ps -q)" ]] || fail "OTHER_DOCKER_JOB_STARTED"
mkdir -p "$OUT/selector"
timeout -s TERM -k 15 1200 docker run --rm \
  --name nbot-v6-jansep-historical-pair-diagnostic \
  --network none --memory=1g --cpus=1 \
  -v "$SOURCE:/research:ro" \
  -v "$ROOT/january-2026-public-history-stage:/history:ro" \
  -v "$OUT/selector:/results" \
  --entrypoint python freqtradeorg/freqtrade:stable_freqai \
  /research/scripts/m2r_asof_25market_selector_diagnostic.py \
  --data /history/futures \
  --config /research/user_data/config.json \
  --output /results/25-market-8h-asof-ranking.json \
  || fail "HISTORICAL_25_ONLY_RANKING_DIAGNOSTIC_FAILED"
stamp "Stage2 25-original-markets as-of 8h diagnostic saved. FULL REAL 25-of-broader-market economic trial remains BLOCKED until historically eligible alternate market data/quotes and native matched trades are validated."

stamp "FINITE_OFFLINE_RESEARCH_COORDINATOR_COMPLETE. No trading service, no model promotion, no paper/live, no futures order."
