# NBOT V5.1 — CS-01 Trade-Price-Only G4 Retest, Owner Decision and Evidence Ledger

**Date:** 15 October 2026.  
**Target branch:** `nbot-v5.1`.  
**Source-only canary SHA pinned:** `f474085753c3f88d81c66a00f00a6d13b8311ae9`.  
**Mode:** `PUBLIC_OBSERVATION_ONLY`, no accounts/orders/model activation, maximum 180 seconds, no daemon.  
**New original-data destination:** Observation VPS `/home/ubuntu/nbot-v5.1-cs01-trade-only-20261015T1656Z` (private mode 0700). Retain previously preserved records and manual backup unmodified.

## Why the change

The previous 20-market three-feed `TRADE/QUOTE/MARK` canary stopped with repeated BTC `bookTicker EVENT_FUTURE_OR_STALE`. Original saved source analysis found a cross-symbol quote backlog rising from subsecond to ~4.5 seconds during seconds-long canaries, with approx 1,000–1,400 accepted quotes/sec. Owner decided to **never request bid/ask for the NEW active V5.1 pipeline**, preferring original `aggTrade` movement with a future immediate assumed simulated MARKET fill and adverse cost model, rather than LIMIT queue/touch calculations.

## Verified specific code changes

- [x] `nbot_v5_1/universe.py`: a version-separated `book_tickers=None` candidate policy accepts exactly **two independent source receipts**, public `exchangeInfo` + 24-hour tickers. Does **NOT** assert the old bid/ask spread gate; preserves USDT-perpetual, source, >=96 five-minute closed-bar history, BTC/100 and frozen stratified selection constraints. Legacy 3-source branch remains in code for historical offline regression only.
- [x] `nbot_v5_1/public_market.py`: the two-source source wrapper validates all returned public raw bytes/time/SHA and passes book=None for this new active policy.
- [x] `scripts/g2_readonly_probe.py`: `probe(trade_only=True)` makes **no `book_tickers()` GET request**, no book metadata receipts; still fetches eligible exchange metadata, 24h activity and 100 source-checked 96-candle histories; operational CS01 service explicitly calls this profile. The old `bookTicker` method and historic opt-in compatibility branch are **present but not executed by this live path**.
- [x] `nbot_v5_1/cs00_source_runtime.py`: strict public route builder `public_routes(...,trade_only=True)` returns only `TRADE + MARK` across 20 symbols, no QUOTE subscription. Historical three-feed function kept for existing lab cases.
- [x] `nbot_v5_1/cs00_public_service.py`: owner profile always uses `trade_only=True`, launches only **two** public WSS workers; stale route watch covers only TRADE/MARK. Strict real aggTrade aggregate ID continuity, event age <=5,000ms and public-mark checks remain unchanged. No Research/PAPER/order code started.
- [x] `scripts/cs01_public_observation_canary.py`: opt-in WSS smoke now connects only `TRADE + MARK` for BTC; full bounded CS01 result will disclose `quote_stream_subscribed:false`.
- [x] Added `tests/test_v5_1_cs01_trade_only_profile.py` with **seven new** no-book discovery/20-market WSS-mode and schema-isolation tests.
- [x] **First Observation VPS regression:** 569/569 older V5.1 tests PASS at a code-only intermediate SHA; **full 576/576 PASS** at code SHA `7812878d53ec9b92ef09c06107d185e1cbc50ab3`, and code after that was unchanged until the pinned smoke release `f474085...` (documentation-only addition). Exact-SHA signoff after all source revisions remains subject to confirming no intervening code changes.
- [x] **Owner-approved two-feed genuine live smoke:** 15 October 2026 16:56 UTC on Observation VPS, commit `f474085...`, BTC `aggTrade` frame 205 bytes, `markPrice@1s` frame 223 bytes, both `RECEIVED_UNQUALIFIED_LOCAL_WSS`, **2/2 live streams PASS**, source qualification FALSE, no orders.
- [ ] **Longer 180-second bounded 20-coin CS01 result:** full status including source cursor pairs, real trade continuity, 20/20 actual quote-free TRADE/MARK symbol coverage, boundaries, exit 0/2 and witnessed original segment receipts. Do not mark until observed.
- [ ] **G4 complete scientific acceptance:** sustained original complete and restorable source epoch, genuinely matured forward Research path, independently reviewed retest across volatility regimes. The 180-second canary alone does not prove full G4.
- [ ] **G5/G6 future trade-only instant simulated MARKET-fill + no-quote adverse economics:** source-only CS01 does NOT turn G5 on. Existing G5/G6/G9 OFFLINE lab contracts still demonstrate old quote-based simulation and must be versioned/adapted before any non-lab virtual/PAPER activation.
- [ ] **G7 independent qualified learning 2,000 outcomes and G8+ models/PAPER:** 0 genuine qualified, HOLD.
- [ ] **Owner's WinSCP offhost backup of original 20261015T152427Z genuine eight-record archive:** still not confirmed; retain on VPS.

## Historical versus new facts

Prior CS01 quote-ingress failure stays real historical evidence; it was not a BTC trading bug or a fictitious 100-symbol G4 subscription. Under the new **2-feed** profile it is **no longer a route that NBOT subscribes to**, but real `aggTrade` gaps, 5-second event-age failures, missing evidence, quote-free modeled economic limits, trade/mark downtime and other source problems remain possible and must be reported.

