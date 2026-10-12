# V5 public live evidence and recovery bridge (PR #38)

Research only. Order authority **NONE**. Not deployed. No V4 source,
collector, databases, services, VPS configuration or execution secrets change.
No selector worker or automatic admission/promotion is installed by this PR.

## Evidence contract

`v5_live_transport` opens two explicitly routed Binance USD-M connections per
bounded shard (maximum 20 symbols): `/market` aggTrade and `/public` bookTicker
plus diff depth at 100ms. These paths follow the current
[Binance connection contract](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect).
The WebSocket library handles ping/pong. A connection close, buffer overflow,
30-second shard silence, late receipt, malformed message or depth sequence
fault invalidates affected paths. Reconnect backs off to 60 seconds. The
bounded queue (2,000), socket queue (64), payload limit (256 KiB), depth buffer
(2,000), and book level cap (5,000 per side) fail closed on overflow.

Trade IDs must be consecutive, transaction timestamps monotonic. Exact last
trade/quote/depth retransmissions are idempotent; conflicting identities fail.
bookTicker update IDs can jump normally: they are **not** aggregate IDs and
do not prove consecutive quote history. Prospective quote quality rests on an
uninterrupted observed WSS session plus independently synchronized depth
`pu` continuity, not a claim that every exchange matching-engine mutation is
published. The 100ms depth stream is itself aggregated. Silent per-symbol feed
loss without an observable protocol fault remains a venue/transport limitation;
this bridge is not an independently certified lossless exchange archive.

Quote-only changes drive LONG exits at bid and SHORT exits at ask, including
stops and trailing updates between trades. Trades establish sequence evidence;
they do not fabricate executable quotes. Across sockets, reversed transaction
times or conflicting quotes at equal timestamps invalidate the entire paired
sample instead of retrospectively sorting events or substituting future quotes.
This deliberately sacrifices some coverage. An identical quote delivered by
both sources cannot ratchet trailing state twice. A closing quote within the
existing five-second horizon grace, an aggregate-stream transaction watermark
at/after that quote, and a synchronized depth ID/time watermark covering the
closing quote are all needed. All arms need the whole shared horizon,
even after early exits. Four-hour horizon, fees, slippage and initial -1R
accounting remain unchanged. The old `PairedExitLab` tick contract is unchanged;
`JointExitLab` uses its arm/accounting rules with a new versioned hash chain.

## Depth and recovery

Buffer diff events before the REST snapshot. Drop events with `u < snapshot
lastUpdateId`; the first accepted event must satisfy `U <= lastUpdateId <= u`.
Every subsequent event must have `pu == previous u`. Quantities are absolute;
zero removes a level, including absent levels. A missed bridge, exhausted or
crossed book, overflow or `pu` break requires resynchronization.
See [Binance local book rules](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly).
A limited snapshot does not certify unlimited depth or a real fill.

`recover_trades` uses public GET `/fapi/v1/aggTrades`, inclusive `fromId`, limit
1,000, and a finite page budget. Every contiguous page and cursor commit
durably; unavailable/empty history returns incomplete, bad sequences fail.
[Binance documents limited recent history availability](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).
During reconnection the first new WSS ID bounds the missing range. Recovery
restores available trade evidence only. **Current REST depth/bookTicker
snapshots cannot recover missed historical book quotes.** Already affected
paired paths stay UNSCORABLE after trade recovery and new book synchronization.

## Durability and funding

Explicit initialization creates a separate V5 SQLite database in WAL mode with
FULL synchronous commits. Each mutation commits an immutable audit event and a
checksummed checkpoint atomically. Checkpoints freeze entries, arm states,
resumable evidence digests, aggregate cursors, funding proofs and bounded pending
results. A compare-and-swap sequence rejects concurrent writers. Database errors
restore in-memory state to the previous commit; corruption/contract mismatch
raises, never resets the database. Restart retains all frozen state but marks
unfinished horizons PROCESS_RESTART because absent quotes are not recoverable.
Previously horizon-complete paths and completed pending results retain their
evidence. Ledger writes retry immutable per-arm outcomes; the durable pending
set is acknowledged only after all writes succeed.

Funding reconciliation exhausts two independently requested, identical public
`/fapi/v1/fundingRate` histories over an explicit symbol/time range, queried at
least 60 seconds after its end. It retains settled rate, funding timestamp and
the mark associated with that charge. No projected markPrice rate, guessed
eight-hour schedule, current mark substitution, incomplete pagination or
network failure establishes coverage. Wrong symbols, invalid marks/rates,
duplicates, contradictory overlapping ranges, unsettled windows and boundary
ambiguity fail closed. Special/multiple same-time rate types cannot be scored
under V1's strictly ordered accounting contract. Empty funding is accepted only
when both completed historical queries agree. Public history is authoritative
venue research evidence, subject to publication/revision risk; agreement is not
proof of private account cash settlement. This credential-free bridge never
queries account income. No actual account position or cash payment is claimed.

Each paired arm uses its own exit window and the existing LONG-pays/SHORT-receives
sign convention. The range proof joins the outcome evidence hash. Missing proof
makes scoring unavailable. See
[Binance funding history fields and pagination](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

## Manual use and outstanding gates

The callable bridge accepts frozen, proven live anchors, ingests events,
reconciles funding, finalizes and durably acknowledges ledger writes. It does not
select entries. The standalone capture command is explicitly opt-in:

```text
python deploy/observation/run_v5_live_evidence.py --research-only --symbols BTCUSDT ETHUSDT
```

Do not run this on the production VPS before the roadmap's resource/cutover
approval gates. There is no installed service. Public REST uses allowlisted GET
paths and parameters, rejects redirects, caps responses at 2 MiB and times out
after 10 seconds. HTTP errors (including rate limits) never become successful
recovery/coverage; reconnect backoff applies. REST-heavy deployments still need
an independently measured IP-weight scheduler before increasing shard count.

The database has a 256 MiB admission budget checked before mutations; pending
results cap at 100, retained funding range proofs cap at 100. The journal grows
Each funding range is limited to 1,000 settlement events.
on disk; it is not automatically pruned. Reaching a limit stops work without
discarding evidence. Full bounded checkpoints per event prioritize correctness;
1 GiB host throughput, WAL/disk budget, retention/export, memory/CPU pressure,
funding publication timing, clock synchronization and prospective multi-day
coverage must be measured before deployment. There is no claim of production
readiness or profitable entry thresholds.

Rollback: leave the opt-in module unused or revert this PR; retain V5 evidence
files for audit. No V4 rollback, collector restart or VPS action is needed.
