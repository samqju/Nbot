# NBOT V5.1 — CS-00 Offline Engineering Progress, Two-VPS Verification & Remaining HOLDs

**Date:** 15 October 2026 (IST)  
**Scope:** Controlled Startup `CS-00` preparation **only**.  
**Verification source:** GitHub `samqju/Nbot`, `nbot-v5.1`, exact independently tested code SHA `30c34c079601cb6a1496172d40ca8ce983f1963a`.  
**Parent status:** **CS-00 [ ] NOT COMPLETE** — substantial OFFLINE subtasks done; first persistent deployable original-public-source runner, existing archive provider configuration, true off-host backup and durable operational monitoring require separate work and owner approval.  
**Permissions:** No permanent deployment, service enabling/starting, public market connection, private source/account/API credentials, virtual source-grade trials, PAPER/testnet/REAL order or model promotion. No storage purchase.

## 1. Owner preferences confirmed and enforced

- Existing archive provider chosen by owner but **name, technology, target region/destination/prefix, capacity, access/backup posture and costs not yet provided**. Do NOT invent a provider, bucket, credentials, remote copy endpoint or quote.
- **30 days is a retention planning target**. The prototype hard-rejects every auto-deletion flag, including retention-related cleanup. No raw data may be automatically deleted without separately approved policy.
- **Local reports and documented emergency response only.** No external email, SMS, chat, webhook, cloud alert integration or account connector activated.
- **ALL NBOT services remain stopped.** No persistent install, service unit or daemon modified on either VPS; a deliberately refusing, non-installable `deploy/cs00_observation_disabled.service.example` is checked into GitHub as design evidence only.
- Production/public source and future real-money order privileges are not implied by this phase. Separate CS-01 owner authorization remains mandatory.

## 2. New audited source and tests

| File | Scope and independent meaning |
| --- | --- |
| `nbot_v5_1/cs00_commissioning.py` | Strict OFFLINE/no-network/no-trade policy; frozen G2 Observation → G3 200-direction status → G4 BTC-included deep 20, **G5 source/admissions forced OFF**; prospective five-minute records; finite synthetic G4 raw-segment custody and local seal/replay; explicit source-gap/restart risk alarms; 30-day no-deletion archive profile; fsynced private `O_EXCL` one-time SHA-checked reports. Cannot claim original source, off-host provider or financial/model release. |
| `nbot_v5_1/cs00_host_monitor.py` | Read-only Linux CPU, 1-minute load, available RAM and disk telemetry; low-resource HOLD reasons, always `HOLD_PENDING_CS00_C_E_AND_OWNER_PERMISSION`. No service modification, account or network. |
| `scripts/cs00_observation_entry.py` | Explicitly non-starting entry: defaults to `STOPPED_OFFLINE_ONLY`. Only optional `--offline-rehearsal` using synthetic temporary fixtures. Public network/serve/paper/testnet/real/unknown CLI switches are *not accepted*. This **is not** a live producer or executable production service. |
| `scripts/cs00_host_preflight.py` | One-shot read-only host telemetry. |
| `benchmarks/cs00_offline_readiness_benchmark.py` | Measures true offline 100 broad / 200 statuses / 20 deep, 12×20×3 = 720 synthetic source-shaped frames/12 sealed segments, fsync and same-host independent replay, injected full-disk/queue HOLD, immutable report. |
| `tests/test_v5_1_cs00_commissioning.py` | CS01–CS24, 24 explicit metadata/source, 30-day, private report, no-order and failure tests. |
| `tests/test_v5_1_cs00_entry.py` | CMD01–CMD06, six no-network/no-service/no-order CLI rejection cases. |
| `tests/test_v5_1_cs00_host.py` | HOST01–HOST04, four current host and negative-resource telemetry tests. |
| `deploy/cs00_observation_disabled.service.example` | **Non-installable/non-functional refusal placeholder**, with no `[Install]`, `RefuseManualStart=yes`, `ExecStart=/usr/bin/false` and no network. It was **not installed**. NOT the future approved CS-01 service; replace with separately reviewed CS-01 public-only implementation after signoff. |

