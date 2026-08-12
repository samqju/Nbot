# Phase 7.3 — Complete Trading-Cost Evidence

## Goal

Make Phase-7 virtual-trade learning labels reflect the measurable round-trip
costs that existed while the virtual position was open, and prevent incomplete
cost labels from triggering or entering context-aware challenger training.

This phase is Observation/learning work only. It does not change candidate
selection, execution risk, leverage, stops, or order authority.

## Cost evidence

For newly completed virtual trades, the cost breakdown now supports:

- configured entry and exit taker fees;
- configured entry and exit slippage;
- measured entry book spread from the immutable Phase 7.1 candidate context;
- measured exit book spread from the Observation-side Binance book ticker; and
- actual Binance funding-rate history events whose funding timestamp occurred
  after virtual entry and on/before virtual close.

Spread is charged as half of the measured entry spread plus half of the measured
exit spread. Funding is normalized into R using the virtual trade's risk
distance. Positive funding is a cost to LONG and a credit to SHORT; negative
funding naturally reverses that relationship.

## Fail-closed evidence policy

A virtual outcome is marked
`FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3` only when:

1. both entry and exit spread measurements are available; and
2. Binance funding history fully covers the virtual holding window.

Funding history is not declared complete when a public response is malformed or
cannot be paged safely. A proven interval with zero funding events is complete
and records `funding_r = 0.0`.

If spread or funding evidence is incomplete, the virtual outcome is still kept
for audit/research, but its cost completeness remains partial.

## Training eligibility

Automatic Phase-7 training now requires BOTH:

- `COMPLETE_PHASE7_1` market context; and
- `FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3` cost evidence.

Historical outcomes are not rewritten or backfilled with guessed spread/funding.
This intentionally resets the qualified evidence cohort to new trustworthy
outcomes rather than allowing the first context-aware challenger to train on
fees/slippage-only labels.

The immutable training snapshot repeats the same eligibility gate, so a trigger
count cannot disagree with the dataset that is actually trained.

## Runtime collection

Observation collects one cost-evidence snapshot per five-minute bucket before
processing that bucket's virtual closures:

- one all-symbol public book-ticker read for exit spread; and
- public funding-history reads covering at least the oldest active virtual trade
  through the current bucket.

Funding history is paged conservatively when needed. Failed evidence collection
does not stop Observation; it only makes affected learning outcomes partial and
therefore ineligible for Phase-7 challenger training.

## Authority boundary

Phase 7.3 grants no paper or real authority. The rules/champion selection path is
unchanged, automatic model runtime activation remains disabled, and Execution is
unchanged.

## Acceptance

Phase 7.3 is accepted when:

1. unit/integration tests prove spread and funding accounting and fail-closed
   evidence behavior;
2. the complete NBOT regression suite passes;
3. Observation remains READY with order authority NONE;
4. the live provider returns trustworthy spread/funding coverage;
5. at least one new real virtual outcome is persisted with complete Phase 7.3
   cost evidence; and
6. automatic training counts only outcomes that have both complete Phase 7.1
   context and complete Phase 7.3 cost evidence.
