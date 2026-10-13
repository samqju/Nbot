"""Bounded manual V5 WSS smoke test; does not persist or trade.

This is a deliberately short-lived public-only connectivity diagnostic.
It is NOT a resilient live observation service. Install existing pinned
websockets dependency separately if unavailable; never auto-install packages.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import time

from nbot.v5.ws_contract import UnsafeStream, decode_frame, stream_urls


async def _sample(route: str, url: str, symbols: tuple[str, ...],
                  *, seconds: int) -> dict:
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError("V5_WEBSOCKETS_DEPENDENCY_MISSING") from exc

    kinds = Counter()
    rejected = Counter()
    frames = 0
    started = time.monotonic()
    try:
        async with connect(
            url, open_timeout=8, close_timeout=2, max_size=64_000,
            max_queue=16, ping_interval=20, ping_timeout=20,
        ) as socket:
            until = started + seconds
            while time.monotonic() < until and frames < 2_000:
                remaining = until - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    message = await asyncio.wait_for(
                        socket.recv(), timeout=min(2.0, remaining)
                    )
                except asyncio.TimeoutError:
                    continue
                frames += 1
                try:
                    item = decode_frame(
                        route, message, received_ms=int(time.time() * 1000),
                        subscribed_symbols=symbols,
                    )
                    kinds[item["kind"]] += 1
                    if item["kind"] == "kline_5m" and item["closed"]:
                        kinds["closed_5m"] += 1
                except UnsafeStream as exc:
                    rejected[str(exc)] += 1
    except Exception as exc:
        return {"route": route, "connected": False,
                "error": type(exc).__name__ + ": " + str(exc)[:140],
                "received_frames": frames, "accepted_events": dict(kinds),
                "rejected_frames": dict(rejected)}
    return {"route": route, "connected": True, "received_frames": frames,
            "accepted_events": dict(kinds), "rejected_frames": dict(rejected),
            "duration_seconds": round(time.monotonic() - started, 2)}


async def run_probe(*, symbols: tuple[str, ...], seconds: int) -> dict:
    if not 8 <= seconds <= 30 or not 1 <= len(symbols) <= 3:
        raise ValueError("V5_WSS_PROBE_BOUNDS_INVALID")
    urls = stream_urls(symbols)
    market, public = await asyncio.gather(
        _sample("market", urls["market"], symbols, seconds=seconds),
        _sample("public", urls["public"], symbols, seconds=seconds),
    )
    success = (
        market["connected"] and public["connected"]
        and market["accepted_events"].get("aggTrade", 0) > 0
        and public["accepted_events"].get("bookTicker", 0) > 0
        and not market["rejected_frames"]
        and not public["rejected_frames"]
    )
    return {"result": "PASS" if success else "HOLD",
            "mode": "PUBLIC_WSS_DIAGNOSTIC_NO_ORDERS",
            "symbols": symbols, "requested_duration_seconds": seconds,
            "market_route": "/market/stream",
            "public_route": "/public/stream",
            "results": [market, public],
            "paper_trades": 0, "order_authority": "NONE",
            "service_started": False, "database_written": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded, read-only Binance WSS market diagnostic")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT",
                        help="Up to three public symbols (default BTCUSDT,ETHUSDT)")
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()
    symbols = tuple(s.strip() for s in args.symbols.split(","))
    try:
        result = asyncio.run(run_probe(symbols=symbols, seconds=args.seconds))
    except (RuntimeError, ValueError, UnsafeStream) as exc:
        print("V5_WSS_PROBE_HOLD:", str(exc))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
