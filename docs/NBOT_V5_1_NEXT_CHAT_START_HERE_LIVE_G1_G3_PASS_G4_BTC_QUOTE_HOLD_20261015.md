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
