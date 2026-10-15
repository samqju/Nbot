# START HERE — NBOT V5.1 G4 Trade-Only Source CS-01 PASS, G5/G6 Model Amendment Next

**Authoritative new-chat handoff | 15 October 2026 | repo `samqju/Nbot` | branch `nbot-v5.1`**  
**Current release decision:** New owner-approved **NO BID/ASK** 20-deep trade-only CS-01 passed its 180-second real-market canary. **FULL G4 independently-qualified operational acceptance still HOLD**, and actual VIRTUAL/PAPER/TESTNET/REAL/model promotion are OFF. This file supersedes earlier 'BTC bookTicker is blocking G4' description **for the new release** but preserves that report as historic failure data.

## What the owner decided

- NEVER request/use bid/ask `bookTicker` for the **active V5.1 trade-price source**: neither REST G1 selection nor G4 public WebSocket deep stream. No deep book data snapshots or high-volume bid/ask recording.
- G1 keeps **100** trading-eligible USDT perpetual coins including BTC, using Binance public metadata/24h turnover and 96+ completed five-minute bars; old **spread filter removed**, therefore do not claim a validated bid/ask spread or book liquidity.
- G3 still produces a 200 coin-side denominator with 24 original detectors, BUT original live 200 cases had **0 actually evaluated patterns** because capacity=0. The G4 **20** deep names are chosen by prospective stratified BTC+gainer+loser+turnover+control hash rotation, NOT detector match count.
- G4 exactly **20 including BTC**, public WSS **`aggTrade`** for original last traded price and aggregate IDs, **`markPrice@1s`** for derivatives mark/funding context. **40** expected actual source cursors, not previous 60, and absolutely no quote WSS.
- G5 VIRTUAL Research and future G9/G10 PAPER **assume immediate MARKET fills in simulation**, at latest causally original traded price plus conservatively modeled adverse spread/slippage, trading fees and relevant funding. NO limit-order availability/touch waiting; quantity queue ignored **only for hypothetical simulation**. A modeled fill is NOT an exchange-confirmed actual fill. Future Testnet/REAL MARKET orders require exchange acceptance+actual fill/position reconciliation.
- **Vision V1.9 preserved unchanged**; exact newer owner policy is recorded in [Product Vision V1.10 amendment](NBOT_V5_1_PRODUCT_VISION_V1_10_TRADE_PRICE_ONLY_AMENDMENT_20261015.md). Prior offline G5/G6/G9 modules still model quote-based source evidence and **MUST be versioned and re-tested before the newly designed Research/PAPER is activated**; do not quietly call these stages completed for the new mode.

## Executed and independently verified 15 Oct 2026

- [x] GitHub V5.1 code revision for **2-source G1** public `exchangeInfo`+`ticker/24hr` with completed bar REST histories and **no REST `bookTicker` call**; 100→20 manifest preserved.
- [x] G4 `public_routes(...,trade_only=True)` emits **only 2 combined public WSS** (TRADE, MARK). The CS01 service forces `trade_only=True`; the old 3-stream route/helper remains dormant only to preserve historical lab compatibility.
- [x] New 7 regression tests `tests/test_v5_1_cs01_trade_only_profile.py`. **576/576 V5.1 tests PASS on Observation VPS** at source code SHA **`7812878d53ec9b92ef09c06107d185e1cbc50ab3`**, again **576/576 PASS on Execution VPS** at later *docs-only plus read-only forensic-script* SHA **`acd1bf7772f0ee5e8797aa2e11c48b42e6f3d3a9`**. No changes to active collector code between those points; do not claim 576 tests reran after *every* documentation edit.
- [x] First real owner-public-only BTC WSS smoke **TRADE + MARK both PASS** at live source SHA **`f474085753c3f88d81c66a00f00a6d13b8311ae9`**, 0 quote WSS.
- [x] Same SHA **owner-authorized 180-second PUBLIC-ONLY full CS01**, start `2026-10-15T16:56:46Z`, exit **0** after timer, auto-stopped:
  - 20/20 source symbols for `aggTrade` and 20/20 for `markPrice@1s`, **40/40 live cursor pairs**.
  - **32,313 genuine raw Binance public-source accepted WSS frames** = **29,372 TRADE + 2,941 MARK**.
  - **0 source gaps**, **0 hard source holds**, no exceptions/errors, **0 quote subscription or archived quote frames**.
  - `source_frames=32313`, `hard_source_gap_count=0`, `source_gap_count=0`, `stop_reason=CS01_TIMED_CANARY_COMPLETED`, `exchange_order_capability=false`, `financial_authority=NONE`, `pipeline.boundaries=1`.
  - Last accepted genuine event-to-receipt latency max **236ms TRADE**, **397ms MARK**; these apply to **accepted archived messages only**, not generalized network SLA.
  - **51 reviewable underlying `f/l` trade-ID skips**. NOT missing aggregate `a` IDs. Genuine gaps in aggregate `a` remain fatal. Do not silently clean or classify all 51 as independently resolved.
