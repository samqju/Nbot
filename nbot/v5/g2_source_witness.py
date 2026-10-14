"""Prospective G2 market-source witness contract, observation-only.

Only the isolated G2 collector path uses it; original G1f remains unchanged.
It cannot authenticate public Binance messages independently; it preserves
exact input snapshots and received times so downstream audits can reject
unknown/missing source history instead of creating retroactive qualifications.
No models, trading, labels or service dependencies.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import sqlite3
from typing import Mapping

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.g1f_journal import canonical, digest
from nbot.v5.public_market import select_universe

MAX_RAW_SNAPSHOT_BYTES = 6_000_000
MAX_COHORT = 50
MAX_QUOTE_AGE_MS = 5000
MAX_TRADE_AGE_MS = 15000
MAX_SPREAD_FRAC = .01
SYMBOL = re.compile(r"[A-Z0-9]{3,24}")


class WitnessHold(ValueError):
    pass


def _canonical_bytes(payload) -> bytes:
    try:
        value=canonical(payload).encode("utf8")
    except (TypeError,ValueError,OverflowError) as exc:
        raise WitnessHold("G2_INVALID_JSON_PAYLOAD") from exc
    if len(value)>MAX_RAW_SNAPSHOT_BYTES:
        raise WitnessHold("G2_SOURCE_PAYLOAD_OVERSIZE")
    return value


class SourceWitness:
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.executescript("""
        CREATE TABLE IF NOT EXISTS g2_cohort_witness(
          cohort_digest TEXT PRIMARY KEY,
          first_event_open_ms INTEGER NOT NULL,
          received_ms INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          payload_sha TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS g2_quote_witness(
          event_open_ms INTEGER NOT NULL,
          symbol TEXT NOT NULL,
          asof_ms INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          payload_sha TEXT NOT NULL,
          PRIMARY KEY(event_open_ms,symbol)
        );
        CREATE TRIGGER IF NOT EXISTS g2_cohort_immutable_u
          BEFORE UPDATE ON g2_cohort_witness
          BEGIN SELECT RAISE(ABORT,'G2_COHORT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g2_cohort_immutable_d
          BEFORE DELETE ON g2_cohort_witness
          BEGIN SELECT RAISE(ABORT,'G2_COHORT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g2_quote_immutable_u
          BEFORE UPDATE ON g2_quote_witness
          BEGIN SELECT RAISE(ABORT,'G2_QUOTE_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g2_quote_immutable_d
          BEFORE DELETE ON g2_quote_witness
          BEGIN SELECT RAISE(ABORT,'G2_QUOTE_IMMUTABLE'); END;
        """)

    def witness_cohort(self, *, exchange: object, ticker: object,
                       selected: tuple[str, ...], received_ms: int,
                       first_event_open_ms: int, exchange_server_ms: int) -> str:
        if (type(received_ms) is not int or type(exchange_server_ms) is not int
                or type(first_event_open_ms) is not int
                or received_ms <= 0 or first_event_open_ms % INTERVAL_MS
                or first_event_open_ms < 0
                or exchange_server_ms > received_ms
                or received_ms - exchange_server_ms > 10_000
                or received_ms < first_event_open_ms + INTERVAL_MS
                or received_ms >= first_event_open_ms + 2*INTERVAL_MS
                or not 2 <= len(selected) <= MAX_COHORT):
            raise WitnessHold("G2_UNIVERSE_CLOCK_OR_SIZE_UNSAFE")
        ranked=select_universe(exchange,ticker,limit=len(selected))
        if ranked!=tuple(selected):
            raise WitnessHold("G2_UNIVERSE_NOT_REPRODUCIBLE")
        if "BTCUSDT" not in ranked:
            raise WitnessHold("G2_BTC_UNAVAILABLE")
        cohort=digest({"selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                       "symbols":tuple(sorted(selected))})
        evidence={
            "version":"NBOT_G2_COHORT_SOURCE_WITNESS_V1",
            "exchange":exchange, "ticker":ticker, "ranked_selected":ranked,
            "received_ms":received_ms, "server_ms":exchange_server_ms,
            "first_event_open_ms":first_event_open_ms,
            "cohort_digest":cohort,
        }
        payload=_canonical_bytes(evidence)
        sha=hashlib.sha256(payload).hexdigest()
        prior=self.db.execute(
            "SELECT payload_sha,payload_json FROM g2_cohort_witness WHERE cohort_digest=?",
            (cohort,)).fetchone()
        if prior:
            if prior!=(sha,payload.decode()):
                raise WitnessHold("G2_COHORT_REPLAY_CONFLICT")
            return cohort
        with self.db:
            self.db.execute(
                "INSERT INTO g2_cohort_witness VALUES (?,?,?,?,?)",
                (cohort,first_event_open_ms,received_ms,payload.decode(),sha))
        return cohort

    def witness_event_quotes(self, *, cohort_digest: str,
                             event_open_ms: int, asof_ms: int,
                             sources: Mapping[str,dict]) -> dict:
        cohort=self.db.execute(
            "SELECT payload_json FROM g2_cohort_witness WHERE cohort_digest=?",
            (cohort_digest,)).fetchone()
        if not cohort:
            raise WitnessHold("G2_COHORT_WITNESS_MISSING")
        ranked=json.loads(cohort[0])["ranked_selected"]
        symbols=set(ranked)
        if (not isinstance(sources,Mapping) or set(sources)!=symbols
                or type(event_open_ms) is not int or event_open_ms % INTERVAL_MS
                or type(asof_ms) is not int
                or not event_open_ms+INTERVAL_MS<=asof_ms
                or asof_ms>=event_open_ms+2*INTERVAL_MS):
            raise WitnessHold("G2_EVENT_DENOMINATOR_OR_ASOF_INVALID")
        assembled=[]
        reasons={}
        for symbol in sorted(symbols):
            r=sources[symbol]
            if not isinstance(r,dict) or set(r)!={
                "bid","ask","quote_received_ms","trade_received_ms",
                "market_connected","public_connected",
                "market_epoch","public_epoch"}:
                raise WitnessHold("G2_SOURCE_FIELDS_MISSING")
            hold=[]
            bid,ask=r["bid"],r["ask"]
            quote_ms,trade_ms=r["quote_received_ms"],r["trade_received_ms"]
            if not all(type(r[k]) is bool for k in ("market_connected","public_connected")):
                raise WitnessHold("G2_INVALID_CONNECTED_FLAG")
            if not r["market_connected"] or not r["public_connected"]:
                hold.append("SOURCE_DISCONNECTED")
            if (type(quote_ms) is not int or quote_ms<0
                    or not 0<=asof_ms-quote_ms<=MAX_QUOTE_AGE_MS):
                hold.append("QUOTE_STALE_OR_MISSING")
            if (type(trade_ms) is not int or trade_ms<0
                    or not 0<=asof_ms-trade_ms<=MAX_TRADE_AGE_MS):
                hold.append("TRADE_STALE_OR_MISSING")
            if (type(bid) not in (int,float) or type(ask) not in (int,float)
                    or not math.isfinite(bid) or not math.isfinite(ask)
                    or bid<=0 or ask<=bid
                    or (ask-bid)/bid>MAX_SPREAD_FRAC):
                hold.append("QUOTE_UNSAFE")
            if any(type(r[k]) is not int or r[k]<=0 for k in ("market_epoch","public_epoch")):
                hold.append("SOURCE_EPOCH_UNKNOWN")
            reasons[symbol]=tuple(sorted(set(hold)))
            proof={
                "version":"NBOT_G2_QUOTE_EVIDENCE_V1",
                "cohort_digest":cohort_digest, "symbol":symbol,
                "event_open_ms":event_open_ms,"asof_ms":asof_ms,
                "source":r,"status":"HOLD" if hold else "SOURCE_RECORDED",
                "hold_reasons":reasons[symbol],
                "paper_fill_grade":"UNVERIFIED",
                "order_authority":"NONE",
            }
            payload=_canonical_bytes(proof)
            assembled.append((event_open_ms,symbol,asof_ms,payload.decode(),
                              hashlib.sha256(payload).hexdigest()))
        with self.db:
            for item in assembled:
                previous=self.db.execute(
                    "SELECT asof_ms,payload_json,payload_sha FROM g2_quote_witness "
                    "WHERE event_open_ms=? AND symbol=?",(item[0],item[1])
                ).fetchone()
                if previous and previous!=(item[2],item[3],item[4]):
                    raise WitnessHold("G2_EVENT_QUOTE_REPLAY_CONFLICT")
            for item in assembled:
                self.db.execute(
                    "INSERT OR IGNORE INTO g2_quote_witness VALUES (?,?,?,?,?)",item)
        return {
            "event_open_ms":event_open_ms,
            "recorded":len(assembled),
            "qualified_local_sources":sum(not v for v in reasons.values()),
            "source_held":sum(bool(v) for v in reasons.values()),
            "source_grade":"LOCAL_UNAUTHENTICATED_WITNESS_ONLY",
            "research_ready":False,
            "order_authority":"NONE",
        }
