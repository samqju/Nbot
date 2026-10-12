"""One shared V4 ranking policy for forward paper exams and paper Execution.

LightGBM lambdarank scores are relative ordering signals, not calibrated
probabilities or expected net R. A negative score is not a loss forecast.
The frozen forward paper policy tests the top finite-scored candidate without
an arbitrary score-sign gate; approved paper Execution must do the same.
This module supplies selection only, never order authority.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable


def rank_candidates(score_candidate: Callable[[Any], float], candidates: Iterable[Any]) -> list[tuple[float, Any]]:
    scored: list[tuple[float, Any]] = []
    for candidate in candidates:
        try:
            score = float(score_candidate(candidate))
        except (KeyError, TypeError, ValueError):
            # One invalid feature vector must not create an invalid proposal.
            continue
        if math.isfinite(score):
            scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1].symbol, item[1].side))
    return scored
