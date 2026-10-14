# NBOT V5 — Independent continuation audit and no-loss consolidation plan

**Recorded:** 2026-10-14 ~13:10 IST; **authority:** original G0–G10 roadmap, v2.8.7 §§10,17–25,45–50 at start of audit. This file is a durable continuation checkpoint, not acceptance of integrated G1 or G4 and not a migration authorization. **All checks performed remotely through Sameer-Laptop -> saved PuTTY Observation-VPS -> `ubuntu@base`; GitHub repository `samqju/Nbot`.**

## 1. Fresh independent production findings (not copied counts)

At UTC 2026-10-14 07:32:18 on actual host `base`:

- Active/enabled `nbot-v5-g1g2g3-observation.service`, MainPID `11327`, `ActiveEnterTimestamp=Wed 2026-10-14 06:46:04 UTC`, `ExecMainStartTimestamp` same, `NRestarts=0`, `Result=success`, `MemoryCurrent=71,102,464` bytes versus 209,715,200-byte limit.
- Approved live code checkout `/home/ubuntu/nbot_v5_integrated_20261014`: Git HEAD `1e7c090d05dc118b290c764d58c2944f56ad4b3b`, **detached** release worktree, clean `git status --porcelain`; production pinned `approved_code_sha.txt` exactly agrees.
- `nbot-v5-integrated-health.timer` active/waiting. Direct read-only `python -m nbot.v5.g3_prod_health` returned `status=PASS`, `violations=[]`, 9 accepted five-minute event manifests, 900 candidate coin-side records, 450 original G2 coin-event source-witness rows, 9 G3 context rows, 50 frozen coins, 0 explicit holds, 0 reported restarts, 0 training labels, `research_ready=false`, `order_authority=NONE`, `recommendation_authority=NONE`. The old 6/600/300/6 snapshot was a correct **earlier** snapshot; latest value is not claimed to be future-proof.
- Read-only SQLite `sqlite3 -readonly ... 'PRAGMA quick_check;'` returned **ok**. Active DB `/home/ubuntu/nbot_v5_integrated_data/g1g2g3.sqlite` had ~6.35MB base file and ~4.13MB WAL at inventory time; an SQLite WAL is LIVE state and must not be removed/copied as an inconsistent lone file. Original frozen G1f backup `g1f_pre_integrated_20261014.sqlite`: SHA256 **c3a3d8f6aac1ff254f8ee3daaff3ce06e72f299cfac01c5ec305cca87ba0d03d** matches prior evidence.
- Collector journal around 07:31 UTC shows both WSS public source connections true, no reported reconnect attempts, trade gaps or restart-missing events. This is a *point-in-time* verification, not proof for the remaining future 24h.
- VPS root filesystem 96GB total, 6.5GB used, 90GB available (7% used). No capacity emergency or reason to delete evidence. No commands restarted, stopped or mutated systemd, source worktrees or DB.

## 2. Exact GitHub ancestry and divergence (API verified 2026-10-14)

| GitHub ref | GitHub SHA | Verified relevant comparison |
|---|---|---|
| `main` | `d497e961e2891c43669d64f2a16d210011d703a4` | `main...integrated`: **diverged**, 186 commits ahead / 45 behind, merge base `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf` |
| `v5-clean-restart-20261013` | `a4fe50bfe0a6e4099b1dda930dac87a4e6bef5f1` *prior to this new audit publication* | Versus integrated: governance advanced 8 commits, integrated advanced 58; merge base `cb68ee247cbbb8577238e7d452ac5e79ebc4d089`. Its newer roadmap/handoff does **not** exist as the same commit in integrated release |
| `feature/v5-observation-g2-20261014` | `af6d5a458eeca047c43d0360ce6a8fd3f76ec799` | G2 vs governance **diverged** 34 ahead / 8 behind; common `cb68ee...` |
| `feature/v5-observation-g3-20261014` | `fdca6980d1c778e2da8466b51631b31287740ff4` | **Linear** 12 commits ahead of G2, 0 behind |
| `feature/v5-observation-integrated-20261014` | `1e7c090d05dc118b290c764d58c2944f56ad4b3b` | **Linear** 12 commits ahead of G3, 0 behind; exact live pinned production |
| `feature/v5-execution-foundation-20261014` | `4f7331c12233260b9422f1ff4ff9711d9b992a30` | Independent Execution development, not to be blindly merged |
| `feature/v5-live-evidence-recovery` | `a10a0408286c12ee9efaaba2bd727770f927b979` | Historical prototype only; excluded from clean V5 |

