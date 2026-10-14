# NBOT V5 G1–G7 implementation and operational evidence — 2026-10-14

**Verdict: substantial implementation and tested guarded deployments; the full continuous G1–G7 system is NOT complete or scientifically accepted. G4 sustained source acquisition failed its operational checks. G5/G6 qualification and G7 paper execution remain locked. No market-driven paper order or real-money order was placed.**

## Code, ancestry and review
Repository: samqju/Nbot. Authoritative governance branch inspected at f63edd862b2e813f513673f83fe45f26b052fbcf; roadmap v2.8.13 §56 before this amendment. G4 PR #39 remained draft/unmerged at 8de8b999465aaf1e75eac3d518dd3eedcfbb3fe8.

Implementation branch: feature/v5-continuous-g4-g7-20261014. Draft continuation: https://github.com/samqju/Nbot/pull/40, stacked on the G4 branch.

Actual commits:
- 13612cc409a2c129ded51839fcf095ee0f2c1cb7 — bounded G5/G6 scientific core, immutable research/model journal, guarded G7 two-book paper core, G4 early maturity and resource budgets; selected Execution foundation files copied from pinned 4f7331c12233260b9422f1ff4ff9711d9b992a30.
- 5dc3378c46456b5747ac5da0d5acbe5386fcb14d — fixed Execution fixture imports; first official integrated CI green.
- ece48c13301e75f02b0ff2b729821c9da62e3556 — original G4 population bridge, original WSS path maturation, offline learning job, locked paper health runner, WAL batching.
- 33a9c825db304e56628b1959582d350147915e5b — corrected systemd restart-limit placement.
- dc4981c966313e53d996776172dce88eaa79a659 — bounded cursor caches and fair route scheduling.
- 12ee08f — retained typed public socket-close diagnostics.
- 899ccf6ace1e07dc08104a756da0778013de3281 — disjoint public quote shards with whole-route failure.
- 3c334634058aaefd4b7ec54715f443c97673fc6b — queue chronology regression fix, parallel shard opening and strict original exchange-event quote freshness.

Git graph audit before governance writes: governance...implementation = 25 governance-only / 159 implementation-only commits; main...implementation = 45 main-only / 287 implementation-only commits. Merge base with governance and Execution foundation: cb68ee247cbbb8577238e7d452ac5e79ebc4d089. No force reset, main merge, PR #39 merge, legacy service activation, worktree deletion or history rewrite was performed. Canonical main consolidation remains unresolved. Separate release pins are explicit below.

## Implemented interfaces
- G4: independently replayed original source prefix, full 50-coin/100-side population, original G1/G2/G3 binding, immutable policy geometry and label intents, bounded original post-decision aggTrade path tracking, early stop/target maturation, censoring without invented losses, and separate source/research ledgers.
- G5: immutable chronological outcome schema, source-lineage/digest checks, overlapping-market-window grouping, dependence-block bootstrap, no-trade comparator, fixed causal relative-strength selector, sequential portfolio drawdown/tail accounting, regime/diversity/side/time-span checks and explicit insufficient-evidence/no-edge results. Its protocol and empirical scientific acceptance still require independent review.
- G6: versioned BTC/coin/volatility/relative strength/breadth/source quality, 24 pattern and coin-structure features; purged chronological fit/calibration/holdout splits; bounded deterministic ridge expected-return learning; calibration/error-based abstention; reproducible artifacts; append-only candidate/disposition registry; independent approval and additional-2,000 Challenger controls. **No original-market-data model was trained or promoted.** The offline job exists; automatic qualified learning cycles and independent original holdout proof are not operationally accepted.
- G7: authenticated versioned envelope core, model identity/expiry/replay checks, separate event-sourced books, side-correct paper prices, explicit verified fee/slippage/funding requirements, exposure/correlation/risk/drawdown vetoes, stop/target/horizon exit, reconciliation, restart locking and kill controls. Synthetic fixtures exercise fills; deployed health mode has no network or unlock path. **Production recommendation transport, qualified models and independent paper release are not enabled.**
- G8: retained synthetic contest/replay/audit interfaces from the existing Execution foundation. No genuine prospective competition started.

These descriptions are component scope, not a claim that every requested engineering/operational milestone has passed.

## Test evidence
- Official final source CI: https://github.com/samqju/Nbot/actions/runs/38563588672 — **659 tests PASS** on 3c334634058aaefd4b7ec54715f443c97673fc6b, 27.211 seconds.
- Direct Observation VPS full suite: **655 tests PASS**, 118.300 seconds, on dc4981c966313e53d996776172dce88eaa79a659. Source log retained locally in evidence/observation-655-tests.log and remotely under g4-forward-integration-verification-20261014-uY0Qi1.
- Direct Execution VPS: **116 tests PASS**, 36.031 seconds, on 33a9c825db304e56628b1959582d350147915e5b; evidence/execution-116-tests.log.
- Local Windows: 48 new science/paper/early-maturity tests passed; later 30 paper/quote tests passed. Broad asynchronous/Unix-permission/SQLite fixture-cleanup runs did not pass on Windows and were not counted as successes.
- Initial official CI failed four imported fixture module paths; correction and subsequent successes are retained. No test count is an economic-outcome count.

