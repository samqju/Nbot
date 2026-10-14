"""E2/E3 offline-only chronological replay and common-window evidence.

Never connects to networks, loads Binance credentials, or activates services.
All time and bid/ask inputs are SYNTHETIC, never claimed to be market evidence.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Mapping

from .execution_engine import (
    OfflineExecutionEngine, PORTFOLIOS, Refused, canonical, number, ZERO,
)

RECEIPT_DOMAIN = b"NBOT-V5-SYNTHETIC-EXECUTION-RECEIPT-V1\n"
MAX_FRAME_BYTES = 16000
MAX_MARKETS = 64
D = Decimal


class ReplayRefused(ValueError):
    pass


@dataclass(frozen=True)
class ReplayRules:
    """Frozen before any test contest; each frame is an as-of synthetic event."""
    contest_start_ms: int
    contest_end_ms: int
    max_holding_ms: int = 4 * 60 * 60 * 1000
    max_evidence_gap_ms: int = 5 * 60 * 1000
    min_settled_per_model: int = 100
    min_shared_frames: int = 100
    min_shared_duration_ms: int = 24 * 60 * 60 * 1000

    def __post_init__(self):
        if (type(self.contest_start_ms) is not int
                or type(self.contest_end_ms) is not int
                or self.contest_start_ms < 0
                or self.contest_end_ms <= self.contest_start_ms):
            raise ValueError("invalid contest UTC boundaries")
        for field in ("max_holding_ms", "max_evidence_gap_ms", "min_settled_per_model",
                      "min_shared_frames", "min_shared_duration_ms"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValueError("invalid frozen contest rule")
        if self.min_shared_duration_ms > self.contest_end_ms - self.contest_start_ms:
            raise ValueError("impossible common duration")


class SyntheticReplay:
    """Atomic replay: one market frame, zero to two signed book intents.

    Signed receipts acknowledge durable decisions, not delivered real orders.
    Each market frame can be submitted once; replays must be byte-identical.
    """

    def __init__(self, engine: OfflineExecutionEngine, rules: ReplayRules, receipt_key: bytes):
        if not isinstance(receipt_key, bytes) or len(receipt_key) < 16:
            raise ValueError("offline receipt key required")
        self.engine = engine
        self.rules = rules
        self._receipt_key = receipt_key
        self._rules_sha = hashlib.sha256(canonical(
            {name: str(value) for name, value in asdict(rules).items()})).hexdigest()
        self._receipt_key_sha = hashlib.sha256(receipt_key).hexdigest()
        c = engine.db
        c.executescript("""
        CREATE TABLE IF NOT EXISTS replay_config(
          id INTEGER PRIMARY KEY CHECK(id=1), rules_sha TEXT NOT NULL,
          receipt_key_sha TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS replay_frames(
          frame_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, symbol TEXT NOT NULL,
          at_ms INTEGER NOT NULL, request_sha TEXT NOT NULL,
          receipt_json TEXT NOT NULL, grade TEXT NOT NULL CHECK(grade='SYNTHETIC'));
        CREATE INDEX IF NOT EXISTS ix_replay_frames_clock ON replay_frames(at_ms,frame_id);
        CREATE TABLE IF NOT EXISTS replay_quote_latest(
          symbol TEXT PRIMARY KEY, reference TEXT NOT NULL, bid TEXT NOT NULL,
          ask TEXT NOT NULL, at_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS replay_marks(
          frame_id TEXT NOT NULL, portfolio TEXT NOT NULL,
          at_ms INTEGER NOT NULL, wallet TEXT NOT NULL, equity TEXT,
          reason TEXT NOT NULL, PRIMARY KEY(frame_id,portfolio));
        CREATE TRIGGER IF NOT EXISTS frames_no_update BEFORE UPDATE ON replay_frames
           BEGIN SELECT RAISE(ABORT,'immutable replay frame'); END;
        CREATE TRIGGER IF NOT EXISTS frames_no_delete BEFORE DELETE ON replay_frames
           BEGIN SELECT RAISE(ABORT,'immutable replay frame'); END;
        CREATE TRIGGER IF NOT EXISTS marks_no_update BEFORE UPDATE ON replay_marks
           BEGIN SELECT RAISE(ABORT,'immutable replay mark'); END;
        CREATE TRIGGER IF NOT EXISTS marks_no_delete BEFORE DELETE ON replay_marks
           BEGIN SELECT RAISE(ABORT,'immutable replay mark'); END;
        """)
        with engine._tx() as db:
            db.execute("INSERT OR IGNORE INTO replay_config VALUES (1,?,?)",
                       (self._rules_sha, self._receipt_key_sha))
            frozen = db.execute("SELECT rules_sha,receipt_key_sha FROM replay_config WHERE id=1").fetchone()
            if (frozen["rules_sha"], frozen["receipt_key_sha"]) != (self._rules_sha, self._receipt_key_sha):
                raise ValueError("FROZEN_REPLAY_RULES_OR_RECEIPT_KEY_CHANGED")

    def _sign(self, receipt: dict) -> dict:
        digest = hmac.new(self._receipt_key, RECEIPT_DOMAIN + canonical(receipt),
                          hashlib.sha256).hexdigest()
        return {"receipt": receipt, "signature": digest, "receipt_grade": "SYNTHETIC"}

    def verify_receipt(self, envelope: dict) -> bool:
        if not isinstance(envelope, dict) or not isinstance(envelope.get("receipt"), dict):
            return False
        if not isinstance(envelope.get("signature"), str):
            return False
        return hmac.compare_digest(self._sign(envelope["receipt"])["signature"], envelope["signature"])

    def _mark(self, portfolio: str, now_ms: int) -> dict:
        db = self.engine.db
        wallet = number(db.execute("SELECT wallet FROM books WHERE portfolio=?",
                                   (portfolio,)).fetchone()[0])
        open_positions = db.execute("SELECT * FROM positions WHERE portfolio=?",
                                    (portfolio,)).fetchall()
        equity = wallet
        for p in open_positions:
            q = db.execute("SELECT * FROM replay_quote_latest WHERE symbol=?", (p["symbol"],)).fetchone()
            if not q or not 0 <= now_ms - q["at_ms"] <= self.engine.policy.max_quote_age_ms:
                return {"wallet": str(wallet), "equity": None,
                        "reason": "HOLD_MISSING_FRESH_MARK"}
            bid, ask = number(q["bid"], positive=True), number(q["ask"], positive=True)
            slip = self.engine.policy.slippage_rate_per_side
            exit_price = bid * (1-slip) if p["side"] == "LONG" else ask * (1+slip)
            qty, entry = number(p["qty"]), number(p["entry"])
            gross = (exit_price-entry)*qty*(1 if p["side"] == "LONG" else -1)
            exit_fee = exit_price * qty * self.engine.policy.taker_fee_rate
            accrued = (entry * qty * self.engine.policy.adverse_funding_rate_per_8h *
                       D(now_ms-p["opened_ms"])/D(28800000))
            equity += gross - exit_fee - accrued
        return {"wallet": str(wallet), "equity": str(equity), "reason": "QUALIFIED_SYNTHETIC_MARK"}

    def advance(self, frame: dict, proposals: list[dict]) -> dict:
        """Apply one fresh, ordered synthetic market tick; never reach into future frames."""
        if not isinstance(frame, dict) or set(frame) != {"frame_id", "event_id", "at_ms", "quote"}:
            raise ReplayRefused("FRAME_CONTRACT_INVALID")
        fid, event_id, at, q = (frame[k] for k in ("frame_id", "event_id", "at_ms", "quote"))
        if (not isinstance(fid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", fid)
                or not isinstance(event_id, str) or not 0 < len(event_id) <= 128
                or type(at) is not int
                or not self.rules.contest_start_ms <= at <= self.rules.contest_end_ms):
            raise ReplayRefused("FRAME_ID_OR_CLOCK_INVALID")
        if not isinstance(proposals, list) or len(proposals) > 2:
            raise ReplayRefused("TOO_MANY_PROPOSALS")
        if not isinstance(q, dict) or set(q) != {
            "source", "symbol", "bid", "ask", "observed_at_ms",
            "healthy", "btc_healthy", "reference",
        }:
            raise ReplayRefused("QUOTE_CONTRACT_INVALID")
        if not isinstance(q["reference"], str) or not 0 < len(q["reference"]) <= 128:
            raise ReplayRefused("QUOTE_REFERENCE_INVALID")
        symbol = q["symbol"]
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]{4,18}", symbol):
            raise ReplayRefused("SYMBOL_INVALID")
        payloads = []
        portfolio_set = set()
        for item in proposals:
            if not isinstance(item, dict) or set(item) != {"payload", "signature"}:
                raise ReplayRefused("PROPOSAL_CONTRACT_INVALID")
            req = item["payload"]
            if not isinstance(req, dict) or req.get("event_id") != event_id or req.get("symbol") != symbol:
                raise ReplayRefused("PROPOSAL_EVENT_MISMATCH")
            book = req.get("portfolio_id")
            if book not in PORTFOLIOS or book in portfolio_set:
                raise ReplayRefused("DUPLICATE_OR_UNKNOWN_BOOK")
            if not isinstance(item["signature"], str):
                raise ReplayRefused("SIGNATURE_INVALID")
            portfolio_set.add(book)
            payloads.append(item)
        try:
            wire = canonical({"frame": frame, "proposals": payloads})
        except (ValueError, TypeError, OverflowError):
            raise ReplayRefused("FRAME_ENCODING_INVALID") from None
        if len(wire) > MAX_FRAME_BYTES:
            raise ReplayRefused("FRAME_SIZE_LIMIT")
        fingerprint = hashlib.sha256(wire).hexdigest()
        with self.engine._tx() as db:
            previous = db.execute("SELECT * FROM replay_frames WHERE frame_id=?", (fid,)).fetchone()
            if previous:
                if previous["request_sha"] != fingerprint:
                    raise ReplayRefused("FRAME_REPLAY_CONFLICT")
                return {**self._sign(json.loads(previous["receipt_json"])), "duplicate": True}
            last = db.execute("SELECT MAX(at_ms) FROM replay_frames").fetchone()[0]
            if last is not None and at < last:
                raise ReplayRefused("NONCHRONOLOGICAL_MARKET_FRAME")
            if last is not None and at - last > self.rules.max_evidence_gap_ms:
                raise ReplayRefused("UNRESOLVED_COMMON_TIMELINE_GAP")
            try:
                bid, ask = self.engine._quote(
                    q, symbol, at-self.engine.policy.max_quote_age_ms, at)
            except Refused as exc:
                raise ReplayRefused(exc.reason) from None
            last_quote = db.execute(
                "SELECT * FROM replay_quote_latest WHERE symbol=?", (symbol,)).fetchone()
            quote_clock = q["observed_at_ms"]
            if last_quote:
                if quote_clock < last_quote["at_ms"]:
                    raise ReplayRefused("REGRESSED_QUOTE_SOURCE_CLOCK")
                if quote_clock - last_quote["at_ms"] > self.rules.max_evidence_gap_ms:
                    raise ReplayRefused("UNRESOLVED_SYMBOL_TIMELINE_GAP")
                if quote_clock == last_quote["at_ms"] and (
                    q["reference"] != last_quote["reference"]
                    or bid != number(last_quote["bid"])
                    or ask != number(last_quote["ask"])
                ):
                    raise ReplayRefused("CONFLICTING_SAME_TIMESTAMP_MARKET_SOURCE")
            elif db.execute("SELECT COUNT(*) FROM replay_quote_latest").fetchone()[0] >= MAX_MARKETS:
                raise ReplayRefused("MAX_MARKETS_LIMIT")
            db.execute("""INSERT INTO replay_quote_latest (symbol,reference,bid,ask,at_ms)
                           VALUES (?,?,?,?,?)
                           ON CONFLICT(symbol) DO UPDATE SET
                           reference=excluded.reference,bid=excluded.bid,
                           ask=excluded.ask,at_ms=excluded.at_ms""",
                       (symbol, q["reference"], str(bid), str(ask), quote_clock))
            closed = {}
            for book in PORTFOLIOS:
                position = db.execute("SELECT side,stop,opened_ms FROM positions WHERE portfolio=? AND symbol=?",
                                      (book, symbol)).fetchone()
                if not position or at <= position["opened_ms"]:
                    continue
                stopped = bid <= number(position["stop"]) if position["side"] == "LONG" else ask >= number(position["stop"])
                timed_out = at - position["opened_ms"] >= self.rules.max_holding_ms
                if stopped or timed_out:
                    close = self.engine.settle_synthetic(book, symbol, q, at)
                    if close["status"] != "SETTLED":
                        raise ReplayRefused("SYNTHETIC_SETTLEMENT_FAILED")
                    closed[book] = {"trigger": "STOP" if stopped else "MAX_HOLD", "result": close}
            decisions = {}
            for item in payloads:
                r = item["payload"]
                decisions[r["portfolio_id"]] = self.engine.submit(r, item["signature"], q, at)
            marks = {}
            for book in PORTFOLIOS:
                mark = self._mark(book, at)
                marks[book] = mark
                db.execute("""INSERT INTO replay_marks
                    (frame_id,portfolio,at_ms,wallet,equity,reason) VALUES (?,?,?,?,?,?)""",
                    (fid, book, at, mark["wallet"], mark["equity"], mark["reason"]))
            receipt = {"version": "nbot.v5.synthetic.receipt.v1", "frame_id": fid,
                       "event_id": event_id, "symbol": symbol, "at_ms": at,
                       "source": "SYNTHETIC", "request_sha256": fingerprint,
                       "closed": closed, "decisions": decisions, "marks": marks,
                       "paper_only": True}
            db.execute("""INSERT INTO replay_frames
                (frame_id,event_id,symbol,at_ms,request_sha,receipt_json,grade)
                VALUES (?,?,?,?,?,?,'SYNTHETIC')""",
                (fid, event_id, symbol, at, fingerprint, json.dumps(receipt,sort_keys=True)))
            return self._sign(receipt)

    def common_window_report(self, at_ms: int) -> dict:
        """No promotion recommendation: a 100-trade count is not enough."""
        if type(at_ms) is not int or not self.rules.contest_start_ms <= at_ms <= self.rules.contest_end_ms:
            raise ReplayRefused("INVALID_REPORT_CUTOFF")
        db = self.engine.db
        last = db.execute("SELECT frame_id,at_ms FROM replay_frames WHERE at_ms<=? ORDER BY at_ms DESC, rowid DESC LIMIT 1",
                          (at_ms,)).fetchone()
        frame_counts = db.execute(
            "SELECT count(*) AS n, MIN(at_ms) AS first_ms, COUNT(DISTINCT event_id) AS events "
            "FROM replay_frames WHERE at_ms<=?", (at_ms,)).fetchone()
        nframes = frame_counts["n"]
        if not last:
            return {"status": "HOLD_NO_SHARED_EVENTS", "comparison_grade": "SYNTHETIC_ONLY"}
        books = {}
        for book in PORTFOLIOS:
            mark = db.execute("SELECT * FROM replay_marks WHERE frame_id=? AND portfolio=?",
                              (last["frame_id"], book)).fetchone()
            settled = db.execute("""SELECT count(*) FROM settled
               WHERE portfolio=? AND closed_ms >= ? AND closed_ms <= ?""",
               (book, self.rules.contest_start_ms, last["at_ms"])).fetchone()[0]
            bookrow = db.execute("SELECT model_id,model_sha,policy_sha FROM books WHERE portfolio=?",
                                 (book,)).fetchone()
            books[book] = {"model_id": bookrow["model_id"], "model_sha": bookrow["model_sha"],
                           "risk_policy_sha": bookrow["policy_sha"],
                           "settled_count": settled, "wallet": mark["wallet"],
                           "equity": mark["equity"], "mark_quality": mark["reason"]}
        latest_time = last["at_ms"]
        minimum_count = all(b["settled_count"] >= self.rules.min_settled_per_model for b in books.values())
        common_duration = latest_time - frame_counts["first_ms"]
        good_marks = all(b["equity"] is not None for b in books.values())
        reasons = []
        if not minimum_count:
            reasons.append("UNDER_100_SETTLED_PER_MODEL")
        if nframes < self.rules.min_shared_frames or common_duration < self.rules.min_shared_duration_ms:
            reasons.append("SHARED_WINDOW_INSUFFICIENT")
        if not good_marks:
            reasons.append("COMMON_ENDPOINT_MARK_UNVERIFIED")
        # Even 100+ is not enough: source maturity, independent market regimes and
        # event-blocked uncertainty are not established by synthetic fixtures.
        reasons.append("MODEL_PROMOTION_NOT_AUTHORIZED")
        reasons.append("INDEPENDENT_REGIME_AND_UNCERTAINTY_UNVERIFIED")
        return {"status": "HOLD_REVIEW_REQUIRED", "reasons": reasons,
                "comparison_grade": "SYNTHETIC_ONLY",
                "window_start_ms": self.rules.contest_start_ms,
                "first_observed_ms": frame_counts["first_ms"],
                "unique_event_ids_not_independent": frame_counts["events"],
                "common_endpoint_ms": latest_time,
                "declared_max_end_ms": self.rules.contest_end_ms,
                "shared_frames": nframes, "common_duration_ms": common_duration,
                "portfolios": books, "paper_promotion_authority": "NONE",
                "real_order_authority": "NONE"}
