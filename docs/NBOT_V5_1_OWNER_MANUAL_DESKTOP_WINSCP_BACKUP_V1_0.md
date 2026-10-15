# NBOT V5.1 — Owner Manual Desktop Backup Using WinSCP

> **LATEST LIVE UPDATE (15 Oct 2026):** This guide's older "NO_V5_1_RECORDS_YET" wording describes **before** the public-only CS-01 canary. Genuine (though **NOT G4 scientifically qualified**) Observation/G3/source records NOW exist on Observation VPS. `~/nbot-backup` already created one **8-file, 103,117-byte** locally hash-verified archive and sidecar in `/home/ubuntu/NBOT_Backups/`. **[ ] Owner WinSCP desktop transfer remains outstanding.** See [current startup handoff](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md).


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

## FINAL CS-00 OFFLINE 563x2 RECORD CHECKPOINT AND MANUAL BACKUP ACCEPTANCE — 15 OCT 2026

**[x] OFFLINE CODE AND RECORD SAFETY ACCEPTANCE ONLY, [ ] CS-00 FULL OPERATIONAL GO, [ ] CS-01 START PERMISSION.** Read [final 563-on-each-VPS original test and prestart evidence](NBOT_V5_1_CS00_563_TWO_VPS_FINAL_OFFLINE_RECORDS_BACKUP_AND_PRESTART_HOLDS_20261015.md) before older 430/464/491/539/553 sections.

**Exact same independently tested executable code:** `a41b65ebb7795bb3e4312e9817e1567f1c1faf5d`; **563/563 PASS Observation VPS AND 563/563 PASS Execution VPS**, both synthetic source/resource benchmarks PASS; no actual Binance public WSS collected, no real original source or PAPER orders. Both isolated test checkouts removed. No NBOT services installed or running on either host.

**Verified subtasks now CHECKED:**
- [x] **B4-OFFLINE G2/G3 state integration:** source-only future public Observation code now durably persists original-shaped 100-observation snapshots, 200 G3 directional detector/label rows, immutable cohort manifest and final event checkpoint to `~/nbot-v5.1-state/{observations,exploration,journals}`; G4 compressed receipts to `evidence`. No original exchange/scientific release.
- [x] **C4 source-writer/owner-backup consistency:** cross-process shared private POSIX lock; backups refuse concurrent/partial 3-file checkpoints, tampered G2/G3, interrupted G4 gzip/meta pair, altered hash chain, and unsafe files. Standalone owner backup file installed on Observation VPS, new SHA256 `e2578e326754415af0b5f4a9fa7aa50d81fb8c24cd3c87b7b6f57674fd11eb4e` (0700).
- [x] **C4 owner destination/layout:** owner-selected existing **1 TB Windows desktop** manual WinSCP; Observation VPS seven private source-category folders (0700), backup destination (0700), with zero genuine records until owner-approved startup. Installed `~/nbot-backup` correctly refused empty source with `NO_V5_1_RECORDS_YET`; no fake archive.
- [x] **D3 OFFLINE gap/restart veto:** source-only collector now requests emergency HOLD/stop on WSS source gap; persisted source segment replay forbids seamless epoch reuse after restart. No auto-trading/API keys enabled.
- [x] **E1/R8 full offline independent 563-test/benchmark two-host acceptance and source cleanliness audit**.
- [x] **C5 previous synthetic cross-VPS compact source+SQLite ledger restore**, preserved as *synthetic only*; owner manual WinSCP real-data transfer still unchecked.

**Genuine unfinished steps REMAIN UNCHECKED, not skipped:** [ ] C4/C5 independent actual owner desktop WinSCP copy/restore and verified genuine retention/capacity; [ ] B4 genuine volatile original public WSS 20/20 TRADE/QUOTE/MARK and G4 old 47 ID semantics (requires future separately authorized source-only CS-01); [ ] actual G4 source evidence quota/endurance, exact quote/mark/funding price/cost, post-restart historical replay with real exchange; [ ] D3/D4 actual deployed source watchdog, responsible operator/alerts/rollback signoff (not installed); [ ] E2 full prestart operator commissioning acceptance; [ ] full CS-00 parent GO; [ ] CS-01 separate owner source start authority; [ ] G4–G10 original scientific/PAPER parents; [ ] G12 real money. **Do not equate offline engineering complete with startup approved.**

**Next owner-facing command** (once authentic data is produced after future CS-01 approval): `~/nbot-backup` on PuTTY Observation VPS, then copy both dated archive and SHA256 from `/home/ubuntu/NBOT_Backups/` into the owner's 1 TB Windows desktop via WinSCP. User currently does not need to run this while genuine records are absent. No cloud spend or background backup daemon.

## Current first-real-records manual backup (15 Oct 2026)

**[x] Owner's backup tool works on real public-source-derived NBOT records and locally verifies the archive:**
`/home/ubuntu/NBOT_Backups/NBOT_V5.1_records_20261015T152427Z_12d35662.tar.gz` (103,117 bytes, 8 files).

**Expected SHA256:** `af306b0decb2dd8753d8049b943f214085d33950ae65118fbf02b580042a5250`. The corresponding `.tar.gz.sha256` companion exists. On-VPS check `sha256sum -c` passed.

**[ ] Owner's next action:** download BOTH matching files with WinSCP to a chosen directory on the 1 TB Windows desktop and verify the local archive hash. This is not claimed to have happened. Do NOT delete the only valid VPS copy or the original unqualified source receipts. Future new backups still use `~/nbot-backup`. Scientific G4 and permanent Observation remain HOLD; see [latest handoff](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md).
