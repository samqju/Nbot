# NBOT V5.1 — First Genuine CS-01 Binance Public-Only Observation Canaries, 15 Oct 2026

> **LATEST CS-01 TRADE-ONLY RETEST (15 OCT 2026):** Owner's V1.10 active source profile does NOT fetch/subscribe to bid/ask. G1 startup uses public exchange info + 24-hour activity + 96 closed 5m candles, with **no book spread validation**; 20 deep symbols receive only original `aggTrade` and `markPrice@1s`. Real owner-approved source-only CS-01 **180s PASS**, 32,313 accepted frames, 40/40 20x2 cursors, 0 hard gaps, stopped, 145 chained records integrity-replayed and a local tar archive checksum verified. **G4 full ongoing/original scientific qualification still [ ] HOLD** (no two-boundary/days/independent economic outcomes), and previous quote-based G5/G6/PAPER lab contracts still need versioned adaptation before activation. Prior 20x3/BTC bookTicker failures are **historical data from the old design**, not current release status. [Vision V1.10 amendment](NBOT_V5_1_PRODUCT_VISION_V1_10_TRADE_PRICE_ONLY_AMENDMENT_20261015.md) | [Actual public-only trade-only canary report](NBOT_V5_1_CS01_TRADE_ONLY_RETEST_RELEASE_RESULTS_20261015.md). Original V1.9 unchanged.


> **NEW CHAT / NAVIGATION:** This is the immutable factual report for the first real canaries, NOT a production-readiness PASS. The authoritative next-session index with the precise G1/G2/G3 limited scope, G4 blocker, tests and real backup is [START HERE](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md). **G3's 200 recorded directional masks were capacity-skipped (no actual detector evaluation)**; do not count these as signal/trade success. Latest tested code `6b7491d8a903cbc248c85327a20919d68f05292f`.


**Owner authorized:** start and verify **PUBLIC OBSERVATION ONLY** after their desktop commander reconnection. Owner did NOT authorize PAPER, testnet, real orders or economic/research model promotion.

**Final HEAD executable checked in these live canaries:** `6b7491d8a903cbc248c85327a20919d68f05292f`. The code has not been installed as a permanent service. All canary processes used isolated shallow clones, explicit time limits and public URLs, and exited. **Final decision: LIVE CONTINUOUS OBSERVATION [ ] HOLD (not production-started); live REST and public WSS connectivity [x] VERIFIED.**

## Confirmed from genuine Binance sources

1. **Public USD-M REST G2 source pass** (pinned SHA `b9ed640dc9c30e2c818f2b3850e8b4b9ff2538f0`): 100/100 genuine 96-closed-bar historical candidates selected, 100 healthy source rows, 0 holds, BTC included, 103 exchange/ticker/book/history receipts hash-archived and replayed, request weight 246, source age 33,003ms, zero orders, exit 0. This is NOT proof of WebSocket continuity or live after-cost outcomes.
2. **Public BTC WSS three-stream smoke PASS** (pinned `964943359814069c84bcd1de7ec912e8ce1cdf70`): `aggTrade`, `bookTicker`, `markPrice@1s` each opened via `/market/stream` or `/public/stream`, returned valid first message, no account/client/order.
3. **Owner permanent V5.1 source folder produced first genuine public REST/G3/WSS receipts**. Owner's installed `~/nbot-backup` produced a **verified eight-file** gzip+SHA snapshot: `/home/ubuntu/NBOT_Backups/NBOT_V5.1_records_20261015T152427Z_12d35662.tar.gz`, 103,117 bytes; SHA-256 `af306b0decb2dd8753d8049b943f214085d33950ae65118fbf02b580042a5250`. Follow-up `sha256sum -c` PASS on Observation VPS. **OFF-HOST** transfer to owner's 1 TB Windows desktop via WinSCP has **NOT occurred**; keep both `.tar.gz` and `.sha256` files.
4. Additional isolated diagnostic state folders `/home/ubuntu/nbot-v5.1-cs01-diagnostic-2` through `-6` contain modest (~0.4–1.5 MiB each) genuine **unqualified canary** receipts. Do not silently copy these into G7's scored original dataset or delete original witnesses until the owner retention choice.

## Actual startup failures discovered and corrected or isolated

