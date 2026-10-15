"""G2 synthetic 100-symbol capacity benchmark. NO network/accounts/orders.

Run from repository root: PYTHONDONTWRITEBYTECODE=1 python3 -B
    benchmarks/g2_observation_benchmark.py

Prints one JSON report; fails the process if declared small-VPS budgets fail.
These are offline closed-candle metadata timings, NOT real Binance ingest or
full original high-frequency market source custody.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_v5_1_g2 import market_fixture, bar, history, END_OPEN, END_DECISION
from nbot_v5_1.universe import select_universe
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.observation_store import CompactObservationStore
from nbot_v5_1.public_market import PublicUsdMClient

MAX_P99_MS = 1000.0
MAX_RSS_KIB = 240 * 1024
MAX_DISK_BYTES = 32 * 1024 * 1024
EVENT_COUNT = 120
SYMBOL_COUNT = 100


def percentile(nums: list[float], pct: float) -> float:
    if not nums:
        raise ValueError("no values")
    values = sorted(nums)
    return values[min(len(values) - 1, int((len(values) - 1) * pct))]


def benchmark() -> dict:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    ex, tick, book, hist, health = market_fixture(145)
    manifest = select_universe(ex, tick, book, hist, health,
                              source_received_at_ms=END_OPEN,
                              selected_at_ms=END_OPEN + 1000)
    if len(manifest.symbols) != SYMBOL_COUNT:
        raise RuntimeError("G2_MOCK_DENOMINATOR_FAILED")
    live_book = ObservationBook(manifest)

    for sym in manifest.symbols:
        if not live_book.bootstrap(sym, history(sym), as_of_ms=END_DECISION):
            raise RuntimeError("G2_MOCK_BOOTSTRAP_FAILED")
    if live_book.buffered_candles != 9600:
        raise RuntimeError("G2_MOCK_RING_CAP_FAILED")

    mock_calls: list[str] = []
    def fake_public(url: str) -> bytes:
        mock_calls.append(url)
        return b"[]"
    api = PublicUsdMClient(allow_public_network=True, transport=fake_public,
                           weight_budget=600, now=lambda: 1_000_000)
    api.exchange_info()
    api.tickers_24hr()
    api.book_tickers()
    for sym in manifest.symbols:
        api.closed_klines(sym, limit=100)
    if api.weight_used != 246 or len(mock_calls) != 103:
        raise RuntimeError("G2_RATE_BUDGET_MISMATCH")

    latencies: list[float] = []
    invalid_coins = set(manifest.symbols[1:11])
    with tempfile.TemporaryDirectory(prefix="nbot-g2-benchmark-") as d:
        store = CompactObservationStore(Path(d), max_bytes=64 * 1024 * 1024)
        store.put_manifest(manifest)
        for iteration in range(EVENT_COUNT):
            clock = FiveMinuteEvent(END_OPEN + iteration * INTERVAL_MS,
                    END_DECISION + iteration * INTERVAL_MS)
            t0 = time.perf_counter()
            if iteration > 0:
                for sym in manifest.symbols:
                    if iteration == 40 and sym in invalid_coins:
                        live_book.mark_gap(sym, reason="DISCONNECTED")
                    next_bar = bar(sym, clock.event_open_ms, received=clock.decision_at_ms)
                    live_book.ingest(next_bar, decision_at_ms=clock.decision_at_ms)
            shot = live_book.snapshot(clock)
            if len(shot.rows) != SYMBOL_COUNT:
                raise RuntimeError("G2_DENOMINATOR_LOST")
            if iteration < 40 and (shot.healthy_count != SYMBOL_COUNT or shot.hold_count):
                raise RuntimeError("G2_VALID_EVENT_FAIL")
            if iteration >= 40 and (shot.healthy_count != SYMBOL_COUNT - 10 or shot.hold_count != 10):
                raise RuntimeError("G2_GAP_NOT_HELD")
            store.put_snapshot(shot)
            latencies.append(1000 * (time.perf_counter() - t0))
        replayed = store.replay()
        if len(replayed) != EVENT_COUNT + 1:
            raise RuntimeError("G2_REPLAY_INCOMPLETE")
        disk = sum(p.stat().st_size for p in Path(d).iterdir())
        if live_book.buffered_candles > SYMBOL_COUNT * 96:
            raise RuntimeError("G2_MEMORY_RING_UNBOUNDED")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "schema": "NBOT_V5_1_G2_BENCHMARK_V1",
        "synthetic_only": True,
        "events": EVENT_COUNT, "symbols": SYMBOL_COUNT, "history_per_symbol": 96,
        "denominator_per_event": SYMBOL_COUNT,
        "simulated_gap_symbols": len(invalid_coins),
        "event_latency_p50_ms": round(percentile(latencies, .50), 3),
        "event_latency_p95_ms": round(percentile(latencies, .95), 3),
        "event_latency_p99_ms": round(percentile(latencies, .99), 3),
        "event_latency_max_ms": round(max(latencies), 3),
        "peak_rss_kib": rss,
        "process_cpu_seconds": round(time.process_time() - start_cpu, 4),
        "wall_seconds": round(time.perf_counter() - start_wall, 4),
        "compact_disk_bytes": disk,
        "fake_http_weight": api.weight_used,
        "fake_http_calls": len(mock_calls),
        "temporary_data_removed": True,
        "limits": {"p99_ms": MAX_P99_MS, "rss_kib": MAX_RSS_KIB,
                   "disk_bytes": MAX_DISK_BYTES},
    }
    report["passed"] = (report["event_latency_p99_ms"] < MAX_P99_MS
                        and rss < MAX_RSS_KIB and disk < MAX_DISK_BYTES)
    return report


if __name__ == "__main__":
    result = benchmark()
    print(json.dumps(result, sort_keys=True), flush=True)
    sys.exit(0 if result["passed"] else 2)
