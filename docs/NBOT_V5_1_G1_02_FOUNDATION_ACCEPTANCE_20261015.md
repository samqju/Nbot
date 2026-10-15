# NBOT V5.1 — G1-02 Safe Foundation Components: Offline Acceptance

**Date:** 15 October 2026 IST  
**Branch:** `nbot-v5.1` — strictly new V5.1 package; no deploy, no services.  
**G1-02 result:** **PASS for the narrow offline journal/mode/guardian component milestone.**  
**G1 parent result:** **NOT PASSED / remains unchecked** pending future full integration, crash durability/recovery, version/runtime and deployment-independent safety acceptance.  
**Trade authorization:** **NONE**; PAPER/TESTNET/REAL remain locked.  
**Authority:** Complete Product Vision V1.9, Engineering Roadmap G1 and approved G0-04/G1-01 scope.

## 1. Implemented and verified GitHub changes

| File | Type / purpose | Exact Git blob SHA-1 |
| --- | --- | --- |
| `nbot_v5_1/foundation.py` | **NEW** immutable OFFLINE/OBSERVATION config, future mode vocabulary still locked, untrusted evidence grades, validated proposal envelope and guardian that only vetoes or returns NO_TRADE | `b2f191b478125cf06937e1498f059737d0081a58` |
| `nbot_v5_1/journal.py` | **NEW** explicit-I/O, owner-private, bounded append-only audit journal using canonical JSON, ordered SHA-256 hash chain, sequential receipts, duplicate-safe retries, `flock`, `O_APPEND`, `fsync` and strict fail-closed replay | `be47689791602b9c4d607ff4437c90e16710b2f8` |
| `tests/test_v5_1_foundation.py` | **NEW** F01–F15: 15 offline negative/positive safety tests for capability locks, evidence grades, clock validation, guardian veto and safe imports | `07f805f63e0e97b634d3b8152ecd6556faa93496` |
| `tests/test_v5_1_journal.py` | **NEW** J01–J18: 18 offline durability/interface tests covering torn writes, altered data, hash links, schema, bad permissions, symlinks, size, replay, guardian-to-journal integration and three simultaneous child writers | `cc50f7526353dba7fa5582b1d5a7385242424d53` |
| `tests/test_v5_1_core.py` | **NARROW TEST HARNESS FIX**: the existing T01 import-safety check now runs in a separate, blocked-network/filesystem/subprocess interpreter, rather than reloading shared classes in-process. Preserves original T01–T12 cases and avoids cross-module type identity collisions | `cf457b06aa0525380fb27f62f4be08c1bbdda6f8` |

**Code commit sequence:**
- G1-02 modes, proposal and guardian: `a1fefdf74f9e677f531f2cc819a8260c4508df43`.
- Bounded append-only journal: `2209dd878904b194c5390bd12dbb2f38c4d4e232`.
- Foundation tests: `48c1e0e60db66a740179960708de91cd8435dc9e`.
- Journal tests: `c4e604ded8d01dde996eb3874b1b16cd386630c8`; byte-identical local test order committed in `77c61289954b652ca972b1f4ff95c93693c5a991`.
- Pre-existing core import safety harness isolation: `b76cfc559e7c942c7be4263b51baf871b3de61f8`.

All **five GitHub file contents were refetched and their blob hashes checked against the exact offline-tested local files**. GitHub compare from closed G1-01 head `2544f6af438ca9b30e986fec59e7a2b41a121ec3` changed exactly these five files; no legacy application, VPS deploy scripts or other code imported.

## 2. G1-02 test results and integrity boundaries

**Final executed command, clean isolated Linux working folder:**

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -f 'TEST_PROCESS_WALL_SECONDS=%e MAX_RSS_KB=%M' \
  python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py' -v