## Original-source pilots — all bounded, all preserved
Every row below passed independent original receipt-chain replay and WAL-aware restored-copy verification. Every full cohort pilot returned operational **HOLD / exit 2**, not scientific GO.

| Pilot folder suffix | Retained receipts | Source-recorded frames | Held frames | Recorded coin coverage aggTrade / mark / book | Result |
|---|---:|---:|---:|---|---|
| jLnnLf | 39,815 | 5,527 | 34,283 | 50 / 50 / 50 | Public disconnect; large source lag |
| tAfp1b | 88,032 | 23,142 | 64,883 | 50 / 50 / 50 | Two public disconnects; batching reduced writes |
| 0Onovk | 79,392 | 31,299 | 48,084 | 50 / 50 / 50 | Public retry exhaustion |
| ORx9Nd | 49,953 | 40,041 | 9,905 | 50 / 50 / 13 | First shard pilot exposed queue-clock ordering fault |
| NEnkx8 | 63,237 | 30,277 | 32,955 | 50 / 50 / 48 | Corrected shards still disconnected; sent close code 1011 |

Roots are /home/ubuntu/nbot-backups/g4-forward-capacity-20261014-<suffix>. They are separate from original historical sources.

Third-pilot head: ad82db0da9ac852303d480df758ee868dddd8ef6f9cbb4e0823dad2ebd028038.
Third restored SQLite SHA256: c1abbbec871a0b0872728e934388d2c8051b667e5b5e1a4130e532fed577442d.
Latest shard-pilot head: 1d04e6baf6f740bd5e29321b8fef279a312343d891c8eaacbbacc66b94507ca7.
Latest shard restored SHA256: 8a417587f55627fd61fb6162452869ab19e00abb3f94b283b6e7edbc2d8696ce.

Third-pilot quote lag: median 11,025 ms, p95 25,610 ms, 41,569 quotes over 5 seconds. Its aggTrade/mark receipts had no over-5-second event lag. This distinguishes the quote bottleneck from a fabricated global clock problem; NTP reported synchronized and the host reported two CPUs.

Separate 50-symbol direct transport capture without SQLite closed after 1,009 frames; median lag 632 ms, p95 796 ms, zero stale frames before disconnect. Head 71958c3f792e47ca0dc78e6808328402dcf23f0ebdf9475783a8541c72f50290.
Separate BTC/ETH 30-second direct capture completed: 30,702 frames, median 120 ms, p95 346 ms, zero stale/future-clock violations. Head 9313a143c3e56692a656fabff1b0f4cabef454bb4e758d27d12e4aad922966a0.
Neither diagnostic supplies a qualified trade outcome or all-50 sustained acceptance.

Original 11,630-receipt vault and its previous gaps remain unchanged and preserved. No missing underlying trade IDs, quotes, costs or funding were filled in. No continuous source daemon was released after the failed capacity tests.

## Deployments, safety rollback and the G1 incident
Observation code stayed pinned to 1e7c090d05dc118b290c764d58c2944f56ad4b3b. The new research bridge was deployed at dc4981c966313e53d996776172dce88eaa79a659, service nbot-v5-continuous-research.service, at 12:11:08 UTC, with a 160 MiB / 20% CPU cap and a process ownership lock.

It actually produced a complete first 100-candidate HOLD population and a zero-outcome G5 insufficient-evidence report. Independent 12:15:40 UTC replay verified **200 held candidates / 204 journal records**, head ac848a12f99ae20eb82ee7e9f105e4ccdc87a81b814763bfdef28ac0fcb5e018; 0 label intents, 0 matured scored outcomes. Restored research SQLite SHA 4ad4d47e753f6e9753f2d77ed89290a1a9f1171f2c344dc1410ce1aa3b576e06.

**Material operational incident:** Original G1's public socket disconnected around 12:11 UTC, reconnected, and its existing permanent interrupted latch caused later full-population WSS_EPOCH_INTERRUPTED holds, beginning with the 12:10 UTC event. The original 09:00 PAXG HOLD remains separately preserved. Later held events are not losses and are not reclassified as accepted. Service uptime alone did not reveal this source failure. The first read-only integration preflight consumed approximately 95% of one CPU for 56 seconds; new workloads coincided with the incident. A causal attribution has not been proved. The controls did not justify claiming that G1 source continuity was unaffected.

All G4 pilots ended. The new research service was stopped and disabled to protect recovery; its source, state and evidence remain retained. It is **currently not a running complete research pipeline**.

