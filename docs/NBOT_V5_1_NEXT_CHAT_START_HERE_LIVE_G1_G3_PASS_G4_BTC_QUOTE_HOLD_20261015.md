# NBOT V5.1 — START HERE: Current Live Status, Exact G4 Blocker and Next-Chat Recovery

**Last reconciled:** 15 October 2026 (IST).  
**GitHub:** `samqju/Nbot` · working branch **`nbot-v5.1`** · immutable latest LIVE-tested executable SHA **`6b7491d8a903cbc248c85327a20919d68f05292f`**.  
**Authoritative product blueprint:** `docs/NBOT_V5_1_COMPLETE_PRODUCT_VISION_V1_9.md` (unchanged).  
**Most important status:** **G1–G3 initial genuine public-data checks PASS in their stated limited scopes. G4 genuine continuous 20-market source verification FAIL/HOLD because of repeated BTCUSDT bid/ask quote `EVENT_FUTURE_OR_STALE`.** NBOT is NOT left running; no PAPER/testnet/REAL orders, account credentials or model promotion were authorized.

> **Before acting in a new chat:** Read THIS file first, then the latest sections of [live CS-01 test report](NBOT_V5_1_FIRST_LIVE_CS01_PUBLIC_ONLY_CANARY_ACTUAL_RESULTS_AND_BTC_QUOTE_HOLD_20261015.md), [owner startup checklist](NBOT_V5_1_CONTROLLED_STARTUP_OWNER_CHECKLIST_AND_EVIDENCE_REGISTER_V1_0.md), [Owner Roadmap](NBOT_V5_1_OWNER_ROADMAP_V1_0.md), [Engineering Roadmap](NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md), [G4 report](NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), and Vision V1.9. Older sections claiming that no public feed was ever tested, that no genuine record exists, or that the next action is to build CS-00 from scratch are **historical pre-canary snapshots**, not the current facts.

## 1. Where the pipeline genuinely reached (do not overclaim)

| Phase | Evidence genuinely observed on Binance | Current gate |
| --- | --- | --- |
| G0/G1 Foundation/100-market selection | Real public 100/100 USD-M selected, BTC included | **[x] initial live scope PASS**, not multi-day endurance |
| G2 broad Observation | 100 genuine histories/96 closed 5m bars each, 0 initial HOLD, 103 raw REST source receipts and replay; initial public source as-of record | **[x] initial source/read-only G2 scope PASS**, not evidence of uninterrupted service |
| G3 Exploration | 200 direction rows (100×LONG/SHORT), 24 detector-state slots per row; recorded live-derived as-of/source statuses and `NO_TRADE` | **[x] initial G3 pipeline/labeling scope PASS**; **0 actual detector evaluations** in the original capacity-fenced demonstration, **200 capacity-skipped**, so don't claim market strategies or evaluated signal edge |
| G4 Deep-20 original market source | 20 symbols incl BTC; TRADE, QUOTE and MARK socket streams all connected and **all 60 source-pair cursors were observed**; last short canary received **12,572 messages** | **[ ] SUSTAINED CLEAN ORIGINAL CONTINUITY / FIRST TOUCH / CUSTODY HOLD**, recurring BTC quote freshness exceeded strict 5 seconds |
| G5/G6 | Full virtual Research code and cost modeling work offline; no qualified real-original trade path/quote/funding/cost ledger yet | **[ ] GENUINE ORIGINAL SCIENCE HOLD** |
| G7/G8 | Learning/Training engineering synthetic-pass; no independently qualified 2,000 mature original net-return outcomes, no legitimate live Champion | **[ ] GENUINE MODEL HOLD** |
| G9/G10 | Offline PAPER management/Challenger engineering exists, but no owner-approved actual PAPER and no Champion | **[ ] PAPER RELEASE HOLD** |
| G11/G12 | G11 integrated offline synthetic test evidence recorded separately; G12 real money prohibited | **G11 offline-only PASS; G12 REAL LOCKED** |

**Critical nuance:** G1–G3 passed *initial live as-of and source/recording checks*, NOT sustained healthy multiple-boundary production Observation. G4 failure prevented qualifying the end-to-end genuine Research/Learning pipeline. G3's 200 records should not be described as 200 evaluated pattern/trading decisions.

