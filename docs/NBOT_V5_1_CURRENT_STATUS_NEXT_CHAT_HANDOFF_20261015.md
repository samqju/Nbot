# NBOT V5.1 — Current Status and Next-Chat Handoff

**Updated:** 15 October 2026 (G4 partial engineering; 20-market real trade-source HOLD; next G4-06-A)  
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
| G4-01 frozen deep20 cohort | **[x] COMPLETE** | Qualified BTC and fair 100→20 source WARMUP_HOLD, every selection/exclusion K/N probability; 8 tests PASS |
| G4-02 public source protocol | **[x] CODE/TEST COMPLETE** | Public USD-M WSS quote/trade/mark source, per-coin trade ID HOLD, routes, local TLS probe |
| G4-03 bounded raw byte segments | **[x] CODE/TEST COMPLETE** | Finite SHA-gzip raw source, fsync, corruption/gap/restart guards; same-host test replay, not off-host science proof |
| G4-04 settled funding separation | **[x] COMPLETE** | Separate public settled BTC funding REST receipt and raw SHA; NOT evidence of position funding debit |
| G4-05 testing/live probe | **[x] COMPLETE WITH LIVE SOURCE DEFICITS** | 186/186 tests on EACH VPS, both 3,600-frame/20-source synthetic benchmarks PASS; actual 3,077 public WSS messages hash-replayed, but 47 trade gaps and only 19/20 valid trade symbols |
| **G4-06 / parent** | **[ ] HOLD, NOT COMPLETE** | [Dated G4 progress/HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**. Need 20/20 clean real source continuity, long-run envelope, independent source grade and off-host archive restore. |
| **G5–G12** | **[ ] NOT STARTED** | Future virtual/paper/real money remain strictly locked |

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

## 4. Next exact remaining G4 work and no-skips handoff

**G4 parent [ ] HOLD, NOT COMPLETE.** Completed code/tests/real public-source sampling must not be conflated with a fully source-qualified 20-market research system. [Full G4 engineering progress and blockers](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), commit **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**; last accepted code SHA **`07186992fdfc8b2fc1b66e39b6d78513ee23891e`**, 186/186 tests PASS separately on BOTH Python3.12.3 VPSs, independent BTC-included 20×3×60 3,600-frame workload p99/RSS/CPU/disk PASS. Actual public WSS capture: **3,077 raw received/replayed frames** (2,673 quote/78 mark/326 accepted trade), **47 rejected trade frame continuity breaks**, **20/20 quote and mark, but 19/20 trade-market coverage**. Public BTC settled-funding history separately verified. All source test archives temporary and removed; no services deployed/trades.

- [x] **G4-01 implemented:** frozen fair 100→20 BTC universe, 100 qualified source cohort, all included/excluded statuses, prospective selection K/N and warmup required — no G5 virtual slots.
- [x] **G4-02–G4-04 implementation and safety tested:** Public USD-M trade/quote/mark WebSocket raw frame identity and per-symbol gap-HOLD, finite owner-private compressed/raw SHA source segments, simulated interrupt/replay, strictly separate public settled funding.
- [x] **G4-05 test/evidence batch completed:** 29 new G4 tests, prior 157 G0–G3 tests, **186/186 on EACH host**, 20×3×60 synthetic frames both host PASS, real public 100→20 WSS capture/sha-replay with missing/gap truth preserved.
- [ ] **NEXT G4-06-A:** Obtain independently clean original public trade, quote and mark sources on **all 20 selected symbols including BTC** with no missing/reordered ID/gaps or unrecorded source epochs. Reselect only at a NEW genuinely source-qualified future cohort; never patch old gaps using candles.
- [ ] **G4-06-B:** Prove real high-rate 20-market sustained traffic, server 24h route reconnect and lossless buffer/archive within VPS disk, CPU, bandwidth, and I/O limits. Synthetic benchmark is not sufficient.
- [ ] **G4-06-C:** Independently validate original provider TLS/session provenance and source grade; keep account/funding and executable quote costs unqualified without separately recorded evidence.
- [ ] **G4-06-D:** Prove actual verified new G4 source archival on the other VPS/off-host destination with hash replay and source epoch-safe restore (old-VPS no-backup waiver never applies to new market evidence).
- [ ] **G4-06-E parent acceptance:** Only after all previous checks and independent two-VPS retest PASS may G4 parent turn [x]; G5+ remain locked meantime.

### Ready-to-use continuation prompt

> Continue NBOT V5.1 from GitHub `samqju/Nbot` branch `nbot-v5.1`. Read `docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md`, both updated Owner/Engineering Roadmaps, Vision V1.9, [G4 progress and HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), and legacy source reuse register. G0–G3 passed fully. G4 PARTIALLY IMPLEMENTED but PARENT remains HOLD [ ]! G4-01 frozen 100→20 with BTC and fair source-warmup states, G4 public original-frame/segment/settled funding contracts, and G4-05 186/186 tests on EACH Python3.12.3 VPS and 3,600-frame deep20 benchmark PASS. Actual public source 100→20 sample captured/replayed 3,077 WSS frames, but had 47 original trade-sequence gaps/rejections and only 19/20 live trade symbols (all 20 quote/mark), so genuine source continuity is NOT qualified. Source revision `07186992fdfc8b2fc1b66e39b6d78513ee23891e`. FIRST complete remaining **G4-06-A clean original 20/20 source continuity**, then **G4-06-B real long-run 20-source resource rate/reconnect/retention**, **G4-06-C independent source/provider/cost grade**, **G4-06-D real off-host source archive/restore**, **G4-06-E full acceptance**. Check each microtask in BOTH roadmaps only after evidence; don't turn G4 parent [x] prematurely. NO service start, no virtual/paper/testnet/real orders. Old data deletion waiver is irrelevant to new source evidence. Do not treat local public WSS frame hashes or BTC settled funding history as actual exchange account fills/costs.

**LATEST STATUS:** G0 [x] · G1 [x] · G2 [x] · G3 [x] · **G4 [ ] HOLD** (G4-01…05 many subtasks [x]; G4-06-A…E [ ]) · G5–G12 [ ]. All order authority LOCKED; no permanent running bot on either VPS.
