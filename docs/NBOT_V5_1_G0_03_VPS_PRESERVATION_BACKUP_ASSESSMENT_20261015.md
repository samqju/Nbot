# NBOT V5.1 — G0-03 VPS Preservation and Backup Assessment

**Date:** 15 October 2026 IST; live server UTC near 04:57 (10:27 IST).  
**Current status following owner decision, 15 Oct 2026:** **G0-03 COMPLETE — LEGACY BACKUPS EXPLICITLY WAIVED (NOT MADE); legacy cleanup permitted in principle but NOT EXECUTED in this task.** Sections 1–7 below are the true, original read-only findings and pre-waiver recommendations. The later owner directive in §8 **supersedes only** their requirement to back up old NBOT artifacts before abandoning them.  
**Method:** Read-only SSH over owner's two already-saved PuTTY sessions, Execution-VPS and Observation-VPS, as ubuntu. No keys/secret contents examined. No VPS writes, service starts/stops, package install, NBOT software tests, private exchange access, order or deletion. GitHub documentation commits only.

## 1. Plain-language result

Both machines are reachable and have considerable free disk but **approximately 1 GiB physical RAM each**. Old code and historical state still exist on both, at engineering/v5-g1-g7-final-closeout-20261015 (exact Git commit 47dd5fa34fae2f222ad23ce521c0c5034c1cadc8). The old observation service is disabled/stopped. Observation-VPS contains a readable old SQLite database **with both its WAL and SHM companions**; Execution-VPS contains historic paper/trading-mode directories and 253 individual paper observation receipts.

**No verified, restorable independent NBOT backup was found.** Both examined NBOT backup directories are empty. Ubuntu's /var/backups had OS package/apt/dpkg backups, not a verified NBOT snapshot. Cloud/provider-level snapshots and other off-host copies **remain UNKNOWN, not proven absent**. The database passes a read-only quick_check, but **that is NOT backup or restore verification**.

**Preservation ruling:** Do not erase, reset, re-checkout, migrate, checkpoint by deleting WAL, vacuum, or repurpose either old NBOT directory. Do not restart historic services. Do not treat older paper evidence as authenticated after-cost market evidence. Document and verify recovery first, then consider a separately scoped cleanup only after approval.

## 2. Live VPS identity and resource inventory

| Evidence | Execution-VPS | Observation-VPS |
| --- | --- | --- |
| Saved PuTTY SSH profile / host label | Execution-VPS / nbot-execution | Observation-VPS / base |
| Login account | ubuntu | ubuntu |
| Live UTC time observed | 2026-10-15 04:56:55 | 2026-10-15 04:57:00 |
| Uptime observed | 1 week 2 days 11h 40m | 1 day 12h 10m |
| Root partition | /dev/sda1 ext4 | /dev/sda1 ext4 |
| Root filesystem capacity | 45 GiB | 96 GiB |
| Root space in use | 4.8 GiB / 11% | 6.7 GiB / 7% |
| Available space | 40 GiB | 90 GiB |
| Physical RAM | 952 MiB | 952 MiB |
| Available RAM initial / final | 695 / 714 MiB | 704 / 719 MiB |
| Total swap | 1,023 MiB | 2,047 MiB |
| Additional dedicated NBOT mounted data volume | None identified in visible mounts | None identified in visible mounts |
| Old Git branch | engineering/v5-g1-g7-final-closeout-20261015 | Same |
| Old Git HEAD | 47dd5fa34fae2f222ad23ce521c0c5034c1cadc8 | Same |
| Old code checkout path | /home/ubuntu/Nbot | /home/ubuntu/Nbot |
| Checkout size | 48 MiB | 274 MiB |
| Tracked worktree modified files (read-only -uno status) | No tracked changes reported | No tracked changes reported |

**Limits:** This is an idle-time capacity snapshot, not a load benchmark. Git status deliberately excluded ignored/untracked data, which MUST be backed up separately. Cloud snapshot inventory, other-user scheduled tasks, all potential supervisors and Binance private account/order state were not verified. Disk estimates and service status cannot qualify 100-light/20-deep/rolling-40 performance.

## 3. Operational and service status

| Item | Execution-VPS | Observation-VPS |
| --- | --- | --- |
| Historical nbot-v5-g1g2g3-observation.service | No such systemd unit found | Unit installed |
| LoadState | not-found | loaded |
| UnitFileState | not-found | disabled |
| ActiveState | inactive | inactive |
| SubState | dead | dead |
| Unit file | Not found | /etc/systemd/system/nbot-v5-g1g2g3-observation.service |
| User crontab probe | No crontab confirmed, or not readable | Same |

Service registration/active-state checks were read-only and name-scoped; they do not prove every possible NBOT process is absent or that any exchange account has zero pending orders. No commands were issued to start/restart/stop anything. No private accounts or keys were inspected.