## 2. The public-only startup that the owner already authorized

Owner expressly requested a real Binance startup after CS-00 offline engineering and reconfirmed Windows Desktop Commander connection. On Observation-VPS a genuine HTTPS/REST probe passed, a BTC-only WSS smoke test passed (aggTrade, bookTicker, markPrice), and a sequence of bounded source-only 20-market canaries followed. This permission was **only for public Observation canaries**; it was NOT a PAPER/real/automatic permanent service release.

- **REST:** 100/100 symbols selected, **103** public original-shape REST receipts replay-checked, 0 initial G2 data HOLD.
- **WSS smoke:** all three public feed kinds returned successfully authenticated-by-TLS Binance envelopes; not scientific source/economics promotion.
- **Initial combined canary:** G2 → G3 → G4 path generated durable genuine public records; process later stopped on uncertainty. A frozen G2/G3/20-deep cohort and compressed G4 receipt files were written under `/home/ubuntu/nbot-v5.1-state/`.
- **Failure 1 fixed:** original 64-hex test permit incorrectly rejected actual 40-hex Git commit SHA. Corrected with tests.
- **Failure 2 fixed:** treating a skip in Binance **underlying** trade `f/l` IDs as a proven lost **aggregate** `a` ID. Updated code tracks underlying gaps as review diagnostics; genuine aggregate-ID losses, overlap/reordering or severe uncertainty still HOLD.
- **Failure 3 remains OPEN:** repeated `FIRST_SOURCE_HOLD:QUOTE:BTCUSDT:EVENT_FUTURE_OR_STALE`; after isolated stale quote/mark events are recorded as `UNQUALIFIED_SOURCE_EVENT` and dropped (never economically usable), **four consecutive stale updates** cause hard source HOLD. Latest run **12,572 frames, all 60 20×3 cursors seen, 3 soft stale skips, 5 reviewed underlying-ID skips**, then hard quote freshness HOLD and **exit 2**. A previous run saw 12,103 frames / 8 soft skips before HOLD. Do not call either a PASS.
- **Performance hypothesis tested and NOT sufficient:** removing per-frame `flock` from memory-only G4 appends did not remove the live stale BTC quote issue. Segment **flush/seal** stays locked and checked for coherent backup.

**The cause of stale quote age is not yet established.** It may be upstream event timestamps, VPS clock skew, frame backlog in Binance combined 20-symbol quote stream, Python receiver scheduling/processing, or another runtime issue; no one of these is proven. Avoid increasing the 5s budget or calling stale quotes valid simply to obtain uptime.

**Latest source tests:** `6b7491d8a903cbc248c85327a20919d68f05292f`; full **569/569 PASS Execution-VPS** at the latest SHA, **569/569 PASS Observation-VPS** at prior `44f4a26453502e671567248796ecff43dde832c8` and targeted source/checkpoint/G4 tests on Observation at latest; **full 569/569 latest SHA Observation regression has NOT been independently confirmed**, so preserve the unchecked line. Tests and real canaries are distinct.

## 3. Exact evidence, record locations and owner manual backup

The first genuine public Observer Research/Exploration/source receipts are in **`/home/ubuntu/nbot-v5.1-state/`** on Observation-VPS. Additional isolated **unqualified** canary root directories `/home/ubuntu/nbot-v5.1-cs01-diagnostic-2` through `-6` preserve short-run source data; avoid silently deleting, promoting or mixing them with qualified G7 results.

Owner's preinstalled and locally tested one-command manual backup: **`~/nbot-backup`** (Observation-VPS PuTTY). It succeeded after real data appeared. Exact verified first bundle:

- **Archive:** `/home/ubuntu/NBOT_Backups/NBOT_V5.1_records_20261015T152427Z_12d35662.tar.gz` (**103,117 bytes**, **8 records**).
- **SHA-256:** `af306b0decb2dd8753d8049b943f214085d33950ae65118fbf02b580042a5250`; matching `.tar.gz.sha256` sidecar.
- **On-VPS `sha256sum -c` PASS**. **[ ] Owner has NOT yet manually transferred + independently hash-verified it on their 1 TB Windows desktop through WinSCP.** Transfer is separate from a genuine-original science acceptance test.
- **Never delete sole source/only verified backup or assume that Binance public trades substitute for NBOT's frozen decisions, labels, quotes, model history and results.** Genuine post-restart Binance historical `aggTrades` automatic gap recovery still requires actual end-to-end long-run proof.

