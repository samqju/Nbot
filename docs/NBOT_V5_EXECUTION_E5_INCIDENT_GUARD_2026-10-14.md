# NBOT V5 — E5 Synthetic Incident Guard (2026-10-14 IST)

**Scope:** Only `feature/v5-execution-foundation-20261014`. Offline-only isolated Execution development; NO Binance order client, live/paper service activation, model promotion or credentials. The Observation roadmap/soak workstream is unchanged.

## What was built

`nbot/v5/execution_incidents.py` adds a local `SyntheticIncidentGuard` around synthetic chronological market replay. Rejected unsafe synthetic frames receive immutable SQLite incident records with safe IDs, SHA256 digest, reason and synthetic clock only: **no raw proposal, signing secret or exchange credential is persisted**. Identical incidents deduplicate; at most **256 distinct incidents** are retained, with an explicit persistent overflow counter and bounded 20-incident operator view.

The synthetic heartbeat returns `NO_REPLAY_EVIDENCE` when the source has never delivered a qualified frame. Once a source is overdue beyond the frozen continuity gap, it returns `SOURCE_TIMEOUT` and activates the **one-way new-entry kill switches** in both paper books. Any existing positions stay **unresolved** until a safe future exit/reconciliation policy is separately validated; no favorable fill or fabricated terminal trade is created. No active worker, transport, scheduler or market-data connection was created.

## E5 evidence

Ten incident tests passed on isolated Execution VPS using temporary databases. They validate bad-source rejection, immutable incident rows, duplicate dedupe, storage cap and overflow, safe metadata, restart, no-feed HOLD, timeout kill and no manufactured settlement. GitHub Actions CI for the exact E5 code commit `dcaaaf9299a97f6fff3d6d79841b1847ff59cbef` **SUCCESS**: https://github.com/samqju/Nbot/actions/runs/38510512351 .

Combined with E1–E4's 62 independent synthetic tests, this is **72 unique offline tests**; final aggregate rerun and legacy-service verification are separately required before closing the milestone.

## Remaining HOLD gates

No verified real-market feed, mature Champion/Challenger, authenticated remote Observation→Execution transport, independent evidence-grade quotation, real fill reconciliation, deployment readiness, scientifically fair independent-regime comparison or live order permission. E5 synthetic incident handling is NOT a production outage playbook and cannot claim any real trading safety or strategy profitability.

**Next safely independent development:** E6 offline versioned transport-contract, key rotation, source-integrity and recovery review against Observation's eventual signed recommendation interface, plus disposable stress drills. Active paper service start, Observation-branch merge, operational remediation or any material financial authority change require separate critical authorization. No such authorization is implied.