The original G1 runner's code confirms interrupted remains latched after reconnection. After fresh independently opened SQLite restore checks, the same approved original service was orderly stopped and started once, preserving its database, frozen cohort, code pin, WAL-derived evidence and all records:
- Recovery root: /home/ubuntu/nbot-backups/g4-forward-g1-source-recovery-20261014-WHyfIU.
- Before-stop restored copy: 68 manifests, 6,800 candidates, 3,400 G2 witnesses, 68 G3 contexts; integrity ok; SHA 029e5921101d46fb12eb438b4f9ea63f30dc38656467e8f5b9bbfa66bb217f7d.
- After-orderly-stop restored SHA: fa75b5f4484170de7dde912237b589212b1b609d9c116bef285dac150618d015.
- New PID 23075; entered service **2026-10-14 12:31:14 UTC / 6:01:14 PM IST**.
- Exactly one manual G1 recovery restart in this work segment. NRestarts=0 after start is a systemd field, not a claim that no manual restart occurred.
- Fresh market/public sockets connected, reconnect counter 0 at the first recovery heartbeat; one restart-missing event was explicitly reported.
- **Original uninterrupted 24h gate cannot be accepted at the old deadline.** New elapsed-24h review is no earlier than **2026-10-15 12:31:14 UTC / 6:01:14 PM IST**, conditional on actual stability and independent original source/held/replay criteria. No reliability PASS is declared.

Execution deployment: nbot-v5-g7-locked.service at immutable release 33a9c825db304e56628b1959582d350147915e5b; started 11:59:52 UTC. Independent 12:15:52 UTC reconciliation: active, zero restarts, ~10 MiB, both books zero fills/positions/fees/funding/realized PnL, no model qualification, LOCKED. The nominal 10,000 per-book starting balance is paper bookkeeping, not Binance funds. Health runner has no network or unlock path. Ledger head 06eeac428b05e56cbfc574e1c1ec9b426c463008138332d9c820f9ad63a2ff0d. Legacy Execution files/services remain preserved/inactive.

## Preservation
Original G1/G2/G3 and G4 online backups were restored with integrity checks before workload changes. Execution legacy SQLite was online-backed up and integrity checked; all copied account/history/config-state evidence bytes were compared and SHA-manifested. No source database reset, archive deletion, old model promotion, forced branch update or real-money API order path was enabled.

Observation original backup root: g4-forward-continuous-preflight-20261014-Vyrw6b.
Execution legacy backup root: v5-continuous-preflight-20261014-CzdifY.
Original cohort file SHA: 043dc133e4f22db4fb1e73b02c3ccf60f10f5e5ca120d19b2fd6a93c345a0dbd.
Original prospective policy file SHA: b2768de6f6771b7c5831c783643ad36d116135f253185362df8a119a24917680.
Off-host report/log/hash anchors were downloaded to this task's outputs/evidence directory. The backups themselves remain on the VPS; downloading report hashes is not a claim that every new SQLite backup was also copied off-host.

## Milestone truth table
| Stage | Engineering / integration | Runtime | Scientific / action release |
|---|---|---|---|
| G1 | Existing source preserved; same-release recovery performed | Original collector restarted and receiving; new reliability review pending | Old 24h continuity HOLD; original criteria retained |
| G2 | Original frozen population/witness contracts retained | Same integrated collector; incident holds preserved | No blanket full-window acceptance |
| G3 | Causal BTC/coin feature contracts retained | Same integrated collector | Incident-held contexts are not usable labels |
| G4 | Source/ledger/path bridge implemented and synthetically integrated | Bounded pilots failed; bridge rolled back; no sustained collector | 0 qualified matured after-cost outcomes; HOLD |
| G5 | Evaluation software implemented; original protocol/baseline proof pending | Produced real zero-outcome insufficient-evidence report during bridge test | >=2,000 qualified outcomes not met; training locked |
| G6 | Actual offline learning/calibration/artifacts/registry implemented | No original training or qualified model; controlled cycle deployment incomplete | Initial and additional-2,000 independent gates locked |
| G7 | Core risk/auth/accounting/recovery tested | Locked two-book zero-orders health service running | Production recommendation transport/unlock qualification incomplete; LOCKED |
| G8 | Synthetic contest/audit preparation retained | No genuine comparison | Requires accepted G5/G6/G7 and eligible models |

## Next executable work and blockers
1. Verify recovered G1's first prospective accepted event and all immutable pre-recovery rows; preserve and classify the exact incident/source-epoch/missing-slot evidence under the original reliability contract.
2. Redesign/benchmark G4 acquisition and batch source verification away from uncapped observation-host load. The 50-symbol quote transport, lag and shared-resource effects remain unresolved; no longer source service is justified by these failed pilots.
3. Restore the research bridge only after resource/isolation and source-quality checks. Current stopped bridge input is a closed historical pilot; it cannot supply new prospective quotes.
4. Add and operationally prove the original cost/funding/source verifier/export path, bounded controlled learning-cycle scheduling and production Observation-to-Execution authenticated transport. Component APIs/tests do not replace those missing operational integrations.
5. Accumulate genuinely matured, independently cost/source-qualified outcomes; apply G5 >=2,000, dependence/diversity/baseline/holdout requirements and G6 additional 2,000 disjoint outcomes. Independently review models and G7 before any paper unlock.
6. Reconcile canonical main only after a source/diff/backup/rollback review; the known divergent history was not silently merged.

There is no scientifically qualified Champion or Challenger, no authorized paper recommendation, no G8 scientific comparison and no profitability claim. Work remains; this report does not label the requested end state achieved.

