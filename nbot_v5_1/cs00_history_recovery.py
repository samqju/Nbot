"""CS-00 OFFLINE ONLY: bounded historical USD-M aggregate-trade recovery.

This module deliberately has *no* HTTP/WebSocket client and *no* service
startup. A future separately authorised source-only runner can supply bytes
from public Binance REST and independently checked official archive files.

It cannot confer original-live, quote, mark, cost, paper or real authority.
Missing history is NOT silently erased: it is excluded from every scored
dataset and a minimal immutable censor receipt remains for auditing.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re
from urllib.parse import urlencode

from .research_intent import number

VERSION = "NBOT_V5_1_CS00_RECOVERY_V1"
MAX_ROWS = 1000
MAX_BODY_BYTES = 2 * 1024 * 1024
RECENT_MS = 48 * 3600 * 1000
MAX_GAP_AGG_IDS = 500_000
MAX_UNFROZEN_PATH_IDS = 10_000
MAX_GAP_DURATION_MS = 48 * 3600 * 1000
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
HOLD_STATES = frozenset({"RECOVERY_PENDING", "RECOVERY_HOLD", "ARCHIVE_PENDING"})
RECOVERED_STATE = "TRADE_PATH_RECOVERED_ONLY"


class SourceRecoveryHold(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceRecoveryHold("CS00_RECOVERY_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _decode(raw: bytes):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BODY_BYTES:
        raise SourceRecoveryHold("CS00_RECOVERY_INVALID_BODY_BOUNDS")
    try:
        data = json.loads(raw, object_pairs_hook=_unique,
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              SourceRecoveryHold("CS00_RECOVERY_NONFINITE_NUMBER")))
    except (ValueError, UnicodeError, TypeError) as exc:
        if isinstance(exc, SourceRecoveryHold):
            raise
        raise SourceRecoveryHold("CS00_RECOVERY_JSON_INVALID") from exc
    if type(data) is not list or not 0 < len(data) <= MAX_ROWS:
        raise SourceRecoveryHold("CS00_RECOVERY_ROWS_INVALID")
    return data


@dataclass(frozen=True)
class RecoveryProof:
    schema: str
    experiment_id: str
    symbol: str
    first_agg_id: int
    last_agg_id: int
    first_trade_ms: int | None
    last_trade_ms: int | None
    trade_count: int
    state: str
    reasons: tuple[str, ...]
    page_sha256: tuple[str, ...]
    chain_sha256: str
    retrospective_only: bool = True
    original_live_decision_verified: bool = False
    exact_historical_quote_verified: bool = False
    mark_trigger_verified: bool = False
    cost_verified: bool = False
    qualifies_scientific_training: bool = False
    financial_authority: str = "NONE"


@dataclass(frozen=True)
class PriceTouch:
    state: str
    barrier: str | None
    trade_at_ms: int | None
    trade_agg_id: int | None
    financial_authority: str = "NONE"


class HistoricalAggTradeRecovery:
    """OFFLINE-bound, ID-cursor paginated source verifier.

    The external transport is intentionally not implemented here. Submitting
    market responses to this object is not a network permission. Long gaps
    can require daily archive followup. All original-quote/cost flags remain
    false; a verified trade sequence is not a verified executable outcome.
    """

    def __init__(self, *, experiment_id: str, symbol: str,
                 first_agg_id: int, last_agg_id: int,
                 gap_start_ms: int, gap_end_ms: int, now_ms: int,
                 side: str | None = None, stop: str | None = None,
                 target: str | None = None):
        if (type(experiment_id) is not str or not _SHA.fullmatch(experiment_id)
                or type(symbol) is not str or not _SYMBOL.fullmatch(symbol)
                or not symbol.endswith("USDT")
                or any(type(v) is not int for v in
                       (first_agg_id, last_agg_id, gap_start_ms, gap_end_ms, now_ms))
                or first_agg_id < 0 or last_agg_id < first_agg_id
                or last_agg_id - first_agg_id + 1 > MAX_GAP_AGG_IDS
                or gap_start_ms <= 0 or gap_end_ms < gap_start_ms
                or gap_end_ms > now_ms
                or gap_end_ms - gap_start_ms > MAX_GAP_DURATION_MS):
            raise SourceRecoveryHold("CS00_RECOVERY_REQUEST_INVALID")
        if (side is None) != (stop is None) or (side is None) != (target is None):
            raise SourceRecoveryHold("CS00_RECOVERY_FROZEN_PRICE_PLAN_REQUIRED")
        if side is not None:
            if side not in ("LONG", "SHORT"):
                raise SourceRecoveryHold("CS00_RECOVERY_SIDE_INVALID")
            stop_price = number(stop)
            target_price = number(target)
            if (side == "LONG" and stop_price >= target_price
                    or side == "SHORT" and stop_price <= target_price):
                raise SourceRecoveryHold("CS00_RECOVERY_PRICE_GEOMETRY_INVALID")
        elif last_agg_id - first_agg_id + 1 > MAX_UNFROZEN_PATH_IDS:
            raise SourceRecoveryHold("CS00_RECOVERY_LARGE_GAP_NEEDS_FROZEN_PRICE_PLAN")
        self.side = side
        self.stop_price = number(stop) if stop is not None else None
        self.target_price = number(target) if target is not None else None
        self._first_touch: PriceTouch | None = None
        self._trade_count = 0
        self.experiment_id = experiment_id
        self.symbol = symbol
        self.first_id = first_agg_id
        self.last_id = last_agg_id
        self.gap_start_ms = gap_start_ms
        self.gap_end_ms = gap_end_ms
        self.now_ms = now_ms
        self.next_id = first_agg_id
        self.last_time_ms: int | None = None
        self.underlying_last: int | None = None
        self.first_time_ms: int | None = None
        self.rows: list[tuple[int, int, Decimal]] = []
        self.pages: list[str] = []
        self.reasons: list[str] = []
        self.finished = False
        self.needs_archive = now_ms - gap_start_ms > RECENT_MS

    def advance_clock(self, now_ms:int):
        """Explicit monotonic recovery worker clock; past the 48h REST
        horizon becomes archive-pending, never silently scored.
        """
        if type(now_ms) is not int or now_ms<self.now_ms:
            raise SourceRecoveryHold("CS00_RECOVERY_CLOCK_REWOUND")
        self.now_ms=now_ms
        if now_ms-self.gap_start_ms>RECENT_MS and not self.finished:
            self.needs_archive=True
        return self.state

    @property
    def state(self) -> str:
        if self.reasons:
            return "RECOVERY_HOLD"
        if self.finished:
            return RECOVERED_STATE
        return "ARCHIVE_PENDING" if self.needs_archive else "RECOVERY_PENDING"

    def next_rest_request(self) -> str | None:
        """Plan at most one public REST page; never perform a request."""
        if self.finished or self.reasons or self.needs_archive:
            return None
        limit = min(MAX_ROWS, self.last_id - self.next_id + 1)
        if limit <= 0:
            return None
        return "/fapi/v1/aggTrades?" + urlencode({
            "symbol": self.symbol, "fromId": self.next_id, "limit": limit})

    def ingest_page(self, raw: bytes, *, received_at_ms: int,
                    source: str = "PUBLIC_REST") -> str:
        """Strictly ingest one original REST response or independently verified archive page.

        The caller must verify an archive's downloaded ZIP/.CHECKSUM and its
        canonical format outside this method. Caller claims are not source
        authenticity proofs; metadata explicitly remains retrospective-only.
        """
        if (self.finished or self.reasons
                or source not in ("PUBLIC_REST", "OFFICIAL_ARCHIVE_CHECKSUM_VERIFIED")
                or type(received_at_ms) is not int or received_at_ms < self.gap_end_ms
                or received_at_ms > self.now_ms):
            raise SourceRecoveryHold("CS00_RECOVERY_PAGE_ORDER_OR_CLOCK")
        if self.needs_archive and source != "OFFICIAL_ARCHIVE_CHECKSUM_VERIFIED":
            raise SourceRecoveryHold("CS00_RECOVERY_REST_OVER_48H")
        rows = _decode(raw)
        expected = self.next_id
        temp: list[tuple[int, int, Decimal, int, int]] = []
        prev_time = self.last_time_ms
        prev_underlying = self.underlying_last
        for row in rows:
            if type(row) is not dict:
                raise SourceRecoveryHold("CS00_RECOVERY_TRADE_SCHEMA")
            try:
                a, f, l, timestamp = (row["a"], row["f"], row["l"], row["T"])
                if (any(type(x) is not int for x in (a, f, l, timestamp))
                        or a != expected or a > self.last_id
                        or f < 0 or l < f
                        or not self.gap_start_ms <= timestamp <= self.gap_end_ms
                        or timestamp > received_at_ms
                        or type(row.get("m")) is not bool):
                    raise SourceRecoveryHold("CS00_RECOVERY_TRADE_ID_TIME_OR_SIDE")
                price = number(row["p"])
                number(row["q"])
                if prev_time is not None and timestamp < prev_time:
                    raise SourceRecoveryHold("CS00_RECOVERY_TRADE_TIME_REVERSED")
                if prev_underlying is not None and f <= prev_underlying:
                    raise SourceRecoveryHold("CS00_RECOVERY_UNDERLYING_TRADE_OVERLAP")
                # Underlying trade IDs can exhibit exchange-side excluded
                # transactions; don't misclassify automatically as lost
                # aggregate messages, but require independent review.
                if prev_underlying is not None and f != prev_underlying + 1:
                    if "CS00_UNDERLYING_TRADE_ID_DISCONTINUITY_REVIEW" not in self.reasons:
                        self.reasons.append("CS00_UNDERLYING_TRADE_ID_DISCONTINUITY_REVIEW")
                temp.append((a, timestamp, price, f, l))
                expected += 1
                prev_time = timestamp
                prev_underlying = l
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, SourceRecoveryHold):
                    raise
                raise SourceRecoveryHold("CS00_RECOVERY_TRADE_FIELDS_INVALID") from exc
        if len(rows) > self.last_id - self.next_id + 1:
            raise SourceRecoveryHold("CS00_RECOVERY_OVERRUN")
        # Never store ambiguous pages as verified trade paths.
        if self.reasons:
            return self.state
        # A frozen price plan evaluates the first touch while streaming and
        # does NOT retain millions of tuples in RAM; only a bounded page is
        # materialized, plus hashes/cursors and the first touch.
        if self.side is None:
            self.rows.extend((a, tm, price) for a, tm, price, _, _ in temp)
        else:
            for agg_id, tm, price, _, _ in temp:
                if self._first_touch is not None:
                    break
                stopped = (price <= self.stop_price if self.side == "LONG"
                           else price >= self.stop_price)
                targeted = (price >= self.target_price if self.side == "LONG"
                            else price <= self.target_price)
                if stopped or targeted:
                    self._first_touch = PriceTouch(
                        "TRADED_PRICE_FIRST_TOUCH_ONLY",
                        "STOP" if stopped else "TARGET", tm, agg_id)
        self._trade_count += len(temp)
        self.pages.append(sha256(raw).hexdigest())
        self.next_id = expected
        self.last_time_ms = prev_time
        self.underlying_last = prev_underlying
        if self.first_time_ms is None:
            self.first_time_ms = temp[0][1]
        if self.next_id > self.last_id:
            self.finished = True
        return self.state

    def proof(self) -> RecoveryProof:
        digest = sha256(json.dumps({
            "version": VERSION, "experiment_id": self.experiment_id,
            "symbol": self.symbol, "first": self.first_id, "last": self.last_id,
            "pages": self.pages, "next": self.next_id, "state": self.state,
            "reasons": self.reasons
        }, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
        return RecoveryProof(
            VERSION, self.experiment_id, self.symbol,
            self.first_id, self.last_id, self.first_time_ms,
            self.last_time_ms, self._trade_count, self.state,
            tuple(self.reasons), tuple(self.pages), digest)

    def traded_price_first_touch(self, *, side: str, stop: str,
                                 target: str) -> PriceTouch:
        if self.state != RECOVERED_STATE:
            return PriceTouch("UNQUALIFIED_SOURCE_HOLD", None, None, None)
        if self.side is not None:
            if (side != self.side or number(stop) != self.stop_price
                    or number(target) != self.target_price):
                raise SourceRecoveryHold("CS00_RECOVERY_FROZEN_PLAN_CHANGED")
            return (self._first_touch if self._first_touch is not None else
                    PriceTouch("TRADED_PRICE_NO_TOUCH_OBSERVED", None, None, None))
        if side not in ("LONG", "SHORT"):
            raise SourceRecoveryHold("CS00_RECOVERY_SIDE_INVALID")
        stop_d = number(stop)
        target_d = number(target)
        if (side == "LONG" and stop_d >= target_d
                or side == "SHORT" and stop_d <= target_d):
            raise SourceRecoveryHold("CS00_RECOVERY_STOP_TARGET_INVALID")
        for agg_id, tm, price in self.rows:
            stopped = price <= stop_d if side == "LONG" else price >= stop_d
            targeted = price >= target_d if side == "LONG" else price <= target_d
            if stopped:
                return PriceTouch("TRADED_PRICE_FIRST_TOUCH_ONLY", "STOP", tm, agg_id)
            if targeted:
                return PriceTouch("TRADED_PRICE_FIRST_TOUCH_ONLY", "TARGET", tm, agg_id)
        return PriceTouch("TRADED_PRICE_NO_TOUCH_OBSERVED", None, None, None)


def eligible_learning_ids(*, labeled_records: tuple[tuple[str, str, str], ...]
                         ) -> tuple[str, ...]:
    """No unknown/censored/held rows in a training/score export.

    Accepts (experiment SHA, evidence status, economic qualification status).
    Scientific-original releases remain separately G7/G8 locked; this helper
    cannot award qualification from caller-owned labels.
    """
    if type(labeled_records) is not tuple:
        raise SourceRecoveryHold("CS00_LABELS_FORMAT")
    result = []
    seen = set()
    for item in labeled_records:
        if (type(item) is not tuple or len(item) != 3
                or type(item[0]) is not str or not _SHA.fullmatch(item[0])
                or item[0] in seen
                or item[1] not in ("PATH_AND_COST_COMPLETE", "TRADE_PATH_ONLY",
                                  "RECOVERY_PENDING", "UNRECOVERABLE_EXCLUDED",
                                  "SOURCE_HOLD", "CENSORED")
                or item[2] not in ("INDEPENDENTLY_QUALIFIED", "COST_PENDING",
                                   "COST_UNQUALIFIED", "EXCLUDED")):
            raise SourceRecoveryHold("CS00_LABELS_MALFORMED_OR_DUPLICATE")
        seen.add(item[0])
        if item[1] == "PATH_AND_COST_COMPLETE" and item[2] == "INDEPENDENTLY_QUALIFIED":
            result.append(item[0])
    # This is a preliminary eligibility *mask*, never a real scientific
    # approval. No qualification number or real-order authority is emitted.
    return tuple(result)