The only provider configuration accepted now is a nonsecret placeholder. This implementation **does not have a public WebSocket transport, real-source Original admission or permanent supervisor**, therefore **CS-00-B remains [ ] HOLD** for deployable-source acceptance despite offline test success. No one should edit the launch script to permit public network without a new source-only reviewed change and owner release.

## 3. Independent verified test results

Exact code SHA `30c34c079601cb6a1496172d40ca8ce983f1963a`, Python 3.12.3, 2 CPU cores per VPS, `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py'`:

| Evidence | Observation VPS | Execution VPS |
| --- | ---: | ---: |
| Prior G0–G11 preserved | 430 | 430 |
| New CS-00 tests | 34 | 34 |
| **Entire suite independently passed** | **464/464 PASS (52.686s)** | **464/464 PASS (54.386s)** |
| Source bench broad / directions / deep | 100 / 200 / 20 | 100 / 200 / 20 |
| Synthetic source frames / fsynced segments | 720 / 12 | 720 / 12 |
| Boundary computation (one event) | 94.307 ms | 92.427 ms |
| p99 per 20-market × 3-source fsync batch | 40.421 ms | 48.428 ms |
| Peak RSS (synthetic bench) | 32,068 KiB | 32,324 KiB |
| CPU seconds (synthetic bench) | 0.723 | 0.718 |
| Local-only raw + copied evidence | 101,190 bytes | 101,190 bytes |
| Synthetic disk-low/queue-HOLD injection | PASS | PASS |
| Original source-qualified frames | **0** | **0** |
| Genuine off-host provider backup | **NOT VERIFIED** | **NOT VERIFIED** |
| Actual market connection/service/trades | **NONE** | **NONE** |

No original exchange source rate, live 24–72h endurance, true public WSS auth, provider remote access or operational alert reception was exercised. Short synthetic source p99 and a 30-day retention planning preference are **not capacity proof** for 20 real volatile-market streams.

**Read-only Linux host preflight after regression:**
- Observation: two logical cores; ~709,860 KiB MemAvailable, ~92,882 MiB free disk, ~0.710 1-minute load.
- Execution: two logical cores; ~709,004 KiB MemAvailable, ~40,236 MiB free disk, ~0.719 1-minute load.
- This is **host availability**, not a long-running Observation process RSS or disk quota acceptance.

Test-only `/tmp/nbot-cs00-verify-tWmvv07P` on Observation and `/tmp/nbot-cs00-verify-mCiI14KJ` on Execution were subsequently removed independently, each with `CS00_TEMP_TREE_CLEAN` and exit 0. A later read-only host check returned **`NO_NBOT_SYSTEMD_SERVICE` and `NO_NBOT_PROCESS` on BOTH**. Unrelated earlier G8 Observation directory remains `OLD_G8_UNTOUCHED`. No permanent filesystem/service/VPS source changes.

## 4. Permanent CS-00-A–E task status, never conflate OFFLINE code with operational readiness

