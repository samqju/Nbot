# Phase 7.5C — Qualified Evidence Ledger and Bounded Raw Spool

## Purpose

Production Phase-7 validation exposed a structural scaling problem: automatic
training repeatedly reconstructed the full candidate-observation/outcome
history.  Moving those joins from Python RAM to temporary SQLite prevented the
first OOM failure, but a real run still expanded tens of megabytes of raw JSONL
into multi-gigabyte temporary SQLite/JSONL workspaces before cohort splitting.

Phase 7.5C removes raw-history reconstruction from the automatic-training hot
path.  Evidence is qualified once when the Observation worker receives a
completed learning outcome, then stored permanently in a compact SQLite ledger.

## New evidence flow

1. Candidate discovered.
2. Candidate writer stores compact Phase-7 candidate facts in the ledger.
3. Virtual outcome completes.
4. The ledger applies the existing dataset-contract validation plus Phase-7
   requirements exactly once:
   - current experiment contract;
   - valid market-event ID;
   - complete Phase-7.1 market context;
   - complete Phase-7.3 cost evidence;
   - valid label;
   - symbol/direction/contract linkage;
   - duplicate protection.
5. Qualified rows enter the permanent evidence ledger.
6. Rejected evidence receives a compact rejection audit reason.
7. The compact pending candidate fact is deleted immediately after a terminal
   QUALIFIED/REJECTED decision; a terminal-decision key prevents reprocessing.
8. Automatic training counts and exports only the qualified ledger.

The production auto trainer no longer reads candidate observations/outcomes to
reconstruct its training evidence.

## Clean generation boundary

`PHASE7_EVIDENCE_GENERATION=PHASE7_LEDGER_V1` is a new evidence generation.
Historical model cutoffs from earlier raw-history generations do not suppress
fresh ledger evidence.  Models trained from this source record the generation
and `training_source=QUALIFIED_EVIDENCE_LEDGER_V1`.

No automatic historical backfill is performed.  Raw pre-7.5C files may be
retained offline for audit or deliberately removed during the clean cutover.

## Raw storage contract

Candidate observations, candidate outcomes, and virtual-trade JSONL files are
now disposable raw spools, not the training database.

Defaults:

- rotate live raw file at 16 MiB;
- retain only the newest four raw segments per spool;
- rotation uses atomic rename without synchronous gzip on the realtime
  Observation path;
- old segments are deleted as the bounded retention window advances.

This keeps raw diagnostic evidence available for recent troubleshooting while
preventing indefinite JSONL growth.

`learning_runtime_state_<env>.json` is deliberately not treated as a raw history
spool.  It is crash-recovery state for unfinished simulations/active virtual
trades and must remain complete while Observation is running.  The clean 7.5C
cutover may reset it, but normal spool pruning never deletes unfinished runtime
state.

## Deliberately unchanged

- candidate-selection rules;
- virtual-trade outcome semantics;
- complete context/cost qualification requirements;
- 1,000-new-qualified-outcome trigger;
- 200-new-independent-event trigger;
- 70/15/15 chronological split;
- one-hour embargo and label-window purging;
- 50/20/20 independent-event cohort floors;
- baseline and ensemble model families;
- sealed-test policy;
- Phase-7 promotion gates and paper-promotion lock;
- Execution worker, risk, orders, stop/trailing logic, and paper routing.

## Runtime acceptance

Do not tag Phase 7.5C complete until the Observation VPS proves all of the
following after a clean ledger reset:

1. Observation starts and creates `phase7_evidence_ledger_live.sqlite3`.
2. `/learning` reports `Training source: QUALIFIED_EVIDENCE_LEDGER_V1` and
   `Ledger generation: PHASE7_LEDGER_V1`.
3. Qualified evidence begins at zero and grows from new Observation outcomes.
4. Raw candidate/outcome/virtual files rotate below the configured bound.
5. `nbot-auto-training.service` can run while raw observation/outcome files are
   absent and still reports the correct ledger counts.
6. No multi-gigabyte temporary dataset join is created by the automatic
   trainer.
7. No new kernel OOM event occurs.
8. Observation remains healthy while training polls the ledger.

The first real challenger is intentionally delayed until the fresh ledger again
satisfies the Phase-7 evidence and cohort gates.
