# NBOT V5.1 — CS-00 Recovery-First Offline Engineering Completion Evidence & Remaining Operational Holds

**Prepared:** 15 October 2026 (IST)  
**Repository:** `samqju/Nbot`, branch `nbot-v5.1`  
**Exact tested executable source revision on BOTH VPSs:** `57968e43d815e4ad84caed88e815f152ab89194a`  
**Result:** **[x] CS-00 ADDITIONAL OFFLINE SOURCE/RUNTIME/RECOVERY/BACKUP/SAFETY ENGINEERING TESTED.**  
**Parent CS-00 startup-readiness:** **[ ] HOLD** until independent deployment/retention/operator acceptance (not authorizable from synthetic tests).  
**CS-01 actual public-only source startup:** **[ ] NOT OWNER AUTHORIZED**. No NBOT service was installed, enabled, started or restarted. No original actual-source Research or Binance account/PAPER/testnet/real mode.

## 1. Owner's approved operating rule

The owner selected V4-style compact immutable Research/Observation ledgers, automatic Binance USD-M `aggTrades` history recovery after VPS crashes/internet/WSS interruptions, next-day checksum-verified public daily files where available, and NO permanent million-tick Training database. Where a virtual experiment's required path/cost evidence is **independently established as unrecoverable**, exclude it completely from Learning, Training, scored win/loss and model promotion; retain a tiny audited `CENSOR/UNRECOVERABLE_EXCLUDED` tombstone in the original candidate denominator. No fabricated win/loss, no retroactive false first-touch, no silent admission after a source/restart HOLD. `PATH_ONLY`, missing quote, missing mark trigger/funding and cost-pending paths remain distinct from independently qualified after-cost Learning samples. Synthetic recordkeeping tests do not grant genuine scientific qualification.

## 2. Exactly what is coded (not claims of actual live operation)

| Capability | Actual code | Evidence / status |
| --- | --- | --- |
| 100 broad finalized G2 + 200 G3 direction/capacity states + frozen mandatory-BTC deep-20 | `nbot_v5_1/cs00_source_pipeline.py`, pre-existing G2/G3/G4 | [x] OFFLINE integrated; source never independently original qualified; no virtual admission |
| Strict public-only fixed routes/frames, epoch/aggregate-ID gap quarantine, bounded 256 last health transitions | `cs00_source_runtime.py` plus `deep_source.py` | [x] OFFLINE local original-shaped frames; duplicate JSON/unsafe routes deny |
| Actual stdlib TLS WSS protocol implementation, pinned `fstream.binance.com`, `/public` vs `/market`, TLS hostname/HTTP 101 accept, client masked ping/pong, bounded server messages, fragmented/reordered/malformed frame HOLD | `cs00_public_ws.py` | [x] OFFLINE codec/negative tests; **[ ] no actual Binance continuous WSS commissioning; requires explicit future CS-01** |
| Manually gated foreground public-only service, one G2 initial public 100-market snapshot, 3 distinct public routes, five-minute G2 bar refresh, source receipt sealing, no auto-reconnect, SOURCE_HOLD/STOP on route failure, no exchange orders | `cs00_public_service.py` | [x] code built and activation refusal tested; [ ] no actual startup/live-source acceptance or installation |
| Strict REST-only `/fapi/v1/aggTrades` bounded pages, 48-hour lookback, 20 weight/page, global 60s budget, retry backoff; rate budget defer does **not** imply irrecoverable experiment | `cs00_recovery_worker.py`, `cs00_history_recovery.py` | [x] injected fake public response tests; [ ] no actual live REST recovery yet |
| Large gap memory bounded: frozen stop/target streamed from 1,000-row pages, without retaining every historical price in RAM; not actual executable fill | `cs00_history_recovery.py` | [x] source-shaped offline and 100k-ID frozen gap tests |
| Binance daily USD-M `aggTrades` ZIP CSV with official-style `.CHECKSUM`, SHA256 and canonical path/layout, safe archive CSV stream, bounded checks | `cs00_daily_archive.py` | [x] generated synthetic ZIP and checksum tests; [ ] archive download/actual genuine date/file/availability still to verify |
| Recovery-exhausted virtual experiment excluded via durable G5 CENSOR; G7 NON-SCORED `UNRECOVERABLE_EXCLUDED` counted as censored in scientific denominator | `research_book.py`, `learning_contract.py`, `learning_science.py` | [x] offline journal/restart/exclusion/tamper tests; genuine source proof independently required |
| Small coherent SQLite WAL backup (using SQLite native `backup`) plus limited owner-private JSONL, SHA manifest, read-only independent verification, no overwrite or automatic delete | `cs00_compact_backup.py`, `benchmarks/cs00_offhost_compact_fixture.py` | [x] on-host tests **and physically different VPS synthetic replay**, measured below |
| Conservative CPU/RAM/disk/queue, source-gap, 5m latency, WSS stale/timeout, heartbeat, emergency stop, no automatic restart, no production orders | `cs00_supervisor.py` + future runner | [x] offline faults and documented controls; [ ] actual persistent watchdog/on-call/notification proof belongs to operator commissioning |
| Bounded signed-looking local reporting and basic disabled/uninstallable systemd example retained; original Python tests | `cs00_commissioning.py`, `cs00_host_monitor.py`, `scripts/cs00_observation_entry.py`, `deploy/cs00_observation_disabled.service.example` | [x] earlier CS-00 OFFLINE tests; never installed, enabled or started |

