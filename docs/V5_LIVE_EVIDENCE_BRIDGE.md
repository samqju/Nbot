# V5 public evidence bridge — V3 observed research contract

Research only. Order authority **NONE**. Not deployed. V4 code, databases,
collectors, services and execution configuration are unchanged. Imports may load
inert collector definitions; import/construction perform no network or database
writes. Initialization and capture are explicit operations.

This document supersedes V2 at PR #38 head
`9a8163c9c7d38cccdb2ae215746492e3d2898896`. Historical statuses/bytes remain
historical; no `SCORED` row is upgraded to certified evidence.

## Trust classification and consumers

Live storage: `NBOT_V5_JOINT_EVIDENCE_V3`. Classification:
`NBOT_V5_EVIDENCE_TRUST_V3`.

| Class | Meaning | Complete-path consumer eligibility |
|---|---|---|
| RECEIVED_EVIDENCE | Validated event durably accepted into the journal | None by itself |
| OBSERVED_STREAM | Provisional simulation over received observations | Prohibited |
| CERTIFIED_PATH | Requires sufficient path, ordering, provenance and funding proofs | Unavailable: no validator exists |
| UNSCORABLE | Known integrity/causal/ordering failure prevents simulation | Prohibited |
| REVOKED | Append-only quarantine overrides an earlier conclusion | Prohibited |

`require_certified_sample` rejects **every** sample for TRAINING, CHAMPION,
PROMOTION and PERFORMANCE. `V5EvidenceStore.certified_pairs` enforces that guard.
Caller-supplied booleans/status/proof dictionaries cannot enable certification.
No V5 learner/promotion integration exists; V3/V4 consumers read their own storage
and remain unchanged. Future V5 consumers must use this boundary. Direct SQL
extraction is not a supported training interface.

The legacy tick lab and V1 ledger retain their mechanical contract and `SCORED`
terminology, not a complete-path proof. `legacy_scored` and `certified=0` make
that explicit; the compatible `scored` count is not a performance claim.
`JointExitLab.finalize` cannot use inherited legacy scoring.

## Provenance, completeness, ordering and entry causality

Two public USD-M connections carry `/market` aggTrade and `/public` individual
bookTicker/diff depth. Routing is checked; sources remain distinct. Aggregate
IDs and book IDs are different sequences. Quotes price LONG exits at bid and
SHORT exits at ask. Stops retain overshoots; trailing updates activate on the
next observation. A/B/C share one frozen entry/risk/quantity and digest.

Consecutive received aggregate IDs, depth `pu` continuity, matching top prices,
source liveness and open sockets cannot prove all intermediate quotes were
published/delivered. A 50ms stop/recovery can disappear inside one depth
interval. Delivered and omitted histories retain different observed results;
neither qualifies as certified. REST snapshots and aggregate recovery cannot
recover historical bid/ask movements.

Joint transaction times must not reverse; local receipts cannot reverse.
Equal-time conflicting prices invalidate the sample. Exact current duplicates
are idempotent. Independent socket skew may reject legitimate paths. These are
conservative local assumptions, not an exchange-wide total ordering guarantee.

Admission validates and mutates under one bridge RLock and durable CAS. Checks
cover connection/sync, IDs, quote/trade receipts, depth age, snapshot completion,
book availability and evidence-validation availability before decision time.
Production availability includes the actual clock after durable acceptance.
Synthetic tests inject accelerated clocks explicitly. Later snapshots never
backdate entry eligibility.

## Provisional horizons and funding lifecycle

A closing quote with trade/depth observations witnesses an observed horizon;
it does not close the evidence window. Further relevant events still pass
ordering/contradiction checks. Published outcomes are observed diagnostics.
Any later received event within a published interval, including closing grace,
causes conservative quarantine, even if a retransmission might be harmless.
No conclusive Binance closing watermark is assumed.

Funding journal states: PENDING request; VERIFIED_RESPONSE_AGREEMENT under
`TWO_EXHAUSTED_HISTORY_RESPONSES` version 1; CONTRADICTED then REVOKED in one
durable invalidation event. Verification means only response agreement, never
completeness/finality/private cash settlement. Superseding a revoked range is
unsupported and requires a newly reviewed proof contract.

Empty responses never establish zero funding. Each arm reports known signed
settlement observations over its own exit interval, separately from gross,
fees and modeled slippage. Total funding, funding R, net quote and net R are
**null**. Boundary settlements are unscorable. Revised overlapping responses
revoke prior proof use and conservatively quarantine symbol-dependent samples,
including pending and acknowledged ledger writes.