**Blueprint:** [Vision V1.10 trade-price-only amendment](NBOT_V5_1_PRODUCT_VISION_V1_10_TRADE_PRICE_ONLY_AMENDMENT_20261015.md), while V1.9 stays byte-for-byte unchanged.

**DO NOT** install a persistent service, start PAPER/TESTNET/REAL, write an order, claim profitable Research, override V1.9 silently or qualify 2,000 outcomes from a modeled instant fill.


## ACTUAL FINAL LIVE CS-01 RETEST — PASS (recorded after run)

**Start:** 2026-10-15T16:56:46.529954Z; **duration cap:** 180 seconds; **process returned:** 0 (PASS) after precisely owner-approved **CS01_TIMED_CANARY_COMPLETED**. Manual foreground only; Observation VPS `python3` process and nbot systemd service list checked afterward, **both empty** at 17:02 UTC. The exact active canary source SHA was **`f474085753c3f88d81c66a00f00a6d13b8311ae9`**; `no_orders:true`, `financial_authority:NONE`, no accounts, no Model/PAPER/testnet/real activity.

- [x] **Two-feed BTC smoke PASS:** BTC original `aggTrade` and `markPrice@1s` both received, no quote subscription.
- [x] **Full 20-market TRADE+MARK 180s canary PASS:** `source_frames=32313`, exactly **40/40 source cursor pairs**, `source_gap_count=0`, `hard_source_gap_count=0`, `errors=[]`, `error=null`; all 20 recorded both kinds. Last live result `source_receipt_files=145` complete `.json` meta files.
- [x] **No bid/ask fetch/subscription under ACTIVE CS01 profile:** a) 100 broad-market startup bootstrap explicitly `trade_only=True` and never calls REST `book_tickers()` b) combined WSS routes only **TRADE** and **MARK**, c) independently replayed evidence contained **ZERO quote frames**. Do not mistake preserved historical legacy functions for a live subscription.
- [x] **Original raw custody read-only replay:** independent script `scripts/cs01_trade_only_readonly_replay.py` (written after the observed source-run, cannot affect its behavior), `DeepSegmentRecorder.replay()` SHA-256 verifies and restitches **145 hash-linked compressed segments** and **32,313 raw source records** without any repairs.
  - `TRADE=29,372`, `MARK=2,941`; original distinct symbols `TRADE=20/20`, `MARK=20/20`.
  - Maximum archived accepted Binance event `E` → host WebSocket receipt delay: **TRADE 236ms**, **MARK 397ms**. These are maxima **for accepted saved frames**, not independent proof of latency outside saved evidence or upstream-source authenticity.
  - Original verified custody chain head **`647114e2ef27e3a67ba5402963b937f5efab0cb77a6f58580fa8842addbdb934`**.
  - `reviewable_underlying_id_skips=51`. These are **underlying trade `f/l` ID** discontinuity review counters, NOT 51 broken `aggTrade a` IDs; no hard aggregate-ID gap observed, continue scientific semantic review.
- [x] **New owner-private manual evidence archive generated/verified locally on VPS** (NOT yet downloaded to owner's 1TB Windows disk):
  - `/home/ubuntu/NBOT_Backups/NBOT_V5.1_TRADE_ONLY_CS01_20261015T1656Z.tar.gz`
  - `/home/ubuntu/NBOT_Backups/NBOT_V5.1_TRADE_ONLY_CS01_20261015T1656Z.tar.gz.sha256`
  - File size **2,778,845 bytes**, 302 tar entries; `sha256sum -c` **PASS** on VPS.
  - Archive sha256: **`de6f2c695867be361edd1d94ae2179632bf4de41d14991017e7566fcf1fee5f4`**. The previously preserved `20261015T152427Z` archive and checksum remain untouched.
- [x] **Real public original G4 ingestion profile PASS for this 3-minute canary**, but **[ ] G4 overall continuous and independently qualified scientific source ACCEPTANCE remains HOLD**: this one canary was not multi-day, did not independently qualify source/exchange signature, did not span two full new five-minute boundaries, did not mature source-graded G5 virtual fills or cost-verified G6 outcomes, did not prove a Windows off-host backup restore. `pipeline.boundaries=1`, no source-graded virtual/PAPER/REAL result.

**Source audit note:** Old 3-feed `bookTicker` stale HOlD remains true historical evidence; the new active mode eliminated that specific traffic channel, not source/clock/aggTrade/mark integrity risks. **Earlier 576 PASS are for active code SHA `781287...`; the canary tested `f474085...` with docs-only additions after `781287...`.** `b874b141...` is later *read-only replay script commit*, not live-service executable, and does not retroactively change the tested collector.

**Outstanding [ ]:** independently run 5-min boundary and longer volatility/endurance of the new two-feed profile; authoritative grade and G5–G10 **no-quote modeled instant market-fill** versioned code/evidence rules; offhost WinSCP verification of these two archive files; retain original diagnostic roots. **Never count 32,313 source frames as Research wins**. This report should supersede provisional 'canary pending' paragraph above.
