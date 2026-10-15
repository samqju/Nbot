# NBOT V5.1 — G4 Deep-20 Source Engineering: Verified Progress & Explicit HOLD

> **LATEST G4 STATUS (15 Oct 2026):** Later owner-approved public-only CS-01 canaries received 20 symbols × (TRADE, QUOTE, MARK), **all 60 cursors observed**, up to **12,572 frames** in the last run. **[ ] G4 sustained original evidence HOLD:** repeated **BTCUSDT bookTicker `EVENT_FUTURE_OR_STALE`** forced safe stop (exit 2). Earlier reported **47 underlying `f/l` trade-ID anomalies require semantic review**; they are not automatically missing aggregate `a` IDs. See [LATEST G1–G4 STATUS + NEXT-CHAT HANDOFF](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md) and [live test report](NBOT_V5_1_FIRST_LIVE_CS01_PUBLIC_ONLY_CANARY_ACTUAL_RESULTS_AND_BTC_QUOTE_HOLD_20261015.md). Historic test descriptions below remain period-accurate but are NOT the latest G4 source gate.


**Date:** 15 October 2026 IST  
**Branch:** `nbot-v5.1`, repository `samqju/Nbot`  
**Exact last fully tested source commit:** `07186992fdfc8b2fc1b66e39b6d78513ee23891e`  
**G4 parent status:** **[ ] HOLD — NOT COMPLETE.** This report deliberately does NOT approve a permanent collector, independent original-exchange source grade, G5 virtual positions, research economic labels, paper/testnet/real orders or starting any VPS services.  
**Unchanged prior gates:** G0 [x], G1 [x], G2 [x], G3 [x] remain PASSED in their own documented engineering scopes.

## Executive finding

The owner requested **all G4**, without skipping or pretending success. The clean V5.1 deep 100→20 shortlist, versioned public USD-M route and frame validation, a bounded compressed byte-preserving source segment recorder, simulated 20×3-source workload and a separate historic settled-funding contract **have been implemented and passed actual offline tests**. A one-shot opt-in real Binance public USD-M 100→20 source run captured/replayed **3,077 real public WSS frames**, but **47 trade-frame continuity problems** were explicitly reported, and one of the 20 selected symbols produced no valid aggregate trade frame in the short window. This is source-HOLD evidence, **not** a clean 20-source original-data release. No independently verified ongoing 20-stream source retention, live disconnect/restore endurance or off-host archival/restore is yet evidenced. Accordingly parent G4 stays unchecked.

## 1. Exact completed small tasks and permanent checkmarks

