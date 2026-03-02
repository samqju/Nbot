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

class Strategy:

    def __init__(self, max_history: int = 200):

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

        # ------------------------------------
        # ML Edge Model (Optional)
        # ------------------------------------
        self._ml_model = None
        self._ml_threshold = 0.60  # minimum probability required

        model_path = "models/edge_model.pkl"
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                self._scaler, self._ml_model = pickle.load(f)

        # ------------------------------------
        # ML Forward Simulation Dataset
        # ------------------------------------
        self._ml_dataset_path = "ml_dataset.jsonl"
        self._pending_simulations = []
        self._ml_lock = threading.Lock()
        self.MAX_FORWARD_CANDLES = 36  # 3 hours on 5m

        # -----------------------------
        # Trade Governor (UNCHANGED)
        # -----------------------------
        self._last_trade_info = {}  # {symbol: (bucket, direction)}
        self.COUNTER_TRADE_SPACING_BUCKETS = 6

        # -----------------------------
        # 5M Windows
        # -----------------------------
        self.SHORT_WINDOW = 10
        self.LONG_WINDOW = 30
        self.WARMUP_WINDOW = 50

    # ======================================================
    # Candle Builder (5M)
    # ======================================================

    def on_price(self, symbol: str, price: float, timestamp: int):

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
                if sim["candles_seen"] >= 5:

                    row = {
                        "symbol": sim["symbol"],
                        "direction": sim["direction"],
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
                        "label": 1 if sim["mae"] >= 0.3 else 0,
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
            if short_range > (2.5 * long_range):
                continue

            bucket = self._current_candle[symbol]["bucket"]

            trend_score = self._trend_score(candles)
            breakout_score = self._breakout_score(candles)

            direction = None
            total_score = 0

            # Strong continuation
            if abs(trend_score) >= 6 and self._strong_pullback(candles):
                direction = "LONG" if trend_score > 0 else "SHORT"
                total_score = abs(trend_score)

            # Breakout (allowed without prior trend)
            elif (
                breakout_score > 0
                and self._is_compressing(candles)
                and self._has_directional_bias(candles)
            ):
                last_close = candles[-1][3]
                prev_close = candles[-2][3]
                direction = "LONG" if last_close > prev_close else "SHORT"
                total_score = breakout_score + 2  # bonus for structured breakout

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

                # Match real RiskManager math exactly
                initial_risk_usd = 0.9 * RISK_PER_TRADE_USD
                qty = initial_risk_usd / last_close
                risk_distance = initial_risk_usd / qty

                simulation = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": last_close,
                    "risk_distance": risk_distance,
                    "candles_seen": 0,
                    "mae": 0.0,
                    "mfe": 0.0,
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
        )
