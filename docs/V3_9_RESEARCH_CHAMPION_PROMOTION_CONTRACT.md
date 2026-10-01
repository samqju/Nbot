# V3.9.6B Research Champion Promotion Contract

Current applicability (2026-10-01): the explicit promotion boundary below is
unchanged. The learned-Testnet experimental route has separate authority and
may use a non-rejected unevaluated model; it does not require, create or imply
Research Champion promotion. Its automatic model selection must not be confused
with a champion-pointer transition. See the
[learned-Testnet contract](LEARNED_TESTNET_CONTRACT.md).

Version: `V39_RESEARCH_CHAMPION_PROMOTION_V1`

This contract implements the first Research Champion pointer transition after
V3.9.3's already-frozen multi-window eligibility gate.  It does not change that
gate and cannot reinterpret a historical PASS/REJECT result.

Promotion is allowed only when `governance-status` reports
`ELIGIBLE_FOR_RESEARCH_CHAMPION_REVIEW`.  The candidate is deterministic: the
model attached to the latest immutable challenger window in that frozen
eligibility basis.  The transition requires the explicit operator confirmation
`PROMOTE_ELIGIBLE_V39_RESEARCH_CHAMPION`.

The first transition records immutable promotion evidence, a generation-1
Research Champion pointer, a model-role record, and a rollback-state record.
The rollback state remains `DEFERRED_UNTIL_PAPER_STAGE_MATURE`; automatic
rollback is not enabled by this phase.  Replacing an existing Research Champion
is intentionally deferred until a later frozen champion-vs-challenger contract
exists.

A Research Champion remains research authority only.  This phase does not grant
Paper Champion authority, recommendation routing authority, Execution authority,
Binance order authority, or real-capital authority.  V3.9.6A must separately
observe the pointer before controlled LIVE/PAPER evidence can be activated.