## Journal, faults, restart, paired publication and migration

Accepted mutations append complete inputs to a SHA-256 chained SQLite journal
and durable head under `BEGIN IMMEDIATE`, WAL/FULL and sequence CAS. WSS events
checkpoint every 128 commits; controls checkpoint immediately. Rollback copies
only the affected book plus bounded lab/funding state. Tail replay applies
recorded operations without network calls. Startup validates the complete
bounded journal, head, checkpoint checksum/chain and revocation overlay.

Storage failure latches a nonrollbackable integrity fault and failed-event
identity. Ingest, admission, reconnect, finalization and publication are blocked.
Cleanup failure cannot clear the latch. `recover_integrity` explicitly records
the fault, quarantines identities, invalidates paths and requires fresh sync;
it does not claim exact missing-event replay. Failed recovery retains the latch.

No trustworthy clean source-close barrier exists across process death. Startup
quarantines prior identities and invalidates all active paths, even horizon
witnesses. Frozen diagnostics survive with revoked effective eligibility.
Corruption/contract mismatch fails closed, never resets storage. Stale owners
are rejected. Checksums detect corruption, not a malicious DB owner recomputing
all hashes.

The foundation adds `v5_observed_pairs` beside unchanged V1 tables. One atomic
immutable row holds all three arms with matching identities/digest. Legacy
paired publication also uses one transaction. Acknowledgment follows commit.
Append-only bridge revocations override immutable ledger bytes on every
diagnostic read. A matching initialized, current, nonfaulted authority is
required; missing/stale authority fails closed. Raw exports without this overlay
are not current reports or eligible datasets.

V1/V2 live checkpoints are rejected. Preserve them with old versioned code for
audit; use a **new filename** for V3, e.g. `live_evidence_v3.db`. No automatic
status rewrite or certified import exists. Moving bridge/ledger files must
preserve the authority binding or use a reviewed migration. Never delete
journals to fit storage.

## Resources and remaining acceptance

Transport bounds: 256 queue items, 2MiB raw queue bytes, 64KiB messages, eight
library slots per socket, 2MiB buffered depth per symbol, 5,000 levels per side,
20 symbols per shard. Raw byte limits do not measure Python RSS. Overflow or
more than two seconds of processing backlog fails closed. SQLite work is off
the event loop; cancellation awaits an in-flight mutation before cleanup.
An unresponsive filesystem cannot be bounded by an asyncio timer.

All tasks have owners and exception callbacks. Snapshot failures propagate;
startup/resync deadline is 15 seconds. Coverage checks run outside FIFO traffic
under the bridge lock. The 30-second ticker-silence threshold rejects uncertainty
but never proves completeness. Rotation at 23 hours invalidates before retry.
Actual venue ping/rotation behavior remains unverified.

PublicRest allowlists unsigned GET, rejects redirects, bounds response/network
time, reserves conservative weights and observes HTTP cooldowns. Shared V5
RequestBudget objects can coordinate shards. Default budgets do not open V4
budget DBs. Shared-IP/collector and cross-process funding quotas remain gates.

Database+WAL cap is 256MiB; reaching it latches capture closed. Retention never
deletes history. Funding ranges cap at 100 and settlements at 1,000/range;
active/pending pairs cap at 100 each. Reviewed export/rotation remains required.
One-book rollback and bounded lab copies still cost time: this is not a fully
incremental materialized-book engine or a proven one-GB deployment.

Run the offline benchmark with
`python deploy/observation/benchmark_v5_evidence.py --events 300`. It reports
desktop timing, traced allocations, disk and restart measurements, not VPS
capacity. Manual capture needs separately approved isolated observed-research
scope. No command enables certified scoring, installs services or orders.

## Official sources checked 2026-10-13

- [Connection routing](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect): public/market split and combined URLs.
- [Public streams](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public): ticker update ID/time fields; depth aggregation intervals; ordinary books exclude RPI orders.
- [Aggregate trades](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/market): 100ms aggregation excludes insurance-fund/ADL trades. NBOT's consecutive-ID check is an implementation assumption, not quote completeness.
- [Local book rules](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly): snapshot overlap, `pu` chaining, absolute quantities and zero removal.
- [REST market data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data): snapshot/aggregate limits and pagination; funding inclusive bounds, ascending order, limit 1,000, charge marks, Regular/Special types, variable interval information and quotas. No universal funding publication-finality SLA or final range watermark was found in these contracts.

No sufficient completeness/finality proof is implemented. A live test can
characterize delivery but cannot disprove the missing-crossing counterexample.
