# NBOT V5.1 — G0-04 Approved First Clean Application-Code Scope (Gate Closed)

**Dated:** 15 October 2026 IST  
**Branch:** nbot-v5.1  
**Current status (15 Oct 2026 owner update):** **G0-04 FIRST-CODE SCOPE APPROVED / CLOSED; actual old VPS cleanup remains UNVERIFIED and G1-01 code/tests NOT STARTED.** The owner subsequently instructed us to give safe manual cleanup commands if remote deletion failed, and **meanwhile complete G0-04**. That supersedes the earlier sequencing *for a documentation-only scope decision*, not for cleanup execution or G1 deployment.

## 1. Why this document exists

The owner originally directed cleanup before G0-04, then specifically instructed us to **finalize G0-04 in parallel** while they run manual old-VPS cleanup instructions if remote deletion is blocked. Both affected SSH profiles were verified; old working trees were on historical Git commit 47dd5fa34fae2f222ad23ce521c0c5034c1cadc8 and no matching old app process was reported in the prior audit.

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

## 3. Approved minimal first code-change set (for future G1-01 implementation)

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

## 5. First implementation protocol following completed G0-04

1. **G0-04 scope approval is independent of actual cleanup**, per the owner's newer instruction to finish the scope while they handle old VPS deletion manually. Verify clean VPS state **before any VPS installation/deployment**; record exact deletion evidence separately when provided. Never remove Ubuntu, SSH/PuTTY authentication, unrelated files or historical GitHub branches.
2. G0-04 is **approved at documentation/specification level** by the owner's 15 Oct 2026 instruction; exact file layouts, signatures and tests below are binding. No application code or runtime test is implied by closing it.
3. Introduce exactly the three clean files on `nbot-v5.1`, with unit tests running in an isolated offline environment. No wholesale V4/V5 module copies.
4. Only when tests pass, link evidence to each completed G1 microtask in both roadmaps immediately. Leave G1 parent unchecked until its entire acceptance gate passes.
5. Future stage and evidence storage (new V5.1 only) must have proper crash recovery and original-source preservation; the owner's waiver of old VPS backups **does not waive new product data integrity**.

## 6. Checkboxes and next step

- [x] **G0-04-SCOPE-DRAFT:** Proposed exact first three files, inherited pure-helper lineage, rejected imports, 12 future tests, mode boundaries and sequencing in GitHub documentation; **15 Oct 2026**, documentation only.
- [x] **G0-03-CLEANUP-BLOCK:** Cleanup command was rejected before execution; read-only checks established old NBOT worktree and old unit remain in place where applicable, **15 Oct 2026**.
- [ ] **G0-03-CLEANUP-EXEC:** Complete approved NBOT-only old-VPS cleanup and verify results on both hosts; **BLOCKED** in this session.
- [x] **G0-04-CLOSE:** Scope finalized/accepted by owner instruction to proceed in parallel while they run manual cleanup; specified the exact 3 new application/test files, pure API contracts, source provenance, no-trade boundary and T01–T12 test plan. **This is a documentation acceptance, not a runtime test.**
- [ ] **G1-01:** Create the three new files and demonstrate actual offline test results; not started.

**No real-money order, paper order, service startup, secrets read, code import or host cleanup has been performed by this scoped G0-04 document. G0-04 scope closed; G0-03-CLEANUP-EXEC and G1-01 implementation/testing remain OPEN.**


## 7. Binding first-code API/validation contract — G0-04 final owner decision

These definitions **narrow** the earlier high-level table and eliminate ambiguity for G1-01. No source file implementing them exists yet.