## 4. Critical old state and evidence inventory — preserve intact

| Host | Verified path / evidence | Inventory | Why it must be protected |
| --- | --- | --- | --- |
| Both | /home/ubuntu/Nbot, .git, config, docs, tests, scripts, logs | Existing legacy checkout on both machines | Keep original historical branch and any ignored/untracked files untouched; no force checkout or git clean. Separate new V5.1 namespace later. |
| Execution | /home/ubuntu/Nbot/runtime/execution | 336 files; ~1.5 MiB | Includes old paper/testnet/real execution state and receipts. |
| Execution | /home/ubuntu/Nbot/runtime/execution/paper/observation_receipts | **253 JSON receipts** | Preserve original bytes/identity; older paper data is not automatically real independent economic evidence. |
| Execution | /home/ubuntu/Nbot/data/execution/paper | 3 files; paper account JSON 71,354 bytes; execution state JSON 6,130 bytes | Don't reset balances or statuses; files' contents were deliberately not inspected. |
| Execution | /home/ubuntu/Nbot/data/execution/{paper,real,testnet}, runtime/execution/{paper,real,testnet}, logs/execution | Present in old tree | Treat real-mode directory presence as data only, NOT proof of open position or of authorization to trade. |
| Observation | /home/ubuntu/Nbot/runtime/observation/g1g2g3.sqlite | **3,907,584 bytes**, SQLite read-only quick_check **ok** | Coherent backup requires SQLite's supported backup procedure; mere raw base-file copy can lose WAL changes. |
| Observation | /home/ubuntu/Nbot/runtime/observation/g1g2g3.sqlite-wal | **4,124,152 bytes** | WAL is potentially uncheckpointed transactions; do not delete/copy in isolation or vacuum. |
| Observation | /home/ubuntu/Nbot/runtime/observation/g1g2g3.sqlite-shm | Present, 32,768 bytes at audit | Companion SQLite coordination file; keep original database files in place during assessment. |
| Observation | Database table metadata | 15 tables, including candle_rows, evidence_events, g1f_candidate_events, g1f_event_manifest, g1f_universe_snapshots, g2_cohort_witness, g2_quote_witness, g3_event_context, v5_directional_evidence, v5_finality_checks, v5_source_epochs | Only table *names* were inspected, not raw market rows. A readable file does not prove genuine after-cost evidence. |
| Observation | /home/ubuntu/Nbot/data/observation/live/model_artifacts/v39 | 2 V3.9-era model-artifact JSON files | Forensic reference only; not an approved V5.1 runtime model. |
| Observation | /home/ubuntu/Nbot/runtime/observation/live | Old status and lock files | Preserve status/source chronology; old locks don't confer current authorization. |
| Both | /home/ubuntu/nbot-final-reset-20261014 | Empty directory (~4 KiB) | Directory name is not a verified backup. |
| Both | Sensitive config, SSH keys, systemd environment, private credentials | Not read | Preserve in secure separately authorized encrypted backup, never expose contents or commit to GitHub. |

### Read-only preservation fingerprints

| File | SHA-256 at audit time |
| --- | --- |
| Observation g1g2g3.sqlite | f5fca3d738df5320ad537e2a96069642ffbe688809266e2e1a81ee05bb754e4c |
| Observation g1g2g3.sqlite-wal | 002b9d8e4b0fdd86a285e209d4d12e74e84cec680774733854c67e912dcd635e |
| Observation systemd unit file | 5c8582b33d3acebbdbac4c83bf6e95767d93388fd8fd5c4d502b7aba40257ca4 |
| Execution paper account.json | 299a53da1ccf6973862a18d19c9557d0c942a8cc42e3610464d335f7cc1c87e9 |
| Execution paper execution_state.json | 3be536dd7d45de3bc5958db3e8bef98688e163fb352654d991f3dd8f00bc2a1a |

These hashes prove an identity for the inspected bytes **at a moment**. They are not a backup, signature of qualified original market data, or verification of retained copies. No DB/paper files were uploaded to GitHub.

## 5. Backups: what was and was NOT verified

- [x] Inspected visible old application data/runtime/backup directories, common named archive/backup/snapshot paths and standard /var/backups OS area (non-exhaustive name-scoped path survey).
- [x] Observation live backups path /home/ubuntu/Nbot/data/observation/live/backups exists but **contains 0 files**.
- [x] Observation testnet backups path /home/ubuntu/Nbot/data/observation/testnet/backups exists but **contains 0 files**.
- [x] /var/backups inspected files were regular OS package metadata backups, **not** a demonstrated NBOT source/data rollback archive.
- [x] Read-only SQLite connect (mode=ro, PRAGMA query_only=ON) returned quick_check=ok on Observation's original database/WAL; **not a copy/restore test**.
- [ ] Provider/OCI cloud boot-volume/instance snapshot policy, latest successful copy, scope/retention and off-host recovery access: **UNKNOWN**.
- [ ] A coherent, hash-verified, encrypted **off-host** preserved NBOT evidence + config backup for each VPS: **NOT DEMONSTRATED**.
- [ ] Trial **restore** to an isolated scratch path with row/receipt counts, hash manifest and SQLite integrity pass: **NOT DEMONSTRATED**.
- [ ] Signed safe cleanup/rollback GO: **NOT DEMONSTRATED**.

