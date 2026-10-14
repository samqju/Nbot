# NBOT V5 — G1–G3 Integrated Observation VPS Rollout and Operational Acceptance
**Recorded:** Wednesday, 14 October 2026 IST  
**Actual server:** Observation VPS `base`  
**Deployment verdict:** **RUNNING, G2 OPERATIONAL SOURCE PASS, G3 OPERATIONAL FEATURE PASS, G1 FULL 24h SOAK IN PROGRESS (NOT YET PASSED).**  
**Trading authority:** NONE. Neither training, paper trading nor Binance private order submission is present or enabled.

## 1. Corrected understanding of old and new services

The legacy V4 Observation units were already inactive and disabled before this change. The already-running older service was **V5 G1f**, not V4. Its source was `/home/ubuntu/nbot_v5_sandbox`, database `/home/ubuntu/nbot_v5_data/g1f_observe.sqlite`, systemd `nbot-v5-observation-only.service`; it had amassed >170 contiguous G1f five-minute records but did not contain original G2 quote/ranking witnesses or persistent G3 contexts.

The integrated new service was deployed **beside it first** without overwriting its code/data, in `/home/ubuntu/nbot_v5_integrated_20261014`, separate original-G2/G3 SQLite `/home/ubuntu/nbot_v5_integrated_data/g1g2g3.sqlite` and distinct `nbot-v5-g1g2g3-observation.service`. Prior worktree `/home/ubuntu/nbot_v5_g3_audit_dev`, temporary G2 proof `/home/ubuntu/nbot_v5_g2_proof_20261014/g2_witnessed.sqlite`, legacy V4 and Execution VPS were untouched.

## 2. Reversible change, frozen version and exact lineage

- Existing active G1f DB safely backed up **ONLINE with sqlite3.Connection.backup** to `/home/ubuntu/nbot_v5_data/g1f_pre_integrated_20261014.sqlite`, 51,490,816 bytes, independent SQLite integrity_check `ok`, SHA256 `c3a3d8f6aac1ff254f8ee3daaff3ce06e72f299cfac01c5ec305cca87ba0d03d`. Old live DB, immutable original 12-hour soak evidence and F: historical archive copies retained.
- Production development branch `feature/v5-observation-integrated-20261014` descended directly from `feature/v5-observation-g3-20261014` at `fdca6980d1c778e2da8466b51631b31287740ff4`. Actual Git on VPS confirmed exact same merge-base and `0 behind, 12 ahead` at release HEAD. **Pin** `1e7c090d05dc118b290c764d58c2944f56ad4b3b` written as nonsecret 0600 file `/home/ubuntu/nbot_v5_integrated_data/approved_code_sha.txt`; before EVERY systemd start, read-only `g3_prod_preflight` independently refuses mismatched Git head, dirty source, wrong server or active legacy V4 services.
- No G3 code was merged into the authoritative roadmap/old running V5 branch or the independent Execution branch. Old V4 services were not enabled.
- New systemd service unit `nbot-v5-g1g2g3-observation.service` is installed/enabled, restart on failure bounded by `StartLimitBurst=2` per hour, CPUQuota=70%, MemoryMax=200 MiB, restricted filesystem access and **no user/private order endpoints**.
- Read-only `nbot-v5-integrated-health.timer` and `nbot-v5-integrated-health.service` installed/enabled; timer begins checking after 30 minutes and repeats hourly. An owner-initiated manual invocation of the ACTUAL systemd health service returned `Result=success`, `ExecMainStatus=0`, with entire reported G1–G3 acceptance status PASS for initial live windows.

## 3. Important service-restart incident during rollout

At roughly **2026-10-14 06:45–06:47 UTC**, the VPS had an automatic Ubuntu `apt-daily-upgrade.service` execution. Systemd logs show both V5 collector services were stopped/started during the maintenance window; there was **no VPS reboot** (boot ID remained `9bc008f6-eaa2-4ced-8a9d-c3f54f3b5a6e`). The older G1f service could not restart because a newly ranked market cohort differed from its initial immutable selection: `G1F_COHORT_ROTATION_REQUIRES_REVIEW`. This is a safe refusal to silently rewrite selection, but older G1f is not a functioning fallback after that incident.

The new integrated G1–G3 service **successfully reused its archived original frozen top50 selection and resumed public WSS**, without corrupting or fabricating old data. Its stable post-maintenance activation timestamp is **2026-10-14 06:46:04 UTC** (12:16:04 IST), original MainPID later `11327`, `NRestarts=0`, memory ~67 MiB under 200 MiB cap. This 24-hour soak clock starts at that timestamp, **not** at the earlier deployment attempt. A strict health report must also inspect systemd ActiveEnterTimestamp/journal because explicit maintenance restarts are not always reflected in NRestarts.

Given the old G1f service's verified failure and the new system's healthy WSS connections, the former `nbot-v5-observation-only.service` and obsolete `nbot-v5-g1g-health.timer` were disabled, preserving their unit files, logs, code and old DB. Old failed unit flag was reset only after diagnostics were captured. No original data was deleted. New integrated service and new health timer stayed active/enabled.

