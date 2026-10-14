# NBOT V5 — G1–G3 Engineering and Storage Release Contract (2026-10-14)

**Status: engineering tests green; operational/scientific acceptance held.** This is a
PR #39-derived, observation-only source release, not a G4–G7 enablement or an
authority to place orders. Draft PR #42 holds the changes. Both VPSs must remain
without active NBOT application services until the complete pipeline is integrated,
the owner approves commissioning, and the independent acceptance gates are met.

## Deployment contract

- Observation hostname `base`: one canonical tree, `/home/ubuntu/Nbot`; the
  pinned `nbot-v5-g1g2g3-observation.service` is **stopped and disabled** with
  `Restart=no`. No timers or other NBOT collectors may be started as a side effect.
- Execution hostname `nbot-execution`: same pinned source tree for offline
  verification. Do not install or start a collection service, market account
  client, simulated order executor or live execution unit.
- Preserve `/home/ubuntu/nbot-final-reset-20261014` on each VPS and the
  off-host `F:\NBOT_V5_RECOVERY_20261014` rollback bundles.
- Retain preexisting SQLite history, including earlier source interruptions,
  quarantine and crash evidence, for read-only audit. **Do not** count that
  interrupted capture as a fresh continuous-24h acceptance.

## High-rate ingestion: bounded state, not a tick database

The WSS market/public transport authenticates only the structure of public
Binance frames (not exchange-signed contents). Every quote and aggregate trade
is decoded **once**, then updates its coin's bounded in-memory latest-state slot.
No individual quote, trade, open candle or full raw frame is inserted into
SQLite or emitted into the systemd journal.

Persistent facts are recorded at source epoch change or finalized five-minute
event boundaries: 96 REST bootstrap candles per coin once per new cohort,
accepted immutable WSS finalized candle records, G1 two-sided candidate
manifest rows, original as-of G2 source quotes, G3 context, and independent
multi-stage WSS/REST finality and quarantine proofs. REST bootstrap candles
cannot retroactively reconstruct any lost trade/quote tick continuity.

| Fixed cadence / bound | Engineering contract |
| --- | --- |
| Public quote slot | At most 1 latest quote/coin (50 for a 50-coin cohort) |
| Aggregate trade slot | At most 1 latest trade/coin (50 total) |
| Candle ring | At most 96 closed five-minute candles/coin (4,800 total for 50) |
| Market-data SQL writes per raw quote/trade tick | **0** |
| Max 5-minute events per day | 288 |
| Per complete 50-coin event | 50 coin closed-bar facts, 50 G2 quote witnesses, 100 candidate-direction rows and 1 G3 context, plus finality/audit records |
| Routine heartbeat logging | At most 1 metrics heartbeat/minute, not per tick |
| SQLite disk guard | 256 MiB across DB **plus WAL plus SHM**, then fail closed |
| Transport rate guard | 750,000 WSS frames per route per bounded 300s interval; exceed -> HOLD |
| Source recovery | New accepted 5m event, source reverified and all three REST finality stages; never backfill missing trades |

An **offline synthetic 50-coin 40,000-tick** regression verifies zero SQLite
writes, zero additional DB/WAL growth, 50 latest quotes, 50 latest trades, and
unchanged fixed candle storage. It also verifies one parser invocation per
message, disallows private/foreign route/source frames, and checks that an
oversize WAL alone triggers the cap. Existing crash/gap/quarantine tests remain.

The event-driven database **is not forever constant in size**. Append-only
five-minute evidence grows with calendar time. On reaching the cap, stop on
explicit resource HOLD; never delete or compact original immutable scientific
evidence in place. A long-term retention/rollover plan must snapshot and
verify prior immutable data off-host, preserve chain-of-custody and source
cohort integrity, then begin a new owner-approved cohort/DB. Do not silently
roll into a fabricated uninterrupted 24-hour interval.

## G1/G2/G3 validation boundaries

- **G1 software engineering:** verified bounded memory/tick coalescing,
  deduplicated disconnects, finite retry budget, source epoch requalification,
  immutable REST-vs-WSS quarantine and restart HOLDs; offline tests PASS.
- **G2 software engineering:** frozen original top-50 cohort, original
  event-clock source quotes, 50/100 per-interval denominator, witness digests,
  rejected source gaps and no after-the-fact invented source; offline tests PASS.
- **G3 software engineering:** fresh volume-ranked G1 universe normalized
  *without changing members*, causal 96-bar histories, independent frozen
  quote/feature replay, BTC regime and per-coin breadth, no look-ahead, and
  immutable context with replay/tamper holds; offline tests PASS.
- A full 50-coin, two-original-event synthetic fixture verifies G1 population,
  G2 100 original quote witnesses, G3 50-member frozen replay, 200 two-sided
  candidates, source digests, corruption and missing-proof refusal.
- **None of these offline PASS statements proves market-source availability,
  genuine 24h uninterrupted operation, source eligibility through all events,
  qualified future economic outcomes, G4 scientific GO, or G5–G7 permission.**

## Next authorized engineering step

Proceed to G4–G7 offline source/label/economics/learning/paper-lock work
without starting application services. Once all are engineered and tested,
conduct an owner-controlled *single coordinated commissioning/soak*; each gate
still requires its own time-bound original evidence and independently defined
sample/maturity quality. No live orders, no testnet order, and no automatic
execution-service activation.
