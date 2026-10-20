"""Research-only FreqAI-to-V7 candidate ranking bridge.

A FreqAI AFTER-COST model may export one prediction per V7 candidate, side
and strategy family. This adapter replays those immutable predictions with
V7's single-capital-slot historical simulator. It does not train FreqAI,
create orders, promote models or make price forecasts comparable to net PnL.

Critical: V7 decision_ms indexes a 5m candle by its *opening* timestamp.
Its completed OHLC features first become known at decision_ms + BAR_MS.
Do not treat that bar's close as known at its opening instant.

Strict label and provenance contracts prevent replaying the official FreqAI
example's future-price target as though it were a trained after-cost net label.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import re

from .data import BAR_MS
from .lab import LABEL_POLICY
from .features import FAMILIES

KNOWN_SYMBOLS = frozenset(("BTCUSDT", "ETHUSDT", "SOLUSDT"))
SIDES = frozenset(("LONG", "SHORT"))
TARGET = "after_cost_trade_net_fraction"
MODEL_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
RECORD_KEYS = frozenset((
    "decision_ms", "symbol", "side", "family", "source_hash",
    "feature_bar_open_ms", "features_ready_ms",
    "training_labels_available_before_ms", "model_sha256",
    "target", "label_policy", "expected_net", "uncertainty_net",
))


@dataclass(frozen=True)
class NetForecast:
    decision_ms: int
    symbol: str
    side: str
    family: str
    source_hash: str
    feature_bar_open_ms: int
    features_ready_ms: int
    training_labels_available_before_ms: int
    model_sha256: str
    target: str
    label_policy: str
    expected_net: float
    uncertainty_net: float

    @classmethod
    def from_mapping(cls, d, *, required_label_policy=LABEL_POLICY):
        if set(d) != RECORD_KEYS:
            raise ValueError("INVALID_PREDICTION_SCHEMA_OR_FUTURE_OUTCOME_COLUMN")
        row = cls(**d)
        if (
            type(row.decision_ms) is not int
            or type(row.feature_bar_open_ms) is not int
            or type(row.features_ready_ms) is not int
            or type(row.training_labels_available_before_ms) is not int
            or row.symbol not in KNOWN_SYMBOLS
            or row.side not in SIDES
            or row.family not in FAMILIES
            or row.feature_bar_open_ms != row.decision_ms
            or row.features_ready_ms != row.decision_ms + BAR_MS
            or row.training_labels_available_before_ms > row.decision_ms
            or row.target != TARGET
            or row.label_policy != required_label_policy
            or not MODEL_SHA_RE.fullmatch(row.model_sha256)
            or not MODEL_SHA_RE.fullmatch(row.source_hash)
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in (row.expected_net, row.uncertainty_net))
            or row.uncertainty_net < 0
        ):
            raise ValueError("FUTURE_LEAK_STALE_MODEL_OR_NON_NET_TARGET")
        return row

    @property
    def key(self):
        return (self.decision_ms, self.symbol, self.side, self.family)


class FreqAINetResearchBrain:
    """Acts as V7 decision.Brain, but reads only frozen after-cost forecasts.

    All three coins are included in each watch; opportunity selection must
    choose a positive uncertainty-adjusted net forecast, or explicitly abstain.
    The comparison is globally across sides, families AND coins, not Freqtrade
    pair execution order. No watch score uses future outcome information.
    """

    def __init__(self, rows, *, cutoff_ms: int, version="FREQAI_NET_RESEARCH_V1",
                 uncertainty_weight: float=1.0, cost_stress: float=0.0,
                 label_policy: str=LABEL_POLICY):
        if not version or not isinstance(cutoff_ms, int):
            raise ValueError("INVALID_VERSION_OR_CUTOFF")
        if not all(math.isfinite(x) and x >= 0
                   for x in (uncertainty_weight, cost_stress)):
            raise ValueError("INVALID_ABSTENTION_MARGIN")
        if label_policy not in (LABEL_POLICY,
            'V7_5M_PAPER_BROKER_1STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_CF_V1'):
            raise ValueError('UNAUTHORIZED_RESEARCH_LABEL_POLICY')
        self.label_policy = label_policy
        self.version = version
        self.cutoff_ms = cutoff_ms
        self.uncertainty_weight = uncertainty_weight
        self.cost_stress = cost_stress
        self.forecasts = {}
        model_digests = set()
        for raw in rows:
            p = raw if isinstance(raw, NetForecast) else NetForecast.from_mapping(
                raw, required_label_policy=label_policy)
            if p.label_policy != label_policy:
                raise ValueError('MIXED_STOP_TARGET_POLICY')
            # A model fitted after examination begins must not retrospectively
            # score earlier bars. Rolling replacements need separate timestamps
            # and a prospective evaluation contract.
            if p.training_labels_available_before_ms > p.decision_ms:
                raise ValueError("MODEL_NOT_AVAILABLE_AT_DECISION")
            if p.key in self.forecasts:
                raise ValueError("DUPLICATE_SIMULTANEOUS_FORECAST")
            self.forecasts[p.key] = p
            model_digests.add(p.model_sha256)
        self.model_digests = tuple(sorted(model_digests))

    @classmethod
    def from_jsonl(cls, path, **kwargs):
        forecasts = []
        with Path(path).open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    forecasts.append(NetForecast.from_mapping(json.loads(line),
                        required_label_policy=kwargs.get('label_policy', LABEL_POLICY)))
        if not forecasts:
            raise ValueError("NO_VERIFIED_FREQAI_NET_FORECASTS")
        return cls(forecasts, **kwargs)

    def score(self, rows, kind):
        if kind == "watch":
            # Three-coin fixed cohort: no early coin exclusion, and no future
            # profitability used to construct universe membership.
            return [(1.0, 1.0) if r["symbol"] in KNOWN_SYMBOLS
                    else (-1.0, -1.0) for r in rows]
        if kind != "opportunity":
            raise ValueError("UNSUPPORTED_FREQAI_RESEARCH_TASK")
        scored = []
        for r in rows:
            key = (r["decision_ms"], r["symbol"], r["side"], r["family"])
            p = self.forecasts.get(key)
            if p is None:
                scored.append((-1.0, -1.0))
                continue
            if (
                p.source_hash != r["source_hash"]
                or p.feature_bar_open_ms != r["decision_ms"]
                or p.features_ready_ms != r["decision_ms"] + BAR_MS
                or p.training_labels_available_before_ms > r["decision_ms"]
            ):
                raise ValueError("PREDICTION_SOURCE_OR_ASOF_MISMATCH")
            net_lower_estimate = (
                p.expected_net
                - self.uncertainty_weight * p.uncertainty_net
                - self.cost_stress
            )
            # V7's own choose() requires net > 0 before selecting highest rank.
            # Rank is an ABSOLUTE economic quantity in the same net-return units,
            # not arbitrary pair-specific LambdaRank scales.
            scored.append((net_lower_estimate, net_lower_estimate))
        return scored
