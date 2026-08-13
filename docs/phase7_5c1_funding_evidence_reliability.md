# Phase 7.5C.1 — Funding Evidence Reliability

## Problem

After the Phase 7.5C clean-ledger cutover, live diagnostics showed a systematic
rejection class: completed virtual outcomes had measured spread and configured
fees/slippage, but `funding_r` was `null` and cost completeness remained
`FEES_SLIPPAGE_SPREAD_ONLY`.

The ledger correctly rejected those rows as `INCOMPLETE_COST`; the defect was
upstream evidence collection, not the ledger gate.

## Fix

This hotfix keeps the Phase-7 fail-closed cost contract unchanged and improves
funding-evidence collection in three ways:

1. When virtual trades are active, Binance funding history now starts exactly at
   the oldest active virtual trade. The previous helper always requested at
   least four hours of global funding history, even when the oldest trade was
   only minutes old. The shorter exact horizon reduces unnecessary rows and
   pagination pressure.

2. Observation makes one immediate bounded retry when the first cost snapshot is
   partial or raises. The refresh still happens before the candle rollover can
   close virtual trades. Healthy buckets still require one provider call; the
   second call exists only to avoid losing a whole rollover to one transient or
   partial funding read.

3. A malformed global funding row for a contract outside NBOT's requested
   Observation universe no longer increments the requested-evidence parse-error
   count. Requested-symbol malformed rows continue to fail closed.

## Unchanged safety/learning semantics

- `funding_r` is never guessed.
- A proven interval with no funding event still produces `funding_r = 0.0`.
- Missing/incomplete funding still produces partial cost evidence.
- Phase 7.5C still rejects incomplete cost evidence.
- Candidate rules, scores, virtual stop/target behavior, model features,
  training thresholds, time split, embargo/purge, challenger gates, paper
  authority, Execution risk, and order authority are unchanged.

## Runtime acceptance

After deployment, confirm that:

- Observation stays healthy;
- cost snapshots normally show `funding_complete=true`;
- new virtual outcomes increasingly carry
  `FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3`;
- the rate of new `INCOMPLETE_COST` / `funding_r=null` rejections drops sharply;
- no extra training-memory or giant temporary-dataset behavior returns.
