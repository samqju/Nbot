"""Prevent training labels from reaching past a chronological test cutoff.

For offline M2R studies, each row has a decision_index and exit_index.
A train example is admissible only if its entire simulated trade resolves
BEFORE the first test decision. This avoids label overlap at train/test
boundaries; FreqAI's separate native internals need their OWN verification.
"""
from __future__ import annotations
from pandas import DataFrame


def purged_opportunity_split(opportunities: DataFrame, cutoff_index: int):
    needed={"decision_index","exit_index","candidate","net_return"}
    if not needed.issubset(opportunities):
        raise ValueError("MISSING_OPPORTUNITY_FIELDS")
    if type(cutoff_index) is not int or cutoff_index < 1:
        raise ValueError("INVALID_CUTOFF")
    if (opportunities["exit_index"]<opportunities["decision_index"]).any():
        raise ValueError("INVALID_TRADE_WINDOW")
    train=opportunities.loc[
        (opportunities["decision_index"]<cutoff_index)
        & (opportunities["exit_index"]<cutoff_index)
    ].copy()
    test=opportunities.loc[opportunities["decision_index"]>=cutoff_index].copy()
    purged=opportunities.loc[
        (opportunities["decision_index"]<cutoff_index)
        & (opportunities["exit_index"]>=cutoff_index)
    ].copy()
    if (not train.empty and train["exit_index"].max()>=cutoff_index):
        raise RuntimeError("UNSAFE_TRAIN_LABEL_OVERLAP")
    if not test.empty and (test["decision_index"]<cutoff_index).any():
        raise RuntimeError("UNSAFE_TEST_BOUNDARY")
    return train, test, purged
