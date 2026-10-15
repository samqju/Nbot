# NBOT V5.1 — G0-04 First Clean Application-Code Scope (Proposed; Gate Not Closed)

**Dated:** 15 October 2026 IST  
**Branch:** nbot-v5.1  
**Status:** **SCOPE DOCUMENTED; G0-04 NOT COMPLETE** because the owner explicitly required legacy VPS cleanup **first**. The attempted authorized cleanup command was blocked before execution, and subsequent read-only inspections confirmed both historical NBOT working directories remain. Do not invent a cleanup success or tick G0-04.

## 1. Why this document exists

The owner directs: first clean older NBOT data on Execution-VPS and Observation-VPS (waives all legacy backup/restoration), **then** complete G0-04, finalizing the first clean application-code scope. Both affected SSH profiles were verified; old working trees were on historical Git commit 47dd5fa34fae2f222ad23ce521c0c5034c1cadc8 and no matching old app process was reported in the prior audit.

**Attempted cleanup outcome:** The execution tool rejected the deletion operation before running it. A subsequent read-only check on 15 Oct 2026 (UTC approximately 05:13) confirmed:

| Target | Execution-VPS | Observation-VPS |
| --- | --- | --- |
| /home/ubuntu/Nbot historical checkout | **PRESENT**, old SHA 47dd5fa34fae | **PRESENT**, old SHA 47dd5fa34fae |
| /home/ubuntu/nbot-final-reset-20261014 old empty marker | PRESENT | PRESENT |
| /etc/systemd/system/nbot-v5-g1g2g3-observation.service | Not present | PRESENT; inactive |
| Any cleanup or backup executed by this session | NO | NO |

No second destructive route was attempted after the block. This is an **execution-environment restriction**, not a statement that the owner withheld permission. Do not claim old VPSs are clean.

## 2. Approved product authority and strict boundaries

Read only the three original V5.1 product/owner/engineering documents and Version 1.9 Vision §§8G–8H as controlling architecture. Seven stages must remain separated. Original V4 24 patterns are *hypotheses*, not profitable models. Future required dimensions remain **up to 100 lightweight observation coins, 20 deep-source coins including BTC, rolling at most 40 active virtual research intents, and a maximum of one global future real exchange position**. Research/learning require genuinely qualified original-source and after-cost economic witnesses. Paper and live trading are LOCKED by separate review.

G0-04 only finalizes a **nontrading G1-01 first-code scope**. It does not authorize market subscription, old SQLite data migration, VPS deployment, simulated portfolio release, Binance account usage or live orders. Historic old-code references shall be provenance only.

## 3. Exact minimal first code-change set, once scope gate is closed

**Target new package:** `nbot_v5_1`, not legacy `nbot` or `nbot.v5`. All files **new**, in GitHub branch `nbot-v5.1`. Do not copy the old directory tree.

| First-code file (proposed; does not yet exist) | Required implementation | Explicit exclusions |
| --- | --- | --- |
| `nbot_v5_1/__init__.py` | Plain `__version__ = "5.1.0"` and no executable startup work | Historical `nbot/__init__.py` declares 3.0.0; never import legacy namespace |
| `nbot_v5_1/core.py` | Pure stdlib-only immutable/validated five-minute event clock; source evidence and reason/state enums; canonical deterministic **version-/domain-separated** SHA-256 IDs; explicit no-order/NO_TRADE authority type; strict timestamp and source-as-of checks | No network client, scheduler, disk writer, sqlite3, external model, trading executor, private API, hidden import-time side effects, old 50 coin limit |
| `tests/test_v5_1_core.py` | Offline stdlib unittest for full T01–T12 safety matrix below; test source/decision timing, canonical hashes, finite JSON and no-order import isolation | No real Binance network traffic, credentials, paper/real orders, VPS service dependency or old database |

**Minimum source provenance for COPY-AND-ADAPT behavior:** historic observation source `nbot/v5/observation_contract.py` on `feature/v5-observation-integrated-20261014` commit `1e7c090d05dc118b290c764d58c2944f56ad4b3b`, **blob 99b9544fe32239e7b707b6ea09a87a452210034b**. Extract only the pure intent of `_canonical`, `_digest`, `Evidence`, `_evidence_reasons`, `INTERVAL_MS=300000`; rewrite their interfaces to V5.1. Original test `tests/test_v5_observation_contract.py` blob `ff0d2aae223233c6ea23c0b45cc5475792e6d723` is historical *synthetic* regression guidance only.

