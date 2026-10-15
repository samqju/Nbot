# NBOT V5.1 — CS-00 Final Offline Engineering, Persistent-Record Checkpoint and Prestart Gate Report

**Date:** 15 October 2026 (IST).  
**Repository:** `samqju/Nbot` branch `nbot-v5.1`  
**Verified executable code SHA on both VPSs:** `a41b65ebb7795bb3e4312e9817e1567f1c1faf5d`  
**Operational status:** **CS-00 OFFLINE ENGINEERING ACCEPTED [x]; CS-00 FULL OPERATIONAL COMMISSIONING [ ] HOLD; CS-01 PUBLIC WSS START [ ] NOT AUTHORIZED; PAPER/TESTNET/REAL [ ] LOCKED.**

## Decision and engineering correction

The owner asked to complete every CS-00 subtask without starting NBOT, selected a 1 TB Windows desktop drive for manual WinSCP backups, and requires irrecoverable Research experiments to be excluded from all scored Learning/Training while preserving tiny censored audit receipts.

The audit discovered **a real source/backup integration gap**: the future CS-01 public-only collector had not persisted its G2/G3 observation/exploration state inside the manual desktop backup source root, nor could the owner backup atomically fence a multi-file record update. The following changes are now coded and independently tested; not merely suggested:

| ID | Engineering acceptance item | Actual result |
| --- | --- | --- |
| CS00-REC-01 | Preserve prospective G2 observation, G3 200 directional Research opportunity labels and immutable 100/20 cohort as recoverable data | [x] `SourceOnlyStateWriter` uses existing `CompactObservationStore` and `ExplorationStore` to write SHA-hashed manifest, 100-observation snapshot, all G3 labels and an additional final event checkpoint |
| CS00-REC-02 | Interruption cannot leave a plausibly complete partial outcome | [x] Missing G3, missing commit, altered G2 or broken SHA aborts owner backup; no fake outcome/record |
| CS00-REC-03 | Manual owner backup and live writer cannot interleave | [x] Writer and owner backup share private Unix `flock` on `~/.nbot-v5.1-state.lock`; held writer forces the owner command to HOLD rather than capture partial state; retry after release passes |
| CS00-REC-04 | Bounded original WSS-segment receipts safe for owner backup | [x] `segment-*.gz/.json` accepted only as complete consecutively numbered matched pairs with immutable meta SHA chain and max-1MiB bounded GZIP replay; missing pair or tampered compressed evidence forces HOLD |
| CS00-REC-05 | Future Observation data-root wiring | [x] `FuturePublicObservationService` now constructs a source-only pipeline with `state_root` and `evidence/` segment directory; pending actual first ever real WSS data and restart acceptance |
| CS00-REC-06 | Restart and stale source continuity | [x] Persisted source receipt replay on attempted restart does not silently requalify a live epoch; pending independent CS-01 restart/warm-up canary |
| CS00-REC-07 | Genuine disconnect/gap not silently ignored | [x] Future WSS worker switches to emergency source HOLD and request-stop after a source-gap status, even when a public retrospective REST recovery task is also queued |
| CS00-REC-08 | Censored outcome not counted as a win or training row | [x] Prior G5/G7 journaled `UNRECOVERABLE_EXCLUDED`, denied scored result and retained denominator tests remain passing |
| CS00-REC-09 | Manual local backup update | [x] The existing `~/nbot-backup` file on Observation VPS was replaced with the newly tested improved version; current SHA256 `e2578e326754415af0b5f4a9fa7aa50d81fb8c24cd3c87b7b6f57674fd11eb4e`, mode 0700, no background job |
| CS00-REC-10 | Owner-private final directory layout | [x] `~/nbot-v5.1-state/{observations,exploration,research,learning,models,journals,evidence}` and `~/NBOT_Backups` all exist and are private mode 0700; no live files placed in them |
| CS00-REC-11 | Honest empty backup state | [x] The installed upgraded owner one-liner `~/nbot-backup` returned `NO_V5_1_RECORDS_YET__NO_FALSE_BACKUP_CREATED`, code 3, no archive created, because no genuine Observation service has run |
| CS00-REC-12 | Full independent G0–G11 and CS-00 regressions | **[x] 563/563 PASS on Observation-VPS and 563/563 PASS on Execution-VPS**, Python 3.12.3, same tested SHA |
| CS00-REC-13 | Synthetic 100 broad / 200 directions / 20 deep resource/read-only rehearsal | [x] Both offline benchmarks PASS: Observation boundary 100.905ms, p99 44.371ms, RSS 32,040KiB, harness bytes 101,190; Execution boundary 98.056ms, p99 68.215ms, RSS 32,356KiB, harness bytes 101,190 |
| CS00-REC-14 | Temporary checkout and stopped-service assurance | [x] Both final test checkouts removed; post-test `systemctl list-units --all nbot*` and `ps -eo comm=` showed no NBOT-named service/process on either host. No WSS connection or exchange order produced by this task |