Last point-in-time host audit (15 October 2026) found **no NBOT Python process and no nbot* systemd unit on either Observation or Execution VPS** after the bounded canaries; no permanent service was installed, no exchange account/order capability or spending. Do not claim these point-in-time results as live ongoing monitoring; recheck before any next runtime.

## 4. Precise next work for the next assistant/engineer

1. **Do NOT start permanent NBOT or PAPER.** First inspect both VPS service/process state and preservation of owner backup; avoid running duplicate canaries. Keep `nbot-v5.1` branch and Vision V1.9 as authority.
2. **Diagnose G4 BTC QUOTE source-event staleness at the source, not by weakening validity checks.** With explicit, bounded public-only owner approval, measure for actual BTC `bookTicker` messages: exchange `E`, host `time.time_ns()`, monotonic timing, clock sync/NTP offset, receive-to-parse/queue-to-flush latency, frames/s per symbol, 20-deep combined WSS vs isolated BTC WSS. Differentiate stale upon ingress from software-created head-of-line backlog. Preserve raw timestamp witnesses and reason codes without recording secrets or unlimited tick archives.
3. Correct proven receiver/transport/clock bottleneck or change feed partitioning if tests justify; retain authentic `aggTrade` ID continuity hard veto, exact bid/ask event-time price/quote qualifications, repeated stale safety HOLD and the user's historical-recovery-first, compact ledger approach.
4. **Test offline fixtures on BOTH VPSs at the same pinned SHA**, then perform a separately approved **time-limited public-only** 20-market canary spanning at least two genuine 5m boundaries, checking ALL 60 pairs, zero unexplained stale/cursor gaps, source age, CPU/RAM/queue/disk/retention, sealed receipt replay and automatic historical recovery after an engineered public-only interruption. Do not mislabel a 2-minute run as 24h operational endurance.
5. Only after real continuity, correct record writing, coherent manual backup and safe watchdog/operator controls pass, obtain separate owner consent for an actual durable Observation service startup. Subsequent G4/G5/G6/G7 science acceptance and PAPER authorization remain separately locked.
6. After each change, check precisely evidenced owner + engineer roadmap substeps and update `docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md`; preserve all failed-canary evidence and hashes. Do not start from old V4/V5 branches, invent market data or trade outcomes, or overfit the time limits.

## 5. Exact code/files relevant for resumption

- `nbot_v5_1/cs00_public_ws.py` — pinned public TLS WebSocket receiver and bounded framing.
- `nbot_v5_1/cs00_source_runtime.py` — trade/quote/mark event validation, per-kind/per-symbol source epochs and separate source HOLD vs soft stale telemetry.
- `nbot_v5_1/deep_source.py` — original exchange event-time/source semantics, strict source grade.
- `nbot_v5_1/deep_segments.py` — packed exact-source receipts and aggregate-ID vs underlying-trade-ID diagnostic.
- `nbot_v5_1/cs00_source_pipeline.py` — 100/200/20 source-only wiring, anomaly ledger, state checkpoint and receipt sealing.
- `nbot_v5_1/cs00_public_service.py` — manually gated foreground public Observation, WSS worker stop conditions.
- `scripts/cs01_public_observation_canary.py` — manual time-bounded public-only test, exit 2 on hard source HOLD (must NOT be interpreted as clean exit).
- `scripts/nbot_v5_1_owner_backup.py` — one-command record archive tool; installed as `~/nbot-backup` on Observation VPS.
- `tests/test_v5_1_g4_source.py`, `tests/test_v5_1_cs00_runtime_work.py`, `tests/test_v5_1_cs00_state_checkpoint_backup.py` — regressions.

**Resume prompt you may copy into a new chat:**

