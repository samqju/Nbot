"""Existing structure rules extracted into candidate generation.

Phase 3.1 deliberately preserves the original Strategy proposal conditions.
This component discovers eligible candidates; final model filtering and
TradeIntent creation remain in Strategy until later Phase 3 patches.
"""

from __future__ import annotations

from config import MAX_NOTIONAL_USD, RISK_PER_TRADE_USD
from strategy.candidate import StrategyCandidate
from strategy.features import CandidateFeatureExtractor
from strategy.setup_detectors import SetupDetectorRegistry


class StructureCandidateGenerator:
    def __init__(self, strategy):
        self.strategy = strategy
        self.feature_extractor = CandidateFeatureExtractor(strategy)
        self.detectors = SetupDetectorRegistry()

    def generate(self) -> list[StrategyCandidate]:
        s = self.strategy
        candidates: list[StrategyCandidate] = []

        for symbol in s._universe:
            candles = s._candle_history.get(symbol)
            if not candles or len(candles) < s.WARMUP_WINDOW:
                continue

            last_close = candles[-1][3]

            # Preserve existing safety filters.
            if last_close < 0.01:
                continue

            short_range = s._avg_range(candles, s.SHORT_WINDOW)
            long_range = s._avg_range(candles, s.LONG_WINDOW)

            if short_range is None or long_range is None:
                continue
            if (short_range / last_close) < 0.0025:
                continue
            if short_range > (4.0 * long_range):
                continue

            current = s._current_candle.get(symbol)
            if current is None:
                continue

            bucket = current["bucket"]
            if s._last_evaluated_bucket.get(symbol) == bucket:
                continue
            s._last_evaluated_bucket[symbol] = bucket

            setup_signals = self.detectors.detect_all(candles)
            if not setup_signals:
                continue

            candidate_features = self.feature_extractor.extract(candles)
            features = candidate_features.as_numpy()[0]
            initial_risk_usd = RISK_PER_TRADE_USD
            qty = MAX_NOTIONAL_USD / last_close
            risk_distance = initial_risk_usd / qty

            if qty <= 0 or risk_distance <= 0:
                continue

            for signal in setup_signals:
                direction = signal.direction
                last = s._last_trade_info.get(symbol)
                if last:
                    last_bucket, last_direction = last
                    if (
                        last_bucket == bucket
                        and last_direction == direction
                    ):
                        continue

                if not s._counter_trade_spacing_ok(
                    symbol,
                    bucket,
                    direction,
                ):
                    continue

                candidate = StrategyCandidate(
                    symbol=symbol,
                    direction=direction,
                    score=signal.rule_score,
                    pattern=signal.pattern,
                    bucket=bucket,
                    features=candidate_features,
                    structure_fingerprint=s._latest_structure.get(symbol),
                    reference_price=last_close,
                )

                simulation = {
                    "candidate_observation_id": candidate.observation_id,
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": last_close,
                    "risk_distance": risk_distance,
                    "candles_seen": 0,
                    "mae": 0.0,
                    "mfe": 0.0,
                    "structure_fingerprint": s._latest_structure.get(symbol),
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

                s.add_pending_simulation(simulation)

                candidates.append(candidate)

        return candidates