```

**Executed output:** **Ran 45 tests in 1.752s; OK; zero failures/errors.** Total measured process wall **2.44s**, peak max RSS **100,624 KiB**. Python **3.13.5**. All seven source/test Python files parsed with Python 3.12 grammar using `ast.parse(..., feature_version=(3,12))`: **PASS**; **Python 3.12 interpreter/runtime tests were NOT executed**. These are synthetic, local tests with a temporary journal sandbox, **not GitHub CI**, real exchange execution, original-source grade proof or VPS endurance. Test process RSS includes Python/stdlib/test harness overhead; it is **NOT** a qualified VPS 100/20/40 capacity result.

**Test breakdown:**

| Group | Count | Outcome |
| --- | --- | --- |
| Existing G1-01 T01–T12 | 12 | **PASS**, including now-isolated side-effect import guard |
| G1-02 F01–F15 | 15 | **PASS**: modes locked, malformed configuration/envelopes and uncertain/future evidence veto, no automatic grade upgrade |
| G1-02 J01–J18 | 18 | **PASS**: append/read integrity, idempotency, damaged/torn tail HOLD, schema/hash conflict, secure-file checks, quota and three concurrent writers |
| **Total** | **45** | **45 PASS / 0 FAILED / 0 ERRORS** |

**Integration observation:** The first combined 41-test run showed 4 cross-test errors because historical G1-01 T01 reloaded the core module and invalidated Python dataclass identity in already-imported guardian tests; **that was a test isolation fault**, not a guardian trade authorization. Repaired by invoking T01 safely in a separate Python subprocess, then independently reran 44-test and final **45-test** full suites. The final five GitHub file hashes match the exact final 45-pass local files.

## 3. Milestone microtasks — complete only where tested

- [x] **G1-02-A:** Versioned, immutable and default OFFLINE/NO NETWORK/NO ORDER configuration; future paper, challenger, virtual and REAL mode values are descriptive only and cannot be activated.
- [x] **G1-02-B:** Closed synthetic/metadata-only source-grade contract, with ORIGINAL_VERIFIED/AFTER_COST_QUALIFIED **explicitly not issuable** in G1; no self-qualification by digest.
- [x] **G1-02-C:** Strict immutable event/proposal/expiration envelope and guardian verdict with unconditional NONE authority and NO_TRADE, including missing, delayed, malformed BTC/symbol sources and model attestation absence.
- [x] **G1-02-D:** Versioned, **4 MiB default capped** append-only, explicit-I/O journal for metadata-only audit events; private regular-file permissions, hash links, unique ID replay, safe idempotence, file fsync and no silent repair.
- [x] **G1-02-E:** Negative tests for unsupported/permissive/symlink/hardlink paths, interrupted tail, tampering and capacity; guardian veto integrated into the audit journal; process-safe advisory concurrent append tested.
- [x] **G1-02-F:** Combined new and regression suite **45/45 PASS** on Python 3.13.5 with 3.12 syntax parse; details above.
- [x] **G1-02-G:** GitHub blob SHA/file compare verifies exact tested copy and only G1-02 files changed.
- [x] **G1-02-H:** G1-01 test reload side effect fixed by isolated import test, verified with entire combined test suite.
- [x] **G1-02 child milestone CLOSED.** No deployment or trading mode entered.
- [ ] **G1 parent:** Full integration/remaining recovery safety, runtime version and broader acceptance not passed; keep OPEN.
- [ ] **G2 and later:** Original Binance data collection, 100/20/40 throughput, 24 detector science, Research after-cost grades, models, paper/live execution all future steps.

## 4. Explicit limitations: not a qualified runtime or a real trade journal

The journal records **limited metadata/reason codes only**, not per-tick source history, market data frames, original quotes, fills, secrets or raw account data. It is **append-only within this implementation**, not a remote immutable/WORM archive. Its SHA-256 chain detects accidental/unauthorized *in-place* mutations under ordinary trust assumptions, **not a malicious holder of write access recomputing the whole chain**. File `fsync` is used on append, but parent-directory fsync, host crash/power-failure matrix, rollback/off-host custody, rotation, crash-safe durable source checkpoints and volume pressure/restart recovery have **NOT** been fully tested. These must be addressed before G1 parent or G4/source-stage claims of reliable custody.

Python POSIX `fcntl` is used for the local journal; it targets Linux offline use only, not Windows/NTFS or network filesystems. The default 4 MiB journal budget caps metadata disk use; exceeding it **fails closed** rather than writing more. A full-market evidence storage engine and genuine economics will be different later stages. No implicit network, import-time writes, credential access, account API or paper/real executor is introduced here.

**Risk policy:** Owner's no-backup decision was for obsolete V3/V4/V5 VPS installations, **NOT newly generated V5.1 evidence**. No V5.1 source/economic evidence must be discarded or inferred through reboot gaps. Services remain STOPPED; paper, testnet and REAL authority remain LOCKED.

**Next:** G1 remaining offline cross-module recovery/bootstrap/security acceptance (suggested G1-03); G1 parent stays [ ] until those tests and acceptance evidence exist.