- [x] **G4-01-A — Source eligibility input:** Deep selector consumes immutable G2 qualified 100-symbol manifest and G3 complete 100×two-side as-of observation. Reject stale manifest, missing BTC, wrong cohort hash or future decision as well as unauthorized G3 order status. Source fields remain public-candle-metadata only.
- [x] **G4-01-B — 20/BTC/dependency cap:** Deterministic **up to 20** unique symbols, always qualified BTC. Every selected record says `SELECTED_WARMUP_HOLD` and `WARMUP_HOLD_NOT_ORIGINAL_VERIFIED` until genuine source warm-up is separately proved. No auto-created Research virtual trades.
- [x] **G4-01-C — Fair breadth/control policy and frozen why:** Stratifies broad universe by gainer, loser, turnover or fallback/control plus BTC, preserves all original overlapping group tags; frozen SHA rotating membership and explicit K/N prospective inclusion probability of EVERY included/excluded candidate. All 100 accounted for when 100 are eligible. No pattern-match-count, hindsight PnL or synthetic profitability ranking.
- [x] **G4-01-D — S01–S08 tests:** Deterministic 20/BTC and entire 100 denominator, wrong cohort/as-of, full capacity/no-pattern selection still WARMUP, prospective propensity, bad count and smaller cohort are all tested PASS.
- [x] **G4-02-A — Exact currently documented public USD-M socket families:** Official [Binance USD-M 14 Oct 2026 routed socket docs](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect) distinguish `wss://fstream.binance.com/public/stream` for `bookTicker` and `/market/stream` for `aggTrade` / `markPrice@1s`. No private/user/order route; 20-market URL budget validated. Historic V5 source paths independently reviewed, no old fixed 50-symbol runtime imported.
- [x] **G4-02-B — Strict raw public message parser:** No implicit network on import, bound frame size, public combined stream identity, matching subscribed symbol/kind/route, epoch and receive/event age, bid/ask positivity and noncrossing, mark/index price and indicative-funding syntax, trade quantity and aggregate/underlying IDs. Per-symbol trade cursors fixed and separately tested; a missing/reordered ID becomes explicit HOLD, never silently repaired by a five-minute candle.
- [x] **G4-02-C — F01–F05 & A10/A11 tests:** QUOTE/TRADE/MARK route/kind/epoch/wrong-symbol/future/stale/nonfinite, per-coin trade gaps and interleaved two-coin IDs all tested PASS. Public TLS WSS local-reception grade is **NOT exchange-signed independent custody**.
- [x] **G4-03-A — Byte-exact source segmentation, bounded RAM and finite disk:** New `deep_segments.py` queues original public raw bytes by route/coin/source epoch, stores exact base64 byte receipts in deterministic gzip segments plus linked SHA256 metadata, owner-private files and directory `fsync`, no per-frame SQLite writes, 1 MiB max uncompressed segment and 64 MiB typical finite test quota, no silent pruning or repair.
- [x] **G4-03-B — Offline crash/tamper/replay behavior:** Independent replay verifies gzip decompression, compressed/body/raw frame SHA, strict structure and **per-symbol underlying/aggregate trade cursor continuity** across segments; two-file partial, malformed/permission/symlink/unknown, incorrect hash, finite quota and broken/overlapping events force HOLD. `attach()` marks all 20 source epochs HOLD after restart rather than falsely recreating missing RAM/source continuity.
- [x] **G4-03-C — A01–A11 segment tests:** Exact raw-byte equality, SHA chains, multi-segment reattach, corrupted gzip, changed manifest, orphan partial after crash, disk limit, private mode, trade gaps, per-symbol interleave and no filesystem effect on import/constructor PASS.
- [x] **G4-04-A — Indicative mark funding vs settled public rate separation:** New `settled_funding.py` strictly parses only public Binance USD-M `GET /fapi/v1/fundingRate?symbol=...&limit=2`, rejects future/unordered settlements, wrong symbol/private route and NaN/Infinity/implausible values; marks grade **PUBLIC_REST_SETTLED_HISTORY_NOT_POSITION_COST** and **zero qualified virtual cost witnesses**.
- [x] **G4-04-B — T01–T05 tests and actual settled BTC public GET:** Observation-VPS, **15 Oct 2026 08:01:29 UTC**, HTTPS 200 public Binance route, two recorded BTC settlements at **00:00 and 08:00 UTC**, public response SHA256 `d3216c03de531ff7509958631b41d5be609a4c2606a965b12a052e0acf53c59e`; no API key, private account endpoint or financial cost qualification.
- [x] **G4-05-A — Complete G1–G4 regression on both VPSs:** **186/186 PASS** each on Python 3.12.3, Observation-VPS 14.882s, Execution-VPS 15.496s, same tested source SHA `07186992fdfc8b2fc1b66e39b6d78513ee23891e`, both unittest exits 0; 157 preexisting G1–G3 + **29 new G4 cases**.
- [x] **G4-05-B — Independent 20×3×60 offline small-VPS benchmark:** Each host selects frozen BTC-including 20 and generates **3,600 simulated raw frames** (1,200 each QUOTE/TRADE/MARK), validates and gzips to 60 chained segments, replays all 3,600 and attaches in a separate restarted recorder with all 20 epochs held. p99 **53.325ms Observation / 60.251ms Execution**; peak RSS **36,408 / 36,396 KiB**, CPU **2.040 / 2.020s**, disk **243,436 bytes** each. Benchmark PASS under 1000ms p99, 256000KiB RSS, 33554432B per-run disk limits. **Synthetic workload, not actual 20-source peak bandwidth/endurance.**
- [x] **G4-05-C — Real public 100→20 read-only discovery and source witness audit:** Observation-VPS at approx **15 Oct 2026 07:58 UTC**, exactly one opt-in read-only TLS public USD-M event. G2 returned 100 qualified live markets with BTC and 96 completed 5m bars each, zero G2 source HOLD, 103 hash-replayed original public REST response receipts (~795,966 compressed bytes), source age 31,692ms, request weight 246. G4 then froze 20 selected BTC-including symbols with all WARMUP_HOLD, manifest SHA `26e7d97117d4a66e30c410a811a221329aadc95ca0d976b3c94b9a77933df6f6`, and probed actual routed TLS sockets. **QUOTE: 2,673 valid frames across 20/20; MARK: 78 valid across 20/20; TRADE: 326 accepted across 19/20, 47 continuity HOLD/rejections.** Total **3,077 raw public WSS frames** (~211,071 compressed segment bytes, two segments) checksum-replayed; **all source test files then deleted** from temporary directory. Exactly 20/20 clean source warm-up was **NOT** achieved.
- [x] **G4-05-D — No unauthorized deployment/trading:** All source/network activities were one-shot opt-in public GET/WSS and temporary test checkouts. No service, virtual experiment, paper/testnet/real position, API key, signed user stream or Binance private endpoint was used.

