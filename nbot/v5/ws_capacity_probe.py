"""Manual high-rate WSS capacity probe for V5; no trading, disk or daemon.

Keeps only the newest bid/ask quote and trade cursor per coin and no more
than 96 CLOSED candles per symbol. This probe deliberately does not qualify
source health, backfill missing trades or create model-training evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import resource
import time
from typing import Sequence

from nbot.v5.stream_buffer import BoundedObservationBuffer
from nbot.v5.ws_contract import UnsafeStream, stream_urls

MAX_SAMPLES_PER_ROUTE = 50_000


async def _sample(route: str, url: str, store: BoundedObservationBuffer,
                  *, seconds: int) -> dict:
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError("V5_WEBSOCKETS_DEPENDENCY_MISSING") from exc
    frames = 0
    rejected = {}
    reached_limit = False
    beginning = time.monotonic()
    try:
        async with connect(
            url, open_timeout=8, close_timeout=2, max_size=64_000,
            max_queue=16, ping_interval=20, ping_timeout=20,
        ) as socket:
            store.connect(route)
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if frames >= MAX_SAMPLES_PER_ROUTE:
                    reached_limit = True
                    break
                timeout = min(1.0, end - time.monotonic())
                if timeout <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(socket.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    continue
                frames += 1
                now_ms = int(time.time() * 1000)
                try:
                    store.consume(route, msg, received_ms=now_ms)
                except UnsafeStream as exc:
                    name = str(exc)
                    rejected[name] = rejected.get(name, 0) + 1
    except Exception as exc:
        return {"route": route, "connected": False,
                "error": type(exc).__name__ + ": " + str(exc)[:160],
                "frames": frames, "rejected": rejected,
                "frame_cap_hit": reached_limit,
                "duration_seconds": round(time.monotonic() - beginning, 2)}
    return {"route": route, "connected": True, "frames": frames,
            "rejected": rejected, "frame_cap_hit": reached_limit,
            "duration_seconds": round(time.monotonic() - beginning, 2)}


async def run_probe(*, symbols: Sequence[str], seconds: int,
                    quote_mode: str = "bookTicker") -> dict:
    if not 8 <= seconds <= 20:
        raise ValueError("V5_CAPACITY_DURATION_INVALID")
    store = BoundedObservationBuffer(symbols, quote_mode=quote_mode)
    urls = stream_urls(symbols, quote_mode=quote_mode)
    started = time.monotonic()
    market, public = await asyncio.gather(
        _sample("market", urls["market"], store, seconds=seconds),
        _sample("public", urls["public"], store, seconds=seconds),
    )
    summary = store.describe()
    problems = []
    for section in (market, public):
        if not section["connected"]:
            problems.append(section["route"].upper() + "_DISCONNECTED")
        if section["frame_cap_hit"]:
            problems.append(section["route"].upper() + "_FRAME_CAP")
        if section["rejected"]:
            problems.append(section["route"].upper() + "_INVALID_FRAMES")
    if not summary["event_counts"].get("trade", 0):
        problems.append("NO_LIVE_TRADES_SEEN")
    if not summary["event_counts"].get("quote", 0):
        problems.append("NO_LIVE_QUOTES_SEEN")
    if store.health.trade_gaps:
        problems.append("TRADE_ID_GAPS_DETECTED")
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "result": "PASS" if not problems else "HOLD",
        "mode": "WSS_BOUNDED_CAPACITY_PROBE_ONLY",
        "eligibility_count": len(symbols),
        "total_symbols_including_btc": len(store.all_symbols),
        "seconds_requested": seconds,
        "quote_mode": quote_mode,
        "total_elapsed_seconds": round(time.monotonic() - started, 2),
        "routes": [market, public],
        "buffer": summary,
        "trade_gap_symbols": sorted(store.health.trade_gaps),
        "peak_process_rss_mib_approx": round(rss_kb / 1024, 2),
        "reasons": problems,
        "order_authority": "NONE",
        "database_written": False,
        "persistent_service_started": False,
        "research_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded read-only V5 WSS capacity probe")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT",
                        help="Comma-separated eligible futures symbols (1 to 50)")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--quote-mode", default="depth5@500ms",
                        choices=("bookTicker", "depth5@500ms"),
                        help="Public book snapshot speed: default top-five at 500ms")
    args = parser.parse_args(argv)
    symbols = tuple(x.strip() for x in args.symbols.split(","))
    try:
        result = asyncio.run(run_probe(symbols=symbols, seconds=args.seconds,
                                       quote_mode=args.quote_mode))
    except (UnsafeStream, ValueError, RuntimeError) as exc:
        print("V5_WSS_CAPACITY_HOLD:", str(exc))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
