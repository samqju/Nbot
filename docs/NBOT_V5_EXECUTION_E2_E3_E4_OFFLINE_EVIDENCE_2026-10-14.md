# NBOT V5 — Execution E2, E3 and E4 Offline Development Evidence

**Evidence date:** 2026-10-14 (IST)  
**Source branch:** `feature/v5-execution-foundation-20261014`; isolated from Observation branch `v5-clean-restart-20261013`, whose roadmap remains at v2.8.1.  
**Scope:** Synthetic-only execution foundation and scientific-control interfaces; **not** an operational or production release.  
**Authority:** ZERO Binance order submission, ZERO service activation, ZERO real paper account connection, ZERO model promotion.

## Milestone E2 — Chronological synthetic replay and paper exits

**Implementation:** `nbot/v5/execution_replay.py`; minimal supporting change to `nbot/v5/execution_engine.py`. One shared sequential market timeline feeds Champion Paper and Challenger Paper books. Recommendation payloads are separately signed and tied to fixed model/experiment/contest and paper-only authority. Replay is bounded to a frozen UTC contest start/end, maximum allowed evidence gap, synthetic quote market count (64), and at most two independent model requests per market frame. Immutable replay receipts include frame digest, signed synthetic evidence acknowledgment, proposed/abstained/rejected/fill decisions, automatic paper-only stop or maximum-holding exit, and marked equity or explicit unverifiable reason. A replayed event with identical payload is idempotent across database restart; a changed replay is rejected. SQLite's atomic outer transaction encloses frame/decisions/fills/exits/marks, with nested savepoints and injected-error tests.

**Economics and realism:** Simulated adverse bid/ask fill plus adverse slippage, taker fees, and conservative funding accrual only. Stops that gap through are filled at the *worse available subsequent qualified synthetic quote*, never at an optimistic exact stop. Neither synthetic execution nor past-only sample tick chronology is proof of executable historical prices. Missing frames over the frozen 5-minute source gap ceiling, missing/stale BTC or quote, conflicting same-source timestamp, quote capture clock rollback, or stale position mark cause explicit HOLD rather than fabricated settled outcomes. Notably, a 4-hour max-hold exit requires continuous synthetic frame evidence (not two conveniently selected endpoints). Qualified equity marks use captured quote timestamp, not processing timestamp.

**E2 STATUS:** Offline source/replay mechanics tested. No continuous independent real quote feed, measured exchange spread/slippage, production transport security, order manager, portfolio lifecycle service or owner-approved paper deployment. **G7/G8 still HOLD**.

## Milestone E3 — Fair shared-window paper evidence audit (synthetic)

**Implementation:** `nbot/v5/contest_audit.py` (read-only). Both books share frozen initial capital, model identities, risk policy, market-event timeline and a single requested UTC cutoff. Report includes per-book numbers of accepted/abstained/rejected/not-emitted decisions, settled outcomes, separately computed after-cost wallet and qualified marked equity return on common initial capital, synthetic fee total, adverse funding accrual, only *observed sampled* drawdown when every necessary mark qualifies, and a zero-return NO_TRADE benchmark. It explicitly distinguishes event IDs from independent market blocks. Every shared-frame receipt is linked to originating decision IDs; direct engine trades or synthetic settlements made outside chronological replay are flagged as contamination/HOLD.

**Mandatory limits:** A 100-settled-trade-per-model count remains a checkpoint, never permission to promote; minimum shared observed frame count and actual elapsed observed time are separate constraints, not assumed from an empty start-to-first-event interval. Event-blocked confidence intervals, regime diversity, actual mature labels, full eligible denominator, prospective independence and verified real-market pricing remain **UNAVAILABLE**; therefore the evaluator ALWAYS returns HOLD, no matter who wins a simulation. Contest outcomes never retrain frozen competitor models. Unresolved market paths can never be counted as settled. No live or paper model swap method exists.

