"""Isolated NBOT V5 offline paper executor. No network, credentials, or real-order API."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

CONTRACT = "nbot.v5.paper.recommendation.v1"
MAX_SIGNED_MESSAGE_BYTES = 8192
DOMAIN = b"NBOT-V5-PAPER-RECOMMENDATION-V1\n"
PORTFOLIOS = ("CHAMPION_PAPER", "CHALLENGER_PAPER")
FIELDS = frozenset((
    "contract_version", "authority", "experiment_id", "contest_id", "model_id",
    "model_sha", "portfolio_id", "event_id", "as_of_ms", "expires_at_ms",
    "symbol", "side", "strategy_tag_ids", "btc_regime_version",
    "coin_structure_version", "expected_after_cost_net_r", "confidence",
    "entry_quote_reference", "stop_price", "execution_policy_version",
    "sequence", "idempotency_key",
))
DEC = Decimal
ZERO = DEC("0")


class Refused(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def number(value: object, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise Refused("INVALID_NUMBER")
    try:
        value = DEC(str(value))
    except (InvalidOperation, ValueError):
        raise Refused("INVALID_NUMBER") from None
    if not value.is_finite() or (positive and value <= ZERO):
        raise Refused("INVALID_NUMBER")
    return value


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def sign_for_synthetic_test(payload: dict, key: bytes) -> str:
    """Helper for offline fixtures; never includes a key or credentials."""
    return hmac.new(key, DOMAIN + canonical(payload), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class FrozenModel:
    model_id: str
    model_sha: str
    experiment_id: str
    contest_id: str | None = None


@dataclass(frozen=True)
class PaperPolicy:
    starting_equity: Decimal = DEC("10000")
    taker_fee_rate: Decimal = DEC("0.0005")
    slippage_rate_per_side: Decimal = DEC("0.0001")
    adverse_funding_rate_per_8h: Decimal = DEC("0.0001")
    max_positions: int = 2
    max_gross_notional_multiple: Decimal = DEC("1")
    max_risk_per_trade: Decimal = DEC("0.01")
    max_total_open_risk: Decimal = DEC("0.02")
    max_cost_to_r: Decimal = DEC("0.25")
    max_realized_drawdown: Decimal = DEC("0.10")
    min_expected_net_r: Decimal = DEC("0.1")
    min_confidence: Decimal = DEC("0.7")
    max_quote_age_ms: int = 2000
    max_recommendation_age_ms: int = 5000

    def __post_init__(self):
        for name in ("starting_equity", "max_positions", "max_gross_notional_multiple",
                     "max_risk_per_trade", "max_total_open_risk", "max_cost_to_r", "max_realized_drawdown"):
            if number(getattr(self, name), positive=True) <= ZERO:
                raise ValueError(name)
        for name in ("taker_fee_rate", "slippage_rate_per_side",
                     "adverse_funding_rate_per_8h", "min_expected_net_r",
                     "min_confidence"):
            if number(getattr(self, name)) < ZERO:
                raise ValueError(name)
        if (self.min_confidence > 1 or self.max_realized_drawdown > 1
                or self.max_quote_age_ms <= 0 or self.max_recommendation_age_ms <= 0):
            raise ValueError("invalid policy")


class OfflineExecutionEngine:
    """One SQLite-backed service core with independent and durable paper books.

    Only independently supplied SYNTHETIC quote fixtures are supported. All
    transactions are atomic, WAL/FULL. No sockets, exchange client or workers.
    """

    def __init__(self, database: str | Path, models: Mapping[str, FrozenModel],
                 signing_keys: Mapping[str, bytes], policy: PaperPolicy | None = None):
        self.policy = policy or PaperPolicy()
        if set(models) != set(PORTFOLIOS) or set(signing_keys) != set(PORTFOLIOS):
            raise ValueError("two explicitly pinned paper model identities and two keys required")
        if any(not isinstance(k, bytes) or len(k) < 16 for k in signing_keys.values()):
            raise ValueError("synthetic signing secrets must be at least 16 bytes")
        if signing_keys[PORTFOLIOS[0]] == signing_keys[PORTFOLIOS[1]]:
            raise ValueError("portfolio signing keys cannot be shared")
        for spec in models.values():
            if not re.fullmatch(r"[0-9a-f]{64}", spec.model_sha):
                raise ValueError("model artifact SHA-256 required")
            if not spec.model_id or not spec.experiment_id:
                raise ValueError("model must be fully identified")
        path = Path(database).expanduser().resolve()
        if any(part.lower() in ("nbot", "v3", "v4", "nbot-mainnet-build") for part in path.parts):
            raise ValueError("LEGACY_DIRECTORY_FORBIDDEN")
        if path == Path(":memory:").resolve() or not path.parent.is_dir():
            raise ValueError("use an existing isolated directory for durable SQLite")
        self.models, self.keys = dict(models), dict(signing_keys)
        self.policy_sha = hashlib.sha256(canonical(
            {name: str(value) for name, value in asdict(self.policy).items()})).hexdigest()
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._schema()
        with self._tx() as c:
            for book in PORTFOLIOS:
                m = models[book]
                c.execute("""INSERT OR IGNORE INTO books
                    (portfolio, model_id, model_sha, experiment_id, contest_id,
                     wallet, peak_wallet, last_sequence, killed, policy_sha)
                    VALUES (?,?,?,?,?,?,?,0,0,?)""",
                    (book, m.model_id, m.model_sha, m.experiment_id, m.contest_id,
                     str(self.policy.starting_equity), str(self.policy.starting_equity), self.policy_sha))
                row = c.execute("SELECT * FROM books WHERE portfolio=?", (book,)).fetchone()
                if (row["model_id"], row["model_sha"], row["experiment_id"], row["contest_id"], row["policy_sha"]) != (
                    m.model_id, m.model_sha, m.experiment_id, m.contest_id, self.policy_sha):
                    raise ValueError("FROZEN_MODEL_MISMATCH: cannot silently swap model after restart")

    def close_database(self):
        self.db.close()

    def _schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS books(
          portfolio TEXT PRIMARY KEY, model_id TEXT NOT NULL, model_sha TEXT NOT NULL,
          experiment_id TEXT NOT NULL, contest_id TEXT, wallet TEXT NOT NULL,
          peak_wallet TEXT NOT NULL, last_sequence INTEGER NOT NULL, killed INTEGER NOT NULL,
          policy_sha TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions(
          id INTEGER PRIMARY KEY, portfolio TEXT NOT NULL, idem TEXT NOT NULL,
          payload_sha TEXT NOT NULL, event_id TEXT NOT NULL, symbol TEXT NOT NULL,
          as_of_ms INTEGER NOT NULL, result TEXT NOT NULL,
          UNIQUE(portfolio,idem), UNIQUE(portfolio,event_id,symbol),
          FOREIGN KEY(portfolio) REFERENCES books(portfolio));
        CREATE TABLE IF NOT EXISTS shared_mock_quotes(
          event_id TEXT NOT NULL, symbol TEXT NOT NULL, reference TEXT NOT NULL,
          observed_at_ms INTEGER NOT NULL, bid TEXT NOT NULL, ask TEXT NOT NULL,
          PRIMARY KEY(event_id,symbol));
        CREATE TRIGGER IF NOT EXISTS quotes_no_update BEFORE UPDATE ON shared_mock_quotes
          BEGIN SELECT RAISE(ABORT,'immutable market quote'); END;
        CREATE TRIGGER IF NOT EXISTS quotes_no_delete BEFORE DELETE ON shared_mock_quotes
          BEGIN SELECT RAISE(ABORT,'immutable market quote'); END;
        CREATE TABLE IF NOT EXISTS positions(
          id INTEGER PRIMARY KEY, portfolio TEXT NOT NULL, symbol TEXT NOT NULL,
          side TEXT NOT NULL, qty TEXT NOT NULL, entry TEXT NOT NULL,
          stop TEXT NOT NULL, risk TEXT NOT NULL, opened_ms INTEGER NOT NULL,
          model_id TEXT NOT NULL, decision_id INTEGER NOT NULL,
          UNIQUE(portfolio,symbol));
        CREATE TABLE IF NOT EXISTS orders(
          id INTEGER PRIMARY KEY, portfolio TEXT NOT NULL, symbol TEXT NOT NULL,
          action TEXT NOT NULL, decision_id INTEGER, at_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS fills(
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, portfolio TEXT NOT NULL,
          symbol TEXT NOT NULL, price TEXT NOT NULL, qty TEXT NOT NULL,
          fee TEXT NOT NULL, at_ms INTEGER NOT NULL, grade TEXT NOT NULL
          CHECK(grade='SYNTHETIC'));
        CREATE TABLE IF NOT EXISTS ledger(
          id INTEGER PRIMARY KEY, portfolio TEXT NOT NULL, category TEXT NOT NULL,
          delta TEXT NOT NULL, wallet_after TEXT NOT NULL, at_ms INTEGER NOT NULL,
          source_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS settled(
          id INTEGER PRIMARY KEY, portfolio TEXT NOT NULL, symbol TEXT NOT NULL,
          position_id INTEGER NOT NULL UNIQUE, opened_ms INTEGER NOT NULL,
          closed_ms INTEGER NOT NULL, gross_pnl TEXT NOT NULL,
          entry_fee TEXT NOT NULL, exit_fee TEXT NOT NULL, funding TEXT NOT NULL,
          net_pnl TEXT NOT NULL, grade TEXT NOT NULL CHECK(grade='SYNTHETIC'));
        CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions
          BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
        CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
          BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
        CREATE TRIGGER IF NOT EXISTS fills_no_update BEFORE UPDATE ON fills
          BEGIN SELECT RAISE(ABORT,'immutable fill'); END;
        CREATE TRIGGER IF NOT EXISTS fills_no_delete BEFORE DELETE ON fills
          BEGIN SELECT RAISE(ABORT,'immutable fill'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
          BEGIN SELECT RAISE(ABORT,'immutable ledger'); END;
        CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
          BEGIN SELECT RAISE(ABORT,'immutable ledger'); END;
        CREATE TRIGGER IF NOT EXISTS settled_no_update BEFORE UPDATE ON settled
          BEGIN SELECT RAISE(ABORT,'immutable settled'); END;
        CREATE TRIGGER IF NOT EXISTS settled_no_delete BEFORE DELETE ON settled
          BEGIN SELECT RAISE(ABORT,'immutable settled'); END;
        """)

    @contextmanager
    def _tx(self):
        """Permit an outer synthetic replay event to atomically include ledger entries."""
        nested = self.db.in_transaction
        if nested:
            self.db.execute("SAVEPOINT nbot_paper_nested")
        else:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("RELEASE SAVEPOINT nbot_paper_nested" if nested else "COMMIT")
        except BaseException:
            if nested:
                self.db.execute("ROLLBACK TO SAVEPOINT nbot_paper_nested")
                self.db.execute("RELEASE SAVEPOINT nbot_paper_nested")
            else:
                self.db.execute("ROLLBACK")
            raise

    def _quote(self, q: dict, symbol: str, as_of_ms: int, now_ms: int):
        if not isinstance(q, dict) or q.get("source") != "SYNTHETIC":
            raise Refused("NO_INDEPENDENT_SYNTHETIC_QUOTE")
        if q.get("healthy") is not True or q.get("btc_healthy") is not True:
            raise Refused("MARKET_DATA_UNVERIFIED")
        if q.get("symbol") != symbol:
            raise Refused("QUOTE_SYMBOL_MISMATCH")
        t = q.get("observed_at_ms")
        if type(t) is not int or not as_of_ms <= t <= now_ms or now_ms - t > self.policy.max_quote_age_ms:
            raise Refused("QUOTE_STALE_OR_FUTURE")
        bid, ask = number(q.get("bid"), positive=True), number(q.get("ask"), positive=True)
        if bid >= ask:
            raise Refused("CROSSED_QUOTE")
        return bid, ask

    def _gate(self, r: dict, q: dict, now_ms: int, book: sqlite3.Row):
        if set(r) != FIELDS or r.get("contract_version") != CONTRACT or r.get("authority") != "PAPER_ONLY":
            raise Refused("CONTRACT_OR_AUTHORITY_INVALID")
        spec = self.models[r["portfolio_id"]]
        if (r.get("model_id"), r.get("model_sha"), r.get("experiment_id"), r.get("contest_id")) != (
            spec.model_id, spec.model_sha, spec.experiment_id, spec.contest_id):
            raise Refused("MODEL_OR_CONTEST_NOT_PINNED")
        if r.get("execution_policy_version") != "mock-paper-v1":
            raise Refused("POLICY_NOT_PINNED")
        if type(r.get("sequence")) is not int or r["sequence"] != book["last_sequence"] + 1:
            raise Refused("REORDERED_SEQUENCE")
        if book["killed"]:
            raise Refused("BOOK_KILLED")
        a, x = r.get("as_of_ms"), r.get("expires_at_ms")
        if type(a) is not int or type(x) is not int or a > now_ms or a < now_ms - self.policy.max_recommendation_age_ms or x < now_ms or x <= a or x - a > self.policy.max_recommendation_age_ms:
            raise Refused("RECOMMENDATION_EXPIRED_OR_FUTURE")
        if not isinstance(r.get("event_id"), str) or not r["event_id"] or len(r["event_id"]) > 128:
            raise Refused("INVALID_EVENT")
        if not isinstance(r.get("idempotency_key"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", r["idempotency_key"]):
            raise Refused("INVALID_IDEMPOTENCY_KEY")
        if not isinstance(r.get("symbol"), str) or not re.fullmatch(r"[A-Z0-9]{4,18}", r["symbol"]):
            raise Refused("INVALID_SYMBOL")
        if r.get("side") not in ("LONG", "SHORT", "ABSTAIN"):
            raise Refused("INVALID_SIDE")
        if not isinstance(r.get("strategy_tag_ids"), list) or len(r["strategy_tag_ids"]) > 16 or not all(
            isinstance(s, str) and 0 < len(s) <= 80 for s in r["strategy_tag_ids"]):
            raise Refused("INVALID_STRATEGY_TAGS")
        if r["side"] == "ABSTAIN":
            return None
        if not r.get("btc_regime_version") or not r.get("coin_structure_version") or not r.get("entry_quote_reference"):
            raise Refused("MISSING_EVIDENCE_VERSION")
        if number(r.get("expected_after_cost_net_r")) < self.policy.min_expected_net_r:
            raise Refused("INSUFFICIENT_NET_EDGE")
        confidence = number(r.get("confidence"))
        if confidence < self.policy.min_confidence or confidence > 1:
            raise Refused("INSUFFICIENT_CONFIDENCE")
        bid, ask = self._quote(q, r["symbol"], a, now_ms)
        if q.get("reference") != r["entry_quote_reference"]:
            raise Refused("QUOTE_REFERENCE_MISMATCH")
        frozen_quote = self.db.execute(
            "SELECT * FROM shared_mock_quotes WHERE event_id=? AND symbol=?",
            (r["event_id"], r["symbol"])).fetchone()
        if frozen_quote and (
            frozen_quote["reference"], frozen_quote["observed_at_ms"],
            number(frozen_quote["bid"]), number(frozen_quote["ask"])) != (
            q["reference"], q["observed_at_ms"], bid, ask):
            raise Refused("SHARED_MARKET_SNAPSHOT_MISMATCH")
        stop = number(r.get("stop_price"), positive=True)
        slip = self.policy.slippage_rate_per_side
        entry = ask * (1 + slip) if r["side"] == "LONG" else bid * (1 - slip)
        distance = entry - stop if r["side"] == "LONG" else stop - entry
        if distance <= ZERO or entry <= ZERO:
            raise Refused("INVALID_STOP_GEOMETRY")
        positions = self.db.execute("SELECT * FROM positions WHERE portfolio=?", (r["portfolio_id"],)).fetchall()
        if len(positions) >= self.policy.max_positions:
            raise Refused("POSITION_LIMIT")
        if any(p["symbol"] == r["symbol"] for p in positions):
            raise Refused("DUPLICATE_OPEN_SYMBOL")
        wallet = number(book["wallet"], positive=True)
        risk_available = wallet * self.policy.max_total_open_risk - sum((number(p["risk"]) for p in positions), ZERO)
        notional_available = wallet * self.policy.max_gross_notional_multiple - sum(
            (number(p["qty"]) * number(p["entry"]) for p in positions), ZERO)
        if risk_available <= ZERO or notional_available <= ZERO:
            raise Refused("PORTFOLIO_RISK_EXHAUSTED")
        risk_budget = min(wallet * self.policy.max_risk_per_trade, risk_available)
        qty = min(risk_budget / distance, notional_available / entry)
        if qty <= ZERO:
            raise Refused("PORTFOLIO_RISK_EXHAUSTED")
        risk = qty * distance
        round_trip_cost = qty * entry * 2 * (self.policy.taker_fee_rate + slip)
        if round_trip_cost / risk > self.policy.max_cost_to_r:
            raise Refused("COST_TO_R_TOO_HIGH")
        return (entry, stop, qty, risk)

    def submit(self, recommendation: dict, signature: str, quote: dict, now_ms: int) -> dict:
        """Authenticated paper recommendation: returns immutable acceptance/abstain/veto."""
        if type(now_ms) is not int or not isinstance(recommendation, dict):
            return {"status": "REJECTED", "reason": "MALFORMED_REQUEST"}
        portfolio = recommendation.get("portfolio_id")
        if portfolio not in PORTFOLIOS or not isinstance(signature, str):
            return {"status": "REJECTED", "reason": "UNAUTHORIZED_PORTFOLIO"}
        try:
            payload = canonical(recommendation)
        except (TypeError, ValueError, OverflowError):
            return {"status": "REJECTED", "reason": "MALFORMED_REQUEST"}
        if len(payload) > MAX_SIGNED_MESSAGE_BYTES:
            return {"status": "REJECTED", "reason": "MESSAGE_SIZE_LIMIT"}
        expected = hmac.new(self.keys[portfolio], DOMAIN + payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return {"status": "REJECTED", "reason": "INVALID_SIGNATURE"}
        digest = hashlib.sha256(payload).hexdigest()
        idem = recommendation.get("idempotency_key")
        event_id = recommendation.get("event_id")
        symbol = recommendation.get("symbol")
        if not all(isinstance(v, str) for v in (idem, event_id, symbol)):
            return {"status": "REJECTED", "reason": "MALFORMED_REQUEST"}
        with self._tx() as c:
            previous = c.execute("SELECT payload_sha,result FROM decisions WHERE portfolio=? AND idem=?",
                                 (portfolio, idem)).fetchone()
            if previous:
                if previous["payload_sha"] != digest:
                    return {"status": "REJECTED", "reason": "IDEMPOTENCY_CONFLICT"}
                return {**json.loads(previous["result"]), "duplicate": True}
            if c.execute("SELECT 1 FROM decisions WHERE portfolio=? AND event_id=? AND symbol=?",
                         (portfolio, event_id, symbol)).fetchone():
                return {"status": "REJECTED", "reason": "DUPLICATE_EVENT"}
            book = c.execute("SELECT * FROM books WHERE portfolio=?", (portfolio,)).fetchone()
            execution = None
            try:
                execution = self._gate(recommendation, quote, now_ms, book)
                result = {"status": "ABSTAINED" if execution is None else "ACCEPTED",
                          "reason": "MODEL_ABSTAIN" if execution is None else "PAPER_FILLED"}
            except (Refused, KeyError, TypeError, ValueError) as exc:
                result = {"status": "REJECTED",
                          "reason": exc.reason if isinstance(exc, Refused) else "MALFORMED_REQUEST"}
            if result["status"] == "ACCEPTED":
                result["grade"] = "SYNTHETIC"
            decision_id = c.execute("SELECT COALESCE(MAX(id),0)+1 FROM decisions").fetchone()[0]
            result["decision_id"] = decision_id
            c.execute("""INSERT INTO decisions (id,portfolio,idem,payload_sha,event_id,symbol,as_of_ms,result)
                         VALUES (?,?,?,?,?,?,?,?)""", (decision_id, portfolio, idem, digest,
                             event_id, symbol,
                             recommendation.get("as_of_ms") if type(recommendation.get("as_of_ms")) is int else -1,
                             json.dumps(result, sort_keys=True)))
            if type(recommendation.get("sequence")) is int and recommendation["sequence"] == book["last_sequence"] + 1:
                c.execute("UPDATE books SET last_sequence=? WHERE portfolio=?", (recommendation["sequence"], portfolio))
            if execution is not None and result["status"] == "ACCEPTED":
                entry, stop, qty, risk = execution
                bid, ask = self._quote(quote, symbol, recommendation["as_of_ms"], now_ms)
                c.execute("""INSERT OR IGNORE INTO shared_mock_quotes
                    (event_id,symbol,reference,observed_at_ms,bid,ask)
                    VALUES (?,?,?,?,?,?)""",
                    (event_id, symbol, quote["reference"], quote["observed_at_ms"], str(bid), str(ask)))
                c.execute("INSERT INTO orders (portfolio,symbol,action,decision_id,at_ms) VALUES (?,?,?,?,?)",
                          (portfolio, symbol, "OPEN_SYNTHETIC", decision_id, now_ms))
                order_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                fee = entry * qty * self.policy.taker_fee_rate
                c.execute("""INSERT INTO fills (order_id,portfolio,symbol,price,qty,fee,at_ms,grade)
                             VALUES (?,?,?,?,?,?,?,'SYNTHETIC')""",
                          (order_id, portfolio, symbol, str(entry), str(qty), str(fee), now_ms))
                c.execute("""INSERT INTO positions
                    (portfolio,symbol,side,qty,entry,stop,risk,opened_ms,model_id,decision_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                          (portfolio, symbol, recommendation["side"], str(qty), str(entry),
                           str(stop), str(risk), now_ms, recommendation["model_id"], decision_id))
                wallet = number(book["wallet"]) - fee
                c.execute("UPDATE books SET wallet=? WHERE portfolio=?", (str(wallet), portfolio))
                c.execute("""INSERT INTO ledger (portfolio,category,delta,wallet_after,at_ms,source_id)
                             VALUES (?,?,?,?,?,?)""", (portfolio, "ENTRY_FEE", str(-fee), str(wallet), now_ms, order_id))
            return result

    def settle_synthetic(self, portfolio: str, symbol: str, quote: dict, now_ms: int) -> dict:
        """Offline-only synthetic exit. No live triggers, order submission or auto-stops."""
        if portfolio not in PORTFOLIOS or type(now_ms) is not int:
            return {"status": "REJECTED", "reason": "INVALID_PORTFOLIO_OR_CLOCK"}
        with self._tx() as c:
            p = c.execute("SELECT * FROM positions WHERE portfolio=? AND symbol=?", (portfolio, symbol)).fetchone()
            if not p:
                return {"status": "REJECTED", "reason": "NO_OPEN_POSITION"}
            if now_ms <= p["opened_ms"]:
                return {"status": "REJECTED", "reason": "NON_FORWARD_EXIT"}
            try:
                bid, ask = self._quote(quote, symbol, p["opened_ms"], now_ms)
            except Refused as exc:
                return {"status": "REJECTED", "reason": exc.reason}
            entry, qty = number(p["entry"]), number(p["qty"])
            slip = self.policy.slippage_rate_per_side
            exit_price = bid * (1 - slip) if p["side"] == "LONG" else ask * (1 + slip)
            gross = (exit_price - entry) * qty * (1 if p["side"] == "LONG" else -1)
            fee = exit_price * qty * self.policy.taker_fee_rate
            entry_fee = entry * qty * self.policy.taker_fee_rate
            elapsed = DEC(now_ms - p["opened_ms"]) / DEC(28800000)
            funding = entry * qty * self.policy.adverse_funding_rate_per_8h * elapsed
            net = gross - fee - entry_fee - funding
            c.execute("INSERT INTO orders (portfolio,symbol,action,decision_id,at_ms) VALUES (?,?,?,?,?)",
                      (portfolio, symbol, "CLOSE_SYNTHETIC", p["decision_id"], now_ms))
            order_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("""INSERT INTO fills (order_id,portfolio,symbol,price,qty,fee,at_ms,grade)
                         VALUES (?,?,?,?,?,?,?,'SYNTHETIC')""",
                      (order_id, portfolio, symbol, str(exit_price), str(qty), str(fee), now_ms))
            previous = number(c.execute("SELECT wallet FROM books WHERE portfolio=?", (portfolio,)).fetchone()[0])
            wallet = previous + gross - fee - funding
            c.execute("INSERT INTO ledger (portfolio,category,delta,wallet_after,at_ms,source_id) VALUES (?,?,?,?,?,?)",
                      (portfolio, "SETTLEMENT_NET_OF_EXIT_FEE_FUNDING", str(gross-fee-funding),
                       str(wallet), now_ms, order_id))
            c.execute("""INSERT INTO settled
                         (portfolio,symbol,position_id,opened_ms,closed_ms,gross_pnl,entry_fee,
                          exit_fee,funding,net_pnl,grade)
                         VALUES (?,?,?,?,?,?,?,?,?,?,'SYNTHETIC')""",
                      (portfolio, symbol, p["id"], p["opened_ms"], now_ms, str(gross),
                       str(entry_fee), str(fee), str(funding), str(net)))
            peak = max(wallet, number(c.execute("SELECT peak_wallet FROM books WHERE portfolio=?",
                                               (portfolio,)).fetchone()[0]))
            drawdown_kill = wallet <= peak * (1 - self.policy.max_realized_drawdown)
            c.execute("UPDATE books SET wallet=?,peak_wallet=?,killed=CASE WHEN ? THEN 1 ELSE killed END WHERE portfolio=?",
                      (str(wallet), str(peak), int(drawdown_kill), portfolio))
            c.execute("DELETE FROM positions WHERE id=?", (p["id"],))
            return {"status": "SETTLED", "grade": "SYNTHETIC", "gross_pnl": str(gross),
                    "fees": str(entry_fee + fee), "funding": str(funding),
                    "net_pnl": str(net), "wallet": str(wallet)}

    def kill_book(self, portfolio: str):
        """One-way within this foundation; reactivation requires separately reviewed code."""
        if portfolio not in PORTFOLIOS:
            raise ValueError("invalid portfolio")
        with self._tx() as c:
            c.execute("UPDATE books SET killed=1 WHERE portfolio=?", (portfolio,))

    def report(self, portfolio: str) -> dict:
        if portfolio not in PORTFOLIOS:
            raise ValueError("invalid portfolio")
        book = self.db.execute("SELECT * FROM books WHERE portfolio=?", (portfolio,)).fetchone()
        positions = self.db.execute("SELECT symbol,side,entry,qty,risk FROM positions WHERE portfolio=? ORDER BY symbol",
                                    (portfolio,)).fetchall()
        settled = self.db.execute("SELECT count(*) FROM settled WHERE portfolio=?", (portfolio,)).fetchone()[0]
        wallet, peak = number(book["wallet"]), number(book["peak_wallet"])
        return {"portfolio": portfolio, "model_id": book["model_id"], "wallet": str(wallet),
                "peak_realized_wallet": str(peak),
                "realized_drawdown_fraction": str(max(ZERO, (peak-wallet)/peak)),
                "open_positions": [dict(x) for x in positions],
                "settled_count": settled, "last_sequence": book["last_sequence"],
                "killed": bool(book["killed"]), "grade": "SYNTHETIC",
                "equity_mark_to_market": "UNAVAILABLE_REQUIRES_INDEPENDENT_MARKS"}

    def integrity(self) -> str:
        return self.db.execute("PRAGMA integrity_check").fetchone()[0]