**Important:** A script with backup in its filename, a folder named backup, Git repository history or free disk space cannot substitute for actual recoverable source data. Don't confuse old synthetic tests with qualified market evidence.

## 6. Ordered preservation, restore and cleanup plan

**P1: Freeze the historical baseline.** Preserve existing /home/ubuntu/Nbot, .git, runtime, data, logs, V3.9 model artifacts, all 253 paper receipts, full observation SQLite+WAL+SHM and disabled unit configuration. Do not reset branch or turn on old apps. Avoid copying secrets to public docs.

**P2: Confirm complete scope.** Check any other app users/supervisors, broader historic evidence paths and provider-managed snapshots under least privilege. Current survey was not an exhaustive privileged scan; name-scoped service checks and an idle process snapshot don't prove an account flat.

**P3: Establish coherent backups.** Using an isolated new backup destination and secure access permissions, capture a SQLite-native consistent backup of observation database (which includes committed WAL state). Preserve other runtime/data/service/source artifacts with ownership and hashes; securely encrypt any sensitive configs/keys under an approved secret-management process. Do not move, delete, checkpoint, vacuum or mutate originals while capturing copies.

**P4: Off-host independent retention.** At least one encrypted independently held and access-controlled recovery copy outside each VPS failure domain, plus provider boot-volume snapshot if available. Record date, immutable backup ID, manifest SHA-256, scope, restore procedure, retention, storage domain and responsible owner. Do not put key material or raw financial/account data in GitHub.

**P5: Prove restoration.** Restore copies only into a fresh isolated scratch directory; show receipt/hash consistency, paper state copy integrity and SQLite integrity_check/row inventory, including committed WAL-era records. Demonstrate that history can be recovered without touching original data or running an old trader.

**P6: Authorize cleanup later.** Produce a written exact path-by-path deletion plan, evidence of successful backup and restore, precise rollback instructions, and owner approval. No global rm, cleanup sweep, git clean/force reset, old service restart or unreviewed migration. Install V5.1 later in its own namespace, storage and service units and test in offline/no-order mode. A valid backup alone does not grant paper or real trading permission.

## 7. G0-03 evidence-backed task status

- [x] **G0-03-A:** Both saved SSH profiles reach the correct host, ubuntu login and UTC audit time verified; no laptop/private key contents read.
- [x] **G0-03-B:** Recorded disk/RAM/swap/root mounts, exact old Git branch/commit and material filesystem directories on both.
- [x] **G0-03-C:** Examined named systemd unit status plus paper/source evidence counts and file metadata without changing mode.
- [x] **G0-03-D:** Located observation DB/WAL/SHM, read-only quick_check PASS, 15-table inventory, and recorded selected file SHA-256 identities.
- [x] **G0-03-E:** Audited accessible local backup paths and documented an explicit data preservation / backup / isolated restore / rollback plan with HOLD gaps.
- [ ] **G0-03-R1 — ACTUAL RESTORABLE BACKUPS:** Coherent source capture, protected independent off-host copies and isolated successful restore must be produced and verified. **HOLD.**
- [ ] **G0-03-R2 — CLEANUP GO:** No deletion/reformat/checkout reset until R1 passes, an exact path list and rollback plan are reviewed, and the owner approves. **HOLD.**
- [ ] **G0-04:** Review new G1-01 application code scope and isolated destination; not done by G0-03.

**Disposition:** The **G0-03 assessment** is PASS, verified live and read-only. **Safe-to-clean, backup/restoration readiness and overall G0 milestone remain UNCHECKED.** No services or state were modified. Subsequent GitHub roadmap ticks must use this assessment commit and explicitly retain the R1/R2 holds.


## 8. Owner-directed legacy backup waiver and closure — 15 October 2026

**Explicit instruction received from the owner after the initial assessment:** "Complete G0-03 without any backup, we are already starting fresh so we don't need anything on VPS which belongs to old version."

**Decision:** The owner deliberately elects to **discard all previous-version NBOT VPS-only data/code/evidence if cleanup is eventually performed**, without preparing or testing legacy backups first. In particular, the 253 old paper receipts, historical V3.9 models, legacy account/state JSON, old observation SQLite database (including WAL/SHM), source/runtime/log contents and past VPS-only provenance may be irrecoverable after deletion or host failure. GitHub legacy branches are a distinct reference source, not a replacement for VPS-only market/database evidence. The owner accepts this risk as a fresh-start choice.