## 4. Two genuine end-to-end persistent G2/G3 five-minute events

The live, newly enabled **permanent** service—not the earlier detached proof command—committed two consecutive event-open bars at **2026-10-14 06:45 UTC and 06:50 UTC**. Both original Binance public data routes connected, no reported reconnect attempts/trade gaps at checkpoint, and both real events passed source/finality verification.

- Frozen original witnessed exchangeInfo snapshot = 927 listed market rows, 525 rankable positive-turnover eligible USDT perpetuals, 50 selected (BTC included), **475 excluded explicitly and never claimed as assessed opportunities**; cohort digest `82176070c5454a174701d4e5b9e49396f070945db62cfd7372a9aac0ff9f7a82`, new live original witness SHA256 `fd05727503afb8c146e603995302a05b9496188fac715b88f851c0994d49dfb3`.
- **G2 independent source_acceptance: PASS**, zero violations, 2/2 fully source-qualified five-minute events, 200/200 two-sided LONG+SHORT candidates, 100/100 independent quote/trade-receipt/source-epoch witness rows, zero held source rows and no missing five-minute time slots. No 475 excluded market outcomes invented.
- For the same 2 original events, **G3 independent causal frozen_replay: PASS**, 50/50 coins AVAILABLE per event, 100/100 coin-event BTC/structure contexts reproducible from the original SHA256-checked 96 past-only closed candles and original witness timestamps; original persisted G3 event rows = 2/2. BTC classified as `RANGE` in both events; heuristic altcoin-only breadth = `-0.4897959184` and `+0.4693877551`; **these are descriptions, not predictions or trade outcomes**.
- G3 context records persisted by actual service for those events with full SHA256 and immutable SQLite triggers; G3 per-event first SHA `a99fd74b08f194225953784ce8afaa71fb5f28c00b554035bbcebe5c47587a82`, second SHA `486cd9df84d905c7698e6b9b5f6870716e3322c314c3267fa69f87cfe20df489`.
- Read-only integrated `g3_prod_health`, both as direct CLI and **actual protected systemd oneshot**, reported **PASS**: 2 event manifests, 200 candidate rows, 100 original G2 source witness rows, 2 immutable G3 contexts, 50 frozen eligible markets, 0 explicit holds, 0 unexpected counted service restarts, memory ~67 MiB, zero order/recommendation/training authority.
- GitHub Actions on exact pinned integrated release SHA `1e7c090d05dc118b290c764d58c2944f56ad4b3b`: **247/247 Python 3.12 tests PASS**, https://github.com/samqju/Nbot/actions/runs/38523923669 . VPS isolated integration and prior G2/G3 synthetic suites also passed. Original F0 backup proof and GitHub branches remained separate.

## 5. Formal stage closure and next checkpoint

| Requirement | Status on 14 October | Honest qualification |
|---|---|---|
| G1 historical F0 copies / integrity / fail-closed boot/source and restart proofs | **PASS with previously documented cross-DB limitations** | The original F0 archive per-database checksum/isolated restore and failure-on-unsafe-source tests passed. A joint cross-DB atomic historical snapshot was never established, so none is claimed. |
| **G1 full NEW integrated 24h unattended operational soak** | **IN PROGRESS / HOLD FOR ELAPSED TIME** | Stable activation 06:46:04 UTC Oct14; earliest 24h 06:46:04 UTC Oct15, with independent journal/DB/health continuity inspection needed. |
| G2 original at-event full 50-coin LONG/SHORT denominator, frozen top50, quote/trade witness, continuous operational integration | **PASS for two accepted genuine permanent-service events** | More runtime evidence is accumulated by the unattended service; missing future source must become HOLD, never fabricated candidate/fill. |
| G3 BTC conditional regime, structure, deterministic no-lookahead swings and actual continuously persisted contexts | **PASS for two accepted genuine permanent-service events** | Real observed `RANGE` regime, other regimes/staleness/shock tested synthetically. No calibrated edge or G4 matured labels. |
| G4 outcome label/economic source path | **NOT STARTED / BLOCKED** | No invented fills/fees/funding or training; do not advance until continuous G1–G3 acceptance and independent G4 specification. |
| Execution VPS paper/live order authority | **NONE** | Execution remains idle; no G6 Champion model, no E6B operational coupling. |

A scheduled **daytime** 24h+ integrated soak review is set for Thursday **15 October 2026, around 12:45 PM IST**, after the earliest full 24h. It must check actual service ActiveEnterTimestamp, unit/timer, source and cohort manifests, no silent event gaps, hourly health journal, SQLite integrity/resource envelope and independent G2/G3 replay. If the operator's connected laptop is offline at that time, automated local server health still runs, but remote ChatGPT validation must report **UNVERIFIED/HOLD** rather than guessing. The user may close the browser and laptop; the VPS alone continues G1–G3 observation.

**No original V4 code, old G1f DB or historical backup was deleted. Never represent 200 candidate records or 100 market contexts as matured virtual-trade outcomes.**