> Continue NBOT V5.1, repo `samqju/Nbot`, branch `nbot-v5.1`. Read `docs/NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md` in full, then the first genuine CS-01 live test report, most recent owner/engineer roadmaps, startup checklist, and Vision V1.9. G1/G2/G3 initial Binance public-source path and record writing passed limited live tests; G3 produced 200 recorded directions but no capacity-fenced real detector evaluations; G4 20×3 raw messages received but source-grade HOLD due repeated stale BTCUSDT bookTicker `EVENT_FUTURE_OR_STALE`. Latest live executable SHA `6b7491d8a903cbc248c85327a20919d68f05292f`; newest full Executive VPS 569/569 tests, Observation full 569/569 on preceding SHA plus targeted latest. All canaries stopped, no permanent service, PAPER/REAL forbidden. First genuine 8-file 103117-byte backup + SHA saved on Observation VPS, WinSCP desktop copy unchecked. **Investigate raw event-time vs VPS clock vs WSS processing/backlog objectively and safely; no threshold stretching, false G4 PASS or unlabeled trade exclusion.** Maintain checkbox/evidence continuity on both roadmaps, use only separately owner-authorized public-only bounded tests; seek explicit permission before a permanent service or trading. Do not redo CS-00 from scratch.

**This document is the latest status bridge. Historical prior G2/G3/G4/CS-00 reports remain archived as snapshots at their original GitHub commits.**


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


## G4 selection and price-source explanation — verified 15 Oct 2026

**User question:** Does G4 select 20 of 100 by the 24 G3 detectors, implying ~100 price updates/sec, and why collect live bid/ask rather than only last traded price?

**Actual V5.1 code verified:** `nbot_v5_1/universe.py::select_universe` chooses 100 broad candidates from active USD-M USDT perpetual markets using adequate 24h quote turnover (default at least $1m), bid/ask presence and spread (max 50 bps by default), >=96 verified final five-minute candles and healthy source markers. Broad composition: include BTC, up to top 50 by volume, top 25 gainers, top 25 losers, fill qualified duplicates/shortfalls by turnover until 100.

