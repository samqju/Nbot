# NBOT V5.1 — Current Status and Next-Chat Handoff

**Updated:** 15 October 2026 (through full G3 engineering acceptance; next G4)  
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
| **G3-01 source/24 detectors** | **[x] COMPLETE** | All 24 exact original V4 IDs, independent SHA catalog, 19 two-sided and five context goldens; pure V5.1 wrapper |
| **G3-02 causal context** | **[x] COMPLETE** | Closed-only BTC/market/coin structures, original group tags, expiry and missingness |
| **G3-03 complete directions** | **[x] COMPLETE** | 100×LONG/SHORT=200, 24 detector states each, distinct capacity/source/NO_MATCH/UNAVAILABLE, NO_TRADE/NONE |
| **G3-04 compressed records** | **[x] COMPLETE** | Fsynced private SHA/gzip full 200×24 masks with tamper/quota/restart hold |
| **G3-05 two-VPS acceptance** | **[x] COMPLETE** | Python 3.12.3 157/157 PASS on EACH VPS and separate 2,400-direction p99/RSS/CPU/disk benchmark PASS |
| **G3-06 public acceptance** | **[x] COMPLETE** | One-time actual 100 public symbol histories/BTC, 103 raw REST receipts, 200 capacity mask rows, no trades |
| **G3 parent** | **[x] COMPLETE, PASS** | [G3 full report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), commit **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**; code SHA `5d9707fe8521bbe17e96036aef0a5ec44a784a96` |
| **G4** | **[ ] NOT STARTED** | Next: fair 100→20 deep coin selection (BTC included) + original trade/quote/funding source provenance, bounded archive and recovery |

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

**Latest next unchecked engineering gate: G4-01**, then remaining G4. **G0/G1/G2/G3 are ALL COMPLETE.** G3 source `5d9707fe8521bbe17e96036aef0a5ec44a784a96` passed 157/157 tests separately on Observation and Execution VPS Python3.12.3, independent 100-symbol ×2 directions ×24 detectors ×12-event p99/RSS/disk/CPU PASS, and a real one-shot public 100→200 all-NO_TRADE capacity-masked observation with 103 original public REST source receipts replayed. Complete acceptance details: [G3 report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**. The old 24 original V4 rule identities are individually ticked in both roadmaps and the historical register; original source commit `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf` remains untouched.

**G4 must not be skipped:** audit exact source candidates (R06/R13/R14), implement a fair decision-time 100→20 deep research shortlist with BTC mandatory, preserve eligibility and inclusion probabilities, then establish independently authentic *original trades, bid/ask quotes, mark and settled-funding evidence* with conservative gap/restart/source epochs, gzip hash-chained bounded segments and observed storage/resource costs. Offline 20-source simulations cannot substitute for original provider witnesses. No existing G2 or G3 metadata hash can promote a trade or profit label. Every G4 microtask needs an individual test/provenance-backed tick in BOTH roadmaps. All actual VPS services remain unstarted until full pipeline/offline acceptance as separately authorized.

### Ready-to-use continuation prompt

> Continue NBOT V5.1 from GitHub `samqju/Nbot` branch `nbot-v5.1`. First read `docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md`, current Owner and Engineering Roadmaps, Vision V1.9, G3 final acceptance report and legacy component reuse register. G0, G1, G2 and **entire G3** (G3-01–G3-06) are marked **[x] PASS**, each with test/commit evidence. G3 source SHA `5d9707fe8521bbe17e96036aef0a5ec44a784a96`, 157/157 tests on BOTH VPS Python3.12.3, 100×2×24 p99/RSS/CPU/disk PASS, actual public 100-market→200 no-capacity G3 receipt replay PASS. Historical V4 24 detector rules are hypotheses, not profitable strategies. Start **G4-01**: fair frozen 100→20 source-qualified deep shortlist including BTC, then authentic trade/quote/mark/funding source and bounded compressed retention/failure/recovery. Review pinned R06/R13/R14 historical code before copying anything. Continue small independent tests and microticks in BOTH roadmaps. Do not deploy/start services or enable paper, testnet or real-money trades. If original-source qualifications cannot be verified, mark exactly that item HOLD; never mark G4 PASS on synthetic price-only or fabricated economic data.

**CURRENT GATE STATUS:** G0 [x] · G1 [x] · G2 [x] · **G3 [x]** · **G4–G12 [ ]**. Entire trading and order authority **LOCKED**; no permanently running NBOT application on either VPS.
