# NBOT V5.1 — BTC/G4 QUOTE Delay Root-Cause Investigation, Saved Original WSS Forensics + V4 Design Review

**Date:** 15 October 2026.  
**Repo/branch:** `samqju/Nbot`, `nbot-v5.1`.  
**Latest actual live-run executable baseline (unchanged):** `6b7491d8a903cbc248c85327a20919d68f05292f`.  
**New diagnostic-only code:** `scripts/cs01_readonly_latency_forensics.py` added after that live baseline, NO active NBOT runtime modification or new source startup.  
**Decision:** **G1–G3 initial genuine-source limited PASS; G4 sustained original 20-market capture/quotes HOLD**; no permanent Observation service or PAPER/REAL orders.

## Key finding: this is a shared high-volume QUOTE delivery backlog, not a BTC-only pricing fault

A read-only inspection of the previously preserved original public WSS segments, `/home/ubuntu/nbot-v5.1-cs01-diagnostic-2` to `-6`, decoded every stored original-shaped raw public envelope, extracted its Binance `data.E` event timestamp and its captured `received_at_ms`, then compared `received_at_ms - E`. The forensic script never contacted an exchange, restarted an NBOT service, printed ticks/prices or changed those files.

| Genuine diagnostic run | Stored accepted QUOTE messages | Quote measured window | All-QUOTE median age at **start** | All-QUOTE median age at **end** | BTC start → end median | Comment |
|---|---:|---:|---:|---:|---:|---|
| diagnostic-2 | 3,060 | 3.032 sec | 429 ms | 653 ms | 435 → 659 ms | Early clean burst |
| diagnostic-3 | 7,096 | 7.164 sec | 562 ms | **4,474 ms** | 557 → **4,639 ms** | Age climbs near five-second source gate |
| diagnostic-4 | 17,459 | 13.889 sec | 444 ms | **4,402 ms** | 728 → **4,395 ms** | Other symbols as delayed as BTC |
| diagnostic-5 | 10,009 | 10.192 sec | 448 ms | **4,466 ms** | 472 → **4,623 ms** | Soft stale events on BTC, SOL, SUI etc |
| diagnostic-6 (last) | 10,242 | 7.254 sec | 940 ms | **4,545 ms** | 727 → **4,633 ms** | **BTC QUOTE** ultimately hard HOLD |

The final run's observed accepted-quote intake was **~1,412 quotes per second** across 20 symbols, or approx 10,242 accepted quoted frames/7.254s; the other runs show ~982–1,257 quotes/sec. At that scale, a single quote socket plus synchronous message verification/receipt handling is a plausible bottleneck. This is an observed sample, not the provider's true peak/full-wire rate.

**Source-type comparison in diagnostic-6:** accepted BTC `TRADE` event-to-receipt median **~641 ms** (p99 1,316 ms); BTC `MARK` median **180 ms** (p99 183 ms). Accepted QUOTE events across symbols age toward **~4.5 seconds**. This makes a constant VPS clock offset or universally broken Binance network less likely; **it does not yet prove which component inside the quote path is responsible.** Other symbols, including ETH, ADA and SOL, also had near-five-second quote ages. BTC receives many quotes, so BTC is often where the threshold is first breached, NOT the sole source of delayed data.

**Important measurement limitations:**

- The saved G4 recorder keeps **accepted** raw frames only. Rejected stale raw `E` frames are **not captured in that exact segment**, so the recorded accepted-frame maximum is inherently **censored near 5,000 ms**. The independent `research/source_anomalies.jsonl` records withheld soft stale statuses and hashes, but does not contain the source `E` value or full rejected payload. Do not infer all Binance frames were younger than 5 sec from accepted segments alone.
- `received_at_ms` is stamped in `FuturePublicObservationService._worker` **after** `PublicTlsSocket.read_message()` returns; it is **not a kernel/hardware timestamp at network arrival**, nor a separate post-processing timestamp. It cannot distinguish Binance upstream delay, TCP/TLS buffering, Python read/message scheduling and lock/CPU contention by itself.
- These were **seconds-long accepted evidence windows** within time-limited canaries, NOT full 24-hour volatility/endurance experiments. No real Research outcome/first-touch/cost source grade or Champion is granted.

## V4 code review: useful architecture exists, but V4's evidence rules are not a safe drop-in

Real historical code was inspected on GitHub repo **`main`**, specifically:

- [`nbot/observation/wss_transport.py`](https://github.com/samqju/Nbot/blob/main/nbot/observation/wss_transport.py): `CombinedStreamRunner` uses **asynchronous socket reception separated from an `asyncio.Queue(maxsize=4096)` consumer**, `websockets` library receive buffers and socket ping behavior, full queue diagnostics, bounded explicit overflow HOLD and restart/backoff. The receive timestamp is assigned on producer ingestion.
- [`nbot/observation/live_two_tier.py`](https://github.com/samqju/Nbot/blob/main/nbot/observation/live_two_tier.py): running streams are split into plan-defined shards, with `market_data_gap` invalidating affected symbol paths; bookTicker disconnection does not automatically destroy every active aggregate-trade chronology.
- [`nbot/observation/wss_market.py`](https://github.com/samqju/Nbot/blob/main/nbot/observation/wss_market.py): per-symbol `SymbolHealth` tracks missing aggregation IDs, reorder and duplicate counters; quote availability is checked before making an executable-price claim.
- [`nbot/observation/v4_research.py`](https://github.com/samqju/Nbot/blob/main/nbot/observation/v4_research.py): on restart V4 **invalidated unresolved trade paths**, rather than fabricating a continuous record.

**Safe lessons to reuse:** separate fast WebSocket read from slower parsing/archival, timestamp at socket handoff, set an **explicit bounded queue**, export queue depth and dropped/held counts, partition QUOTE by symbol group or give BTC an independent quote reader, and quarantine source scope/pair rather than automatically invalidating all unrelated markets when quote health degrades. Keep strict G4 scientific provenance, frozen cohort hashes, cause-of-loss receipts and retro-recovery distinction.

**Unsafe V4 shortcut NOT to copy:** `WssMarketState.executable_quote` checks age relative to **receipt time** rather than independently proving `Binance event E → actual decision time` freshness. V4 also supplies `receipt_time` as fallback if quote `E` is absent. This is **not** sufficient for V5.1's first-touch/bid-ask cost evidence. Likewise V4's reconnect and bounded queue may drop messages; **any overflow/connection gap must remain visible HOLD/recovery/exclusion**, never silent data continuity.

### Direct V5.1 bottleneck candidate

[`nbot_v5_1/cs00_public_service.py`](https://github.com/samqju/Nbot/blob/nbot-v5.1/nbot_v5_1/cs00_public_service.py) creates **one QUOTE WSS worker for a combined 20-symbol bookTicker stream**. The same thread calls `PublicTlsSocket.read_message()`, then directly runs `SourceOnlyPipeline.ingest_offline_frame()`, which verifies the envelope, checks stale and cursor invariants, SHA hashes and queues source receipts in [`deep_segments.py`](https://github.com/samqju/Nbot/blob/nbot-v5.1/nbot_v5_1/deep_segments.py). Under 1,000–1,400+ QUOTE messages/sec this serial receive/parse/custody loop may fall behind. Trade/mark run in separate much lighter threads and remain substantially fresher.

**This is the current leading engineering hypothesis, supported by a growing age ramp across many symbols.** It is not yet independently proven that quote backlog happens *inside* NBOT rather than prior to socket handoff.

## Exact next fix and acceptance (keep user informed, no hidden startup)

- [x] Retrieve and analyze original stored WSS segment bytes from **five** canaries, with distribution, BTC-vs-others, trade-vs-quote-vs-mark, first/last chronology.
- [x] Review V4's actual async producer/consumer, sharding, per-symbol health, overflow, restart handling.
- [x] Add committed reusable *read-only* forensic script to V5.1 GitHub; no live-service code changed.
- [ ] Instrument **upstream E → socket `read_message` return → queue enqueue → downstream decision** timestamp components separately, with monotonic durations and queue depth/overflow per feed. Check system clock/NTP offset.
- [ ] Compare **BTC isolated** quote socket, then 5-symbol and 20-symbol quote loads. Determine whether userland reader/combined-stream backpressure or upstream network/source is causing delay.
- [ ] If on-box bottleneck demonstrated, adapt V4's **bounded sharded fast-reader/consumer** pattern to V5.1 as new tested clean code; do not import legacy account/trading modules, hardcode old 50-symbol conventions, skip hashes, or change the owner's 100 broad/20 deep/40 virtual plan.
- [ ] Preserve hard max 5s decision-time evidence rule, strict `aggTrade a` continuity and per-experiment `UNRECOVERABLE_EXCLUDED` audit. Soft stale quote remains unqualified and logged; repeated stale quote maintains HOLD until scientifically justified per-symbol containment is proven.
- [ ] Run new adversarial offline tests both VPSs on one pinned SHA, then **separately owner-approved, bounded public-only** isolated-vs-combined canary, several five-minute boundaries and independent source/backup verification before marking G4; no permanent Observation daemon without authorization.

**Current state:** CS-00 offline software complete with intentional operator holds; bounded CS-01 public canary ran and safely stopped on G4; **G1/G2/G3 limited initial live checks passed**, G4 ongoing source HOLD, G5–G10 qualified original scientific/PAPER gates locked, G12 real money locked. User's 1 TB desktop backup solution is ready, but the local WinSCP transfer of the first genuine eight-file backup remains unverified. Continue with [LATEST START-HERE HANDOFF](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md).