**E3 STATUS:** Synthetic comparison and fail-closed review **PASS** for the tested protocol only; scientifically valid model comparison still **NOT READY**.

## Milestone E4 — Bounded 50-market and 100/100 synthetic regression

**Implementation:** `tests/test_v5_execution_mock_contest.py` exercises a 50-symbol quote scenario with no forced entries, and a 200-frame / 100-settled-paper-trades-per-book shared forward contest, using declared toy model fixtures, known artificial bid/ask, low per-trade paper risk, mock max-hold exits and restart halfway through. Both portfolios preserve wallet, settlement IDs and model/policy/receipt identities across restart. The engine still returns HOLD even when count and shared time/frame gates are met.

**Critical discovered failure, corrected before acceptance:** Initial 100-trade test reproduced a `UNIQUE constraint failed: settled.position_id` error on sequential close/reopen for the same symbol: SQLite reused a deleted row ID from `positions`. Fixed by `INTEGER PRIMARY KEY AUTOINCREMENT`, with fail-closed rejection of prior incompatible prototype `positions` schemas. Hardened immutable orders and added a short independent regression for distinct settled IDs. Existing V3/V4 databases are never migrated or opened. The initial failing test is preserved in GitHub Actions history; the latest corrected build passes.

**E4 STATUS:** Synthetic 100/100 accounting and 50-market no-trade capacity acceptance **PASS**, without any evidence of profit, ability to reliably observe 50 active live market feeds, production-ready resource throughput, inference quality or live orders.

## Test/evidence and operational isolation

The checked code is restricted to `nbot/v5/execution_engine.py`, `nbot/v5/execution_replay.py`, `nbot/v5/contest_audit.py`, the isolated `tests/test_v5_*execution*.py` and `tests/test_v5_contest_audit.py` test suites and `.github/workflows/v5-isolated-execution.yml`. All fixture keys are synthetic and injected at test time. No sensitive or private exchange credential is requested/stored/committed. WAL/FULL SQLite databases for tests live in temporary paths. The isolated Execution VPS development clone is `/home/ubuntu/nbot_v5_execution_dev` and is NOT a service directory. No changes are needed on Observation `base`.

Final verified GitHub CI: **SUCCESS**, run https://github.com/samqju/Nbot/actions/runs/38510259392 at exact code+documentation commit `1ffb38ac987565416e69159dec4f4e3fdb78a6e2` (Python 3.12, isolated execution suite). Independent Execution VPS checkout at the same commit ran **51 execution/replay/mock contest tests PASS** and **11 contest-audit tests PASS**, total **62/62**. Final read-only operational verification: `nbot-execution-live-paper.service` and `nbot-control-tunnel-live-paper.service` both **inactive**, isolated Git worktree clean. No Observation VPS command, production service or exchange order was executed.

## Gating status and follow-up

- **E2/E3/E4 offline acceptance only:** PASS within stated fixture boundaries.
- **Observation G1g / matured research / first Champion:** unchanged and independently gated. No model artifacts are assumed available.
- **G7 integrated paper engine with independent trusted feeds and authentication:** HOLD.
- **G8 prospective model comparison:** HOLD.
- **G9 any model promotion / real orders:** NOT AUTHORIZED.
- **Main/Observation branch merge:** NOT PERFORMED.

**Next independent offline work (no critical approval needed):** E5 design and synthetic tests of durable feed/outage incident acknowledgments, operator-readable reconciliation and failure recovery, stronger independent as-of quote/source identity checks, bounded evidence and structured risk reports, with a frozen external authenticated transport contract. Integration with Observation model output must wait for version/schema compatibility and its independent readiness gate. Creating/starting a persistent Execution service, changing V3/V4 processes, changing paper authority/model routing, acquiring Binance private API credentials, and all financial authority changes require separately scoped critical approval; this document grants none.

**Honest assessment:** This is a testable safety/accounting platform. It is NOT evidence that autonomous trading, positive expectancy, model selection, or real-money trading can safely start.
