"""Optional ONE-SHOT read-only public USD-M G2 source probe.

Use: python3 -B scripts/g2_readonly_probe.py --public-network
Default without flag: NO NETWORK. No service, secrets, private/user/order API,
execution modes or persistent writes. Printed hashes are diagnostic only,
NOT independent source custody or authentic high-frequency witnesses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.public_market import PublicUsdMClient, PublicMarketHold, select_from_public_responses
from nbot_v5_1.universe import select_universe, UniverseHold
from nbot_v5_1.observation import ObservationBook, rest_closed_bar
from nbot_v5_1.source_archive import PublicSourceArchive, PublicArchiveHold


def probe(*, enabled: bool, max_history_requests: int = 140,
          archive: PublicSourceArchive | None = None) -> dict:
    if type(enabled) is not bool or not enabled:
        raise PublicMarketHold("G2_EXPLICIT_PUBLIC_NETWORK_PERMISSION_REQUIRED")
    if type(max_history_requests) is not int or not 100 <= max_history_requests <= 160:
        raise ValueError("G2_PROBE_LIMIT_INVALID")
    client = PublicUsdMClient(allow_public_network=True, weight_budget=450)
    ex = client.exchange_info()
    tick = client.tickers_24hr()
    book = client.book_tickers()
    if archive is not None:
        for receipt in (ex, tick, book):
            archive.append(receipt)
    if (type(ex.body) is not dict or type(tick.body) is not list
            or type(book.body) is not list):
        raise UniverseHold("G2_PROBE_API_SCHEMA_CHANGED")
    if max(ex.received_at_ms,tick.received_at_ms,book.received_at_ms) - min(
            ex.received_at_ms,tick.received_at_ms,book.received_at_ms) > 15_000:
        raise UniverseHold("G2_PROBE_SOURCE_CLOCK_MISMATCH")
    # This is a DISCOVERY CANDIDATE order, not an accepted manifest: no symbol
    # can be marked qualified until an actual verified >=96 closed-bar response.
    candidates = set()
    for raw in ex.body.get("symbols", []):
        if (type(raw) is dict and raw.get("contractType") == "PERPETUAL"
                and raw.get("status") == "TRADING"
                and raw.get("quoteAsset") == "USDT"
                and raw.get("marginAsset") == "USDT"):
            candidates.add(raw.get("symbol"))
    provisional_history = {s: 100 for s in candidates}
    provisional_health = {s: True for s in candidates}
    provisional = select_universe(ex.body, tick.body, book.body,
            provisional_history, provisional_health,
            source_received_at_ms=max(ex.received_at_ms,tick.received_at_ms,book.received_at_ms),
            selected_at_ms=int(time.time()*1000))
    # Prefer nominated group symbols, then remaining high-turnover eligible.
    ranked = sorted((r for r in tick.body if r.get("symbol") in candidates),
                    key=lambda r: (-float(r.get("quoteVolume","0")),r["symbol"]))
    order = list(dict.fromkeys(list(provisional.symbols)+[r["symbol"] for r in ranked]))
    verified_bars = {}
    history_count = {}
    history_health = {}
    history_receipts = []
    failed = {}
    for symbol in order[:max_history_requests]:
        try:
            response = client.closed_klines(symbol, limit=100)
            if archive is not None:
                archive.append(response)
            if type(response.body) is not list:
                raise ValueError("KLINES_NOT_ARRAY")
            # The *last* REST kline may still be forming. Never accept it
            # until close-time + 1 <= known-at response-receive time.
            done = [r for r in response.body
                    if type(r) is list and len(r) >= 7
                    and type(r[6]) is int and r[6]+1 <= response.received_at_ms]
            if len(done) < 96:
                raise ValueError("HISTORY_SHORT")
            parsed = [rest_closed_bar(symbol,r,known_at_ms=response.received_at_ms,
                                     epoch=0,route="public_rest") for r in done[-96:]]
            if any(parsed[i].open_ms != parsed[i-1].open_ms+INTERVAL_MS
                   for i in range(1,len(parsed))):
                raise ValueError("HISTORY_GAP")
            verified_bars[symbol] = parsed
            history_count[symbol] = len(parsed)
            history_health[symbol] = True
            history_receipts.append((symbol,response.body_sha256,response.received_at_ms))
        except (PublicMarketHold,ValueError,TypeError,IndexError) as exc:
            failed[symbol] = type(exc).__name__ + ":" + str(exc)[:60]
        if len(history_count) >= 100:
            break
    # Make no positive claim when source ages out during the 100+ live calls.
    now_ms = int(time.time()*1000)
    source_clock = max(ex.received_at_ms,tick.received_at_ms,book.received_at_ms)
    freshness_ms = now_ms - source_clock
    if freshness_ms > 60_000:
        raise UniverseHold(f"G2_PROBE_UNIVERSE_SOURCE_STALE_AFTER_HISTORY:{freshness_ms}")
    selected = select_from_public_responses(ex,tick,book,history_count,history_health,
                    selected_at_ms=now_ms)
    book_state = ObservationBook(selected)
    for symbol in selected.symbols:
        if symbol not in verified_bars or not book_state.bootstrap(
                symbol,verified_bars[symbol],as_of_ms=now_ms):
            book_state.mark_gap(symbol,reason="LIVE_BOOTSTRAP_HOLD")
    # Current last completed five-minute event; never retroactively use a
    # later candle or availability at a decision that occurred in the past.
    open_ms = (now_ms//INTERVAL_MS-1)*INTERVAL_MS
    event = book_state.snapshot(FiveMinuteEvent(open_ms,now_ms))
    root = hashlib.sha256(json.dumps(sorted(history_receipts),
                         separators=(",",":")).encode()).hexdigest()
    archived = archive.replay() if archive is not None else ()
    archived_bytes = sum((archive.root/r.name).stat().st_size for r in archived) if archive is not None else 0
    return {
        "schema":"NBOT_V5_1_G2_PUBLIC_SMOKE_V1",
        "public_only":True,"source_grade":"PUBLIC_REST_METADATA_NOT_ORIGINAL",
        "received_at_ms":source_clock, "selected_at_ms":now_ms,
        "public_source_age_ms":freshness_ms,
        "public_exchange_rows":len(ex.body["symbols"]),
        "public_24h_rows":len(tick.body),
        "public_book_rows":len(book.body),
        "api_digests":{"exchange":ex.body_sha256,"ticker":tick.body_sha256,
                       "book":book.body_sha256,"history_root":root},
        "selected_symbols":len(selected.symbols),
        "qualified_available":selected.qualified_count,
        "btc_included":"BTCUSDT" in selected.symbols,
        "history_verified_symbols":len(history_count),
        "history_failed":failed,
        "event_closed_metadata_count":event.healthy_count,
        "event_hold_count":event.hold_count,
        "asof_event_open_ms":open_ms,
        "manifest_sha":selected.selection_digest,
        "event_sha":event.snapshot_id,
        "request_weight":client.weight_used,
        "archive_replay_receipts":len(archived),
        "archive_compressed_bytes":archived_bytes,
        "archive_source_root":hashlib.sha256(json.dumps(sorted(
             (r.response.kind,r.response.received_at_ms,r.response.body_sha256)
             for r in archived),separators=(",",":")).encode()).hexdigest() if archived else None,
        "archive_is_unauthenticated_public_rest":True,
        "no_orders":True,
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--public-network",action="store_true",
                    help="Explicit one-time GET-only public Binance USD-M check")
    ap.add_argument("--max-history-requests",type=int,default=140)
    args=ap.parse_args()
    try:
        # All original public bytes are captured, fsynced, then hash-checked
        # by replay; the test archive is automatically deleted afterwards.
        # Do not confuse this temporary probe with operational source storage.
        with tempfile.TemporaryDirectory(prefix="nbot-g2-public-replay-") as d:
            archive=PublicSourceArchive(Path(d),budget_bytes=64*1024*1024)
            result=probe(enabled=args.public_network,
                         max_history_requests=args.max_history_requests,
                         archive=archive)
            print(json.dumps(result,sort_keys=True),flush=True)
        print("G2_PUBLIC_ARCHIVE_REPLAYED_AND_TEMP_CLEANED",flush=True)
    except (PublicMarketHold,PublicArchiveHold,UniverseHold,ValueError) as exc:
        print(json.dumps({"status":"G2_PUBLIC_PROBE_HOLD",
              "reason":str(exc),"no_orders":True}),flush=True)
        sys.exit(2)
