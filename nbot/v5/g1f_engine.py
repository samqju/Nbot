"""G1f event audit: immutable WSS final, 3 REST checks, health, patterns.

One BTC-context + 50-symbol observation event; zero labels, orders, or
automatic selection. Any unavailable source yields UNSCORABLE and holds.
"""
from __future__ import annotations

import asyncio
import time

from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.finality_quarantine import FinalityQuarantine, STAGES, single_closed_rest
from nbot.v5.g1f_journal import CandidateJournal
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import public_get

MAX_SPREAD_FRAC = .01
MAX_QUOTE_AGE_MS = 5000
MAX_TRADE_AGE_MS = 15000
REST_WORKERS = 6


def feed_holds(session, symbols, *, event_open_ms: int, measured_ms: int,
               interrupted: bool = False) -> dict[str,tuple[str,...]]:
    """Read-only instantaneous feed snapshot; never a research-ready claim."""
    results={}
    for symbol in symbols:
        reasons=[]
        coin=session.store.coins[symbol]
        if not session.store.health.market_connected:
            reasons.append("MARKET_DISCONNECTED")
        if not session.store.health.public_connected:
            reasons.append("PUBLIC_DISCONNECTED")
        if interrupted:
            reasons.append("WSS_EPOCH_INTERRUPTED")
        if symbol in session.store.health.trade_gaps:
            reasons.append("AGG_TRADE_ID_GAP")
        quote=coin.last_quote
        trade=coin.last_trade
        if quote is None or not 0<=measured_ms-quote["received_ms"]<=MAX_QUOTE_AGE_MS:
            reasons.append("QUOTE_NOT_FRESH")
        elif (quote["ask"] <= quote["bid"] or
              (quote["ask"]-quote["bid"])/quote["bid"] > MAX_SPREAD_FRAC):
            reasons.append("QUOTE_SPREAD_UNSAFE")
        if trade is None or not 0<=measured_ms-trade["received_ms"]<=MAX_TRADE_AGE_MS:
            reasons.append("TRADE_NOT_FRESH")
        # We do not certify full aggTrade continuity from REST candles.
        if session.ledger.inspect(symbol)["last_event_open_ms"]!=event_open_ms:
            reasons.append("WSS_FINAL_EVENT_MISSING")
        if session.ledger.inspect(symbol)["open_candle_gates"]:
            reasons.append("CANDLE_LEDGER_HELD")
        if (len(coin.closed_candles)!=96 or
            coin.closed_candles[-1][0]!=event_open_ms):
            reasons.append("HISTORY_NOT_96_AT_EVENT")
        results[symbol]=tuple(sorted(set(reasons)))
    return results


async def audit_event(session, journal: CandidateJournal,
                      finality: FinalityQuarantine, *,
                      symbols, cohort_digest: str, event_open_ms: int,
                      getter=public_get, sleep=asyncio.sleep,
                      clock=lambda: int(time.time()*1000),
                      interrupted: bool = False,
                      rest_delay_seconds: float = 8.0) -> dict:
    if clock() < event_open_ms+INTERVAL_MS:
        raise EvidenceHold("G1F_EVENT_NOT_CLOSED")
    # Capture data health NOW, before slow REST comparisons.
    issues=feed_holds(session,symbols,event_open_ms=event_open_ms,
                      measured_ms=clock(),interrupted=interrupted)
    finals={}
    for s in symbols:
        row=session.ledger.db.execute("""
            SELECT first_seen_ms,candle_json,first_source
            FROM candle_rows WHERE symbol=? AND open_ms=?
        """,(s,event_open_ms)).fetchone()
        if row and row[2]=="WSS_FINAL":
            import json
            value=tuple(json.loads(row[1]))
            try:
                finality.record_wss_final(
                    s,event_open_ms,received_ms=row[0],candle=value)
                finals[s]=value
            except Exception:
                finality.quarantine(
                    s,event_open_ms,"WSS_PROOF_INVALID",
                    observed_ms=clock(),evidence_sha="INVALID")
        else:
            finality.quarantine(
                s,event_open_ms,"WSS_FINAL_MISSING_OR_REST_ONLY",
                observed_ms=clock(),evidence_sha="NO_WSS_FINAL")
    sem=asyncio.Semaphore(REST_WORKERS)
    for index,stage in enumerate(STAGES):
        if index:
            await sleep(rest_delay_seconds)
        async def one(symbol):
            async with sem:
                if symbol not in finals:
                    return
                params={
                    "symbol":symbol,"interval":"5m",
                    "startTime":str(event_open_ms),
                    "endTime":str(event_open_ms+INTERVAL_MS-1),
                    "limit":"1"}
                try:
                    payload=await asyncio.to_thread(
                        getter,"/fapi/v1/klines",params)
                    bar=single_closed_rest(payload,event_open_ms=event_open_ms)
                    finality.check(
                        symbol,event_open_ms,stage,
                        observed_ms=clock(),
                        wss_candle=finals[symbol],rest_candle=bar,
                    )
                except Exception:
                    finality.quarantine(
                        symbol,event_open_ms,
                        "REST_STAGE_INVALID_"+stage,
                        observed_ms=clock(),evidence_sha="HOLD")
        await asyncio.gather(*(one(s) for s in symbols))
    review=finality.evidence_status(
        symbols,event_open_ms,min_valid=10,min_fraction=.8)
    confirmed=set(review["verified_symbols"])
    # If BTC or cross-section is invalid, no eligible pattern may appear.
    btc_good=review["btc_verified"] and not issues.get("BTCUSDT")
    eligible=review["evidence_cohort_eligible_for_future_review"]
    if not btc_good:
        eligible=False
    history={}
    if eligible:
        for symbol in confirmed:
            if not issues.get(symbol):
                history[symbol]=tuple(session.store.coins[symbol].closed_candles)
        if "BTCUSDT" not in history:
            history.clear()
            eligible=False
    quarantine={
        s:tuple(finality.reasons(s,event_open_ms))
        +(("FINALITY_NOT_VERIFIED",) if s not in confirmed else ())
        for s in symbols
    }
    recorded=journal.commit_event(
        cohort_digest=cohort_digest,event_open_ms=event_open_ms,
        observed_ms=clock(),eligible_symbols=symbols,
        candles_by_symbol=history,
        quarantine=quarantine,health_holds=issues,
        btc_valid=btc_good,coverage_valid=eligible,
    )
    return {**recorded,
            "source_verified":len(confirmed),
            "quarantined":len(review["quarantined_symbols"]),
            "health_held":sum(bool(x) for x in issues.values()),
            "finality_three_stage":True,
            "research_ready":False,"training_labels_created":0,
            "order_authority":"NONE"}