## 2. G4 acceptance blockers — independently unchecked

- [ ] **G4-06-A — Clean 20/20 actual trade+quote+mark source epochs and warm-up:** The only real sample had one symbol with no aggregate trade and 47 trade-ID discontinuities. A source checkpoint must account for each omitted/uncertain frame; do NOT patch continuity by using one-second/five-minute candles. Need independently sampled clean epochs, all three data types, per-symbol route/receive proofs and zero unresolved gaps before source-grade advancement.
- [ ] **G4-06-B — Endurance and actual 20-market resource envelope:** A 4-second-per-route public sample and 60 synthetic rounds do **NOT** prove volatile-market tick/message rates, websocket 24-hour reconnects, server disconnects, buffer saturation, peak CPU/I/O jitter, repeated disk segment rollover or finite long-run quotas. Prove actual sustained 20-source workloads at the small-VPS capacity limit without starting unauthorized long-running services.
- [ ] **G4-06-C — Scientifically independent original-source custody:** The local public TLS WSS probe can verify TLS server certificate at capture, raw payload and hash in the *temporary recorder*, but the captured segment format does not yet hold an independent signed exchange-origin proof or a separate verified network/session acquisition receipt. Mark-price `r` is indicative next funding, and public settled funding history is not proof of position-specific funding cash flow. Retain honest grades; do not claim executable bid/ask fills from bookTicker samples or complete first-touch paths across gaps.
- [ ] **G4-06-D — Real archived evidence restore from another host / outage:** The 60-event test demonstrates same-host code-level SHA/gzip replay and forced source HOLD after restart, **not** an independently stored off-host source archive, restore of a complete epoch, tamper-proof independent source audit, physical VPS interruption, lossless cross-host handoff or an operational archive policy with retention headroom.
- [ ] **G4-06-E — Full G4 parent engineering acceptance:** G4 must remain **[ ] HOLD** until missing original-source continuity, long-run throughput, independent archive/restore and fully qualified 20-source evidence are demonstrated. G5, G6–G12 and trading unlocks remain [ ].

## 3. Files, tested source and evidence integrity

All code is in **new `nbot_v5_1` modules**, not old `nbot.v5`, and tests run offline or explicitly opt-in public-only. Exact GitHub SHA `07186992fdfc8b2fc1b66e39b6d78513ee23891e` was used for both target VPS 186-test suites and 20-source simulation.

| File | Purpose | Git blob SHA at accepted test revision |
| --- | --- | --- |
| `nbot_v5_1/deep_selection.py` | Frozen 100→20 source-warmup shortlist | `a4c1eed365f1169909d51d8ebad667dc1edbd50c` |
| `nbot_v5_1/deep_source.py` | Public USD-M WSS 20/3 route and raw frame | `bc768115417066df7b422afeb3e7a47cbb552277` |
| `nbot_v5_1/deep_segments.py` | Bounded gzip chain original raw source byte custody | `25aa99d8e667ba13f2ae0caa767d719909353262` |
| `nbot_v5_1/settled_funding.py` | Settled public funding receipt separate from mark/index | `194fa6ae405ff32771705a735b91c11f1bd3f798` |
| `tests/test_v5_1_g4_selection.py` | 8 selection/source-warmup cases | `d0071be8505381f89192e016696c67fd3eb3958a` |
| `tests/test_v5_1_g4_source.py` | 16 route/epoch/gap/custody/crash cases | `2fbab2cd1786f86e2e57bd55e80dd728c13c1cdf` |
| `tests/test_v5_1_g4_funding.py` | 5 funding history nonqualification cases | `a66a7ddd436dd16001c48973efc9687c63da1148` |
| `benchmarks/g4_deep20_benchmark.py` | 3,600 raw messages / 60 round two-VPS performance | `be3351d25b90bf2c5333dac8e137c1d4c0595c67` |
| `scripts/g4_public_wss_probe.py` | Opt-in TLS public WSS 100→20 smoke/replay, no service | `95f9884b3e56b0ba091cf82dfec51e8717b9d51e` |