**Rejected imports:** whole `nbot/v5/observation_contract.py`, `initialize_candidate_ledger`, `append_candidate_records`, `build_candidate_records`, old `MAX_SYMBOLS=50`, `NBOT_V5_CANDIDATE_OBSERVATION_V2`, `sqlite3` dependency, `nbot/__init__.py` V3 version identity, old `nbot.v5.ws_contract`, `nbot.v5.source_epochs`, old V4 research engine and old paper/exchange executors. Later approved G2–G12 tasks design those components independently.

## 4. The G1-01 acceptance matrix (to IMPLEMENT and RUN later; nothing has passed)

| Test ID | Required test demonstration |
| --- | --- |
| T01 | Import is side-effect-free and cannot access FS/network/db/order by default |
| T02 | Package identity precisely V5.1; no historical runtime import or fixed old path |
| T03 | Aligned closed 300,000-ms candle event and valid decision clock are accepted |
| T04 | Invalid booleans/nonintegers/negative/future/stale/premature timestamps fail closed |
| T05 | Missing, stale, future, disconnected or unknown BTC/symbol/source state yields HOLD/UNAVAILABLE |
| T06 | No original source digest/route proof implies **no original-grade economic claim** |
| T07 | Canonical hash is deterministic independent of dict key order; new namespace/version domain separation |
| T08 | NaN/Infinity/unserializable or unexpected payload is rejected |
| T09 | Evidence reasons deterministic and auditable, never interpreted as a fill or PnL |
| T10 | Default authority NONE and NO_TRADE; no paper/live/virtual order-entry interface |
| T11 | No old 50-symbol constant, V3/V4 package imports, V5 schema/table names or database side effects |
| T12 | Fully offline isolated tests, no host environment variables/secret use or accidental side effects |

Acceptance gate for G1-01 is **all 12 actually executed offline tests PASS**, module/source diff inspection, static import-side-effect review, exact GitHub commit, and owner-friendly roadmap ticks. Merely writing tests or invoking historical test reports does not count.

## 5. First implementation protocol after clearing G0-04

1. Confirm both legacy VPS worktrees and the retired observation unit are actually cleaned *if the owner still requires cleanup first*; record each target and observed absence. Do not remove Ubuntu, SSH, PuTTY authentication or unrelated files, and never remove historical GitHub branches.
2. Explicitly mark this G0-04 scope accepted/closed with a new GitHub commit, linking cleanup evidence and the named three-file proposal. This has **not** happened in this document.
3. Introduce exactly the three clean files on `nbot-v5.1`, with unit tests running in an isolated offline environment. No wholesale V4/V5 module copies.
4. Only when tests pass, link evidence to each completed G1 microtask in both roadmaps immediately. Leave G1 parent unchecked until its entire acceptance gate passes.
5. Future stage and evidence storage (new V5.1 only) must have proper crash recovery and original-source preservation; the owner's waiver of old VPS backups **does not waive new product data integrity**.

## 6. Checkboxes and next step

- [x] **G0-04-SCOPE-DRAFT:** Proposed exact first three files, inherited pure-helper lineage, rejected imports, 12 future tests, mode boundaries and sequencing in GitHub documentation; **15 Oct 2026**, documentation only.
- [x] **G0-03-CLEANUP-BLOCK:** Cleanup command was rejected before execution; read-only checks established old NBOT worktree and old unit remain in place where applicable, **15 Oct 2026**.
- [ ] **G0-03-CLEANUP-EXEC:** Complete approved NBOT-only old-VPS cleanup and verify results on both hosts; **BLOCKED** in this session.
- [ ] **G0-04-CLOSE:** Finalize/accept first-code scope **after** the owner-requested cleanup, with commit and proof; not yet passed.
- [ ] **G1-01:** Create the three new files and demonstrate actual offline test results; not started.

**No real-money order, paper order, service startup, secrets read, code import or host cleanup has been performed by this scoped G0-04 document.**
