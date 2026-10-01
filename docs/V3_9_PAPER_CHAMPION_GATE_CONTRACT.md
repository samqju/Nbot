# V3.9.6A Paper Champion Gate Freeze

Current applicability (2026-10-01): these frozen gates are unchanged.
Experimental learned-Testnet use, positive training setup statistics and the
small-VPS benchmark cannot count as Paper Champion evidence. The recent setup
labels do not replace this contract's market-regime coverage. Research targets
are simulated four-hour ATR-based R; execution uses its own risk/exit lifecycle,
so equivalence and operational degradation must be established from genuine
linked evidence. See [current learner limitations](SMALL_VPS_LEARNER.md).

Version: `V39_PAPER_CHAMPION_GATE_V1`

This contract freezes the minimum V3.9 Paper Champion evidence gate **before**
any Research Champion is permitted to accumulate LIVE/PAPER evidence toward
that title. It does not promote a Research Champion and does not grant paper,
Execution, Binance-order, or real-capital authority.

## Research prerequisite

A current V3.9 Research Champion pointer must exist first. The original rejected
`WALK_FORWARD_CHAMPION_V1` result remains immutable and cannot satisfy this
prerequisite. A Research Champion is still only research authority.

## Frozen sustained LIVE/PAPER floor

The sample floor uses the mature V1 paper-governance reference of 150 completed
paper trades and 100 independent market events before Paper Champion promotion,
then strengthens it with V3 chronology/confidence requirements:

- at least 150 completed Research-Champion LIVE/PAPER trades;
- at least 100 independent market events;
- at least 30 elapsed days;
- at least 20 distinct UTC dates;
- 2,000 market-event bootstrap samples at 95% confidence;
- after-cost mean-R confidence lower bound strictly positive;
- last 30 completed paper trades have positive mean net R;
- maximum drawdown no more than 5R;
- maximum losing streak no more than 5 trades;
- maximum symbol concentration 25%;
- maximum UTC-date concentration 20%;
- maximum single observed market-regime concentration 70%;
- at least two observed trend, volatility, and liquidity regimes;
- funding regimes monitored as available without manufacturing variation;
- mean research-to-paper operational degradation no worse than 0.10R;
- median winner capture at least 50%;
- linked Research Champion must retain its frozen weak-baseline advantage;
- drift monitored and no unresolved safety defect;
- Testnet regression must pass on the current release before final judgment;
- automatic rollback/authority controls must be proven if they are enabled.

## Evidence start boundary

Only LIVE/PAPER evidence produced **after** the Research Champion is explicitly
activated for the controlled V3.9.6 paper-evidence stage may count. V3.8
operational canaries and pre-Research-Champion paper activity cannot be relabeled
as Paper Champion economics.

## Current expected state

Until a Research Champion exists, status must remain:

`WAIT_FOR_RESEARCH_CHAMPION`

and `paper_champion_authority=false`.
