# ==========================================================
# Strategy — 5M Structured Conservative (Engine Compatible)
# ==========================================================

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional
from strategy.trade_intent import TradeIntent
import os
import pickle
import numpy as np
import json
import threading
from config import RISK_PER_TRADE_USD, MAX_NOTIONAL_USD
from strategy.structure_classifier import StructureClassifier

class Strategy:

    def __init__(self, max_history: int = 200, system_log=None):
        self.system_log = system_log
        # -----------------------------
        # Candle Storage
        # -----------------------------
        self._current_candle: Dict[str, dict] = {}
        self._candle_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        self._last_ts: Dict[str, int] = {}
        self._universe = set()
        self._warmed_up = False

        self._classifier = StructureClassifier()
        self._latest_structure = {}

        # ------------------------------------
        # ML Edge Model (Optional)
        # ------------------------------------
        self._model_path = "models/edge_model.pkl"
        self._model_mtime = None
        self._ml_model = None
        self._scaler = None
        self._ml_threshold = 0.50  # minimum probability required
        self._model_schema_version = 2
        self._ml_feature_names = (
            "short_range",
            "long_range",
            "trend_score",
            "wick_ratio_recent",
            "body_ratio_recent",
            "range_acceleration",
            "dist_high",
            "dist_low",
            "directional_consistency",
        )

        self._load_model_if_exists()
        # ------------------------------------
        # ML Forward Simulation Dataset
        # ------------------------------------
        self._ml_dataset_path = "ml_dataset.jsonl"
        self._pending_simulations = []
        self._ml_lock = threading.Lock()
        self.MAX_FORWARD_CANDLES = 120  # 10 hours on 5m

        # -----------------------------
        # Trade Governor (UNCHANGED)
        # -----------------------------
        self._last_trade_info = {}  # {symbol: (bucket, direction)}
        # Last current-candle bucket evaluated per symbol. Since the
        # strategy uses completed candles only, a new current bucket means
        # exactly one newly closed 5-minute candle is available.
        self._last_evaluated_bucket = {}
        self.COUNTER_TRADE_SPACING_BUCKETS = 6

        # -----------------------------
        # 5M Windows
        # -----------------------------
        self.SHORT_WINDOW = 10
        self.LONG_WINDOW = 30
        self.WARMUP_WINDOW = 50

    # ======================================================
    # ML Hot Reload
    # ======================================================

    def _load_model_if_exists(self):

        if not os.path.exists(self._model_path):
            return

        mtime = None

        try:
            mtime = os.path.getmtime(self._model_path)
            if self._model_mtime == mtime:
                return

            with open(self._model_path, "rb") as f:
                artifact = pickle.load(f)

            if not isinstance(artifact, dict):
                raise RuntimeError("LEGACY_MODEL_ARTIFACT_UNSUPPORTED")

            schema_version = artifact.get("schema_version")
            feature_names = tuple(artifact.get("feature_names", ()))
            scaler = artifact.get("scaler")
            model = artifact.get("model")

            if schema_version != self._model_schema_version:
                raise RuntimeError(
                    f"MODEL_SCHEMA_MISMATCH | expected={self._model_schema_version} "
                    f"actual={schema_version}"
                )
            if feature_names != self._ml_feature_names:
                raise RuntimeError(
                    "MODEL_FEATURE_ORDER_MISMATCH | "
                    f"expected={self._ml_feature_names} actual={feature_names}"
                )
            if scaler is None or model is None:
                raise RuntimeError("MODEL_ARTIFACT_INCOMPLETE")

            expected_count = len(self._ml_feature_names)
            scaler_count = getattr(scaler, "n_features_in_", expected_count)
            model_count = getattr(model, "n_features_in_", expected_count)
            if scaler_count != expected_count or model_count != expected_count:
                raise RuntimeError(
                    "MODEL_FEATURE_COUNT_MISMATCH | "
                    f"expected={expected_count} scaler={scaler_count} model={model_count}"
                )

            # Install only after the entire artifact passes validation. A bad
            # hot-reload never replaces the last known-good in-memory model.
            self._scaler = scaler
            self._ml_model = model
            self._model_mtime = mtime

            if self.system_log:
                self.system_log.info(
                    f"ML_MODEL_LOADED | schema={schema_version} | "
                    f"features={expected_count}"
                )

        except Exception as e:
            # Quarantine this exact rejected artifact. It will be retried only
            # after the model file is replaced and its modification time changes.
            if mtime is not None:
                self._model_mtime = mtime

            if self.system_log:
                self.system_log.error(
                    f"ML_MODEL_REJECTED | mtime={mtime} | error={e}"
                )

    # ======================================================
    # Candle Builder (5M)
    # ======================================================

    def on_price(self, symbol: str, price: float, timestamp: int):

        # The exchange price stream may contain every listed contract. The
        # strategy must build candles only for the active selected universe.
        if self._universe and symbol not in self._universe:
            return

        bucket = timestamp // 300000  # 5m bucket

        candle = self._current_candle.get(symbol)

        if candle is None or candle["bucket"] != bucket:

            if candle is not None:
                self._candle_history[symbol].append(
                    (
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                    )
                )

                # Keep the latest market-structure fingerprint aligned
                # with the newest completed 5-minute candle.
                try:
                    self._latest_structure[symbol] = self._classifier.fingerprint(
                        list(self._candle_history[symbol])
                    )
                except Exception as e:
                    if self.system_log:
                        self.system_log.error(
                            f"STRUCTURE_FINGERPRINT_ERROR | "
                            f"symbol={symbol} | error={e}"
                        )

                # Update forward simulations
                self._update_simulations(symbol)

            self._current_candle[symbol] = {
                "bucket": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }

        else:
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        self._last_ts[symbol] = timestamp

        # Warmup check
        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

    # ======================================================
    # Historical Warmup Seeder
    # ======================================================

    def seed_candle_history(self, symbol: str, candles) -> int:
        """
        Replace one symbol's completed history with closed REST candles.

        UniverseManager calls this while preparing newly added symbols,
        before committing the new universe to Strategy. Therefore this
        method must not reject a symbol merely because it is not yet in
        self._universe.
        """
        ordered = sorted(candles, key=lambda item: int(item[0]))
        history = self._candle_history[symbol]
        history.clear()

        last_bucket = None

        for timestamp, o, h, l, c in ordered:
            bucket = int(timestamp) // 300000

            # Defensive de-duplication for repeated REST rows.
            if bucket == last_bucket:
                continue

            o = float(o)
            h = float(h)
            l = float(l)
            c = float(c)

            if min(o, h, l, c) <= 0:
                continue
            if h < max(o, c) or l > min(o, c) or h < l:
                continue

            history.append((o, h, l, c))
            last_bucket = bucket

        # Historical rows are completed candles. The current live candle must
        # be created only by the first live tick received after startup.
        self._current_candle.pop(symbol, None)
        self._last_ts.pop(symbol, None)
        self._last_evaluated_bucket.pop(symbol, None)

        if history:
            try:
                self._latest_structure[symbol] = self._classifier.fingerprint(
                    list(history)
                )
            except Exception as e:
                if self.system_log:
                    self.system_log.error(
                        f"STRUCTURE_FINGERPRINT_ERROR | symbol={symbol} | error={e}"
                    )

        self._warmed_up = bool(
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        )

        return len(history)

    # ======================================================
    # Warmup Seeder (UNCHANGED CONTRACT)
    # ======================================================

    def seed_candle(
        self,
        symbol: str,
        o: float,
        h: float,
        l: float,
        c: float,
        timestamp: int,
    ):

        bucket = timestamp // 300000

        self._candle_history[symbol].append((o, h, l, c))

        candles = list(self._candle_history[symbol])

        if len(candles) < 20:
            return

        try:
            fingerprint = self._classifier.fingerprint(candles)
            self._latest_structure[symbol] = fingerprint
        except Exception as e:
            if self.system_log:
                self.system_log.error(
                    f"STRUCTURE_FINGERPRINT_ERROR | symbol={symbol} | error={e}"
                )
        self._current_candle[symbol] = {
            "bucket": bucket,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
        }

        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

    # ======================================================
    # Universe
    # ======================================================

    def set_universe(self, symbols):
        self._universe = set(symbols)

    def get_structure(self, symbol):
        return self._latest_structure.get(symbol)

    def is_warmed_up(self) -> bool:
        return self._warmed_up

    # ======================================================
    # Helpers
    # ======================================================

    def _counter_trade_spacing_ok(self, symbol, bucket, direction):
        """
        Prevent immediate counter-trade.
        Allow same-direction continuation.
        """
        last = self._last_trade_info.get(symbol)

        if last is None:
            return True

        last_bucket, last_direction = last

        # Only block opposite direction
        if last_direction != direction:
            return (
                bucket - last_bucket
            ) >= self.COUNTER_TRADE_SPACING_BUCKETS

        return True

    def _avg_range(self, candles, window):
        if len(candles) < window:
            return None
        recent = list(candles)[-window:]
        ranges = [(c[1] - c[2]) for c in recent]
        return sum(ranges) / len(ranges)

    def _trend_score(self, candles):
        c_list = list(candles)
        closes = [c[3] for c in c_list[-10:]]
        score = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                score += 1
            elif closes[i] < closes[i - 1]:
                score -= 1
        return score

    def _strong_pullback(self, candles):
        if len(candles) < 5:
            return False

        last3 = list(candles)[-3:]
        r0 = last3[0][1] - last3[0][2]
        r1 = last3[1][1] - last3[1][2]
        r2 = last3[2][1] - last3[2][2]

        return r1 < r0 and r2 < r1

    def _breakout_score(self, candles):
        c_list = list(candles)

        highs = [c[1] for c in c_list[-20:]]
        lows = [c[2] for c in c_list[-20:]]
        last_close = c_list[-1][3]

        if last_close > max(highs[:-1]):
            return 4
        if last_close < min(lows[:-1]):
            return 4
        return 0

    # --------------------------------------------------
    # STRUCTURE QUALITY SCORE
    # --------------------------------------------------

    def _structure_score(self, candles):

        trend = abs(self._trend_score(candles)) / 10.0

        ranges = [(c[1] - c[2]) for c in candles]

        short = sum(ranges[-5:]) / 5
        long = sum(ranges) / len(ranges)

        volatility = short / long if long > 0 else 0

        breakout = abs(self._breakout_score(candles))

        pullback = 1.0 if self._strong_pullback(candles) else 0.0

        score = (
            0.35 * trend +
            0.30 * volatility +
            0.20 * breakout +
            0.15 * pullback
        )

        return score

    def _is_compressing(self, candles):
        """
        Strong compression:
        - Last 8 candles tighter than prior 12
        - AND bodies shrinking
        """

        if len(candles) < 25:
            return False

        c = list(candles)

        recent = c[-8:]
        prior = c[-20:-8]

        recent_range = sum(x[1] - x[2] for x in recent) / len(recent)
        prior_range = sum(x[1] - x[2] for x in prior) / len(prior)

        if prior_range <= 0:
            return False

        # Volatility compression
        if recent_range >= (0.65 * prior_range):
            return False

        # Body contraction
        recent_body = sum(abs(x[3] - x[0]) for x in recent) / len(recent)
        prior_body = sum(abs(x[3] - x[0]) for x in prior) / len(prior)

        if recent_body >= prior_body:
            return False

        return True

    def _has_directional_bias(self, candles):
        """
        Require directional push before breakout.
        Prevents entering random spikes.
        """

        if len(candles) < 15:
            return False

        closes = [c[3] for c in list(candles)[-10:]]

        up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_moves = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])

        return max(up_moves, down_moves) >= 6

    # ==========================================================
    # Machine Learning
    # ==========================================================
    def _build_ml_features(self, candles):
        """
        Expanded structural feature vector.
        Designed for early adverse-move learning.
        """

        c = list(candles)
        last_close = c[-1][3]

        short_range = self._avg_range(candles, self.SHORT_WINDOW)
        long_range = self._avg_range(candles, self.LONG_WINDOW)
        trend_score = self._trend_score(candles)

        # --------------------------------------------------
        # Wick ratio (last 5 candles)
        # --------------------------------------------------
        recent = c[-5:]
        wick_ratios = []
        body_ratios = []

        for o, h, l, cl in recent:
            total = h - l
            if total <= 0:
                continue
            body = abs(cl - o)
            wick = total - body
            wick_ratios.append(wick / total)
            body_ratios.append(body / total)

        wick_ratio_recent = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0
        body_ratio_recent = sum(body_ratios) / len(body_ratios) if body_ratios else 0

        # --------------------------------------------------
        # Range acceleration (short vs long)
        # --------------------------------------------------
        range_acceleration = (
            (short_range / long_range)
            if short_range and long_range and long_range > 0
            else 0
        )

        # --------------------------------------------------
        # Distance from 20 high/low
        # --------------------------------------------------
        highs_20 = [x[1] for x in c[-20:]]
        lows_20 = [x[2] for x in c[-20:]]

        dist_high = (
            (last_close - max(highs_20)) / last_close
            if highs_20 else 0
        )

        dist_low = (
            (last_close - min(lows_20)) / last_close
            if lows_20 else 0
        )

        # --------------------------------------------------
        # Directional consistency (last 6 closes)
        # --------------------------------------------------
        closes = [x[3] for x in c[-6:]]
        up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_moves = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
        directional_consistency = max(up_moves, down_moves)

        return np.array([
            short_range / last_close if short_range else 0,
            long_range / last_close if long_range else 0,
            trend_score,
            wick_ratio_recent,
            body_ratio_recent,
            range_acceleration,
            dist_high,
            dist_low,
            directional_consistency,
        ]).reshape(1, -1)

    # ======================================================
    # Forward Simulation Labeling
    # ======================================================
    def _update_simulations(self, symbol):

        candles = self._candle_history.get(symbol)
        if not candles:
            return

        latest = candles[-1]
        high = latest[1]
        low = latest[2]

        finished = []

        with self._ml_lock:
            for sim in self._pending_simulations:

                # A newly closed candle may update only simulations for
                # the same symbol. Cross-symbol prices would corrupt MAE,
                # MFE, candle counts, and every resulting training label.
                if sim["symbol"] != symbol:
                    continue

                entry = sim["entry_price"]
                direction = sim["direction"]
                risk = sim["risk_distance"]

                # Convert to R units
                if direction == "LONG":
                    adverse_move = (entry - low) / risk
                    favorable_move = (high - entry) / risk
                else:
                    adverse_move = (high - entry) / risk
                    favorable_move = (entry - low) / risk

                sim["mae"] = max(sim["mae"], adverse_move)
                sim["mfe"] = max(sim["mfe"], favorable_move)

                sim["candles_seen"] += 1

                # --- EARLY WEAKNESS LABEL ---
                label = None

                # After first 3 candles decide
                if sim["candles_seen"] == 3:
                    if sim["mae"] >= 0.5:
                        label = 1  # BAD ENTRY
                    else:
                        label = 0  # GOOD ENTRY

                # Hard stop at 5 candles to finalize dataset row
                if sim["candles_seen"] >= self.MAX_FORWARD_CANDLES:

                    target_r = sim["mfe"] - sim["mae"]

                    row = {
                        "schema_version": 2,
                        "observation_type": "FORWARD_SIMULATION",
                        "timestamp": int(time.time()),
                        "symbol": sim["symbol"],
                        "direction": sim["direction"],
                        "structure": str(sim["structure_fingerprint"].get("structure"))
                        if sim.get("structure_fingerprint") else None,
                        "trend": str(sim["structure_fingerprint"].get("trend"))
                        if sim.get("structure_fingerprint") else None,
                        "volatility": str(sim["structure_fingerprint"].get("volatility"))
                        if sim.get("structure_fingerprint") else None,
                        "compression": str(sim["structure_fingerprint"].get("compression"))
                        if sim.get("structure_fingerprint") else None,

                        "short_range": sim["short_range"],
                        "long_range": sim["long_range"],
                        "trend_score": sim["trend_score"],
                        "wick_ratio_recent": sim["wick_ratio_recent"],
                        "body_ratio_recent": sim["body_ratio_recent"],
                        "range_acceleration": sim["range_acceleration"],
                        "dist_high": sim["dist_high"],
                        "dist_low": sim["dist_low"],
                        "directional_consistency": sim["directional_consistency"],
                        "mae_3": sim["mae"],
                        "mfe_3": sim["mfe"],
                        "target_r": target_r,
                        "label": 1 if target_r > 0 else 0,
                    }

                    self._append_ml_dataset(row)
                    finished.append(sim)

            for f in finished:
                self._pending_simulations.remove(f)

    def _append_ml_dataset(self, row):
        """
        Append-only JSONL dataset.
        Each row written as single line.
        No full-file rewrite.
        """
        try:
            line = json.dumps(row)
            with open(self._ml_dataset_path, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # ======================================================
    # Main Proposal Logic
    # ======================================================

    def propose_intent(self) -> Optional[TradeIntent]:

        if not self._warmed_up:
            return None

        candidates = []

        for symbol in self._universe:

            candles = self._candle_history.get(symbol)
            if not candles or len(candles) < self.WARMUP_WINDOW:
                continue

            # --------------------------------------------------
            # STRUCTURE SAFETY FILTERS (NEW)
            # --------------------------------------------------

            last_close = candles[-1][3]

            # 1️⃣ Reject ultra low priced coins
            if last_close < 0.01:
                continue

            # 2️⃣ Reject dead structure (too small average range)
            short_range = self._avg_range(candles, self.SHORT_WINDOW)
            long_range = self._avg_range(candles, self.LONG_WINDOW)

            if short_range is None or long_range is None:
                continue

            # Require meaningful movement (at least 0.25% average range)
            if (short_range / last_close) < 0.0025:
                continue

            # 3️⃣ Reject volatility spikes (exhaustion move)
            if short_range > (4.0 * long_range):
                continue

            current = self._current_candle.get(symbol)
            if current is None:
                continue

            bucket = current["bucket"]

            # Evaluate each symbol at most once after a 5-minute candle
            # closes. propose_intent() is called on every market tick, so
            # without this guard the same completed-candle setup can create
            # repeated candidates and duplicate forward simulations.
            if self._last_evaluated_bucket.get(symbol) == bucket:
                continue
            self._last_evaluated_bucket[symbol] = bucket

            trend_score = self._trend_score(candles)
            breakout_score = self._breakout_score(candles)

            direction = None
            total_score = 0

            # Strong continuation
            if abs(trend_score) >= 6 and self._strong_pullback(candles):
                direction = "LONG" if trend_score > 0 else "SHORT"
                total_score = self._structure_score(candles)
                # ------------------------------------------
                # STRUCTURE SCORE DEBUG (LOW FREQUENCY)
                # ------------------------------------------
                if total_score >= 0.6 and self.system_log:
                    self.system_log.info(
                        f"STRUCTURE_SCORE | "
                        f"symbol={symbol} | "
                        f"direction={direction} | "
                        f"score={total_score:.3f}"
                    )

            # Breakout (allowed without prior trend)
            elif (
                breakout_score > 0
                and self._is_compressing(candles)
                and self._has_directional_bias(candles)
            ):
                last_close = candles[-1][3]
                prev_close = candles[-2][3]
                direction = "LONG" if last_close > prev_close else "SHORT"
                total_score = self._structure_score(candles)

            if direction:
                bucket = self._current_candle[symbol]["bucket"]

                # -------------------------------------------------
                # HARD THROTTLE: Prevent repeated same-bucket firing
                # -------------------------------------------------
                last = self._last_trade_info.get(symbol)
                if last:
                    last_bucket, last_direction = last

                    # If same candle bucket AND same direction,
                    # skip re-proposal entirely
                    if (
                        last_bucket == bucket
                        and last_direction == direction
                    ):
                        continue

                if not self._counter_trade_spacing_ok(
                    symbol, bucket, direction
                ):
                    continue

                # ------------------------------------------
                # Start ML Forward Simulation (ALL setups)
                # ------------------------------------------
                last_close = candles[-1][3]

                features = self._build_ml_features(candles)[0]

                # Match the actual position sizing contract: quantity is
                # derived from the configured notional, while price-distance
                # risk is derived from USD risk divided by that quantity.
                initial_risk_usd = RISK_PER_TRADE_USD
                qty = MAX_NOTIONAL_USD / last_close
                risk_distance = initial_risk_usd / qty

                if qty <= 0 or risk_distance <= 0:
                    continue

                simulation = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": last_close,
                    "risk_distance": risk_distance,
                    "candles_seen": 0,
                    "mae": 0.0,
                    "mfe": 0.0,
                    "structure_fingerprint": self._latest_structure.get(symbol),
                    "short_range": float(features[0]),
                    "long_range": float(features[1]),
                    "trend_score": float(features[2]),
                    "wick_ratio_recent": float(features[3]),
                    "body_ratio_recent": float(features[4]),
                    "range_acceleration": float(features[5]),
                    "dist_high": float(features[6]),
                    "dist_low": float(features[7]),
                    "directional_consistency": float(features[8]),
                }

                with self._ml_lock:
                    self._pending_simulations.append(simulation)

                candidates.append((symbol, direction, total_score))

        if not candidates:
            return None

        # Top 3 ranking
        candidates.sort(key=lambda x: x[2], reverse=True)
        best_symbol, best_direction, _ = candidates[0]

        # Governor update
        bucket = self._current_candle[best_symbol]["bucket"]

        # ------------------------------------------
        # ML Probability Filter
        # Hot reload check (cheap stat call)
        # No side effects
        # Safe during open position
        self._load_model_if_exists()
        # ------------------------------------------
        if self._ml_model:
            candles = self._candle_history[best_symbol]
            features = self._build_ml_features(candles)

            features_scaled = self._scaler.transform(features)
            prob = self._ml_model.predict_proba(features_scaled)[0][1]

            if prob < self._ml_threshold:
                return None  # Reject low probability trade

        # Record last trade info ONLY when trade approved
        self._last_trade_info[best_symbol] = (
            bucket,
            best_direction,
        )

        return TradeIntent(
            symbol=best_symbol,
            direction=best_direction,
            pattern="STRUCTURE_5M",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
            structure_fingerprint=self._latest_structure.get(best_symbol),
        )
