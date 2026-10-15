"""G2 USD-M 100-symbol discovery from declared as-of public snapshot inputs.

No implicit HTTP, account endpoints, caching, fills, original-source grade or
historical schema imports. Inputs are untrusted and must be independently
captured with route/receive proof in later source-custody gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

UNIVERSE_SCHEMA = "NBOT_V5_1_UNIVERSE_V1"
BTC = "BTCUSDT"
_MAX_BROAD = 100
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
_GROUPS = ("TURNOVER", "GAINER", "LOSER", "FALLBACK", "BTC_MANDATORY")
_MIN_TURNOVER = Decimal("1000000")
_MAX_SPREAD_BPS = Decimal("50")


class UniverseHold(ValueError):
    """A critical universe invariant could not be proven."""


def _number(value: object) -> Decimal:
    if type(value) is not str or len(value) > 60:
        raise ValueError("G2_NUMBER_FORMAT_INVALID")
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("G2_NUMBER_INVALID") from exc
    if not n.is_finite():
        raise ValueError("G2_NUMBER_NONFINITE")
    return n


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class SymbolCandidate:
    symbol: str
    quote_turnover: Decimal
    change_percent: Decimal
    spread_bps: Decimal
    history_closed: int
    source_healthy: bool


@dataclass(frozen=True)
class UniverseEntry:
    symbol: str
    groups: tuple[str, ...]
    quote_turnover: str
    change_percent: str


@dataclass(frozen=True)
class UniverseManifest:
    schema: str
    selected_at_ms: int
    source_received_at_ms: int
    source_digest: str
    selection_digest: str
    entries: tuple[UniverseEntry, ...]
    rejected: tuple[tuple[str, str], ...]
    qualified_count: int

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(e.symbol for e in self.entries)


def select_universe(
    exchange_info: dict, tickers: list[dict], book_tickers: list[dict],
    history_closed: dict[str, int], source_health: dict[str, bool],
    *, source_received_at_ms: int, selected_at_ms: int,
    turnover_floor: str = "1000000", max_spread_bps: str = "50",
) -> UniverseManifest:
    """Deterministic 50 turnover + 25 gainers + 25 losers, then qualified fill.

    Eligibility is fail closed: active USD-M USDT-margin PERPETUAL,
    adequate settled public 24h turnover, positive bid/ask with spread <=
    limit, >=96 externally witnessed closed 5m bars, healthy source marker.
    The supplied markers are NOT proof of original-source chain of custody.
    """
    for t in (source_received_at_ms, selected_at_ms):
        if type(t) is not int or t < 0:
            raise UniverseHold("G2_UNIVERSE_CLOCK_INVALID")
    if selected_at_ms < source_received_at_ms or selected_at_ms - source_received_at_ms > 60_000:
        raise UniverseHold("G2_UNIVERSE_SOURCE_STALE")
    if (type(exchange_info) is not dict or type(tickers) is not list
            or type(book_tickers) is not list or type(history_closed) is not dict
            or type(source_health) is not dict):
        raise UniverseHold("G2_UNIVERSE_INPUT_TYPE")
    floor, spread_limit = _number(turnover_floor), _number(max_spread_bps)
    if floor <= 0 or spread_limit <= 0:
        raise UniverseHold("G2_UNIVERSE_THRESHOLDS_INVALID")
    listings = exchange_info.get("symbols")
    if type(listings) is not list:
        raise UniverseHold("G2_UNIVERSE_NO_EXCHANGE_INFO")

    def indexed(rows: list[dict]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for row in rows:
            if type(row) is not dict or type(row.get("symbol")) is not str:
                raise UniverseHold("G2_UNIVERSE_BAD_MARKET_ROW")
            sym = row["symbol"]
            if sym in result:
                raise UniverseHold("G2_UNIVERSE_DUPLICATE_MARKET_ROW")
            result[sym] = row
        return result

    stats, books = indexed(tickers), indexed(book_tickers)
    candidates: dict[str, SymbolCandidate] = {}
    rejected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in listings:
        if type(raw) is not dict or type(raw.get("symbol")) is not str:
            raise UniverseHold("G2_UNIVERSE_BAD_SYMBOL_ROW")
        symbol = raw["symbol"]
        if symbol in seen:
            raise UniverseHold("G2_UNIVERSE_DUPLICATE_EXCHANGE_SYMBOL")
        seen.add(symbol)
        if not _SYMBOL.fullmatch(symbol):
            rejected.append((symbol, "BAD_SYMBOL"))
            continue
        if (raw.get("contractType") != "PERPETUAL"
                or raw.get("status") != "TRADING"
                or raw.get("quoteAsset") != "USDT"
                or raw.get("marginAsset") != "USDT"):
            rejected.append((symbol, "INELIGIBLE_CONTRACT"))
            continue
        ticker, book = stats.get(symbol), books.get(symbol)
        if ticker is None or book is None:
            rejected.append((symbol, "SOURCE_MISSING"))
            continue
        if type(history_closed.get(symbol)) is not int or history_closed[symbol] < 96:
            rejected.append((symbol, "HISTORY_UNVERIFIED"))
            continue
        if source_health.get(symbol) is not True:
            rejected.append((symbol, "SOURCE_UNHEALTHY"))
            continue
        try:
            turnover = _number(ticker.get("quoteVolume"))
            change = _number(ticker.get("priceChangePercent"))
            bid, ask = _number(book.get("bidPrice")), _number(book.get("askPrice"))
            if turnover < floor or bid <= 0 or ask <= 0 or ask < bid:
                raise ValueError("G2_MARKET_UNTRADEABLE")
            spread = (ask - bid) * 20_000 / (bid + ask)
            if spread > spread_limit:
                rejected.append((symbol, "SPREAD_EXCESSIVE"))
                continue
        except (ValueError, TypeError, InvalidOperation):
            rejected.append((symbol, "INVALID_MARKET_METRICS"))
            continue
        candidates[symbol] = SymbolCandidate(symbol, turnover, change, spread,
                                             history_closed[symbol], True)

    if BTC not in candidates:
        raise UniverseHold("G2_BTC_NOT_QUALIFIED")
    ranking_turnover = sorted(candidates, key=lambda s: (-candidates[s].quote_turnover, s))
    ranking_up = sorted(candidates, key=lambda s: (-candidates[s].change_percent, s))
    ranking_down = sorted(candidates, key=lambda s: (candidates[s].change_percent, s))
    tag_map: dict[str, set[str]] = {s: set() for s in candidates}
    for names, count, tag in ((ranking_turnover, 50, "TURNOVER"),
                              (ranking_up, 25, "GAINER"),
                              (ranking_down, 25, "LOSER")):
        for sym in names[:count]:
            tag_map[sym].add(tag)
    selected: list[str] = []
    selected_set: set[str] = set()

    def add(sym: str) -> None:
        if sym not in selected_set and len(selected) < _MAX_BROAD:
            selected.append(sym)
            selected_set.add(sym)

    add(BTC)
    tag_map[BTC].add("BTC_MANDATORY")
    for names, count, tag in ((ranking_turnover, 50, "TURNOVER"),
                              (ranking_up, 25, "GAINER"),
                              (ranking_down, 25, "LOSER")):
        for sym in names[:count]:
            add(sym)
    for sym in ranking_turnover:
        if len(selected) >= _MAX_BROAD:
            break
        if sym not in selected_set:
            tag_map[sym].add("FALLBACK")
            add(sym)
    if len(selected) != min(len(candidates), _MAX_BROAD):
        raise UniverseHold("G2_UNIVERSE_DENOMINATOR_INVALID")
    entries = tuple(UniverseEntry(s, tuple(t for t in _GROUPS if t in tag_map[s]),
                                  str(candidates[s].quote_turnover),
                                  str(candidates[s].change_percent)) for s in selected)
    # Original inputs may contain exchange-specific fields and identifiers; only
    # selected normalized evidence is hashed/persisted here, not secret values.
    normalized = {"schema": UNIVERSE_SCHEMA,
                  "received": source_received_at_ms,
                  "exchange": sorted((s, str(v.quote_turnover), str(v.change_percent),
                                      str(v.spread_bps), v.history_closed)
                                     for s, v in candidates.items()),
                  "rejected": sorted(rejected)}
    source_digest = _digest(normalized)
    manifest_payload = {"schema": UNIVERSE_SCHEMA, "at": selected_at_ms,
                        "source": source_digest,
                        "entries": [(e.symbol, list(e.groups), e.quote_turnover,
                                     e.change_percent) for e in entries]}
    return UniverseManifest(UNIVERSE_SCHEMA, selected_at_ms,
                            source_received_at_ms, source_digest,
                            _digest(manifest_payload), entries,
                            tuple(sorted(rejected)), len(candidates))
