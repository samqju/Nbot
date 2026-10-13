# NBOT V5 — second independent security, correctness and evidence-integrity audit

Audit date: 12 October 2026 (Asia/Calcutta). Repository: [samqju/Nbot](https://github.com/samqju/Nbot). Target: [PR #38](https://github.com/samqju/Nbot/pull/38).

## Executive summary

**Verdict A — safe to merge as inactive research-only code: NO.**

**Verdict B — safe to deploy for live forward collection and scored virtual trades: NO.**

Reviewed commit: **`9a8163c9c7d38cccdb2ae215746492e3d2898896`**. The GitHub PR head matched that SHA both before inspection and at the final recheck. PR remained open and unmerged. Base inspected: `9b7fbbb27cdad067cdcdddd012402e00b59ada81`; remediation compared with `7d4fb9157f1a6036c1a8e581af31ff5dfb752371`.

The literal older-depth overwrite and zero-bookTicker admission defects are corrected. The larger evidence-integrity problem is not: a missing stop crossing lasting only 50 milliseconds can still turn a losing trade into three confidently `SCORED` horizon exits. Independent reproductions also found backdated admission using a later snapshot, reuse of a contradicted funding proof across restart, premature horizon sealing, continuation after losing a stop event to a failed database write, a validation/entry race, and swallowed asynchronous snapshot exceptions.

The five false-scoring/causality findings H1–H5 are merge blockers under the stated research contract. Keeping the code inactive avoids immediate operational exposure; it does not make its callable scoring interface correct. M1 should also be fixed before merge. M2 requires an explicit ownership contract or an atomic admission fix. No real-order authority defect was established.

Examined the full six-file PR diff, both new modules and all their tests, existing paired-exit/accounting/foundation modules, relevant quality/selection interfaces, V5 architecture documents, the entire master plan, the manual entry point, CI workflow and package imports. Repository sources were not edited. All synthetic databases and harnesses were isolated in the audit workspace. No orders, Binance REST/stream connections, VPS access, service restarts, PR review submission, comments, commits or pushes occurred.

Executed 74 focused existing tests: 70 passed and four ended in Windows SQLite file-cleanup errors. All 31 new bridge tests and all three existing transport tests passed outside the restricted sandbox. The three transport tests each timed out at 20 seconds inside it. Added 19 recorded main adversarial checks, four independent safety checks, five additional transport fault cases and two further snapshot-failure repeats. The main adverse cases were reproduced twice with identical outcomes. Ran a local 20-symbol checkpoint benchmark. These are synthetic accelerated event-time paths, not four-hour wall-clock or live exchange runs.

Independently fetched the requested [CI run 38281033032](https://github.com/samqju/Nbot/actions/runs/38281033032) and job `114918083097`: success; regression log reports **1,490 tests in 102.008 seconds, OK**. This verifies the reported CI result, not the missing adversarial properties. The full 1,490-test suite was not rerun locally.

## Original blocker verification

### P1-A — older depth replacing newer bookTicker: FIXED for the original mechanism

Independent sequence, BTCUSDT, milliseconds:

1. Initial aggregate ID 10 and synchronized depth/ticker ID 100 at `T=99,900`, bid/ask `99.9/100`; entry decision at `100,000`.
2. bookTicker `u=102`, `T=100,100`, bid/ask `98.5/98.6`, captured at `100,120`.
3. Older depth `u=101`, `pu=100`, `T=100,050`, bid/ask `99.9/100`, captured at `100,120`.

Expected: reject the older depth anchor, invalidate the active path, prohibit a new stale SHORT. Actual: `V5_DEPTH_BEHIND_TICKER`, feed disconnected, active path `FEED_UNCERTAIN`. The PR's executed regression additionally verifies the stale SHORT admission raises `LIVE_ANCHOR_UNPROVEN` and all three prior-path results are `UNSCORABLE`. No old-price overwrite remains in this sequence.

Independent reversed arrival test also rejected a ticker with ID 100/time `100,050` after depth ID 101/time `100,100`. Conflicting equal-time prices before horizon completion caused `JOINT_QUOTE_ORDER_AMBIGUOUS`; exact repeated ticker messages added only one path event. Existing tests verified quote receipt causality, future event times, depth duplicate conflicts, `pu` gaps and restart invalidation.

Limits: this verdict does not certify all admissions. H2 independently bypasses snapshot receipt causality; M2 bypasses validation through a concurrent disconnect. H4 shows equal-time ambiguity is no longer checked once the horizon flag is set. Event receipt delay is checked against exchange time, but there is no general monotonic receipt-time proof across all streams.

### P1-B — zero bookTicker scoring: PARTIALLY FIXED

The literal startup scenario is fixed. Independent bridge initialization with trade ID 10 plus synchronized depth ID 100, **zero ticker messages**, then `add(entry)` raised `V5_ENTRY_LIVE_ANCHOR_UNPROVEN`; active count remained zero. The executed PR regression also directly inserts a lab path without ticker provenance and verifies all three results are `UNSCORABLE` at finalization.

Additional executed checks:

- BTCUSDT's ticker became silent while ETHUSDT received a fresh ticker at `131,000`; coverage checked at `131,020` disconnected BTC, left ETH connected and made all BTC outcomes `UNSCORABLE`.
- After all three arms stopped at `100,100`, a trade at `131,100` without intervening ticker evidence made all three outcomes `UNSCORABLE`.
- An unfinished checkpoint restarted with `quote=None`, reason `PROCESS_RESTART`, and all three outcomes `UNSCORABLE`.
- PR tests passed for busy trade/depth traffic concealing ticker silence, greater-than-30-second missing crossing/recovery, recovery not restoring historical quotes, and reconnect snapshot not repairing affected paths.

However, H1 proves the watchdog does not establish the required complete quote path. Both input histories satisfy the configured liveness checks; one omits a stop and still scores three winners. Therefore the broader missing-bookTicker-coverage blocker is only partially remediated.

## Newly discovered findings

Severity concerns research correctness and operational reliability. No CRITICAL finding involving real-money execution or credential access was established.

### H1 — HIGH: sub-threshold omitted crossing still yields three SCORED outcomes

Affected: [`v5_live_evidence.py:95–102`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L95), lines 144–150, 412–417, 620–638 and 646–655.

Initial LONG: decision `100,000`, entry ask `100`, bid `99.9`, stop `99`, quantity `2`, aggregate anchor 10, depth/ticker anchor 100. Deadline `14,500,000`.

Exact divergent sequence:

| Evidence | Exchange time | ID | Bid/ask | Captured at |
|---|---:|---:|---|---:|
| Initial anchor | 99,900 | ticker/depth 100 | 99.9/100 | before entry |
| Stop crossing, delivered only in reference run | 100,050 | ticker 101 | 98.5/98.6 | 100,055 |
| Recovery ticker | 100,100 | ticker 103 | 99.9/100 | 100,110 |
| Aggregated depth | 100,100 | U=101, u=103, pu=100 | 99.9/100 | 100,115 |
| Trade | 100,100 | aggregate 11 | trade price 100 | 100,120 |

Then every 20,000 milliseconds until the deadline, deliver ticker, depth and trade in that order: matching stable top of book, increasing ticker/depth IDs, `pu=previous u`, consecutive aggregate IDs; receipts `T+10`, `T+15`, `T+20`. Call coverage at `T+25`. At deadline deliver `100.5/100.6` with matching depth and trade watermarks. Reconcile two empty funding reads after the grace period and finalize. **No silence constants were patched.** The harness specifies every subsequent event algorithmically.

Expected safe behavior under a complete-executable-path contract: an unverifiable intervening quote path must not produce a certified score.

Actual without the crossing: all three `SCORED`, exit time `14,500,000`, fill `100.5`, gross `+0.5R`. With the crossing delivered: all three `SCORED` but stop time `100,050`, fill `98.5`, gross `−1.5R`. Reproduced twice for each history. The hidden movement/recovery fits inside one 100ms depth aggregation interval; endpoint book state and depth `pu` continuity do not reveal its intermediate best price.

This is an injected missing-message counterexample, not evidence that Binance actually lost this packet in production. TCP ordering does not solve publication completeness or prove that a subscribed application stream contained every indispensable quote. Jumping ticker IDs cannot identify which intermediate IDs changed top of book.

Impact: fabricated favorable labels and invalid paired policy comparisons can enter the research ledger. Lowering the watchdog threshold cannot prove absence of an arbitrarily shorter crossing.

Correction: version the outcome contract. With these feeds, label only **observed-stream simulation** outcomes and exclude them from any dataset requiring certified path completeness; otherwise return `UNSCORABLE`. Certified scoring requires an authoritative sequenced quote feed with a completeness contract and replay/gap reconciliation covering the actual stop path, or another explicitly defined model that does not depend on unknown intrainterval extrema. A second independent recorder can expose disagreements but is not, by itself, a proof of completeness.

### H2 — HIGH: required snapshot can arrive after the admitted decision

Affected: [`v5_live_evidence.py:345–362`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L345), snapshot lines 458–480.

Sequence: trade/depth anchor at `99,900`, receipt `99,920`; ticker ID 100 at `99,900`, receipt `99,940`; then snapshot `lastUpdateId=100`, transaction time `99,900`, **receipt `100,500`**. Afterwards request entry timestamp **`100,000`** using matching bid/ask `99.9/100`.

Expected: reject because synchronized-book proof did not exist at decision time. Actual: admitted, active count 1, twice. `synced_since=100,500` exists, but `add()` checks only quote/trade receipt. Snapshot sets quote receipt back to the earlier ticker receipt. Later depth receipt is also omitted from admission's maximum receipt check.

Impact: hindsight entry eligibility and false claims that depth/quote confirmation was contemporaneously available. This contradicts the documented inclusion of snapshot completion in capture causality.

Correction: store a causal availability watermark for the reconstructed book, including snapshot completion and every applied depth update, and require it at or before entry. Perform that check and entry mutation atomically. Separate exchange timestamps, socket capture receipts and book-validation availability timestamps.

### H3 — HIGH: contradicted funding proof remains valid across restart

Affected: [`v5_live_evidence.py:593–617`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L593), finalization lines 643–660.

Sequence after the fully populated 20-second-observation horizon from H1:

1. At `END+60,000`, two history scans for `[100,000,14,500,000]` return `[]`; the bridge stores a coverage proof.
2. Two later scans for the same interval both contain `fundingTime=105,000`, rate `0.001`, charge mark `105`, BTCUSDT.
3. Reconciliation raises `V5_FUNDING_PROOF_CONFLICT`.
4. Restart the bridge, then finalize using the original empty proof key.

Expected: the affected proof/window must be durably revoked; dependent outcomes must be quarantined as funding-unproven. Actual: old proof still present; all three `SCORED`, funding `0.0`, twice. For these horizon-held LONG arms the newly observed settlement would be **−0.21 quote units per arm**.

The conflict is raised before any `_change`; neither the conflict nor revocation is checkpointed. An exception to the caller does not make the persisted old proof unusable. Pending completed outcomes also bypass proof reconsideration entirely.

Related guarantee gap: two immediate reads from the same endpoint can agree while both omit an unpublished settlement. Binance's retrieved funding documentation supplies inclusive bounds, ascending pagination, rate/time/charge-mark fields; it does not establish a universal 60-second publication-finality guarantee. The publication-risk disclosure in the PR does not satisfy a contract forbidding assumed zero coverage.

Correction: durably record proof states and revocations, invalidate every overlapping dependent window, and require a valid proof at both finalization and ledger consumption. Use versioned invalidation/quarantine records for previously immutable outcomes. Capture prospective symbol-specific schedules/publication evidence, reconcile expected settlements with their actual charge marks, and defer certification until finality/completeness is defensible. Do not substitute a fixed eight-hour schedule or predicted mark.

### H4 — HIGH: horizon flag suppresses contradictory evidence at the horizon itself

Affected: [`v5_live_evidence.py:93–96`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L93), lines 144–150; existing [`v5_paired_exits.py:179–181`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_paired_exits.py#L179).

After the continuous synthetic path, the closing ticker/depth at `END=14,500,000` have ID 820; closing aggregate ID 730 has the same timestamp. Receipts are `END+10/+15/+20`. This sets `horizon_witnessed=True`. Before funding/finalization, deliver ticker **ID 821**, **the same transaction timestamp END**, conflicting bid/ask **98.5/98.6**, receipt `END+30`.

Expected under the implementation's equal-time ambiguity policy: invalidate, or establish a stronger ordered close barrier before finalization. Actual: feed accepts the packet but `JointExitLab.event()` skips the path before any conflict check. Gap stays `None`; all three score at the previous `100.5` horizon quote, twice.

This is evidence *at* the already sealed boundary, not merely an unrelated post-horizon outage. The identical kind of ambiguity invalidates a path before sealing. Matching one depth/trade watermark is not proof that all delayed same-time source messages have arrived. Blanket invalidation for any genuinely later outage is unnecessary, but retroactive uncertainty within the certified window must remain actionable.

Correction: separate provisional horizon observation from evidence finality. Continue checking packets whose exchange times fall in the scored window until a defensible per-source close barrier is established. Preserve durable revocation/quarantine for later-discovered contradictions; merely waiting a fixed extra interval is another bounded-lateness assumption that must be explicit.

### H5 — HIGH: lost stop event after failed persistence does not poison the bridge

Affected: [`v5_live_evidence.py:287–320`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L287), ingest exception handling 375–381.

Sequence: normal LONG anchor; attempt ticker ID 101 at `100,050`, bid/ask `98.5/98.6`, receipt `100,055`. Inject `sqlite3.OperationalError("disk full")` at `_connect()` for that mutation. The memory rollback removes the stop event. After storage is available again, catch the exception and continue with recovery ticker/depth ID 103 at `100,100`, then the full regular path and funding proof.

Expected: the bridge must require replay of the exact failed event or durably mark affected paths uncertain before later ingestion/scoring. Actual: all three score at horizon `100.5`, twice. Ticker IDs may jump, so the next packet cannot establish whether the discarded ID crossed a stop.

Scope: reproduced through the public synchronous bridge interface. The provided `run_session()` normally unwinds on this exception and attempts `disconnect()` in `finally`; a real restart invalidates unfinished paths. This reproduction does **not** assert that the stock transport silently catches disk failure and continues. The defect is that rollback alone leaves the bridge reusable, with no enforced poisoned state; cleanup persistence may itself fail on the same disk fault.

Correction: set a nonrollbackable in-memory integrity-fault latch on a failed evidence commit, prohibit new admissions/scoring until explicit recovery, and preserve invalidation durably once storage recovers. A recovery API must replay the exact failed event before accepting any later event if it wants to retain eligibility. Test disk failure during both ingestion and subsequent disconnect.

### M1 — MEDIUM: dynamically created snapshot task failures are discarded

Affected: [`v5_live_transport.py:147–164`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_transport.py#L147), watchdog 103–118 and snapshot 99–101.

Mock both sockets open indefinitely. Public socket delivers one depth event. Its asynchronous REST snapshot raises `OSError("synthetic REST failure")` immediately. Market socket stays open with no events.

Expected: promptly propagate REST failure, invalidate/close the session and permit a bounded retry. Actual in three executions: **"Task exception was never retrieved"**, and the session remains running until the harness's two-second timeout. The last two measured durations were 2.018 and 2.008 seconds. The feed is disconnected only by cancellation cleanup.

Cause: `asyncio.wait(tasks, ...)` observes its initial task set. The consumer appends snapshot tasks while that wait is pending. A new snapshot can fail before the wait finishes; the code then filters out **every** done task at line 164, including tasks never returned in `done`, without retrieving their exception. The symbol remains in `snapshots`, preventing another snapshot request. The ticker watchdog skips unsynchronized feeds, and its queued messages keep the shared consumer timeout alive.

Impact: unavailable capture/resynchronization, unobserved failure and possible indefinite session stall. Fresh admissions remain blocked while unsynchronized, so this isolated scenario did not produce a false score.

Correction: use structured task supervision or a failure queue/completion callback for every dynamically created task; retrieve exceptions before reaping tasks. Clear/retry snapshot ownership only under an explicit resynchronization policy. Add a bounded startup/synchronization deadline.

### M2 — MEDIUM: admission validation and mutation are not atomic

Affected: [`v5_live_evidence.py:345–362`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_live_evidence.py#L345).

Sequence: normal synchronized feed, no active path. Thread A passes `add()` validation, then pauses immediately before `_change(ENTRY)`. Thread B calls ordinary `disconnect("BTCUSDT")`, which commits disconnected/empty quote state. Resume A; it acquires the mutation lock and adds the now-invalid entry.

Expected: reject the admission. Actual twice: active count 1, `connected=False`, no exception, new path `gap_reason=None`. The harness uses a barrier around the `_change` call to control timing, not altered validation or disconnect logic.

Impact: an entry may be admitted after losing the source. Documented single-writer use limits exposure: the current capture consumer serializes feed mutations and installs no selector. Multiple threads sharing the callable bridge are not protected by its apparent per-mutation RLock/CAS safeguards. This is not evidence that the current CLI already runs a concurrent admission worker.

Correction: perform admission validation inside the same `_change` lock/action as insertion, or enforce and test strict thread/task ownership for every read/validation/mutation. Cross-process CAS does not fix this same-object race.

### L1 — LOW: existing ledger connections are not explicitly closed

Affected: existing [`v5_foundation.py:64–76`](https://github.com/samqju/Nbot/blob/9a8163c9c7d38cccdb2ae215746492e3d2898896/nbot/observation/v5_foundation.py#L64), uses at 132, 164 and 176. This file is not changed by PR #38.

`with sqlite3.Connection` commits/rolls back; it does not close the connection. Four existing foundation/paired/selection tests ended with `WinError 32` removing database files during temporary-directory cleanup. Their recorded failures are cleanup errors, not failed price/funding assertions. The new bridge tests call `gc.collect()` in teardown and passed.

Impact: platform-dependent file locks and resource lifetime dependent on garbage collection. Correction: explicitly close connections with a context manager/finally or `contextlib.closing`. This is inherited cleanup debt, not a new PR #38 merge blocker by itself.

## Test results and limitations

### Existing offline tests executed

| Test group | Executed | Result |
|---|---:|---|
| `test_v5_live_evidence.BridgeTests` | 31 | all passed |
| Transport allowlist/routing/opt-in | 1 | passed outside sandbox, 0.033s |
| Transport snapshot buffer + aggregate recovery | 1 | passed outside sandbox, 0.296s |
| Transport closed-socket propagation | 1 | passed outside sandbox, 0.079s |
| `test_v5_foundation` | 8 | six passed; two Windows database cleanup errors |
| `test_v5_paired_exits` | 15 | fourteen passed; one Windows database cleanup error |
| `test_v5_selection` | 9 | eight passed; one Windows database cleanup error |
| `test_v5_market_quality` | 4 | all passed |
| `test_v5_regression_infrastructure` | 4 | all passed |
| **Total** | **74** | **70 passed, four cleanup errors** |

Most mechanical bridge fixtures patch the ticker silence constant to more than four hours; the production coverage rule is reinstated explicitly in selected regression tests. Their passes must not be interpreted as production-path coverage tests. The independent four-hour-event-time harness used the unmodified 30-second rule, regular 20-second observations and normal bridge persistence throughout.

Initial sandbox execution also encountered inaccessible system temporary directories; relocating TEMP/TMP into the workspace resolved synchronous bridge testing. The three asynchronous transport tests then each hit a 20-second process timeout inside the sandbox. Repeating outside it resolved all three without changing source. Python was **3.12.14 on Windows**. The bundled runtime lacks `websockets`; mocked transport tests inject their connector and do not require it. Actual library-version behavior, real ping/pong and socket I/O were not tested. Repository pins `websockets==17.2` in `requirements-wss.txt`.

### Independent checks executed

| Check | Expected safe result | Actual | Repeatability |
|---|---|---|---|
| Original older depth after new ticker | reject/invalidate | `DEPTH_BEHIND_TICKER`, disconnected | independent once; PR regression also passed |
| Zero ticker startup | reject admission | rejected; active 0 | independent once; PR regression also passed |
| Reversed arrival | reject/invalidate | ticker reversed/conflict | once |
| Equal-time disagreement before close | all unscorable | path ambiguity marker | once |
| Exact duplicated ticker | idempotent | one path event | once |
| Omitted 50ms crossing | no certified score | three horizon scores | twice, identical |
| Same crossing delivered | actual stop execution | three stops at 98.5 | twice, identical |
| Snapshot received after entry time | reject | admitted | twice, identical |
| Contradicted funding proof + restart | revoke proof | three zero-funding scores | twice, identical |
| Equal-time contradiction after horizon witness | reject/quarantine | three previous-price scores | twice, identical |
| Failed stop commit followed by continued ingestion | reject/replay | three horizon scores | twice, identical |
| Concurrent validation/disconnect | reject | admitted while disconnected | twice, barrier controlled |
| V1 checkpoint under V2 code | reject | contract mismatch | once |
| One silent symbol beside fresh other symbol | invalidate silent path | all three unscorable | once |
| Source failure after early exits | invalidate all policies | all three unscorable | once |
| Incomplete checkpoint restart | invalidate/clear quote | restart reason; all unscorable | once |
| Snapshot REST failure | propagate/reconnect | failure discarded until timeout | three, consistent |
| Wrong source routing | reject session | routing error, disconnected | once |
| Simultaneous socket closure | reject session | `WSS_CLOSED`, disconnected | once |
| External session cancellation | cancel/cleanup | `CancelledError`, disconnected | once |
| Queue saturation injection | propagate overflow promptly | outer 2s deadline completed only after 28.539s, TimeoutError | once; further investigation required |

The queue test injected 2,001 immediate messages into the 2,000-item queue. Its delay and exception did not match the expected prompt overflow result. It is recorded as an unresolved supervision/scheduling observation, not a independently localized additional false-scoring finding. A two-second asyncio timeout is not a hard process deadline when synchronous work or cancellation cleanup blocks the loop.

### Requested scenario coverage

Startup absence, prolonged busy-source silence, separate-symbol silence, missed stop/recovery, duplicates, ordering, incomplete restart, failure after early exits, trade recovery and reconnect/resnapshot were exercised. Brief missing coverage was independently shown unsafe. Concurrent admission/disconnect was tested. Simultaneous closures and cancellation were mocked.

Not fully exercised: real successful socket reconnection and restored subscriptions, actual 24-hour forced rotation, simultaneous live resynchronizations under REST limits, actual ping/pong, a concurrent depth/ticker scheduling stress matrix, clock jumps, lost buffered frames inside the actual WebSocket library, publication revisions on Binance, sustained multi-day capture, abrupt process kill/power failure, real disk exhaustion during cleanup, and Linux one-GB memory pressure. Existing rollback/concurrent-writer/corruption tests were executed, but do not substitute for those integration tests.

## Complete pipeline assessment

### Transport and source identity

Market/public paths and source validation match the retrieved Binance routed-connection contract. Public REST restricts paths/parameters, uses GET, rejects redirects, bounds responses and specifies timeouts. Ping/pong handling is delegated to the WebSocket library; the stock code relies on the venue's 24-hour close rather than implementing a proactive rotation timer. Mock closure handling passed; live behavior remains unverified. [Binance connection contract](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect).

The watchdog is independently *scheduled*, but its work is enqueued into the **same FIFO queue** and executed by the same synchronous consumer. SQLite writes run on that event loop; aggregate recovery awaits a worker thread before processing more queue items. Backlog can delay checking, and a blocked loop prevents the watchdog from waking. No per-symbol monotonic wall-clock deadline is enforced independently of that queue. The 30-second policy intentionally rejects genuine quiet markets too, which affects usable-sample selection and must be reported.

### Aggregate trades and recovery

The bridge checks consecutive aggregate IDs and nondecreasing trade transaction times. Exact current duplicate normalized trades are idempotent; old repeats/gaps are conservatively rejected. Recovery starts at inclusive `fromId`, validates chronology/IDs, limits pages, and commits page cursors. Partial recovery/restart and incorrect sequences passed the existing tests. Aggregate recovery does not call the executable-quote lab and cannot repair historical quotes. No new defect was independently established in pagination. Raw trade sub-ID continuity (`f/l`) is not a separate completeness proof beyond the assumed aggregate-ID contract.

### Order-book reconstruction

Snapshot overlap `U <= lastUpdateId <= u`, dropping older updates, subsequent `pu` continuity, absolute quantities and zero removal match retrieved venue reconstruction rules. Decimal identity, crossed books, exhaustion/overflow and duplicate conflicts are checked. The implementation is deliberately conservative about late depth relative to ticker. Comparing order-book IDs does not turn ticker jumps into a consecutive quote sequence; aggregate IDs belong to a different sequence. Snapshot-completion causality is broken by H2. [Binance local-book rules](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly).

Strict equality of top prices for admission and conservative cross-source ordering can reject normal asynchronous source skew. That is a coverage/selection issue rather than evidence of false acceptance by itself. Comparability, timestamp tie semantics and publication ordering of both feeds still need source-specific validation. A limited snapshot also cannot prove depth beyond captured levels or executable quantity for arbitrary position size; these are reference-price simulations with modeled slippage.

### Paired exits and accounting

Executed tests confirm LONG exits use bid, SHORT exits use ask, stop overshoots use observed prices, integer trailing changes activate on the next observation, fixed-target and time policies share a frozen entry, and early exits do not abandon the shared path. Horizon-before-stop priority is explicitly documented in the existing policy; it was not treated as a newly discovered defect. Basic fee/slippage arithmetic, funding sign and per-arm settlement windows passed.

H1 and H4 undermine the price-path prerequisite beneath those otherwise consistent mechanics. A hash certifies the bytes/events actually consumed, not that unseen crossings did not occur. H3 undermines the funding prerequisite. Pairing three arms over the same incomplete path reproduces the same uncertainty three times.

### Funding

Pagination, invalid marks/rates, wrong symbols, duplicates, unsupported Special rates, contradictory reads, exact settlement boundaries and individual arm windows are conservatively checked and tested. The rate/time/charge-mark fields used are supported by the retrieved venue documentation. Exhaustion of returned pages is not proof that all settlements have been published. Two requests to one endpoint are not independent sources of truth; no documented 60-second completeness SLA was established. H3 proves even an observed contradiction is not retained as a durable veto. [Binance funding-history contract](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#Get-Funding-Rate-History).

### Crash/database behavior

Within a successful mutation, immutable journal insert, ID registration and checksummed checkpoint update are in one `BEGIN IMMEDIATE` transaction, with WAL/FULL and sequence CAS. Executed tests covered rollback, a second initialized owner, corrupt checkpoint rejection, permanent decision IDs and partial ledger retry. An unfinished restart invalidates its quote path, and V1/V2 contract mismatch is rejected. H5 concerns continued use after rollback; H3 persists invalid funding eligibility across restart; H4 incorrectly treats a horizon flag as final evidence.

The three ledger outcomes are separate immutable writes, not one group transaction. A partial group is retained for retry, but any future learner must query only complete, matching three-arm sets or use an atomic paired-set publication marker. This is documented inherited behavior, not a newly introduced hidden atomicity claim. Actual power-loss durability and storage behavior were not tested.

### Resources and one-GB VPS

Measured on this Windows audit host: 20 synthetic symbols, 1,000 levels per book side, zero active hypotheses, 100 durable trade mutations. Elapsed mutation time **9.574s**, throughput **10.445 events/s**, p95 mutation **109.725ms**, serialized checkpoint **506,618 bytes**, final DB+WAL size **1,642,496 bytes**. Another adversarial process was running concurrently; this is a diagnostic desktop measurement, not a controlled capacity certification or VPS extrapolation.

Each event serializes a rollback copy and a new complete checkpoint, including all shard books, active/pending paths and funding proofs, then performs a full durable write. Under an active 20-symbol 100ms depth workload, as many as roughly 200 depth messages/s could precede ticker/trade traffic; the measured host result demonstrates that item caps alone do not establish sufficient service rate. Actual traffic depends on symbol activity and must be measured.

The application queue permits 2,000 messages, each with a 256KiB socket payload ceiling: approximately **500MiB of raw payload capacity alone**, before decoded Python objects and copies. Two socket queues of 64 such payloads add up to approximately 32MiB of payload capacity. These are upper-bound calculations, not measured RSS. Book buffers and Python allocation overhead can substantially add to the budget. No proof of safety on a one-GB host follows from O(1) arm state.

Twenty-symbol shards mean three separate bridges/six sockets for a 60-symbol universe. The journal is not pruned, proofs cap at 100, and the 256MiB admission check occurs before a mutation. Retention/export and limit handling need measurement; the cap stops capture rather than providing indefinite operation. REST snapshot bursts have no shared IP-budget integration with the existing collector. A deployment needs a shared weight scheduler, byte-based buffering, a storage design with sufficient sustained throughput, independent processing-delay deadlines and explicit memory limits.

### Order-authority isolation

Only six V5-specific files changed; no V4 source, databases, service units or execution paths appear in the diff. The manual command requires opt-in and installs no service. No execution client or credential argument is present in either new module; order stubs raise. Public transport does not sign requests or call private/order endpoints. The isolated checkout remained clean after tests.

Python package initialization imports existing `nbot.observation.observer` and `worker` modules, so claims of literally importing no collector modules are too broad. Their import does not instantiate collectors or start workers. A fresh-process audit hook around importing the two V5 modules recorded no SQLite connection, filesystem mutation or socket connection, and no `nbot.execution` module import. Actual VPS files/credentials/services were intentionally not inspected.

## Evidence-integrity assessment

The current system can demonstrate identities and order of **received** aggregate trades, consistency of the received depth reconstruction, observed side-correct quote triggers, known feed faults, transactional persistence and reproducible simulation over its accepted observations.

It cannot demonstrate a complete lossless executable bid/ask path. Ticker IDs can jump; depth aggregates multiple updates; source liveness is an elapsed-time heuristic; a healthy socket is not a publication completeness certificate. Endpoint equality and a closing trade/depth watermark do not prove all intervening extrema or same-time boundary events were seen. A missing quote interval and a legitimate unchanged interval can produce indistinguishable accepted observations. H1 provides a concrete pair of such histories with materially different stops.

The strict requirement is therefore **not achievable merely by tuning this watchdog or adding more ordinary snapshots**. Either obtain a feed/replay architecture with an authoritative continuity/completeness contract adequate to the proposed label, or change the experiment to explicitly score only observed-stream behavior with versioned uncertainty and prohibit promotion of those observations into certified continuous-path training targets. An independent recorder is useful for validation and fault detection; agreement cannot manufacture an unavailable guarantee.

Funding has the analogous issue: receipt of two matching current histories verifies agreement of responses, not all unpublished settlements or finality. Detected contradictions must at minimum revoke eligibility durably.

Documentation already discloses parts of these limitations. That is useful transparency, but `SCORED` plus `JOINT_WSS_EVIDENCE_RESOLVED` still conveys certainty incompatible with the master plan's continuously proven path and no-fabricated-zero requirements. Prospective benchmarking can characterize failure rates; it cannot logically disprove the adversarial indistinguishability counterexample.

## Remaining acceptance requirements

Before merging the present scoring contract, fix H1–H5 or explicitly version/remove the unsupported certification semantics, repair M1, and make admission ownership atomic/enforced. Re-run the standalone counterexamples and latest-head CI; maintain the negative results as regressions. Ensure future ledger readers cannot consume partial paired sets or revoked evidence.

Before any deployment, additionally require:

1. Authorized isolated Binance capture against an independently recorded reference: source mapping, timestamp/update-ID semantics, delays, reconnects, depth synchronization, transient quote disagreements and missing-crossing detection. No such live run was authorized or performed here.
2. More than 24-hour continuous mock/live observation covering forced close/rotation, REST failures/rate limits, simultaneous source reconnects and quiet symbols. Verify subscription restoration and post-fault admissions.
3. Prospective funding schedule/publication/charge-mark reconciliation across variable intervals, late or revised records, boundaries and unsupported settlement types. Keep uncertain windows unscorable.
4. Linux one-GB measurements with representative 20-symbol shards and eventual 60-symbol load: RSS, swap, CPU, p95/p99 capture/processing delay, queue bytes, sustained DB/WAL growth, disk sync latency and collector coexistence. The desktop benchmark is insufficient.
5. Abrupt process kill/restart and real storage-failure exercises, including failure while committing invalidation; concurrent owners and consumer/admission races; immutable quarantine/revocation and complete paired-ledger publication.
6. A retention/export plan and byte-aware backpressure policy that fail closed without poisoning historical labels, shared REST IP-budget coordination, clock synchronization/monotonic deadlines and visibility into evidence attrition.
7. Explicit deployment approval through the existing roadmap/cutover process. Preserve V4 and its collector. No profitability or deployment readiness follows from CI.

## Final verdicts

**A — Is PR #38 now safe to merge as inactive, research-only code? NO.** H1 demonstrates fabricated favorable outcomes under the claimed complete-path contract; H2 violates decision causality; H3 reuses contradicted funding after restart; H4 suppresses within-window contradictions; H5 permits a lost observed stop after failed persistence. These are callable research correctness defects, not solely prospective VPS concerns. M1 adds a reproducible silent transport failure. An explicit redesign that removes unsupported certification could make an inactive capture-only/observed-stream prototype separately reviewable, but that is not the current contract.

**B — Is V5 safe to deploy for live forward collection and scored virtual trades? NO.** All merge blockers remain, plus unresolved source/funding finality, real transport behavior, resource/retention/rate-limit measurements and crash/cutover acceptance. Collection-only experimental operation would need its own reviewed scope and resource approval; this report does not authorize it.

## Recommended next actions

1. **P1:** Disable certified `SCORED` publication for paths whose quote/funding completeness cannot be proved. Decide the versioned evidence model before adding further liveness heuristics; keep current uncertain paths `UNSCORABLE` or separately excluded observed-stream outcomes.
2. **P1:** Durably revoke contradictory funding proofs and quarantine every dependent outcome, including across restart and pending-ledger retry. Verify zero-funding finality against actual settlement completeness evidence.
3. **P1:** Require book/snapshot availability at or before decision time; move admission validation into its locked transaction. Add snapshot-delay and disconnect-race regressions.
4. **P1:** Make horizon finality provisional until within-window source ordering is defensible; allow later-discovered invalidity to quarantine otherwise immutable outcomes.
5. **P1:** Poison the bridge on failed evidence commits unless the exact event is replayed safely. Test failure of invalidation persistence as well as the initial stop write.
6. **P2:** Supervise every snapshot task explicitly, clear ownership correctly, propagate faults and add a synchronization deadline. Isolate/watch processing deadlines beyond the shared FIFO and investigate delayed overflow cancellation.
7. **P2:** Replace whole-shard checkpoint-per-event processing with a measured durable journal/incremental state strategy; preserve atomicity and fail-closed semantics. Add byte limits, retention and shared REST scheduling, then benchmark on the actual intended host under approved isolated conditions.
8. **P3:** Close inherited ledger connections explicitly, retain complete-group publication semantics and clarify that package imports load inert collector definitions. Re-run focused tests plus latest-head/merged-main CI after a reviewed correction.

## Reproduction artifacts

The accompanying evidence bundle contains standalone harnesses, raw result JSON, focused-test logs, the full PR diff and rerun instructions. The main harness has no network calls and uses production thresholds. Synthetic event times and IDs are explicit in its input helpers and progression loop. Test harness edits were confined to the audit workspace; the audited repository's tracked files remained unchanged.