- First full runner failed before any network due GitHub commit ID being 40 hex, while synthetic approval fixtures wrongly assumed 64. Fixed `FuturePublicObservationService` + 7-case approval tests, then retried.
- Live public-only runner successfully bootstrapped initial 100/200/20 and received **998, 3,532, 8,520, 19,058, 12,103 and 12,572** public frames across separate bounded iterations (some attempts intentionally short). At least two iterations covered all **60** symbol/feed cursor combinations (20 × Trade/Quote/Mark). **Frame volume is NOT continuity qualification.**
- A real `TRADE_ID_GAP` false HOLD was verified: underlying `f/l` transaction IDs can skip despite contiguous aggregate `a` IDs (Binance aggTrade excludes insurance-fund and ADL transactions). The G4 recorder now **records an underlying ID review count without inventing an aggTrade source gap**; reverse/overlapping underlying IDs and missing aggregate IDs still hard HOLD. New regression tests pass. Prior G4 47 alleged gaps are still not independently adjudicated.
- Subsequent actual first source HOLD was reliably classified **`FIRST_SOURCE_HOLD:QUOTE:BTCUSDT:EVENT_FUTURE_OR_STALE`**. A high-volume BTC `bookTicker` WSS message exceeded the strict 5-second event/receipt freshness guard; source or receiver lag not yet attributed. We first retained a hard HOLD; then added source-only **discard + private anomaly JSONL receipt** for up to three consecutive stale QUOTE/MARK events per pair. Four consecutive stale messages, a stale TRADE, genuine missing aggregate data or order/price mismatches still hard HOLD. Eight isolated stale QUOTE/MARK messages were discarded in one run, and all remained excluded from genuine economic qualification.
- Measured removing per-frame backup `flock` while retaining the lock for **atomic sealed-source segment and manifest checkpoint publication**. This did not resolve the repeated BTC quote age issue. We did **not** relax the 5-second price freshness check or forge valid Research results.
- **Last canary (SHA `6b7491d8...`)**: initial 100/200/20, 12,572 real WSS frames, all 60 source cursor pairs touched, 3 quote/mark stale skips, 5 reviewable underlying-ID discontinuities, then repeated `BTCUSDT QUOTE EVENT_FUTURE_OR_STALE` triggered a hard source HOLD. Exit **2**; future source-only process stopped automatically, no PAPER/testnet/real orders.

## Tests, stop, safety, state

- Final pre-throughput SHA `44f4a26453502e671567248796ecff43dde832c8`: **569/569 full regression PASS each on Observation and Execution**.
- Final throughput-only code SHA `6b7491d8a903cbc248c85327a20919d68f05292f`: targeted Observation-side source-pipeline/state-checkpoint/G4 receipts tests **7 + 11 + 18 PASS**; latest full **569/569 PASS on Execution VPS**. Final SHA full Observation VPS 569/569 not yet independently rerun; do not claim it.
- Final point-in-time Ubuntu checks (2026-10-15 ~15:47 UTC): **no NBOT python processes and no nbot* systemd units on either VPS**; Observation existing backup `sha256sum -c` says OK, main state root size 204KiB.
- Both VPSs are still execution-locked. Authentic 20/20 continuous G4 quote/mark/trade/source, restart/replay and original-after-cost virtual evidence **not accepted**. Scientific/Champion/PAPER and G12 real release remain prohibited.
- All production service setup is **uninstalled**, non-persistent. The owner-approved activity was a bounded CS-01 PUBLIC-ONLY STARTUP/CANARY, NOT a successfully stabilized permanent Observation daemon.

## One concrete next engineering blocker before leaving NBOT running

**Diagnose BTC `bookTicker` `E` event-time vs VPS receipt-time skew and high-frequency WebSocket reader backlog under the 20-symbol public `/public/stream` load.** Compare low-load direct BTC quote latency to full combined stream, instrument socket-read queue lag/clock offset, and restructure bounded reception/custody or isolated symbol-specific source recovery **without silently accepting stale cost/first-touch witnesses or weakening the defined scientific gates**. Then verify a clean time-limited public-only canary across actual five-minute boundaries, and only afterward decide whether to install an opt-in durable Observation service. Repeated ad hoc timeout/threshold increases are not a valid solution.

**Manual owner WinSCP next action:** transfer the above exact .tar.gz and .sha256 from `/home/ubuntu/NBOT_Backups/` to the desktop, compare SHA, but don't confuse that copy with original-source scientific qualification.

[Owner's WinSCP guide](NBOT_V5_1_OWNER_MANUAL_DESKTOP_WINSCP_BACKUP_V1_0.md) · [Controlled startup checklist](NBOT_V5_1_CONTROLLED_STARTUP_OWNER_CHECKLIST_AND_EVIDENCE_REGISTER_V1_0.md).

## Reconciled next-chat status

**[x]** Binance real 100-source initial G1/G2, 200 directional G3 receipt generation, all 3 BTC public WSS feed kinds, all 60 deep source cursors, safe shutoff, first locally validated 8-file genuine VPS backup. **[ ]** Continuous reliable G4 original-source coverage because **BTC QUOTE `EVENT_FUTURE_OR_STALE`**, [ ] WinSCP desktop backup transfer, [ ] 20-source temporal endurance, [ ] original cost/first touch, [ ] model/PAPER/real releases.

All next steps, corrected trade-ID semantics and code SHA are consolidated in [this newer current handoff](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md); do not start a permanent collector on the strength of a limited source smoke run.
