#!/usr/bin/env bash
# READ-ONLY VPS checklist. Does not install packages, start a bot, or send orders.
set -u

echo "NBOT V6 / VPS preflight (read-only)"
fail=0
warn=0

if [[ -r /etc/os-release ]]; then
  source /etc/os-release
  echo "System: ${PRETTY_NAME:-unknown} / $(uname -m)"
  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "WARN: setup guide is tested/designed for Ubuntu."
    warn=$((warn + 1))
  fi
fi

echo "CPU cores: $(nproc)"
memory_kib=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
memory_mb=$((memory_kib / 1024))
echo "RAM: ${memory_mb} MiB"
if (( memory_mb < 1900 )); then
  echo "WARN: under 2 GB: only tiny FreqAI experiments have been demonstrated."
  warn=$((warn + 1))
elif (( memory_mb < 3900 )); then
  echo "WARN: full 30-day/25-pair capacity is unverified at this RAM."
  warn=$((warn + 1))
fi
disk_mb=$(df -Pm . | awk 'NR==2 {print $4}')
echo "Free disk at current folder: ${disk_mb} MiB"
if (( disk_mb < 20000 )); then
  echo "WARN: use a larger disk (30–50 GB recommended)."
  warn=$((warn + 1))
fi

for dep in git curl python3; do
  if command -v "$dep" >/dev/null 2>&1; then
    echo "OK: $dep"
  else
    echo "MISSING: $dep"
    fail=$((fail + 1))
  fi
done
if command -v docker >/dev/null 2>&1; then
  echo "OK: $(docker --version)"
  if docker compose version >/dev/null 2>&1; then
    echo "OK: $(docker compose version)"
  else
    echo "MISSING: Docker Compose plugin"
    fail=$((fail + 1))
  fi
else
  echo "MISSING: Docker Engine (see VPS_SETUP.md)"
  fail=$((fail + 1))
fi

if command -v curl >/dev/null 2>&1; then
  for entry in \
    "spot|https://api.binance.com/api/v3/exchangeInfo" \
    "futures|https://fapi.binance.com/fapi/v1/exchangeInfo"; do
    label="${entry%%|*}"
    url="${entry#*|}"
    status=$(curl --silent --show-error --location \
      --connect-timeout 6 --max-time 15 \
      --output /dev/null --write-out '%{http_code}' "$url") || status="000"
    if [[ "$status" == "200" ]]; then
      echo "OK: Binance $label public API (HTTP $status)"
    else
      echo "BLOCKED: Binance $label public API (HTTP $status)"
      fail=$((fail + 1))
    fi
  done
fi

echo "Warnings: $warn | Failed checks: $fail"
if (( fail > 0 )); then
  echo "DO NOT START. Fix the failed checks using VPS_SETUP.md."
  exit 1
fi
echo "BASIC HOST PRECHECK PASSED. This does NOT prove model, data, or trading readiness."