**Important local-vs-GitHub mismatch:** `/home/ubuntu/Nbot` locally sits on `main` at `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`. Its `origin/main` tracking ref had not fetched recent 45 GitHub `main` commits, so local `git status -sb` misleadingly reported `main...origin/main` without a warning. DO NOT interpret it as current remote synchronization. Read-only inventory did not update these refs. Local G1f sandbox has a separate `.git` main repository with G2/G3/integrated as **linked worktrees** pointing to sandbox's Git metadata. Critically: do not delete `nbot_v5_sandbox` merely because its older service is disabled; destroying its `.git` can break the live pinned worktree and preflight! G2/G3 local audit worktree HEADs were respectively `9b890098e1050a84de30d788ff32fbf6866b7b49` and `d818bc173c04c4279a7f6a3dff52faff35209c99`, not identical to present GitHub accepted feature tip; preserve pending refs before cleanup.

## 3. Twelve-directory role inventory, immutable until reviewed

| Observed `/home/ubuntu` path | Size at inspection | Keep / logical role |
|---|---:|---|
| `Nbot` | 262MB | Older local `main`, future canonical source after reconciliation |
| `nbot_v5_integrated_20261014` | 5.7MB | **ACTIVE**, detached, pinned, linked Git worktree; not touched |
| `nbot_v5_integrated_data` | 11MB | **ACTIVE** WAL SQLite + pin; not touched |
| `nbot_v5_sandbox` | 16MB | G1f source **AND Git metadata owner of active live/G2/G3 worktrees** |
| `nbot_v5_data` | 102MB | Original G1f DB + validated old online backup |
| `nbot_v5_g2_audit_dev` | 6.8MB | G2 historical development worktree/proof lineage |
| `nbot_v5_g3_audit_dev` | 5.6MB | G3 development worktree/proof lineage |
| `nbot_v5_g2_proof_20261014` | 4.0MB | Original G2 source-witness proof SQLite and provenance |
| `nbot_v5_venv` | 18MB | Active shared Python runtime, no removal |
| `nbot-backups` | 419MB | retained backup/restoration evidence |
| `nbot_f0_snapshot_staging` | 625MB | F0 frozen historic forensic staging |
| `nbot-release-records` | ~8KB | immutable release audit pointers |

These sizes are point-in-time and not file-level manifest/restore verification. No archive/prune is authorized by this inventory.

## 4. Controlled, non-destructive source and infrastructure consolidation (PLAN ONLY)

**A. Evidence inventory first.** Capture `git worktree list --porcelain` for BOTH Git repositories (old `Nbot` and sandbox), every branch ref/local HEAD/untracked file, `git merge-base`, status, source file digests, unit `ExecStart` and pin, running processes, DB base/WAL, older F0/G1f/G2 proof, backup/retention paths and off-host copies. Independently verify full file manifests and restorability; avoid computing live DB SHA as an unstable durability proxy.

**B. Reconcile Git without contaminating V5.** From fresh GitHub remote `main`, separately review the 45 main-only commits, the G1/G2/G3/integrated train, and the newer roadmap-only governance commits. Prepare ONE PR to canonical `main` only after semantic diff, V4 prototype exclusion, paths/dependency review, accepted tests and rollback agreement. Prefer reviewed integration commits/explicit isolated V5 source import to silent force resets; preserve historical main commits and branch refs. Keep independent Execution branch out of Observation merge. Document any conflict resolution with old V4 source. No production service points at `main` directly.