**Measured operational host state at final read-only check:** Observation root partition 96G capacity, 91G available (6% used); Execution 45G capacity, 40G available (11% used). This is a point-in-time prestart sample, not a long-run production stress claim.

### Source acceptance and authority limitations

All full-suite frames and G2/G3/G4 source receipts above were generated in **offline synthetic fixtures**. Actual public Binance feed WSS, real REST rate limits, real 20/20 TRADE/QUOTE/MARK continuity, 47 prior trade-ID anomalies, historical ZIP availability, latency under volatile traffic, live cost/spread/funding first touch, 24-hour+ endurance and a genuine off-host original-source restore **remain unverified**. Binance history can retrospectively reconstruct eligible traded-price chronology, **not original decision-time observation or historical executable bid/ask**.

The public REST recovery scheduler still requires future **post-restart actual gap/cursor reconciliation with genuine exchange data**; the old in-memory queue is not itself a restart-proof archive of every source cursor. In particular, a source WSS restart is still HOLD until separately reviewed. No G4–G10 scientific or original-source parent changed from HOLD as a consequence of these tests.

### Remaining CS-00 obligations that cannot be completed under the no-start instruction

- [ ] **Owner desktop WinSCP copy/hash restore:** user will execute `~/nbot-backup` after genuine records exist and manually transfer both `.tar.gz` and `.sha256` from `/home/ubuntu/NBOT_Backups/` to their 1 TB Windows drive. No user-PC transfer is fabricated by this test.
- [ ] **Owner manual frequency/retention and original source custody proof:** the owner selected storage *destination and mechanism*, but final retention/capacity for genuine sustained data, cross-file write behavior during genuine forward Research, and small source/quote/mark economic witnesses require real source evidence. Do not delete the last verified copy.
- [ ] **CS-00 D3/D4 actual operating/rollback signoff and future service installation:** disabled/uninstalled code cannot demonstrate deployed watchdog, operator contacts or emergency stop of a running original collector. Do not install/start a permanent NBOT service without the separately reviewed deployment and source-only permission.
- [ ] **CS-00 E2 parent operational GO:** full operational authority remains **HOLD**. A G11+CS00 synthetic acceptance is not the G4 first real-source acceptance, nor CS-01 owner authorization.
- [ ] **CS-01 and G4–G10 genuine source/science/PAPER:** owner has not authorized source collection, PAPER or testnet. G12 real trading remains locked.

**Next safe gate:** Review this entire pack, decide the owner's manual backup frequency, retention and optional hash-verification/restore drill, and obtain a **new explicit CS-01 owner authorization** before any public-only Binance Observation canary. Otherwise keep all services OFF.

## Reproduction

On each VPS, using a temporary `nbot-v5.1` shallow checkout pinned to the exact code SHA, the following passed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1*.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 -B benchmarks/cs00_offline_readiness_benchmark.py
```

Additional 10-case source checkpoint/backup tests include successful complete owner backup with G2/G3, altered/missing G2/G3, incomplete G4 segment, changed segment byte, hard lock contention and safe retry, source-epoch restart veto and full 20-symbol source receipt coverage. Actual owner one-liner updated and locally tested on Observation VPS. No persistent collector installed or started. No synthetic file left in the user's backup folder.

**Authoritative release rule:** [ ] CS-00 full parent HOLD; [x] newly delivered offline software subchecks checked; [ ] CS-01 start NOT authorized; [ ] G4–G10 genuine parent acceptance; [ ] G12 REAL locked. All new work confined to `nbot-v5.1`; product Vision V1.9 unchanged.
