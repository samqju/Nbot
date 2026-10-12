"""V5 opt-in read-only adapter for canonical 5-minute Observation evidence.

This module makes NO network call and opens the existing collector SQLite
database only in immutable read-only mode. Exchange instrument rules must
be supplied as authenticated, point-in-time metadata by a later bridge.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Mapping

from .v5_selection import Bar, Instrument, Observation, FIVE_MINUTES_MS, LOOKBACK


def read_completed_event(
    database_path: str | Path, *, event_open_ms: int, now_ms: int,
    instruments: Mapping[str, Instrument] | None = None,
) -> tuple[Observation, ...]:
    """Return point-in-time event observations, or fail closed on incomplete event."""
    if event_open_ms < 0 or event_open_ms % FIVE_MINUTES_MS or now_ms < 0:
        raise ValueError("V5_EVENT_INVALID")
    path = Path(database_path).resolve()
    if not path.is_file():
        raise ValueError("V5_MARKET_DATABASE_MISSING")
    instruments = {} if instruments is None else dict(instruments)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        event = conn.execute(
            """SELECT e.event_close_ms,e.captured_at_ms,e.status,
                      p.evidence_mode,p.context_complete,p.membership_quality
               FROM market_events e
               JOIN event_provenance p USING(event_open_ms)
               WHERE e.event_open_ms=?""", (event_open_ms,),
        ).fetchone()
        if event is None or event[2] != "COMPLETE":
            raise ValueError("V5_MARKET_EVENT_NOT_COMPLETE")
        close_ms, captured_ms, _, mode, context, membership = event
        if (int(close_ms) != event_open_ms + FIVE_MINUTES_MS - 1
                or not (int(close_ms) <= int(captured_ms) <= now_ms)
                or mode != "LIVE_POINT_IN_TIME" or context != 1
                or membership != "POINT_IN_TIME"):
            raise ValueError("V5_MARKET_EVENT_PROVENANCE_INVALID")
        quotes = conn.execute(
            """SELECT s.symbol,s.bid_price,s.ask_price,s.quote_volume_24h_usd,
                      s.funding_rate,s.universe_rank,s.captured_at_ms,
                      m.membership_quality
               FROM market_snapshots s
               JOIN universe_membership m
                 ON m.event_open_ms=s.event_open_ms AND m.symbol=s.symbol
               WHERE s.event_open_ms=?
               ORDER BY s.symbol""", (event_open_ms,),
        ).fetchall()
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?",
            (event_open_ms,),
        ).fetchone()[0]
        if len(quotes) > 500 or not quotes or len(quotes) != snapshot_count:
            # A missing membership row must not silently remove an instrument.
            raise ValueError("V5_MARKET_EVENT_UNIVERSE_INVALID")
        observations = []
        for symbol, bid, ask, quote_volume, funding_rate, rank, captured, membership_quality in quotes:
            # Do not silently drop symbols lacking complete membership.
            if membership_quality != "POINT_IN_TIME" or int(captured) > now_ms or (
                int(captured) < int(close_ms) or int(captured) > int(captured_ms)
            ):
                raise ValueError("V5_SNAPSHOT_PROVENANCE_INVALID")
            bars = conn.execute(
                """SELECT event_open_ms,open_price,high_price,low_price,close_price,quote_volume
                   FROM candles_5m
                   WHERE symbol=? AND event_open_ms BETWEEN ? AND ?
                   ORDER BY event_open_ms""",
                (symbol, event_open_ms - (LOOKBACK - 1) * FIVE_MINUTES_MS,
                 event_open_ms),
            ).fetchall()
            observations.append(Observation(
                str(symbol), event_open_ms, int(close_ms), int(captured),
                float(bid), float(ask), float(quote_volume),
                None if funding_rate is None else float(funding_rate),
                int(rank), tuple(Bar(int(t),float(o),float(h),float(l),float(c),float(v))
                                 for t,o,h,l,c,v in bars),
                provenance_ok=True,
                instrument=instruments.get(str(symbol)),
            ))
    return tuple(observations)