**Source-release security caveat:** `FutureCs01Permit` verifies the structure, exact requested code revision and expiry of a **user-supplied approval reference**; it is **not** a cryptographically authenticated owner signature or permission to initiate activity. Deployment operator must authenticate the owner's separate explicit CS-01 approval externally before constructing/using it. All operations remain public-only even if the reference is forged. No production account/private/trade client is present.

**Scientific caveat:** traded-price chronology recovered after a disconnect may prove a LAST-TRADE stop-before-target ordering when aggregate-ID/time history is independently complete. It cannot re-create what NBOT actually received before an earlier decision or missing historic bid/ask, mark-price trigger, executable fill or full funding/fee witnesses. Missing economic information means no qualified G7/G8 result. Retrospective recovery may take longer than REST's 48-hour horizon or fail during upstream outage; original missingness is recorded and never silently scored.

## 3. Independent target-VPS results (actual)

Frozen GitHub source `57968e43d815e4ad84caed88e815f152ab89194a`. Python 3.12.3 Ubuntu both hosts; isolated private temporary shallow clones; zero service changes; standard complete suite:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1*.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 -B benchmarks/cs00_offline_readiness_benchmark.py
```

| Measured item | Observation-VPS (`base`) | Execution-VPS (`nbot-execution`) |
| --- | ---: | ---: |
| Combined existing G0–G11 + CS-00 tests | **539/539 PASS** | **539/539 PASS** |
| Suite elapsed | 56.187s | 58.108s |
| Benchmark source/decision footprint | 100 / 200 / 20 | 100 / 200 / 20 |
| Synthetic QUOTE/TRADE/MARK frames / sealed segments | 720 / 12 | 720 / 12 |
| Initial five-minute event processing | 99.330 ms | 99.503 ms |
| Synthetic 20-deep source fsync p99 batch | 48.418 ms | 40.353 ms |
| Peak benchmark process RSS | 32,140 KiB | 32,284 KiB |
| Benchmark process CPU | 0.659 s | 0.662 s |
| Benchmark local finite storage | 101,190 bytes | 101,190 bytes |
| Offline benchmark | **PASS** | **PASS** |
| Isolated suite checkout cleaned | `CS00_RELEASE_CHECKOUT_REMOVED` | `CS00_RELEASE_CHECKOUT_REMOVED` |
| Original live market data qualified | **0** | **0** |
| Actual live PAPER/testnet/real orders | **0** | **0** |

**Budget checked by the OFFLINE synthetic harness:** p99 less than 1,500ms, process RSS less than 256,000KiB, harness disk less than 33,554,432 bytes. These synthetic frame rates are NOT a live 20-market high-volatility source stress, 24/72-hour soak, operator deployment, or quote/economic qualification. The host benchmark's `archive_actual_offhost_verified=false` reflects **its separate same-host G4 source-shaped copy**, not the independent compact-ledger cross-VPS trial below.

## 4. Physically different VPS compact-evidence copy/recovery (SYNTHETIC ONLY)

- **Actual sender:** Observation-VPS, isolated `/tmp/nbot-cs00-offhost-src-WQOHoP`, source SHA `4a25cbfe37fc9be30f93ada0913f40f8d25b9f17`. Generated a synthetic pre-declared 100/200 event, a Research `UNRECOVERABLE_EXCLUDED` (net R null), one source recovery-only witness and a consistent SQLite-WAL Learning lineage database. Used native SQLite backup and wrote four private files.
- **Actual receiver:** Execution-VPS, independently created `/tmp/nbot-cs00-offhost-dst-7ClN1B`; byte-for-byte transferred the gzipped 1,119-byte tar package through the authorized PuTTY laptop bridge, unpacked to private scratch and replayed with `verify_compact_backup()`.
- **Exact package SHA256 sender AND receiver:** `b6f6606fb74c6479c38e41ee5fe52f882766de5b8410929259deca5f34d8416f`.
- **Exact independently verified manifest SHA256 both hosts:** `138e3ee3211f41809482427c3c753c8520ee88bae42460ad9565105cb1fc1e39`.
- **Identical returned proof:** `files=4`, `total_bytes=12654`, `order_authority=NONE`, `scientifically_qualified_original=false`. Pure single-host `verify_compact_backup()` rightly returns `offhost_independently_verified=false` because an isolated library cannot determine its physical sender; independent host identity, transfer and matching outputs above establish this separate **synthetic backup trial**, not exchange-signed provenance.
- **Housekeeping:** both temporary verifier checkout and staged sender/receiver folders, plus two failed-test disposable checkouts, removed by exact known path with verified successful output. No unrelated `/tmp/nbot-g8-...` files changed; no production service restarted or installed.

This demonstrates a viable minimal backup plan **without selecting/buying a new cloud archival provider**. It does **not** establish unattended permanent external storage, laptop availability, actual long-run daily volume, backup retention or real ORIGINAL G4 off-host archive custody.

## 5. Granular CS-00 checklist truth

- [x] **CS-00-A1/A2** previously independently accepted exact-source and two-host baseline audit.
- [x] **CS-00-B1/B2/B3** preexisting offline contract, disabled entrypoint and G2/G3/G4 source-shaped acceptance.
- [x] **CS-00-B4-OFFLINE** future public-only TLS transport, 100/200/20 source-only foreground composition, explicit source epochs and no-auto restart on loss, and source-only safety gate coded and tested.
- [x] **CS-00-C1/C2/C3** existing immutable small data/archive tests with no automatic deletion.
- [x] **CS-00-C4-DESIGN** owner-selected lightweight essential Research/Observation/economic receipts and selectively necessary source evidence, no mandatory all-tick cloud archive.
- [x] **CS-00-C5-SYNTHETIC-OFFHOST** independent cross-VPS small receipt/SQLite restoration, separately measured and digest verified; do NOT check the G4-06-D genuine actual-original parent from it.
- [x] **CS-00-D1/D2** original offline monitor/fail-closed tests.
- [x] **CS-00-D3-OFFLINE** heartbeat/queue/disk/RSS/route staleness, stop on fault, no auto recovery without source audit.
- [x] **CS-00-R1/R2-OFFLINE/R3-OFFLINE/R4-OFFLINE/R6-OFFLINE/R7-OFFLINE/R8** owner design, public trade recovery worker, daily ZIP fallback, cost/first-touch masks, large incremental page and emergency tests, compact off-host synthetic restore and both-host 539/539 evidence.
- [ ] **CS-00-C4-OPERATIONAL** select actual permanent minimal off-host destination/retention/quota and obtain owner consent to create durable services/storage on VPS/laptop; no provider purchase is necessary.
- [ ] **CS-00-B4-OPERATIONAL** independently demonstrate actual continuous live public WSS/100+20 source, TLS session receipts, volatile-rate pressure and reconnect/cursor/outage/endurance with narrow CS-01 owner approval; engineering tests alone do not qualify original market source.
- [ ] **CS-00-D3/D4-OPERATIONAL** approve actual emergency contacts, watchdog/control configuration, immutable source release/signed owner artifact, monitored stop/drain/rollback on deployment. No actual service installation was authorized, so no such system proof was run.
- [ ] **CS-00-E2 FULL PRESTART SIGNOFF**, pending the narrow operator/retention/deployment decision and independent operator handover review.
- [ ] **CS-01 public-only live observation startup owner approval** separately needed; user only authorized OFFLINE engineering this turn.
- [ ] **G4–G10 authentic original-source, independent after-cost and genuine PAPER parent gates**, none automatically checked by these synthetic/source-shaped tests.
- [ ] **G12 real account/real money**, entirely excluded.

**Recommendation:** The requested OFFLINE CS-00 implementation work is completed as far as technically testable **without starting NBOT**; maintain the master CS-00 full operational signoff as HOLD until the owner chooses minimal persistent record custody and gives a separate controlled CS-01 source-only commissioning approval. Do not make full CS-00 operational GO contingent on a paid cloud provider: the proved Execution-VPS synthetic off-host test plus a reviewed laptop/backup policy may suffice if sustained genuine rates and disaster recovery justify it. The owner has not authorized ongoing unattended replication, so leave it OFF.

## 6. Handoff and future verification

Keep this document, [Master Startup Plan](NBOT_V5_1_CONTROLLED_STARTUP_AND_LIVE_EVIDENCE_MASTER_PLAN_V1_0.md), [Owner Checklist](NBOT_V5_1_CONTROLLED_STARTUP_OWNER_CHECKLIST_AND_EVIDENCE_REGISTER_V1_0.md), both owner/engineering roadmaps and the latest dated handoff in sync. The last sections supersede old narrative snapshots. First future operational action is **CS-01 source-only owner-approved canary after narrow readiness/backup/alert decision**. Verify 20/20 genuine TRADE/QUOTE/MARK, the old 47 trade-ID semantics, actual sustained disk/CPU/quote/mark feeds, and physically separate ORIGINAL archive restore before G4 parent signoff. No PAPER/TESTNET/REAL.