**New Python package:** \`nbot_v5_1\` is independent of older \`nbot\`. Use Python standard library only. No import side effects beyond creating immutable Python constants and type/class definitions; no optional old fallbacks. Exactly three new files in G1-01, as listed in §3.

### 7.1 Canonical exported symbols in nbot_v5_1/core.py

| Export | Exact conceptual contract |
| --- | --- |
| \`INTERVAL_MS = 300_000\` | Five-minute boundary constant; immutable, no wall-clock access. |
| \`CORE_SCHEMA_VERSION = "NBOT_V5_1_CORE_V1"\` | A *new* explicit identity domain; old legacy schema identifiers remain historical. |
| \`FiveMinuteEvent(event_open_ms: int, decision_at_ms: int)\` | \`@dataclass(frozen=True)\`, strict integers excluding booleans, \`event_open_ms >= 0\` and divisible by \`INTERVAL_MS\`; \`decision_at_ms >= event_open_ms + INTERVAL_MS\`. \`event_close_ms\` computed; no I/O or implicit now-time. |
| \`SourceEvidence(last_closed_bar_open_ms: int, source_max_bar_open_ms: int, observed_at_ms: int, source_digest: str | None, source_epoch: int | None, route_state: str, quality_issues: tuple[str, ...] = ())\` | \`@dataclass(frozen=True)\`; recorded metadata, **not a claim of original proof or qualified fills**. Explicit routes states \`HEALTHY\`, \`GAP\`, \`UNKNOWN\`; evidence is separately tested against event. Absence stays absence. Raw source bytes and TLS attestations are future G2/G4 work. |
| \`evidence_hold_reasons(event: FiveMinuteEvent, evidence: SourceEvidence | None, *, prefix: str)\` | Return a sorted deduplicated tuple of stable reason codes. \`None\` gives \`{prefix}_MISSING\`. Check no future/stale/wrong candle, invalid epochs/digests, unhealthy source; \`observed_at_ms\` must lie between close and decision. Fail closed; no hidden source recovery. |
| \`canonical_digest(domain: str, payload: JSON-compatible value) -> str\` | Lowercase SHA-256 of UTF-8 \`json.dumps\` with \`sort_keys=True\`, separators \`(",", ":")\`, \`allow_nan=False\`, **without arbitrary string coercion**; input wrapped with \`CORE_SCHEMA_VERSION\` and an explicit non-empty whitelisted domain from \`event\`, \`evidence\`, \`intent\`. New IDs must not collide with old domain-independent V5 hashes. Reject floats/NaN/Infinity if unsafe, boolean in integer fields, unsupported objects; no filesystem cache. |
| \`ObservationAuthority\` and \`ObservationDisposition\` (closed enums) | Authority value **NONE** only in first code slice; disposition values **OBSERVE_ONLY**, **HOLD**, **NO_TRADE** (not order instructions). No enum may enable \`LIVE\`, \`PAPER\`, buy/sell, fill or order placement. |

**Failure semantics:** All invalid evidence stays visible via HOLD reasons, rather than being converted to a matching pattern or synthetic observation. Missing BTC or symbol evidence is HOLD; absence of a source_digest/verified source-epoch never upgrades a candle to original authenticated economic evidence. The first core module does **not** accept a market-universe size; therefore it cannot accidentally enforce historic 50-symbol capacity or claim 100/20/40 has been implemented. The future G2/G3 event scheduler owns active-universe and capacity masks; G1 does not.

**Source boundary:** A 64-character digest proves only content identity *if the upstream original bytes and route custody were independently established elsewhere*. Do **not** encode source/economic qualification as a truthy digest flag; actual verification and after-cost label admission are later separate gates.

### 7.2 Precise T01–T12 test acceptance elaboration

- T01: assert imports under stubbed/blocked network, subprocess, file writes, DB open and old package modules do not attempt I/O or trading.
- T02: \`__version__ == "5.1.0"\`, core identifier is V5.1-only, no \`nbot\` import or service startup.
- T03: valid aligned event/decision inputs, including earliest legal decision exactly at close; deterministic \`event_close_ms\`.
- T04: reject booleans, floats, negative, misaligned event and decision before close; evidence future/stale/invalid timestamps HOLD.
- T05: missing BTC/symbol evidence, disconnected/unknown route, invalid epoch, incomplete source and wrong candle all produce explicit stable reasons.
- T06: digest missing/invalid and no independently verified source custody never imply qualified original market provenance or after-cost score.
- T07: same dict data with different insertion order hashes identically; differing event/domain/schema changes the ID.
- T08: reject NaN, Infinity, non-JSON objects and forbidden numeric coercions with explicit errors; no \`default=str\`.
- T09: stable sorted unique reason codes independent of input issue order and repeated evaluation.
- T10: no order-placement functions/classes/credentials/private Binance imports; defaults are \`NONE\` and \`OBSERVE_ONLY\`/\`HOLD\` or \`NO_TRADE\`.
- T11: static scan and import isolation rule out \`MAX_SYMBOLS = 50\`, old package/version/table names, any SQLite connection or database migration.
- T12: run solely offline with hermetic synthetic fixtures and explicit no-side-effect assertions; report command, environment, count and failures in both roadmaps.

**Exit evidence to record for G1-01:** Exact GitHub file+commit SHAs, readable code/test diffs, command and per-test results (no historical pass substituted), no-order/source HOLD negative cases, and environment/resource observation. Only then may G1-01 be ticked. Later old-source reuse requires separate module-level audit.

## 8. Updated task decision, 15 October 2026

- [x] **G0-04-F1:** Exact new Python package boundary and strictly limited three-file scope fixed.
- [x] **G0-04-F2:** Imported behavior traced to pinned historical source blob, no legacy module or database copied.
- [x] **G0-04-F3:** Pure immutable source/clock/authority/digest API and failure behaviors fixed in §7.
- [x] **G0-04-F4:** Detailed 12 offline verification cases plus evidence thresholds fixed.
- [x] **G0-04-CLOSE:** Owner explicitly directed G0-04 scope finalization in parallel with manual VPS cleanup. Code-scope review is now complete, separate from deployment/cleanup status.
- [ ] **G0-03-CLEANUP-EXEC:** Historical working folders and service still present at most recent read-only check; owner will provide results of manual cleanup.
- [ ] **G1-01-CODE-AND-TEST:** No V5.1 application source or unit tests written or run yet.

**Final outcome:** **G0-04 PASS as a DOCUMENT/SCOPE decision**, G0 parent still OPEN pending old VPS cleanup verification; G1 implementation/testing NOT STARTED; paper and real-money trading remain LOCKED.
