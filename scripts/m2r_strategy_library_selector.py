"""Compatibility import; canonical selector lives with Freqtrade strategy.

Avoid drifting copies: both standalone planning tests and the installed
user_data Docker strategy import the exact SAME pure selector implementation.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "user_data" / "strategies"))
from nbot_v6_library_selector import (CandidateBlock, SelectorDecision, VALID_FAMILIES,
    VALID_REGIMES, parse_utc, parse_blocks, choose_validated_strategy)
