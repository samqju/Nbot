"""G1e one-shot 50-market public WSS finality and independent REST audit.

Only a bounded diagnostic: no daemon, account keys, order calls, trading,
training labels, or edits to legacy V4/Execution data. All SQLite files
are temporary and removed on exit. Every market MUST pass every check.
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

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.public_market import (
    HISTORY, PublicMarketDataError, closed_event_from_server_time,
    public_get, select_universe,
)
from nbot.v5.ws_contract import UnsafeStream, stream_urls
from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.reconnect_policy import ReconnectPolicy, FeedRecoveryHold

MAX_SECONDS = 340
MAX_FRAMES_PER_ROUTE = 250_000


async def _listen(
    route: str, url: str, collector: ObservationContinuity,
    policy: ReconnectPolicy, deadline: float, reached: asyncio.Event,
    faults: list[str], target_ms: int,
) -> None:
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        faults.append("WEBSOCKETS_NOT_INSTALLED")
        reached.set()
        return

    frames = 0
    last_progress = time.monotonic()
    while time.monotonic() < deadline and not reached.is_set():
        connected = False
        try:
            async with connect(
                url, open_timeout=10, close_timeout=2, max_size=64_000,
                max_queue=16, ping_interval=20, ping_timeout=20,
            ) as stream:
                policy.on_connect(route)
                collector.connect(route)
                connected = True
                while time.monotonic() < deadline and not reached.is_set():
                    if frames >= MAX_FRAMES_PER_ROUTE:
                        faults.append(route + "_FRAME_BUDGET_EXHAUSTED")
                        reached.set()
                        break
                    if route == "market" and time.monotonic()-last_progress >= 30:
                        print("G1E_PROGRESS",
                              "final", collector.stats["wss_final_appended"],
                              "of", len(collector.symbols),
                              "quotes", collector.stats["sampled_quote_updates"],
                              "trades", collector.stats["trade_updates"],
                              flush=True)
                        last_progress = time.monotonic()
                    try:
                        frame = await asyncio.wait_for(
                            stream.recv(),
                            timeout=max(.05, min(1.0, deadline-time.monotonic())),
                        )
                    except asyncio.TimeoutError:
                        continue
                    frames += 1
                    received = int(time.time()*1000)
                    category = collector.consume(
                        route, frame, received_ms=received,
                    )
                    if category.startswith("HOLD_"):
                        faults.append(route + "_" + category)
                        reached.set()
                        break
                    if category == "APPENDED_WSS_FINAL":
                        if all(
                            target_ms in collector.final_opens[s]
                            for s in collector.symbols
                        ):
                            reached.set()
                            break
        except (UnsafeStream, EvidenceHold, ValueError) as exc:
            faults.append(route + "_INVALID_SOURCE_" + str(exc)[:90])
            reached.set()
        except Exception as exc:
            faults.append(route + "_CONNECTION_INTERRUPTED_" + type(exc).__name__)
            # One fault means this run can no longer prove uninterrupted WSS
            # history, but allow bounded transport retry as a diagnostic.
            if policy.routes[route].retry_attempts >= policy.MAX_ATTEMPTS:
                reached.set()
            else:
                collector.disconnect(route)
                policy.on_disconnect(route, "SOCKET_INTERRUPTED")
                try:
                    delay = policy.retry_delay(route)
                    await asyncio.sleep(min(delay, max(0, deadline-time.monotonic())))
                except FeedRecoveryHold:
                    reached.set()
        finally:
            if connected:
                collector.disconnect(route)
                policy.on_disconnect(route, "SOCKET_CLOSED")
    collector.stats[route + "_frames"] = frames


def _get_96(symbol: str, last_open: int, getter=public_get):
    return getter("/fapi/v1/klines", {
        "symbol": symbol, "interval": "5m",
        "startTime": str(last_open-(HISTORY-1)*INTERVAL_MS),
        "endTime": str(last_open+INTERVAL_MS-1), "limit": str(HISTORY),
    })


async def run_probe(
    *, top: int = 50, seconds: int = 338, getter=public_get,
) -> dict:
    if type(top) is not int or not 2 <= top <= 50:
        raise EvidenceHold("V5_G1E_LIMIT_INVALID")
    if type(seconds) is not int or not 90 <= seconds <= MAX_SECONDS:
        raise EvidenceHold("V5_G1E_DURATION_INVALID")
    event, server_time = closed_event_from_server_time(getter("/fapi/v1/time"))
    if abs(int(time.time()*1000)-server_time) > 90_000:
        raise EvidenceHold("V5_G1E_CLOCK_SKEW")
    selected = select_universe(
        getter("/fapi/v1/exchangeInfo"), getter("/fapi/v1/ticker/24hr"),
        limit=top,
    )
    urls = stream_urls(selected, quote_mode="depth5@500ms")
    target = event + INTERVAL_MS
    faults: list[str] = []
    initial = 0
    compare_count = 0
    invalid_compares: list[str] = []
    final_by_symbol: dict[str, bool] = {}
    restart_counts: dict[str, int] = {}
    quote_count = trade_count = 0
    frames = {}
    peak = 0.0
    policy = ReconnectPolicy()

    with TemporaryDirectory(prefix="nbot_v5_g1e_cohort_") as directory:
        dbpath = Path(directory) / "g1e_temp.db"
        with ObservationContinuity(selected, dbpath) as collector:
            for symbol in collector.symbols:
                try:
                    rows = _get_96(symbol, event, getter)
                    label, written = collector.restore_rest(
                        symbol, rows, event_open_ms=event,
                        observed_ms=int(time.time()*1000),
                    )
                    if label != "BOOTSTRAPPED" or written != HISTORY:
                        raise EvidenceHold("V5_G1E_BOOTSTRAP_WRONG_LENGTH")
                    initial += 1
                except (PublicMarketDataError, EvidenceHold) as exc:
                    faults.append(symbol + "_REST_BOOTSTRAP_" + str(exc)[:80])
                    break
            if initial == len(collector.symbols) and not faults:
                print("G1E_INITIAL_96_BAR_COHORT",
                      initial, "target_ms", target, flush=True)
                if int(time.time()*1000) >= target + INTERVAL_MS:
                    faults.append("BOOTSTRAP_EVENT_WAS_ALREADY_MISSED")
                else:
                    finish = asyncio.Event()
                    deadline = time.monotonic()+seconds
                    await asyncio.gather(
                        _listen("market", urls["market"], collector, policy,
                                deadline, finish, faults, target),
                        _listen("public", urls["public"], collector, policy,
                                deadline, finish, faults, target),
                    )
            final_by_symbol = {
                s: target in collector.final_opens[s]
                for s in collector.symbols
            }
            quotes = collector.store.coins
            quote_count = sum(c.last_quote is not None for c in quotes.values())
            trade_count = sum(c.last_trade is not None for c in quotes.values())
            frames = {
                "market": collector.stats["market_frames"],
                "public": collector.stats["public_frames"],
                "total_validated_trades": collector.stats["trade_updates"],
                "total_sampled_quotes": collector.stats["sampled_quote_updates"],
                "wss_finals": collector.stats["wss_final_appended"],
            }
            if all(final_by_symbol.values()) and not faults:
                print("G1E_FINALS_COMPLETE", len(final_by_symbol),
                      "checking independent REST proof", flush=True)
                for symbol in collector.symbols:
                    try:
                        rows = _get_96(symbol, target, getter)
                        status, added = collector.ledger.synchronize_asof_rest(
                            symbol, rows, event_open_ms=target,
                            observed_ms=int(time.time()*1000),
                        )
                        if status != "MATCHED" or added:
                            raise EvidenceHold("V5_G1E_SOURCE_PROOF_NOT_EXACT")
                        compare_count += 1
                    except (EvidenceHold, PublicMarketDataError) as exc:
                        invalid_compares.append(symbol + "_" + str(exc)[:80])
            # Persisted source truth tested only after connection closes.
        with CandleEvidenceLedger(dbpath) as verified:
            for symbol in selected:
                record = verified.inspect(symbol)
                restart_counts[symbol] = record["closed_bar_count"]
                if record["open_candle_gates"]:
                    faults.append(symbol + "_OPEN_LEDGER_GATES")
        peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 2)
    final_count = sum(final_by_symbol.values())
    restarted_count = sum(n >= 97 for n in restart_counts.values())
    # A socket generation can transport valid data while research remains
    # unqualified: policy always reports research_ready=False.
    passed = (
        initial == len(selected)
        and final_count == len(selected)
        and compare_count == len(selected)
        and restarted_count == len(selected)
        and not faults and not invalid_compares
    )
    return {
        "result": "PASS" if passed else "HOLD",
        "mode": "50_MARKET_REAL_WSS_FINAL_AND_REST_COMPARE_ONLY",
        "selected_symbol_count": len(selected),
        "symbol_list": list(selected),
        "rest_bootstrap_96_count": initial,
        "wss_final_symbol_count": final_count,
        "final_missing_symbols": sorted(s for s,v in final_by_symbol.items() if not v),
        "cross_source_rest_match_count": compare_count,
        "cross_source_mismatch": invalid_compares,
        "sqlite_reopened_97_count": restarted_count,
        "route_frames": frames,
        "sampled_last_quotes_at_shutdown": quote_count,
        "sampled_last_trades_at_shutdown": trade_count,
        "peak_rss_mib_approx": peak,
        "transport_policy": policy.status(),
        "temporary_database_removed": not dbpath.exists(),
        "faults": faults,
        "research_ready": False,
        "training_labels_created": 0,
        "persistent_service_started": False,
        "order_authority": "NONE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded actual 50-symbol WSS 5m final→REST proof; no orders"
    )
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--seconds", type=int, default=338)
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(run_probe(top=args.top, seconds=args.seconds))
    except (EvidenceHold, PublicMarketDataError, UnsafeStream,
            OSError, ValueError) as exc:
        print("G1E_HOLD", type(exc).__name__, str(exc), flush=True)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2), flush=True)
    return 0 if report["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