**C. Reproducible immutable release, later.** Following full integrated G1 operational acceptance and approved cutover: propose `/srv/nbot/releases/<SHA>` with frozen source/correct read-only Git metadata and preflight pin, `/srv/nbot/current` atomically selectable release, `/home/ubuntu/Nbot` as sole mutable canonical source checkout. Source release must NOT depend on deletable sandbox-linked `.git` metadata. Prove clean SHA, correct imports, restricted permissions, independent complete tests and boot-failure rollback before switching systemd. Do not cut over during soak.

**D. Durable SQLite and historical research evidence, later.** Stage online `sqlite3.Connection.backup` of running DB (WAL-aware), independent offline `integrity_check` and event/source/G3 replay against original SHA manifests, carry source/ingestion cursor without lost or duplicate five-minute slots. Only after tested backup & restoration and owner approval migrate one service/data path atomically to private `/var/lib/nbot/observation` (future `research` and `paper` private namespaces as required). Retain original G1f/G2/F0 and date/SHA manifests in controlled `/srv/nbot/archive` with off-VPS restore evidence.

**E. Archive old folders only last.** Confirm no live process, systemd unit, Git worktree Git-common-dir or backup depends on any candidate path. Owner separately approves every irreversible removal. Move small reversible batches and verify fallback before deletion. **Zero directory deletion during this audit.** Target *one source authority + immutable releases + private data + managed archive*, not a single physical code/data directory.

**F. Paper/live distinct ledger policy.** No emptying of observation/G2/G3/F0 history. At a separately authorized paper or real launch, create an independently versioned zero-position **portfolio ledger**, keep market source/evidence immutable and accessible, separate virtual research, paper fills and actual exchange fills. ABSTAIN and 0R no-trade stay valid.

## 5. Safe offline G4 work completed without touching Observation runtime

Temporary branch `feature/v5-g4-offline-contract-20261014` based **exactly** on integrated release SHA `1e7c...`. Adds `docs/NBOT_V5_G4_OFFLINE_CONTRACT_2026-10-14.md`, a deterministic pure `nbot/v5/g4_offline_gate.py` requiring source provenance, causal policy clocks, exact 24-pattern denominator, full maturity and original price-path/quote-cost witnesses, plus `tests/test_v5_g4_offline_gate.py` (21 mock tests). The output is strictly `PENDING/HOLD/REPLAY_READY`, never SCORED. **No labeler, no trade fill, no model, no SQLite write, no production connection, no service or new VPS folder.** The gate labels neither virtual trade profit nor scientific efficacy.

Official GitHub Actions on G4 branch head `363bf7760232a7363cbac915f5ed9e015ad31b87`: **268/268 tests PASS**, https://github.com/samqju/Nbot/actions/runs/38529672257, including accepted 247 plus 21 new synthetic cases. Draft, unmerged, no-deployment review: https://github.com/samqju/Nbot/pull/39. This is *offline engineering acceptance only*, **NOT G4 operational/scientific PASS**.

## 6. Remaining mandatory stop/go checkpoints

**Oct 15, 2026 06:46:04 UTC / 12:16:04 IST earliest:** independent 24h G1 integration check: actual systemd timestamps/journal complete window including non-NRestarts stops, service timer hourly logs and failures, DB integrity, all expected 5m event IDs and frozen cohort, G2 original quote/trade receipts, G3 immutable contexts and replay, source gaps/holds, memory and strict no-order/no-label flags. If any continuity ambiguity, **HOLD/UNVERIFIED**, record incident and evidence. Do not create arbitrary new wait. Scheduled ~12:45 IST independent review remains existing checkpoint; opening laptop/browser itself does not control VPS continuity.

After independently accepted upstream and approved production cutover, complete G4 original price/quote/funding path and label economics, independent censored/unresolved terminal proofs. Then G5 viability and baselines -> proposed 2,000 genuinely matured quality outcomes -> G6 learning/challengers -> G7 guard -> G8 independent Champion/Challenger paper -> G9 sign-off -> G10 continuous evidence, without skipping. Fair 100-trade paired competitions mean genuine Execution VPS paper outcomes, never 100 observed candidates.

**Changes in this checkpoint:** Documentation plus isolated G4 branch/PR and CI only. Live source SHA, GitHub `main`, production service, systemd unit paths, production SQLite, backups, Execution VPS all left unchanged.
