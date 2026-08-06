"""Existing structure rules extracted into candidate generation.

Phase 3.1 deliberately preserves the original Strategy proposal conditions.
This component discovers eligible candidates; final model filtering and
TradeIntent creation remain in Strategy until later Phase 3 patches.
"""

from __future__ import annotations

from config import (
    EXECUTION_MODE,
    EXPERIMENT_CANDLE_INTERVAL,
    MAX_NOTIONAL_USD,
    PAPER_ENTRY_SLIPPAGE_PCT,
    PAPER_EXECUTION_VARIANT_ID,
    PAPER_EXIT_SLIPPAGE_PCT,
    PAPER_TAKER_FEE_RATE,
    RISK_PER_TRADE_USD,
    RULE_MODEL_VERSION,
    STRATEGY_VARIANT_ID,
    STRATEGY_VERSION,
    TRADING_ENV,
    VIRTUAL_STRATEGY_VARIANT_ID,
    VIRTUAL_TRADE_MAX_CANDLES,
    VIRTUAL_TRADE_TARGET_R,
)
from strategy.candidate import StrategyCandidate
from strategy.features import CandidateFeatureExtractor
from strategy.experiment_contract import (
    build_experiment_context,
    build_market_event_id,
    new_decision_batch_id,
)
from strategy.setup_detectors import SetupDetectorRegistry


class StructureCandidateGenerator:
    def __init__(self, strategy):
        self.strategy = strategy
        self.feature_extractor = CandidateFeatureExtractor(strategy)
        self.detectors = SetupDetectorRegistry()

    def generate(
        self,
        *,
        decision_batch_id: str | None = None,
        decision_bucket: int | None = None,
    ) -> list[StrategyCandidate]:
        s = self.strategy
        candidates: list[StrategyCandidate] = []
        decision_batch_id = (
            str(decision_batch_id).strip()
            if decision_batch_id is not None
            else new_decision_batch_id()
        )
        if not decision_batch_id:
            raise ValueError("DECISION_BATCH_ID_INVALID")

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
            if (
                decision_bucket is not None
                and bucket != int(decision_bucket)
            ):
                continue
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

                structure_fingerprint = s._latest_structure.get(symbol)
                market_event_id = build_market_event_id(
                    environment=TRADING_ENV,
                    candle_bucket=bucket,
                    candle_interval=EXPERIMENT_CANDLE_INTERVAL,
                )
                experiment_context = build_experiment_context(
                    decision_batch_id=decision_batch_id,
                    market_event_id=market_event_id,
                    strategy_version=STRATEGY_VERSION,
                    strategy_variant_id=STRATEGY_VARIANT_ID,
                    selection_model_version=RULE_MODEL_VERSION,
                    environment=TRADING_ENV,
                    execution_mode=EXECUTION_MODE,
                    candle_bucket=bucket,
                    structure_fingerprint=structure_fingerprint,
                    paper_taker_fee_rate=PAPER_TAKER_FEE_RATE,
                    paper_entry_slippage_pct=PAPER_ENTRY_SLIPPAGE_PCT,
                    paper_exit_slippage_pct=PAPER_EXIT_SLIPPAGE_PCT,
                    virtual_variant_id=VIRTUAL_STRATEGY_VARIANT_ID,
                    virtual_target_r=VIRTUAL_TRADE_TARGET_R,
                    virtual_max_candles=VIRTUAL_TRADE_MAX_CANDLES,
                    paper_variant_id=PAPER_EXECUTION_VARIANT_ID,
                    candle_interval=EXPERIMENT_CANDLE_INTERVAL,
                )
                candidate = StrategyCandidate(
                    symbol=symbol,
                    direction=direction,
                    score=signal.rule_score,
                    pattern=signal.pattern,
                    bucket=bucket,
                    features=candidate_features,
                    structure_fingerprint=structure_fingerprint,
                    reference_price=last_close,
                    decision_batch_id=decision_batch_id,
                    market_event_id=market_event_id,
                    strategy_version=STRATEGY_VERSION,
                    strategy_variant_id=STRATEGY_VARIANT_ID,
                    model_version=RULE_MODEL_VERSION,
                    execution_eligible=(
                        symbol in s._execution_universe
                    ),
                    experiment_context=experiment_context,
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
                    "structure_fingerprint": structure_fingerprint,
                    "decision_batch_id": decision_batch_id,
                    "market_event_id": market_event_id,
                    "strategy_version": STRATEGY_VERSION,
                    "strategy_variant_id": STRATEGY_VARIANT_ID,
                    "model_version": RULE_MODEL_VERSION,
                    "experiment_context": experiment_context,
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