**Historic reference code reviewed:** V5 `ws_contract.py` @ `1e7c090d...` blob `29d5c0b0fc5160ab891b145875c42bb81bd597a0`, `g4_forward_stream_contract.py` @ `91d904b...` blob `d2c0b03ee2f90ea9e96ce505406995cedd78343a`, and segmented source recorder `g4_segmented_source.py` @ `47dd5fa...` blob `4c1035225aa0a7b30f9d2cf7b87c659b482d61ce`. **No old 50-market assumptions, account/private endpoints or unused V3/V4/V5 runtime were copied.**

## 4. Next-chat recovery & exact remaining actions

Read this G4 progress/HOLD report alongside [Owner Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_OWNER_ROADMAP_V1_0.md), [Engineering Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md), [G3 PASS report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md) and original Vision V1.9 before any continuation.

The **very next uncompleted item** is **G4-06-A: prove clean current original-public trade/quote/mark sources for all selected 20 including BTC**, preserving honestly unresolved trade-ID gaps. Then measure actual sustained 20-source rate, disk archive headroom and off-host restore, distinguish settled public funding vs account position-specific payments, and re-run BOTH VPS regression/benchmarks before G4 parent signoff. A new event must freeze a new cohort and source epochs prospectively; never silently relabel the previous 20 as source-ready.

**Release safety:** All existing V5.1 and legacy services remain STOPPED/UNINSTALLED, no virtual/paper/real trading order permitted, no money at risk. Owner's old-installation no-backup waiver does NOT waive data safety for newly generated G4 source evidence. No permanent source files were collected during this one-shot test; the downloaded test sample was held in temporary directory and deleted.

**Final status:** G0 [x] · G1 [x] · G2 [x] · G3 [x] · **G4 [ ] HOLD** (many tested tasks [x], blockers above [ ]) · G5–G12 [ ]. Parent G4 must NOT be checked without its real original source and restore proofs.

## Latest real G4 acceptance delta — 15 Oct 2026

- [x] Public-only Binance TLS WSS TRADE/QUOTE/MARK smoke succeeded.
- [x] Combined 20-deep symbol group and all 60 stream/symbol cursors received genuine feed messages; source receipts persisted in the V5.1 records root and diagnostic roots.
- [x] Underlying `f/l` ID discontinuity is now counted as review signal, **not automatically lost aggTrade `a` frame**. True aggTrade ID gaps/reorders still fail closed; former 47 alarms need independently adjudicated original evidence.
- [x] Isolated stale book/mark events are excluded from economic/source qualification and separately journaled; repeated four-in-a-row still causes the safe source HOLD.
- [ ] **G4-06-A/G4 parent continuous original-source source freshness:** latest 12,572-frame canary **failed** repeated `QUOTE:BTCUSDT:EVENT_FUTURE_OR_STALE`; source grade remains HOLD.
- [ ] Identify root cause with exchange E event time vs VPS receipt/NTP/combined 20-symbol queue delay; test isolated BTC and full loads before correcting code. Removing per-frame backup flock did NOT solve it.
- [ ] Qualify full 20/20 continuous source, genuine 5-minute boundary endurance, gap recovery, original off-host evidence, spread/mark/funding witnesses and independently tested scientific economics.
- [ ] Full latest SHA 569-test suite on Observation-VPS; 569/569 latest SHA PASS Execution-VPS, Observation full 569/569 PASS at previous SHA plus targeted latest tests.
- [ ] Permanent Observation startup remains NOT APPROVED/NOT INSTALLED. No PAPER or REAL activity.

**Next action:** instrument & fix verified BTC bookTicker ingress staleness, then rerun both VPS regression plus a separately owner-approved bounded public-only canary. Consult [new chat start-here file](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md).


## G4 QUOTE BACKLOG FORENSICS — MEASURED 15 OCT 2026

**LATEST CORRECTED DIAGNOSIS (supersedes the earlier BTC-only description):** The BTCUSDT quote freshness HOLD is part of a **multi-symbol high-frequency QUOTE lag ramp**, not a demonstrated BTC market malfunction. An entirely **read-only** analysis of genuine saved CS01 `segment-*.gz` frames from five previous canaries compared Binance raw `E` event time with V5.1 `received_at_ms` (timestamp stamped AFTER WebSocket `read_message` return).

| Archived genuine canary | Accepted QUOTE frames | ALL-symbol start → end median event-to-receipt lag |
|---|---:|---:|
| diagnostic-2 | 3,060 | 429ms → 653ms |
| diagnostic-3 | 7,096 | 562ms → **4,474ms** |
| diagnostic-4 | 17,459 | 444ms → **4,402ms** |
| diagnostic-5 | 10,009 | 448ms → **4,466ms** |
| diagnostic-6 | 10,242 | 940ms → **4,545ms** |