**What was NOT done:** No backup was created or tested; no provider-level copy was verified; no previously found backup was claimed. No file, directory, database, service or remote operating-system setting has been deleted or changed as part of closing G0-03. The old data remains in place at the last verified read-only audit. No credentials, real exchange balances/open orders, or other people's data were examined.

**Effect on G0-03 closure:** Original R1 (mandatory backups before any old-NBOT abandonment) is now **N/A — waived by the owner**, not PASSED by doing a backup. Original R2 (approval to discard older NBOT assets) is **approved in principle by the owner**, not a claim that old assets have been deleted. The old R1/R2 HOLD statements in §§1–7 describe the prior recommendation at the time of the read-only assessment and no longer block the G0-03 milestone. The *execution* of any cleanup, if useful for G1 deployment, must be a separate explicitly logged step with exact target paths, before/after checks and a clear statement that restoration will be impossible without copies.

**Scoped cleanup guardrails, even with waiver:** Limit any eventual cleanup to positively identified **legacy NBOT application-specific** code, units and data on the named two VPSs. Do not delete Ubuntu/system files, shared libraries, authorized users, SSH keys/PuTTY authentication, unrelated data, network configuration, or GitHub old branches. Confirm no old NBOT process or pending system action can interfere, and avoid accidental removal of the current or future V5.1 work. No exchange-order or paper/live operating permission is inferred from this consent.

**Important non-waiver:** This one-time waiver covers *historical installations only*. It does **not** waive V5.1's requirement for authenticated original market/source custody, crash-safe new V5.1 source data, scientific evidence lineage, finite-storage controls, qualified economic outcomes, or separately reviewed future paper/real release safety. V5.1 must start in a new clean namespace and cannot claim qualified results from abandoned old VPS source.

### Owner-override completion check

- [x] **G0-03-W1:** Explicit legacy backup waiver and accepted risk documented with date; no false backup-PASS.
- [x] **G0-03-W2:** Owner decision to allow abandonment of previous NBOT VPS contents recorded; R1/R2 old HOLD removed as blockers *for G0 only*.
- [x] **G0-03-W3:** Assessment evidence retained (host resources, app paths, SQLite metadata, old code branch, old service state) and non-legacy safety/authorization boundaries retained.
- [ ] **G0-03-CLEANUP-EXEC:** Actual old app data/service removal or VPS reset. NOT PERFORMED, and not a prerequisite to declaring the G0-03 assessment/waiver complete.
- [ ] **G0-04:** First narrow new application-code scope review; separate milestone.

**Final G0-03 disposition:** **COMPLETE**, closed by live inventory plus the owner's explicit decision that **no legacy backup shall be made**. **Backup outcome: NOT DONE / WAIVED**, not verified. **VPS cleanup outcome: NOT DONE**. Remaining G0-04 and new-code gates continue separately.


## 9. Verified owner-executed cleanup after waiver (15 Oct 2026)

**New later evidence, superseding the forward-looking cleanup status in §§1–8:** The owner manually executed guarded old-NBOT-only cleanup commands in both PuTTY sessions, supplied successful PuTTY outputs, and the assistant independently reconnected to **both** VPSs using read-only SSH checks on 15 Oct 2026 at **05:30:38Z (Execution)** and **05:30:43Z (Observation)**. Complete audit and path-by-path after-state: [G0 Cleanup Completion](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_CLEANUP_COMPLETION_20261015.md), GitHub commit **81dadf68a9949b847fd8f38336c5d532eab861cd**.

- [x] **G0-03-CLEANUP-EXEC (later result):** Both `/home/ubuntu/Nbot` installations absent, both empty old `nbot-final-reset-20261014` markers absent; retired Observation-VPS `nbot-v5-g1g2g3-observation.service` file absent; no name-matched NBOT unit/process; remote verifications exit 0. Scope of PASS is the specifically checked old application paths/services, **not exhaustive all-system erasure**.
- [x] Owner-directed NO-BACKUP waiver retained correctly: **NO backup/restore was created or verified**, and legacy VPS-only research/paper state may be permanently lost. The old GitHub historical source branches are not deleted.
- [x] Existing VPS SSH still works; no V5.1 software installed, no new unit started and no trading authorization changed.
- [x] **G0-03 completed and cleanup formally verified**; earlier HOLD statements represent historical chronology only. G0-04 first-code scope is separately accepted; new G1 implementation remains open.

**New final status:** G0-03 and its owner-requested cleanup are **PASS**. Remaining work follows the clean V5.1 roadmap; the legacy backup waiver applies only to **OLD** VPS installations.
