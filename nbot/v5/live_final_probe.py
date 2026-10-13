"""Manual bounded real-WSS 5-minute FINAL close to temporary SQLite audit.

Use ONLY an isolated V5 sandbox. This is a single diagnostic run, never a
collector daemon, no Binance credentials, no trading, no model training.
A PASS requires at least one actual kline.x=true event per selected symbol
whose open_ms follows an independently REST-verified 96-candle snapshot.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import resource
from tempfile import TemporaryDirectory
import time
from typing import Sequence

from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import (
    PublicMarketDataError, closed_event_from_server_time, public_get,
    select_universe,
)
from nbot.v5.ws_contract import UnsafeStream, stream_urls

MAX_SECONDS = 340
MAX_FRAMES = 60_000


async def _listen(route, socket_url, session, deadline, finished, bad, target):
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        bad.append("WEBSOCKETS_NOT_INSTALLED")
        return
    frames = 0
    try:
        async with connect(
            socket_url, open_timeout=10, close_timeout=2,
            ping_interval=20, ping_timeout=20,
            max_size=64_000, max_queue=16,
        ) as ws:
            session.connect(route)
            last_heartbeat = time.monotonic()
            while time.monotonic() < deadline and not finished.is_set():
                if frames >= MAX_FRAMES:
                    bad.append(route + "_FRAME_CAP")
                    break
                now = time.monotonic()
                try:
                    frame = await asyncio.wait_for(
                        ws.recv(), timeout=max(.05, min(1., deadline - now))
                    )
                except asyncio.TimeoutError:
                    if route == "market" and now - last_heartbeat >= 30:
                        counts = session.stats
                        print("G1D_HEARTBEAT",
                              "wss_final", counts["wss_final_appended"],
                              "quote", counts["sampled_quote_updates"],
                              "trade", counts["trade_updates"], flush=True)
                        last_heartbeat = now
                    continue
                frames += 1
                now_ms = int(time.time() * 1000)
                try:
                    result = session.consume(
                        route, frame, received_ms=now_ms,
                    )
                except (EvidenceHold, UnsafeStream, ValueError) as exc:
                    bad.append(route + "_" + str(exc))
                    break
                if result == "APPENDED_WSS_FINAL":
                    print("G1D_REAL_FINAL", session.stats["wss_final_appended"],
                          "at_ms", now_ms, flush=True)
                    if all(
                        any(x >= target for x in session.final_opens[s])
                        for s in session.symbols
                    ):
                        finished.set()
            session.stats[route + "_frames"] = frames
    except Exception as exc:
        bad.append(route + "_" + type(exc).__name__ + "_" + str(exc)[:80])
    finally:
        # A disconnected session NEVER automatically recertifies either feed.
        session.disconnect(route)


async def run_probe(*, top: int = 2, seconds: int = 335,
                    getter=public_get) -> dict:
    if type(top) is not int or not 1 <= top <= 3:
        raise EvidenceHold("V5_G1D_PROBE_TOP_OUT_OF_RANGE")
    if type(seconds) is not int or not 45 <= seconds <= MAX_SECONDS:
        raise EvidenceHold("V5_G1D_PROBE_DURATION_OUT_OF_RANGE")
    event_open, server_ms = closed_event_from_server_time(
        getter("/fapi/v1/time")
    )
    if abs(int(time.time() * 1000) - server_ms) > 90_000:
        raise EvidenceHold("V5_G1D_PROBE_CLOCK_SKEW")
    exchange = getter("/fapi/v1/exchangeInfo")
    ticker = getter("/fapi/v1/ticker/24hr")
    eligible = select_universe(exchange, ticker, limit=top)
    target = event_open + INTERVAL_MS
    urls = stream_urls(eligible, quote_mode="depth5@500ms")
    issues = []
    results = {}
    with TemporaryDirectory(prefix="nbot_v5_g1d_final_") as folder:
        path = Path(folder) / "g1d_only.db"
        with ObservationContinuity(eligible, path) as session:
            for symbol in session.symbols:
                try:
                    result = session.retrieve_rest(
                        symbol, event_open_ms=event_open,
                        observed_ms=int(time.time() * 1000), getter=getter,
                    )
                    if result[1] != 96:
                        raise EvidenceHold("V5_G1D_BOOTSTRAP_NOT_96")
                except (EvidenceHold, PublicMarketDataError) as exc:
                    issues.append("BOOTSTRAP_" + symbol + "_" + str(exc))
                    break
            if not issues:
                print("G1D_REST_SEED", len(session.symbols),
                      "x96 closed bars; waiting for live WSS FINAL",
                      "target_ms", target, flush=True)
                finished = asyncio.Event()
                deadline = time.monotonic() + seconds
                await asyncio.gather(
                    _listen("market", urls["market"], session,
                            deadline, finished, issues, target),
                    _listen("public", urls["public"], session,
                            deadline, finished, issues, target),
                )
            # After disconnect all source-health/certification should HOLD.
            results = session.snapshot(
                event_open_ms=target,
                now_ms=int(time.time() * 1000),
            )
        # Close first and then reopen actual SQLite file for durable proof.
        persisted = {}
        with CandleEvidenceLedger(path) as check:
            for symbol in eligible:
                report = check.inspect(symbol)
                persisted[symbol] = {
                    "final_event_open_ms": report["last_event_open_ms"],
                    "closed_candles_after_reopen": report["closed_bar_count"],
                    "candle_gates": report["open_candle_gates"],
                    "research_ready": report["research_ready"],
                }
        certified = all(
            row["closed_candles_after_reopen"] >= 97
            and row["final_event_open_ms"] >= target
            and not row["candle_gates"]
            for row in persisted.values()
        )
    result = "PASS" if certified and not issues else "HOLD"
    return {
        "result": result, "mode": "LIVE_FINAL_WSS_SQLITE_REOPEN_ONLY",
        "observed_symbols": eligible,
        "initial_closed_event_open_ms": event_open,
        "target_final_event_open_ms": target,
        "source_issues": issues,
        "final_candles_confirmed_for_every_coin": certified,
        "reopened_ledger": persisted,
        "observation": results,
        "peak_rss_mib_approx": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        "temporary_database_removed": not path.exists(),
        "persistent_service_started": False,
        "research_ready": False, "training_labels_created": 0,
        "order_authority": "NONE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1d read-only final WSS 5m persistence proof")
    parser.add_argument("--top", type=int, default=2)
    parser.add_argument("--seconds", type=int, default=335)
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(run_probe(top=args.top, seconds=args.seconds))
    except (EvidenceHold, PublicMarketDataError, UnsafeStream, OSError,
            ValueError) as exc:
        print("G1D_PROBE_HOLD", type(exc).__name__, str(exc), flush=True)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2), flush=True)
    return 0 if report["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