- [x] Independent **read-only full source custody replay** on Observation VPS using `scripts/cs01_trade_only_readonly_replay.py`: all **145** hash-linked gzip+JSON pairs, **32,313** saved raw receipt hashes/frame validation and symbol/kind audit PASS. Last chain head `647114e2ef27e3a67ba5402963b937f5efab0cb77a6f58580fa8842addbdb934`.
- [x] New **private, one-off backup on Observation VPS locally verified** with `sha256sum -c`:
  `/home/ubuntu/NBOT_Backups/NBOT_V5.1_TRADE_ONLY_CS01_20261015T1656Z.tar.gz`
  `/home/ubuntu/NBOT_Backups/NBOT_V5.1_TRADE_ONLY_CS01_20261015T1656Z.tar.gz.sha256`
  2,778,845 bytes, SHA256 `de6f2c695867be361edd1d94ae2179632bf4de41d14991017e7566fcf1fee5f4`.
- [x] Fresh VPS status Oct 15 approx 17:02 UTC: **no active python3 NBOT process and no nbot systemd service**, neither automatic daemon nor PAPER/REAL order.
- [x] **19 related technical/status/roadmap/evidence documents updated and READ-BACK VERIFIED 19/19** with current no-bid/ask profile and G4/G5-G11 truthful scopes.
- [x] Original failed three-stream quote-era canaries, original witness folders `/home/ubuntu/nbot-v5.1-cs01-diagnostic-2` to `-6` and initial eight-file manual backup preserved. No overwrite or deletion.

## What is still NOT done (honest holds)

- [ ] **G4 FULL:** one 180s canary and `pipeline.boundaries=1` do not prove multiple completed 5-minute boundaries, 24h/day-long volatility/drift/gaps, true exchange-signed provenance, independently maintained backups, source restarts and retentions. These must get future controlled authorizations and verification; do not tick G4 master acceptance.
- [ ] **Original first old owner backup** `NBOT_V5.1_records_20261015T152427Z_12d35662.tar.gz` + `.sha256`, AND new **2.8MB trade-only archive + sha**, still need owner to **WinSCP download both files to 1TB Windows HDD and compare Windows SHA256**. VPS checksum alone is NOT independent offhost proof. Keep evidence untampered.
- [ ] **G5/G6 clean actual source/Research:** G5 lab-only synthetic test policies remain disabled; G6 economic audit is still quote-dependent lab demonstration from V1.9. Must implement strict **instant assumed MARKET fills from `aggTrade` with conservative adverse cost model, total taker fees+funding and explicit economic evidence grade**, then rerun tests. No bid/ask ingestion may be reintroduced accidentally. No real Research activation without separate authority.
- [ ] **G7:** 0/2,000 independent genuinely qualified matured outcomes, even though 32,313 frames were ingested. A frame is not a successful trade or economic experiment.
- [ ] **G8:** no qualified real-source Champion; **G9/G10** PAPER, Testnet, Real remain OFF and require separate stages and approvals. **G11** synthetic whole-loop only; **G12 REAL LOCKED**.

## Immediate next engineering goal (no restarting already-passed source unnecessarily)

**Implement V1.10 price-only G5 virtual-market and G6 after-cost model without bid/ask, in new code, with source-grade uncertainty, stress testing and dual-VPS regression.** Preserve owner-locked mode boundaries. Then assess whether another bounded public-only G4 live test across actual five-minute boundaries, and longer resilience canaries, can close the remaining G4 microgates. Do not launch Research/PAPER/real or permanent NBOT service without the user's additional permission. There is no reason to reinstate the quote WSS feed.

**Original detailed contemporary report:** [Source-only full CS01 actual results, exact audit/backups](NBOT_V5_1_CS01_TRADE_ONLY_RETEST_RELEASE_RESULTS_20261015.md). Owner-facing Roadmap/Engineering Roadmap headers describe latest profile; their earlier original lines are historical scopes.

## Copy/paste to start next chat

> Continue NBOT V5.1 from `docs/NBOT_V5_1_NEXT_CHAT_START_HERE_TRADE_ONLY_CS01_PASS_20261015.md` on `samqju/Nbot` branch `nbot-v5.1`. Our owner-approved NO-BID-ASK 100→20 discovery and genuine Binance aggTrade+MARK WSS CS01 PASSED (32,313 original accepted frames, 40/40 cursors, 0 hard gaps, 145 SHA-linked source segments replayed, two VPSes 576 offline tests). STOPPED safely. Vision V1.10 supersedes quote-based sections of V1.9 without deleting V1.9. Finish remaining G4 multi-boundary/long-run checks when separately authorized, and convert future G5/G6 Research, and later PAPER, to **instant simulated MARKET fills based on original trade prices + prospectively conservative modeled costs**; never fetch/use bid-ask in active pipeline. Preserve strict source gaps, 0 qualified Research counts, no PAPER/Testnet/REAL, and keep granular roadmaps/documentation updated with empirical results.
