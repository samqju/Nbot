#!/usr/bin/env bash
# V6-ONLY, researcher explicit one-shot offline historical native backtest.
# Status by default. --execute performs exactly ONE window, never a daemon.
set -euo pipefail
mode="$1"
vps="/root/nbot-v6-m1-20261016"
cd "$vps/source"
test "$(git branch --show-current)" = "prototype/v6-freqtrade-freqai-20261016"
test -z "$(git status --porcelain=v1)"
if [[ "$mode" != "--status" && "$mode" != "--execute" ]]; then exit 2; fi
for w in 30 60 90 180; do
  case "$w" in
    30) from=20260215 ;;
    60) from=20260315 ;;
    90) from=20260415 ;;
    180) from=20260715 ;;
  esac
  out="$vps/jansep-20261017/w$w"
  state="$out/run-state.txt"
  name="nbot-v6-m2r-jansep2026-$w""d-20261017"
  if [[ -f "$state" ]] && grep -q '^EXIT_CODE=0$' "$state"; then
    test "$(find "$out/backtest_results" -name '*.zip' | wc -l)" -eq 1
    test "$(find "$out/models/$name" -name '*_model.joblib' | wc -l)" -ge 25
    echo "VERIFIED_COMPLETED_WINDOW=$w"
    continue
  fi
  if [[ -n "$(docker ps -q)" ]]; then echo "BUSY_ALREADY_RUNNING"; exit 0; fi
  if [[ -f "$state" ]] && ! grep -q '^EXIT_CODE=124$' "$state"; then
    echo "HALT_UNEXPECTED_PREVIOUS_RUN_FAILURE_$w"; exit 2
  fi
  echo "NEXT_OFFLINE_WINDOW=$w"
  if [[ "$mode" == "--status" ]]; then exit 0; fi
  conf="$vps/source/user_data/config.m2r-jansep2026-$w""day-offline.json"
  python3 - "$conf" "$w" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); w=int(sys.argv[2])
assert d["dry_run"] is True and d["nbot_m2r_research_only"] is True
assert d["nbot_m2r_event_funding_labels"] is True and d["nbot_m2r_purge_internal"] is True
assert d["nbot_live_mode"] is False and d["nbot_paper_research_mode"] is False
assert d["max_open_trades"] == 1 and d["force_entry_enable"] is False
assert d["exchange"] == {"key":"","secret":""}
assert d["api_server"]["enabled"] is False and d["telegram"]["enabled"] is False
assert d["freqai"]["train_period_days"] == w and d["freqai"]["backtest_period_days"] == 7
PY
  mkdir -p "$out"
  attempt=1
  while [[ -e "$out/attempt-$attempt.log" ]]; do attempt=$((attempt+1)); done
  if [[ -f "$state" ]]; then cp "$state" "$out/run-state-prior-$attempt.txt"; fi
  printf 'STARTED_UTC=%s\nWINDOW_DAYS=%s\nATTEMPT=%s\n' "$(date -u +%FT%TZ)" "$w" "$attempt" > "$state"
  set +e
  timeout -s TERM -k 60 18000 docker run --rm \
    --name "nbot-v6-jansep-w$w-offline" --network bridge --memory=6g --cpus=2 \
    -v "$vps/source:/research:ro" -v "$vps/january-2026-public-history-stage:/history:ro" \
    -v "$out:/results" --entrypoint freqtrade \
    freqtradeorg/freqtrade:stable_freqai backtesting \
    -c /research/user_data/config.json \
    -c "/research/user_data/config.m2r-jansep2026-$w""day-offline.json" \
    --userdir /results --datadir /history \
    --strategy NbotV6TradeOutcomeFundingResearch \
    --strategy-path /research/user_data/strategies \
    --freqaimodel NbotV6PurgedLightGBMRegressor \
    --freqaimodel-path /research/user_data/freqaimodels \
    --timerange "$from-20261001" --fee 0.0005 --cache none --export trades \
    > "$out/attempt-$attempt.log" 2>&1
  rc=$?
  set -e
  printf 'EXIT_CODE=%s\nSTOPPED_UTC=%s\n' "$rc" "$(date -u +%FT%TZ)" >> "$state"
  echo "ENDED_WINDOW=$w EXIT_CODE=$rc"
  exit "$rc"
done
echo ALL_FOUR_NATIVE_WINDOWS_DONE