Last accepted-run window held 10,242 QUOTE frames across 7.254s, **about 1,412 QUOTE frames/sec**, with BTC end-run median 4,633ms; OTHER symbols shared similar delays. In diagnostic-6, BTC TRADE median ~641ms and MARK median ~180ms. This is **strong evidence of a quote-stream throughput/backpressure bottleneck**, not definite proof the Binance upstream or one particular Python line is responsible. Frames rejected at age>5000ms are absent from accepted G4 segment archives; source anomaly ledger records their exclusion, not their full raw exchange `E`. Do NOT count saved max<5000ms as source health proof.

**V4 has a useful tested *design reference***: old `main` `nbot/observation/wss_transport.py` has an async fast receiver and bounded queue (4096); old `live_two_tier.py` supports separate feed shards/per-symbol market-data gap invalidation. Do not copy V4 wholesale or its weaker receipt-time-only quote freshness semantics. V5.1 currently processes all 20-symbol QUOTE payloads synchronously on ONE socket worker, unlike separate TRADE/MARK workers. The engineering priority is instrument E→wire-read→queue→process timing and test isolated BTC vs sharded 5/20 symbol loads, then implement bounded backpressure-aware receiving **without relaxing V5.1's strict 5-second source-age requirement**, hard aggTrade continuity or scientific HOLD.

**Evidence register:** [Full per-run source-forensic + V4 architecture comparison](NBOT_V5_1_G4_REAL_QUOTE_LATENCY_FORENSICS_V4_CODE_COMPARISON_20261015.md); [Read-only inspection script](../scripts/cs01_readonly_latency_forensics.py). Neither action started NBOT or altered its executable public-only service. **[x] observed source-age ramp quantified, [x] V4 code reviewed, [ ] source-vs-socket-vs-consumer delay decomposition, [ ] V4-inspired tested clean transport change, [ ] sustained healthy 20/20 G4 source canary, [ ] original first touch/economics, [ ] owner WinSCP transfer.** Current G1–G3 initial live PASS limited, G4 sustained HOLD, NO PAPER/REAL, no permanent process start.

**Next assistant:** Read this newest section along with [current definitive next-chat handoff](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md). Older comments merely calling it a 'BTC issue' are historical partial descriptions; most QUOTE symbols see the common age ramp.

## G4 hypothesis checked: Is 100-to-20 reduction failing? (15 Oct 2026)

**Result: [x] Config/route reduction VERIFIED, [ ] G4 quote throughput still HOLD.** Owner asked if NBOT accidentally keeps subscribing to **all 100 markets at full tick speed** after G3 instead of restricting G4 to 20. The code check did not find that error:

- **G2 = 100 broad-market closed-five-minute REST candle histories**, not a permanent 100-coin bookTicker millisecond feed. Do not equate 100 markets with a measured 500 updates/sec; that figure was an illustrative hypothetical only.
- `nbot_v5_1/cs00_source_pipeline.py` checks exactly **100 G2 snapshot rows, 200 G3 directional rows, and 20 selected deep symbols including BTC**. It refuses a mismatched cohort.
- `nbot_v5_1/cs00_source_runtime.py::public_routes` refuses anything other than **20 unique symbols with BTC**; `nbot_v5_1/deep_source.py::stream_urls` constructs **three combined connections** using only those 20 symbols: one each for TRADE, QUOTE, MARK. It does **not** create 100 high-frequency subscribers or 60 different sockets.
- The latest actual live canary recorded exactly **20 selected deep symbols** and **60 source-pair cursors (= 20 symbols × 3 data types)**. This confirms the restricted 20-market feed operated during the trial, though the canary still exited 2 due aged BTC bookTicker quotes.
- The saved forensic run shows around **1,412 accepted quote updates per second** even with only 20 symbols; high traffic alone can create backlog if one worker receives, parses, validates, hashes and queues every raw quote sequentially. This rate is a measured sample, NOT an invented exchange request rate.

**Conclusion:** Do NOT change the G2→G3→G4 sequence or shrink the 100 broad universe to mask a source bottleneck. Current leading problem is **throughput/backpressure of the actual 20-market QUOTE stream** (other coins also lag, not just BTC). It is still necessary to instrument event `E` vs wire-read receipt vs processing before attributing fault exclusively to NBOT. No live service started, no security threshold loosened, no PAPER/real orders.

[Detailed archived original-feed forensics and V4 comparison](NBOT_V5_1_G4_REAL_QUOTE_LATENCY_FORENSICS_V4_CODE_COMPARISON_20261015.md).
