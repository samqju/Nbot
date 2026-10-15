# NBOT V5.1 — Current Status and Next-Chat Handoff

**Updated:** 15 October 2026  
**Repository:** [samqju/Nbot](https://github.com/samqju/Nbot), branch **`nbot-v5.1`**, not `main`.  
**Authoritative, unmodified product blueprint:** [Vision V1.9](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_COMPLETE_PRODUCT_VISION_V1_9.md).  
**Current roadmaps:** [Owner Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_OWNER_ROADMAP_V1_0.md) and [Engineering Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md).

## 1. Single authoritative gate status

| Milestone | Current checked state | What this means |
| --- | --- | --- |
| G0 | **[x] COMPLETE** | Old source assessment, targeted owner-run two-VPS legacy cleanup, owner waiver of **OLD** version backups, and approved clean first-code plan |
| G1-01 | **[x] COMPLETE** | Pure versioned core, closed-five-minute identity/evidence HOLD, no order authority |
| G1-02 | **[x] COMPLETE** | Mode locks, guardian veto and bounded audit journal |
| G1-03 | **[x] COMPLETE** | Conservative source cursor, restart HOLD, file-and-directory fsync, simulated crash/corruption tests |
| G1-04 | **[x] COMPLETE** | Full G1 independent acceptance, actual Python 3.12.3 tests on **both** VPSs |
| **G1 parent** | **[x] COMPLETE, PASS** | All four G1 phases complete **for the nontrading offline foundation**. The separate [G1 final report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md) now says so explicitly at top AND bottom |
| G2-01–G2-06 | **[x] COMPLETE** | Public USD-M qualified 100-symbol cohort, closed five-minute history, source/timing/archive records, independent negative tests, two-VPS benchmark, actual one-shot public verification |
| **G2 parent** | **[x] COMPLETE, PASS** | [G2 final report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md) |
| **G3** | **[ ] NOT STARTED** | Next milestone: causal 24-detector Exploration; G4–G12 still [ ] |

**User clarification (15 October 2026):** A previous chat connection was interrupted after G2 code and roadmap commits. Subsequent GitHub readback confirmed the G2 final acceptance report and BOTH checked roadmaps survived. The G1 report explicitly contained `parent G1 [x] — PASS` but also had a historical line saying G2 was next; that text has been clarified. **No G1 subtask is incomplete.**

## 2. Reproducible evidence with exact pinned source revisions

**G1 tested source:** `c1408ff00ff05ec6349a85202ee877708df87cd0`. **67/67** offline tests PASS under Python 3.13.5 (local) and independently Python **3.12.3 on BOTH VPSs**. The G1 acceptance report lists all 67 cases and exact source file SHA-1s. This G1 completion is *offline/nontrading-only*.

**G2 tested source:** `4ba07385bb06ad8cde2460d83953448386f1a751`, with **no application-source changes after this commit** (only evidence/roadmap/handoff documentation). The following ran on BOTH VPSs from temporary cloned GitHub checkouts under Python **3.12.3**:

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py' -q` — **120/120 PASS** on Observation-VPS (3.308s) and Execution-VPS (3.377s), both exit 0.
- `PYTHONDONTWRITEBYTECODE=1 python3 -B benchmarks/g2_observation_benchmark.py` — both PASS for 100 symbols × 96 closed bars × 120 synthetic five-minute events with 10 forced source gaps. Observation-VPS p95/p99 **50.500/51.867 ms**, RSS **37,964 KiB**, CPU **2.2465 s**; Execution-VPS p95/p99 **51.823/60.326 ms**, RSS **37,868 KiB**, CPU **2.1026 s**. Each temporary source/snapshot test used **2,713,184 bytes**; 100-record denominator was verified each event.
- One-time real public GET-only Observation-VPS probe `python3 -B scripts/g2_readonly_probe.py --public-network --max-history-requests 130` — **100/100 eligible USD-M symbols including BTC**, each with 96 contiguous closed 5m candles, 100 current METADATA_CLOSED rows and 0 HOLD, request weight **246**, **103 byte-exact public source receipts hash-verified and replayed** (~792,894 gzip bytes); 0 account/order calls. The public test archives and checkout were automatically deleted; no permanent source streaming/archival service was installed.

**G2 source/test/benchmark files:** `nbot_v5_1/universe.py`, `observation.py`, `observation_store.py`, `public_market.py`, `source_archive.py`; `tests/test_v5_1_g2.py`, `test_v5_1_g2_archive.py`, `test_v5_1_g2_receipts.py`; `benchmarks/g2_observation_benchmark.py`, `scripts/g2_readonly_probe.py`. Exact final SHA-1s and all G2 individual passes live in the G2 final acceptance report.

## 3. Hard boundaries — NOT approved or proven

- **No permanent V5.1 deployment/service running on either VPS**. The source/bench host checkouts were temporary and cleaned. No paper/testnet/real order, account credentials or exchange private APIs accessed.
- The G2 actual public REST bytes **are not** independently authenticated original high-frequency trade, quote, mark, funding or fill evidence. No after-cost profit label can be issued by G1/G2. The owner waiver of OLD abandoned data backups does NOT extend to NEW V5.1 original source custody/restore/retention.
- Full source-grade 20-deep market monitoring, rolling 40 virtual trial outcomes, model economics, Champion/Challenger paper books and eventual real execution each retain later independent gates and real-money release controls.
- A physical VPS power cut, genuine long-lived streaming load, external provider rate bans and off-host archive/restore have **not** been claimed as qualified by G1/G2 short synthetic tests.

## 4. Next engineering work, without skipping milestones

**Next unchecked engineering gate:** **G3-01**, then G3-02 onward. The Engineering Roadmap §4 G3 requires independent provenance and semantic review of all **24 historical V4 detector implementations** (pin source commit, exact old path and blob). Re-implement or port only reviewed semantics into the clean V5.1 package; keep all 24 state names and unavailable flags stable. Need causal BTC / market / coin structure at known-at clocks, full **up-to-200 symbol–direction denominator** from 100 markets × two sides, explicitly distinguish NOT_EVALUATED_CAPACITY, NOT_EVALUATED_SOURCE, UNAVAILABLE, NO_MATCH and NO_TRADE. No false strategy profitability or hidden future candles. Every independently proven task must be ticked in BOTH roadmaps, accompanied by exact GitHub code commits, test outputs and an owner-readable dated report. **Never tick a G3 subphase before its evidence exists.**

### Ready-to-use continuation prompt

> Continue NBOT V5.1 in GitHub `samqju/Nbot` branch `nbot-v5.1`. First read `docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md`, the Owner and Engineering Roadmaps, Vision V1.9, and the G1/G2 final acceptance reports. G0, G1 (G1-01 through G1-04) and G2 (G2-01 through G2-06) are fully passed with exact evidence; G3 is next. Complete the next requested G3 subphase against the original V4 source references, without wholesale old code copying. Independently run tests, record exact code hashes and results, tick every microtask in BOTH roadmaps, and preserve the no-trade/source-custody restrictions. Never enable paper/testnet/real trading. If tests or dependencies cannot be proven, mark that precise item HOLD instead of falsely marking PASS.

**Status truth:** G0 [x] · G1 [x] · G2 [x] · **G3 [ ]** · G4–G12 [ ]; all exchange order authority LOCKED.
