"""G7 one engine, two independent event-sourced paper books.

No network or exchange client exists. Default and restart state is LOCKED.
Every release needs an independently authenticated, expiring gate bundle.
Missing original fee/slippage/funding proof never becomes a zero cost.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from nbot.v5.research_store import ResearchStore
from nbot.v5.science import canonical, digest, sha, verify_review

BOOKS = ("CHAMPION_PAPER", "CHALLENGER_PAPER")
DOMAIN = b"NBOT-V5-PAPER-ENVELOPE-V2\n"


def dec(x, positive=False):
    if not isinstance(x, str) or len(x) > 80:
        raise ValueError("PAPER_DECIMAL_REQUIRED")
    try:
        v = Decimal(x)
    except InvalidOperation as exc:
        raise ValueError("PAPER_NUMBER_INVALID") from exc
    if not v.is_finite() or (positive and v <= 0):
        raise ValueError("PAPER_NUMBER_INVALID")
    return v


def sign(body, key):
    return hmac.new(key, DOMAIN + canonical(body).encode(), hashlib.sha256).hexdigest()


class GuardedPaper:
    def __init__(self, path, *, policy, models=None, keys=None, reviewer_key=None, synthetic=False):
        self.policy = json.loads(canonical(policy))
        required = {"capital", "risk_fraction", "max_open_risk", "max_exposure_multiple", "max_positions",
                    "max_drawdown_fraction", "min_lower_net_r", "max_quote_age_ms", "max_message_age_ms"}
        if set(policy) != required:
            raise ValueError("PAPER_POLICY_SHAPE")
        for k in required - {"max_positions", "max_quote_age_ms", "max_message_age_ms"}:
            dec(policy[k], True)
        if (not 0 < dec(policy["risk_fraction"]) <= dec(policy["max_open_risk"]) <= Decimal("0.02")
                or not 0 < dec(policy["max_drawdown_fraction"]) <= Decimal("0.1")
                or not 0 < dec(policy["max_exposure_multiple"]) <= 1
                or type(policy["max_positions"]) is not int or not 1 <= policy["max_positions"] <= 10
                or type(policy["max_quote_age_ms"]) is not int or not 1 <= policy["max_quote_age_ms"] <= 1000
                or type(policy["max_message_age_ms"]) is not int or not 1 <= policy["max_message_age_ms"] <= 5000):
            raise ValueError("PAPER_RISK_POLICY_WEAKENED")
        self.models, self.keys = models or {}, keys or {}
        self.reviewer_key, self.synthetic = reviewer_key, synthetic
        self.release = None
        self.store = ResearchStore(path, paper=True)
        try:
            self.store.append("paper-policy", "POLICY", 0, {"policy": self.policy, "grade": "SYNTHETIC" if synthetic else "ORIGINAL"})
            self.reconcile()
        except BaseException:
            self.store.close()
            raise

    def unlock(self, envelope, now_ms):
        # No runtime key defaults. A synthetic release cannot enter original DB.
        stage = envelope.get("body", {}).get("release_stage", "COMPARISON") if isinstance(envelope, dict) else "COMPARISON"
        allowed = {BOOKS[0]} if stage == "CHAMPION_ONLY" else set(BOOKS)
        if stage not in ("CHAMPION_ONLY", "COMPARISON"):
            raise ValueError("PAPER_RELEASE_STAGE_INVALID")
        if set(self.models) != allowed or set(self.keys) != allowed:
            raise ValueError("PAPER_TWO_QUALIFIED_MODELS_REQUIRED")
        if (any(not isinstance(k, bytes) or len(k) < 32 for k in self.keys.values())
                or (len(allowed) == 2 and self.keys[BOOKS[0]] == self.keys[BOOKS[1]])):
            raise ValueError("PAPER_SEPARATE_KEYS_REQUIRED")
        subject = digest({"models": self.models, "policy": self.policy,
                          "grade": "SYNTHETIC" if self.synthetic else "ORIGINAL"})
        body = verify_review(envelope, key=self.reviewer_key, subject_sha256=subject,
                             purpose="G7_PAPER_RELEASE", now_ms=now_ms)
        gates = ("g5_accepted", "g7_accepted", "champion_qualified")
        if not self.synthetic:
            gates += ("owner_paper_authorized",)
        if stage == "COMPARISON":
            gates += ("g6_accepted", "challenger_qualified")
        else:
            # Roadmap sections 18.3 and 19 authorize the first Champion stage,
            # but require a NEW explicit authenticated release, never fallback
            # from a failing two-model release or an unsigned configuration.
            gates += ("owner_paper_authorized", "g6_champion_validation_accepted")
        if (any(body.get(k) is not True for k in gates)
                or body.get("grade") != ("SYNTHETIC" if self.synthetic else "ORIGINAL")):
            raise ValueError("PAPER_SCIENTIFIC_GATES_LOCKED")
        for model in self.models.values():
            if not sha(model) or self.store.db.execute(
                    "SELECT 1 FROM research_journal WHERE identity=?",
                    ("model-revoked:"+model,)).fetchone():
                raise ValueError("PAPER_MODEL_INVALID_OR_REVOKED")
        self.release = envelope
        self.store.append("release:"+digest(envelope), "RELEASE", now_ms, envelope)

    def revoke_model(self, model_sha256, envelope, now_ms):
        body = verify_review(envelope, key=self.reviewer_key,
                             subject_sha256=model_sha256,
                             purpose="G7_MODEL_REVOCATION", now_ms=now_ms)
        if body.get("grade") != ("SYNTHETIC" if self.synthetic else "ORIGINAL"):
            raise ValueError("PAPER_REVOCATION_GRADE")
        self.store.append("model-revoked:"+model_sha256,"MODEL_REVOKED",now_ms,
                          {"model_sha256":model_sha256,"review":envelope})
        self.kill("MODEL_APPROVAL_REVOKED",now_ms)

    def kill(self, reason, now_ms):
        self.release = None
        self.store.append("kill:"+digest([reason, now_ms]), "KILL", now_ms, {"reason": reason})

    def _records(self):
        return [(kind, json.loads(raw)) for kind, raw in self.store.db.execute("SELECT kind,body FROM research_journal ORDER BY seq")]

    def project(self):
        state = {b: {"cash": dec(self.policy["capital"]), "peak": dec(self.policy["capital"]),
                     "positions": {}, "fees": Decimal(0), "funding": Decimal(0), "realized": Decimal(0), "fills": 0} for b in BOOKS}
        for kind, body in self._records():
            if kind not in ("OPEN", "CLOSE"):
                continue
            book = state[body["book"]]
            if kind == "OPEN":
                if body["symbol"] in book["positions"]:
                    raise ValueError("PAPER_RECONCILE_DUPLICATE_POSITION")
                book["positions"][body["symbol"]] = body
                book["cash"] -= dec(body["fee"])
                book["fees"] += dec(body["fee"])
            else:
                old = book["positions"].pop(body["symbol"], None)
                if old is None or old["decision_id"] != body["decision_id"]:
                    raise ValueError("PAPER_RECONCILE_ORPHAN_SETTLEMENT")
                gross = (dec(body["price"])-dec(old["price"]))*dec(old["qty"])*(1 if old["side"] == "LONG" else -1)
                if gross != dec(body["gross"]):
                    raise ValueError("PAPER_RECONCILE_PNL_MISMATCH")
                book["cash"] += gross-dec(body["fee"])-dec(body["funding"])
                book["fees"] += dec(body["fee"])
                book["funding"] += dec(body["funding"])
                book["realized"] += gross-dec(body["fee"])-dec(body["funding"])-dec(old["fee"])
                book["peak"] = max(book["peak"], book["cash"])
            book["fills"] += 1
        return state

    def reconcile(self):
        audit = self.store.audit()
        state = self.project()
        for b, book in state.items():
            balance = dec(self.policy["capital"])+book["realized"]-sum(dec(p["fee"]) for p in book["positions"].values())
            if balance != book["cash"]:
                raise ValueError("PAPER_CASH_RECONCILE_MISMATCH")
        return {**audit, "books": {b: {"cash": str(s["cash"]), "positions": len(s["positions"]), "fills": s["fills"],
                                       "fees": str(s["fees"]), "funding": str(s["funding"]), "realized": str(s["realized"])} for b, s in state.items()},
                "paper_state": "LOCKED" if self.release is None else "RELEASE_REQUIRES_PER_ACTION_VERIFICATION",
                "real_money_authority": "NONE"}

    def _quote(self, q, now_ms, symbol):
        if (not isinstance(q, dict) or q.get("symbol") != symbol or not sha(q.get("receipt_sha256"))
                or type(q.get("at_ms")) is not int or not 0 <= now_ms-q["at_ms"] <= self.policy["max_quote_age_ms"]
                or q.get("source_verified") is not True or q.get("grade") != ("SYNTHETIC" if self.synthetic else "ORIGINAL")):
            raise ValueError("PAPER_QUOTE_UNVERIFIED_OR_STALE")
        bid, ask = dec(q["bid"], True), dec(q["ask"], True)
        if bid >= ask or (ask-bid)/bid > Decimal("0.01"):
            raise ValueError("PAPER_QUOTE_CROSSED_OR_WIDE")
        if not self.synthetic:
            verify_review(q.get("independent_review"), key=self.reviewer_key,
                          subject_sha256=digest({k: v for k, v in q.items() if k != "independent_review"}),
                          purpose="G7_QUOTE", now_ms=now_ms)
        return bid, ask

    def _economics(self, e, now_ms):
        if (not isinstance(e, dict) or e.get("grade") != ("SYNTHETIC" if self.synthetic else "ORIGINAL")
                or e.get("independently_verified") is not True
                or not all(sha(e.get(k)) for k in ("fee_receipt_sha256", "slippage_policy_sha256", "funding_receipt_sha256"))):
            raise ValueError("PAPER_COST_PROOF_MISSING")
        fee, slip = dec(e["fee_rate"]), dec(e["slippage_rate"])
        if not 0 <= fee <= Decimal("0.01") or not 0 <= slip <= Decimal("0.01"):
            raise ValueError("PAPER_COST_BOUNDS")
        if not self.synthetic:
            verify_review(e.get("independent_review"), key=self.reviewer_key,
                          subject_sha256=digest({k: v for k, v in e.items() if k != "independent_review"}),
                          purpose="G7_COST", now_ms=now_ms)
        return fee, slip

    def submit(self, envelope, quote, economics, now_ms):
        body = envelope.get("body", {}) if isinstance(envelope, dict) else {}
        identity = "decision:"+digest(body)
        previous = self.store.db.execute("SELECT body FROM research_journal WHERE identity=?", (identity,)).fetchone()
        if previous:
            return {"duplicate": True, **json.loads(previous[0])}
        try:
            if self.release is None:
                raise ValueError("G7_PAPER_LOCKED")
            verify_review(self.release, key=self.reviewer_key,
                          subject_sha256=digest({"models": self.models, "policy": self.policy, "grade": "SYNTHETIC" if self.synthetic else "ORIGINAL"}),
                          purpose="G7_PAPER_RELEASE", now_ms=now_ms)
            book = body.get("book")
            if book not in self.models or not hmac.compare_digest(envelope.get("signature", ""), sign(body, self.keys[book])):
                raise ValueError("PAPER_AUTHENTICATION_FAILED")
            if (body.get("version") != "NBOT_V5_PAPER_V2" or body.get("model_sha256") != self.models[book]
                    or body.get("authority") != "PAPER" or body.get("side") not in ("LONG", "SHORT")
                    or not sha(body.get("decision_id")) or type(body.get("at_ms")) is not int
                    or type(body.get("expires_ms")) is not int
                    or not body["at_ms"] <= now_ms < body["expires_ms"]
                    or now_ms-body["at_ms"] > self.policy["max_message_age_ms"]
                    or body.get("source_quality_ok") is not True or body.get("regime_gate_ok") is not True
                    or dec(body["lower_net_r"]) < dec(self.policy["min_lower_net_r"])):
                raise ValueError("PAPER_RECOMMENDATION_GATE")
            if any(k == "OPEN" and b["book"] == book and b["decision_id"] == body["decision_id"] for k, b in self._records()):
                raise ValueError("PAPER_REPLAY_DECISION")
            state = self.project()[book]
            positions = state["positions"]
            if (body["symbol"] in positions or len(positions) >= self.policy["max_positions"]
                    or any(p["risk_group"] == body["risk_group"] for p in positions.values())):
                raise ValueError("PAPER_POSITION_OR_CORRELATION_LIMIT")
            # New entries abstain while any older position lacks a fresh mark.
            if positions:
                raise ValueError("PAPER_PORTFOLIO_MARKS_REQUIRED")
            if state["cash"] <= state["peak"]*(1-dec(self.policy["max_drawdown_fraction"])):
                raise ValueError("PAPER_DRAWDOWN_KILL")
            bid, ask = self._quote(quote, now_ms, body["symbol"])
            fee_rate, slip = self._economics(economics, now_ms)
            price = ask*(1+slip) if body["side"] == "LONG" else bid*(1-slip)
            stop, target = dec(body["stop"], True), dec(body["target"], True)
            sign_side = 1 if body["side"] == "LONG" else -1
            risk_per_unit = (price-stop)*sign_side
            if risk_per_unit <= 0 or (target-price)*sign_side <= 0:
                raise ValueError("PAPER_STOP_TARGET_GEOMETRY")
            risk = state["cash"]*dec(self.policy["risk_fraction"])
            qty = risk/risk_per_unit
            exposure = qty*price
            if (risk > state["cash"]*dec(self.policy["max_open_risk"])
                    or exposure > state["cash"]*dec(self.policy["max_exposure_multiple"])):
                raise ValueError("PAPER_EXPOSURE_VETO")
            result = {"status": "PAPER_FILLED", "book": book, "decision_id": body["decision_id"], "symbol": body["symbol"],
                      "side": body["side"], "price": str(price), "qty": str(qty), "risk": str(risk), "fee": str(exposure*fee_rate),
                      "stop": str(stop), "target": str(target), "at_ms": now_ms, "risk_group": body["risk_group"],
                      "model_sha256": body["model_sha256"], "quote_sha256": quote["receipt_sha256"], "cost_sha256": digest(economics),
                      "grade": "SYNTHETIC" if self.synthetic else "ORIGINAL", "real_money_authority": "NONE"}
            kind = "OPEN"
        except (ValueError, KeyError, TypeError) as exc:
            result, kind = {"status": "REJECTED", "reason": str(exc), "orders_created": 0, "real_money_authority": "NONE"}, "REJECT"
        self.store.append(identity, kind, now_ms, result)
        return result

    def exit(self, book, symbol, quote, economics, now_ms, *, horizon_ms=14400000):
        if horizon_ms != 14400000:
            raise ValueError("PAPER_HORIZON_NOT_FROZEN")
        position = self.project()[book]["positions"].get(symbol)
        if position is None:
            raise ValueError("PAPER_NO_POSITION")
        if type(now_ms) is not int or now_ms <= position["at_ms"]:
            raise ValueError("PAPER_EXIT_NOT_FORWARD")
        bid, ask = self._quote(quote, now_ms, symbol)
        fee, slip = self._economics(economics, now_ms)
        side = 1 if position["side"] == "LONG" else -1
        mark = bid if side == 1 else ask
        stop, target = dec(position["stop"]), dec(position["target"])
        if not ((mark-stop)*side <= 0 or (mark-target)*side >= 0 or now_ms-position["at_ms"] >= horizon_ms):
            return {"status": "OPEN", "unrealized": str((mark-dec(position["price"]))*side*dec(position["qty"]))}
        if (type(economics.get("funding_coverage_from_ms")) is not int
                or type(economics.get("funding_coverage_to_ms")) is not int
                or economics["funding_coverage_from_ms"] > position["at_ms"]
                or economics["funding_coverage_to_ms"] < now_ms):
            raise ValueError("PAPER_SETTLED_FUNDING_MISSING")
        funding = dec(economics["funding_quote"])
        price = bid*(1-slip) if side == 1 else ask*(1+slip)
        qty = dec(position["qty"])
        gross = (price-dec(position["price"]))*side*qty
        result = {"book": book, "symbol": symbol, "decision_id": position["decision_id"], "price": str(price), "qty": str(qty),
                  "gross": str(gross), "fee": str(price*qty*fee), "funding": str(funding), "at_ms": now_ms,
                  "quote_sha256": quote["receipt_sha256"], "cost_sha256": digest(economics), "status": "PAPER_SETTLED",
                  "grade": "SYNTHETIC" if self.synthetic else "ORIGINAL", "real_money_authority": "NONE"}
        self.store.append("settlement:"+digest([book, position["decision_id"]]), "CLOSE", now_ms, result)
        return result