- [x] **CS-00-A1** Read-only verification of current two-VPS host environment, NBOT process/service absence, and already proven G11 initial baseline.
- [x] **CS-00-A2** Pin exact new CS-00 source SHA and independently retest all **464/464** regression checks on both target VPSs.
- [x] **CS-00-B1** New strict source-only OFFLINE Observation seam for actual existing G2/G3/G4 pipeline; run 100/200/20 synthetic contracts without G5 source-verified admission or trading authority.
- [x] **CS-00-B2** Explicit disabled/nonfunctional startup template and CLI denied for network/service/order operations; no install or autostart.
- [x] **CS-00-B3** Source-shaped synthetic 20×3 custody, frame-gap HOLD, private bounded segments, local sealed verification and finite durability demonstration.
- [ ] **CS-00-B4** Build and independently test a truly ready-to-deploy, persistent, public-data-only original-source collector/transport/supervisor with frozen source epochs, startup/shutdown, queue and failure safeguards; currently only OFFLINE laboratory coordinator/blocked command. **NO START until CS-01 separately authorized**.
- [x] **CS-00-C1** Record owner archive preference as EXISTING PROVIDER pending details; hold unqualified transfer, no credential/source provider access.
- [x] **CS-00-C2** Record initial 30-day planning target and reject ALL automatic deletion.
- [x] **CS-00-C3** Local-only synthetic seal/replay/corrupt permission guard code proof; G11 previously checked physical synthetic cross-VPS transfer and does not equal genuine source/provider custody.
- [ ] **CS-00-C4** Receive nonsecret provider type/service/region/destination/available quota/current encryption/retention capabilities and choose budget, restore proof & actual off-host method. **Owner details needed; no credentials in GitHub/chat.**
- [ ] **CS-00-C5** Independently test exact selected provider off-host copy/restore and capacity/cost controls with **synthetic-only** data under a separate owner-approved setup operation. No accidental persistent configuration.
- [x] **CS-00-D1** Implement local read-only host CPU/RAM/disk and hypothetical alert/HOLD reports; six command denial tests and immutable private report verification.
- [x] **CS-00-D2** User preference: documented local alert report / emergency procedures only; no email/webhook integration until separately requested.
- [ ] **CS-00-D3** Bind actual source queue and long-running collector heartbeats to a persistent reviewable watchdog, source gap/latency/restart records, safe stop/runbook and a named owner/operator stop channel; dry-run fault/recovery without live data and approve actual resource quotas.
- [ ] **CS-00-D4** Reviewed secure deployment/rollback/shutdown with exact source/config hashes; **installation and start are separate** and not granted.
- [x] **CS-00-E1** Independently run full 464-case combined suite and 720-frame offline rehearsal on both VPSs; verify cleanup, host services stopped and no source/account use.
- [ ] **CS-00-E2** Independent reviewer signs complete CS-00 parent only once B4, C4/C5, D3/D4 are adequately proven and provider details settled.
- [ ] **CS-00-E3** Owner authorizes **CS-01 public-only startup** by separate narrow approval. **Not requested or granted by this CS-00 engineering message.**
- [ ] **CS-00 PARENT READY TO START ORIGINAL PUBLIC OBSERVATION:** **HOLD** pending all required technical/provider/operator gates and a separate permission to actually start.

## 5. Outstanding info needed from owner — nonsecret only

The owner has an existing storage provider. To draft the provider adapter without connecting or buying anything, ask for **provider/service name, storage interface (S3-compatible object store, native object store, SFTP, mounted storage or other), target region, approximate available quota/plan and whether immutable/versioned retention is available**. If the user knows an uncredentialed hostname/endpoint, it can be supplied **only as needed**. **Do not ask for or collect access keys, passwords, secret tokens, PPK contents, URLs containing tokens, security questions, personally identifying billing data or key files.** Do not connect or configure without scope/approval.

Owner alert preference: LOCAL-REPORTS-AND-EMERGENCY-RUNBOOK only. Operator notification integration remains disabled.

## 6. Next safe technical tasks and blockers

1. Wait for provider metadata (C4), then design adapter and synthetic remote restore test with separate consent before any remote provider access or persistent VPS installation.
2. Complete B4: actual unattended public-only source-intake transport and no-secret supervisor/verified on-disk epoch source custody, **while running only injected offline fixtures**. Never silently add private/account routes.
3. Complete D3/D4: actual workload watchdog, alert log/no external integration, resources/guardrails, stop/restart/rollback dry run, operator approval.
4. Rerun full two-VPS tests at the new source SHA, record provenance and only then consider an independent CS-00 paper-readiness signoff. If any work requires a persistent VPS change or storage purchase, obtain **explicit owner approval first**.
5. **Separate later owner instruction** needed for CS-01 first genuine public market canary. All G4–G10 original-source/scientific/paper and G12 real trading gates remain UNCHANGED / HOLD.

**Final status:** real-money financial authority NONE, model qualification original 0, live original source captured 0, original independent off-host archive 0; CS-00 offline source/code/monitoring partial tasks PASS, parent CS-00 HOLD. G11 remained [x] offline and G12 [ ] locked.