`nbot_v5_1/deep_selection.py::choose_deep` then selects **exactly 20** for G4, **not the 20 strongest G3 detector matches**: BTC mandatory (1); budget up to 4 from gainer stratum, up to 4 from loser, up to 7 from volume/turnover; the remaining 4+ slots are distributed by unfilled eligibility population (code's actual algorithm greedily chooses the biggest remaining stratum). Within each category, selected names rotate deterministically based on precommitted hash of event/seed/stratum/symbol. Overlapping candidate group tags are retained, but each symbol is assigned one selection stratum in GAINER→LOSER→TURNOVER→CONTROL priority. The full 100-to-20 denominator and inclusion probability are preserved. **G3 is required for a complete, causal, source-compatible 100×2/200 record and NO_TRADE authority, but actual detector MATCH counts/results are explicitly NOT used to select deep-20**; prevents cherry-picking and permits diverse prospective controls. Under the initial live run, G3's 200 labels had 24 detector status slots each but all actual detector computations were `NOT_EVALUATED_CAPACITY` (capacity 0). Do not say 24 detectors selected or vetted the final 20 or produced profitable signals.

**Stream load:** `nbot_v5_1/deep_source.py::stream_urls` constructs **only 3 combined WSS routes**, containing only these **20 selected** symbols each: `aggTrade` (last executed trade price/quantity with trade chronology), `bookTicker` (current *best bid and ask* quotes, available liquidity) and `markPrice@1s` (mark/index/indicative funding). 20 coins does **not** imply a fixed 5 updates each or 100 total updates per second. Five earlier actual archived diagnostic bursts measured **~1,000–1,400 accepted quote messages/sec across the selected 20**, highly variable by coin and activity.

**Why quotes rather than just latest last traded price:** a last trade may be between the bid/ask and might not represent a buyable or sellable price for a new virtual order. E.g. if last $100, bid $99.90, ask $100.10, pretending to BUY at last $100 understates transaction cost. Bid/ask is critical for genuine simulated first-touch, spread and after-cost Research G5/G6, whereas last executed trades remain important for actual path/trigger analysis and mark for derivative accounting. **All three streams have distinct jobs; do NOT replace bid/ask with last trade and claim economic accuracy.** The 5-second event-`E` source freshness rule must remain intact.

**Scope and open choice:** This is a truthful description of the current **stratified fairness/control design**, not proof it is necessarily the final optimal commercial watchlist or a promise that G3 detector-based prioritization was implemented. Any later policy change needs explicit design review, no silent removal of controls/selection probabilities, and regression + live evidence. The current G4 failure is documented high-volume **cross-symbol bid/ask receive/processing lag**, not accidental 100-symbol deep-WSS subscription. [Detailed original source forensics](NBOT_V5_1_G4_REAL_QUOTE_LATENCY_FORENSICS_V4_CODE_COMPARISON_20261015.md).


## OWNER DESIGN PREFERENCE — LOWER QUOTE LOAD, LAST TRADE PRIMARY (15 OCT 2026)

**Owner proposal (under review, NOT signed off or coded):** Owner is concerned that processing every live `bookTicker` change for 20 markets will become an enormous high-volatility traffic burden. They prefer **actual last-traded-price movement as the main G4/G5 virtual Research path**, with practical tolerance/slippage for simulated entry/exit prices, and wish to reduce bid/ask work to what is necessary. Do not interpret this as permission to fabricate fills, delete original evidence, start an NBOT service or downgrade Champion scientific gates.

**Reviewed product contract:** `docs/NBOT_V5_1_COMPLETE_PRODUCT_VISION_V1_9.md` §§8.1–8.4 specifically requires an original future price path, **relevant entry AND exit bid/ask evidence**, realistic fees/spread/slippage/funding, and prospectively frozen trade assumptions. It expressly states that an aggregate trade crossing a price does NOT itself prove an executable fill. The Vision does **not** require archiving or analyzing every intermediate quote tick for all 20 symbols. Do not overwrite or silently modify the Vision.

**Proposed minimal-load solution (requires owner design review, offline regression, then separately authorized live canary):**
- [ ] Keep original continuous enough `aggTrade` last-trade price and trade-ID/source continuity for **movement, trigger order, stop/target/horizon**. Preserve public mark/funding data for derivative costs.
- [ ] Keep only a **fast lightweight top-of-book receive path**, ideally sharded or bounded fast-reader/consumer as V4 taught us; don't run full hashing/durable emission/expensive Research calculations on **every** quote. Maintain RAM latest quote + timestamp and a bounded causal receipt/evidence ring for selected prospective decision, entry and exit checkpoints, plus periodic calibration samples. **Do not claim that RAM-only unsaved quotes independently prove original execution.**
- [ ] On any virtual entry/exit, use an independently time-stamped **fresh** original bid/ask snapshot at the appropriate causal time and actual trade movement, apply predeclared realistic spread/slippage plus applicable fee/funding rules; do not charge spread twice. Real quote snapshots must still be retained when claiming source-qualified after-cost research.
- [ ] Permit a **separately labeled ESTIMATED_RESEARCH_ONLY** virtual result if entry/exit original quote evidence is unavailable, using conservatively predeclared adverse fill buffers/calibrated slippage (possibly volatility/liquidity-dependent). This cannot be quietly promoted into `G7` independent qualified return counts, `G8` Champion, or PAPER release without further evidence review; mark uncertainty and counterfactual bias clearly.
- [ ] On quote input overflow/stale/gap, label relevant virtual entry/exit unqualified, HOLD affected source or suspend its live first-touch qualification rather than silently substituting last price. Keep hard aggregate-ID gaps and irreversible missing original history as HOLD/EXCLUDED and audit footprint.
- [ ] Quantify CPU, RAM, queue lag, price-age and original quote coverage at 1/5/20-symbol high-volatility samples before selecting final quote cadence/coalescing/sharding. No arbitrary 100 quotes/sec assumption; earlier source archive had ~1,400+ accepted quote messages/sec with **20** symbols.

**Key tradeoff in simple terms:** Follow *last traded prices* for where the market moved, but keep *occasional relevant bid/ask snapshots* for what a virtual buy/sell would realistically cost. **A fixed "small leniency" without original quotes can support exploratory estimates, not independently proven profitable tradability.** Separating these grades preserves the user's practical speed objective and the V1.9 product's evidence discipline. No code changed by this discussion. G4 remains HOLD from measured multi-symbol QUOTE bottleneck; permanent source service/PAPER/REAL remain OFF.
