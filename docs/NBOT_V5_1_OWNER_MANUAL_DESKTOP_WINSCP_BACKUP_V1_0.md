# NBOT V5.1 — Owner Manual Desktop Backup Using WinSCP

**Owner decision (15 October 2026):** Keep a second copy of NBOT's valuable records on the owner's existing **1 TB Windows desktop hard disk**, transferred manually through WinSCP. No cloud purchase or automatic service.

## Every backup: one PuTTY command and one WinSCP transfer

1. Log into the existing **Observation-VPS** PuTTY session as ubuntu.
2. Run exactly: `~/nbot-backup`
3. If the output says `BACKUP_CREATED_AND_LOCALLY_VERIFIED`, look in `/home/ubuntu/NBOT_Backups/` on that VPS. Two new files have appeared: one dated `NBOT_V5.1_records_...tar.gz` and a corresponding `...tar.gz.sha256`.
4. Open WinSCP and connect to the same Observation VPS. In its **remote** pane browse to `/home/ubuntu/NBOT_Backups/`; in the **local** pane open a folder on your 1 TB desktop drive. Drag **both matching files** to the local folder.
5. The sha256 text file holds the expected digest for the tar.gz archive. On Windows you can use PowerShell `Get-FileHash -Algorithm SHA256 'C:\path\to\downloaded.tar.gz'` and compare its Hash to the first value of the downloaded sha256 file. Do not delete the only VPS copy until the desktop copy has been checked.
6. To back up again later, run the **same** PuTTY command. Every new backup has a unique name. No existing backup is overwritten or automatically deleted.

**If the result is `NO_V5_1_RECORDS_YET__NO_FALSE_BACKUP_CREATED`, that is correct today:** we have not started live Observation and there are no permanent genuine Research/Observation files in the newly prepared state directory. The command refuses to create an empty misleading archive. All other `BACKUP HOLD` messages need engineering review; they must not be treated as a successful backup.

## Exact scope and guardrails

- Installed single-file executable: `/home/ubuntu/nbot-backup` (mode 0700), Observation VPS only.
- Source directory: `/home/ubuntu/nbot-v5.1-state/` (mode 0700). Future NBOT writers MUST store their genuine Observation, Exploration, Research, Learning, model, journal and selectively necessary source evidence records here, under approved named categories or files.
- VPS output directory: `/home/ubuntu/NBOT_Backups/` (mode 0700). The command creates an internally verified gzip TAR with SHA manifest and a downloadable SHA256 sidecar.
- Source files are allowlisted. Suspicious secret names, symlinks, unsafe permissions, inconsistent files, unrecognized formats and exceeding a bounded storage budget cause a **HOLD** rather than silently omit records. SQLite is snapshotted with its native online backup API and integrity check, including committed WAL state.
- No automatic copying, retention deletion, email, paid storage, network fetching, code-server start, live-market data feed, trading account, PAPER or real orders.
- **Important consistency boundary:** different independent files have *per-file* change checks, not yet a globally atomic snapshot while a future bot actively writes. The future Observation runtime must bind all genuine state writers to this root and coordinate a verified checkpoint/consistent live backup before this becomes a fully reliable operational process.
- **Important second-host boundary:** this copies only the Observation VPS. If real PAPER activity is ever separately approved for Execution VPS, its records will require a separate backup arrangement.
- Manual frequency and retention remain the owner's choice; the VPS cannot keep unlimited dated archives indefinitely. Do not erase the only proven valid backup.

## Proof and statuses

- [x] The installed script's SHA256 matched the GitHub source: `df8dbac184dc64b01cb5a2dcd4f44972eaf0169fd2908e99130f3e0040e97e11`, code commit `85a4b4a9186cbdb2f81c57bc3df06c9b70e754f9`.
- [x] Fourteen new synthetic safety tests PASS on Observation VPS.
- [x] The installed command refused to produce a backup when no V5.1 records existed (expected exit 3).
- [x] The installed command subsequently created a dated 579-byte synthetic test archive + SHA sidecar. A real `sha256sum -c` returned **OK**; TAR contents contained only the synthetic test record and MANIFEST.json.
- [x] These specifically named **synthetic** fixtures and archive files were removed afterward, leaving the owner's backup folder clean. The executable and two 0700 folders remain.
- [ ] A genuine completed NBOT record backup has not been created: NBOT remains STOPPED.
- [ ] The owner has not yet used WinSCP to copy and verify a genuine backup on the 1 TB desktop.
- [ ] Permanent V5.1 source writers, global consistent checkpoints and source-related economic receipts have not been tied to the new root under actual live operation.
- [ ] Full CS-00 operational readiness and owner permission for CS-01 genuine Observation startup remain unchecked. G4–G10 genuine-source/science/PAPER gates HOLD; G12 real LOCKED.

Versioned code: [manual backup tool](../scripts/nbot_v5_1_owner_backup.py), [14 safety tests](../tests/test_v5_1_cs00_manual_owner_backup.py), [CS-00 master plan](NBOT_V5_1_CONTROLLED_STARTUP_AND_LIVE_EVIDENCE_MASTER_PLAN_V1_0.md).