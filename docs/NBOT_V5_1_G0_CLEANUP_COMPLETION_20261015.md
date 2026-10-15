# NBOT V5.1 — G0 Legacy VPS Cleanup: Owner Execution + Independent Verification

**Date:** 15 October 2026, IST.  
**GitHub branch:** `nbot-v5.1`.  
**Disposition:** **PASS — the scoped prior-version NBOT application directories and the retired observation systemd unit are absent on both named VPSs.**  
**Backup treatment:** Owner explicitly waived backup or restoration of historical NBOT VPS-only contents in the recorded G0-03 decision. **No historical backup was created or tested.** Irretrievable legacy-only evidence loss was knowingly accepted. Historical **GitHub branches remain source references**; no old-branch removal was undertaken.

## 1. Scope and chain of evidence

1. On 15 Oct 2026 the owner expressly authorized old-NBOT-only VPS cleanup without backup, first via agent and then with a manual PuTTY command if automated remote deletion failed. The prior automated cleanup attempt was rejected by remote tool control before execution. Earlier read-only probes confirmed the old data still existed.
2. The owner subsequently **personally executed** guarded PuTTY cleanup on the two existing sessions and provided the following success results (shown here as received, without assumptions about hidden steps):
   - Observation-VPS: host `base`, `Prechecks passed. Removing old NBOT installation components if present.`, then `NBOT_LEGACY_CLEANUP_SUCCESS`; root filesystem /dev/sda1 `96G total, 5.1G used, 91G available, 6% used`.
   - Execution-VPS: host `nbot-execution`, same prechecks and `NBOT_LEGACY_CLEANUP_SUCCESS`; root filesystem /dev/sda1 `45G total, 4.8G used, 40G available, 11% used`.
3. **Separate independently executed read-only SSH verification** used the saved PuTTY profiles and existing username `ubuntu`. Scripts checked exact paths for existence/symlinks, reviewed name-scoped NBOT systemd units and process listings, sampled the home top-level (no private contents read), and checked disk capacity. Both remote verifier processes finished with **exit status 0** and explicit completion sentinel `END_NBOT_V51_POST_CLEANUP_VERIFY`.

## 2. Independently verified after-state

| Verified item | Observation-VPS | Execution-VPS |
| --- | --- | --- |
| Hostname via SSH | `base` | `nbot-execution` |
| UTC verification time | **2026-10-15T05:30:43Z** | **2026-10-15T05:30:38Z** |
| SSH login | `ubuntu`, successful | `ubuntu`, successful |
| `/home/ubuntu/Nbot` | **ABSENT** | **ABSENT** |
| `/home/ubuntu/nbot-final-reset-20261014` | **ABSENT** | **ABSENT** |
| `/etc/systemd/system/nbot-v5-g1g2g3-observation.service` | **ABSENT** | **ABSENT** |
| Systemd unit-file name-scoped search (`^nbot(-|\.)`) | **NO MATCHES** | **NO MATCHES** |
| Python old NBOT runner/`nbotctl` process name-scoped search | **NO MATCHES** | **NO MATCHES** |
| `/home/ubuntu/.ssh` directory | Present (contents not read) | Present (contents not read) |
| Root disk | 96G total, 5.1G used, 91G available, 6% | 45G total, 4.8G used, 40G available, 11% |
| Remote read-only verifier process result | **exit 0** | **exit 0** |

The independent after-state is stronger than relying on the owner's `NBOT_LEGACY_CLEANUP_SUCCESS` string alone. It proves the specifically listed directory/unit paths are absent and no matching process/service name was found **at inspection time**. It does **not** certify that every possible hidden old-NBOT file anywhere on the OS was deleted, all other managers/cron users were searched exhaustively, or that provider snapshots are absent. The already authorized owner decision was to remove the known historical installation, not wipe operating systems.

## 3. Every small verified tick

- [x] **G0-CLEANUP-01:** Owner provided manual PuTTY success log for **Observation-VPS**, 15 Oct 2026.
- [x] **G0-CLEANUP-02:** Owner provided manual PuTTY success log for **Execution-VPS**, 15 Oct 2026.
- [x] **G0-CLEANUP-03:** Independently reconnected to **Observation-VPS** and verified both old application/marker paths plus retired systemd file absent; no name-scoped NBOT systemd unit/process; SSH still works; verifier exit 0, 15 Oct 2026 05:30:43Z.
- [x] **G0-CLEANUP-04:** Independently reconnected to **Execution-VPS** with same checks and exit 0, 15 Oct 2026 05:30:38Z.
- [x] **G0-CLEANUP-05:** Confirmed no old backup claimed, no SSH removal or unrelated-path cleanup claimed, no new V5.1 app/service installed, no code tests or paper/live orders executed in this validation.
- [x] **G0-03-CLEANUP-EXEC:** **PASS** for the explicitly identified historical NBOT install directories/retired unit on both hosts; based on both user execution records **and** fresh independent SSH verification.
- [x] **G0-04:** Previously completed first-code-only scope review remains valid; approved three independent new files and 12 offline test cases in [G0-04 scope document](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_04_FIRST_CODE_SCOPE_V1_0.md).
- [x] **Overall G0 closure recommendation:** G0-01 register, G0-02 source audit, G0-03 inventory/waiver and now verified old cleanup, G0-04 scope acceptance all have evidence; update both roadmaps' *parent G0* statuses with new commits after reviewing this file.
- [ ] **G1-01 implementation:** Must separately write `nbot_v5_1/__init__.py`, `nbot_v5_1/core.py`, `tests/test_v5_1_core.py`, and actually run/pass T01–T12. **Not started by VPS cleanup.**

## 4. Non-waived V5.1 safeguards

The owner's **old** backup waiver does not waive the **new** V5.1 original-source evidence retention, size/CPU/RAM controls, interrupted-feed HOLD, scientific provenance, after-cost economics, crash recovery or later release approvals. No paper, testnet or real exchange order is authorized by G0. Both VPSs are intentionally ready for an *independent future V5.1 deployment step*, not yet configured or benchmarked for production workloads.

**End-state:** Owner-run historical VPS cleanup independently verified **PASS**. No historical recovery copies were made. Follow subsequent G1 development acceptance gates; actual application code/tests, runtime deployment and all trading modes remain NOT DONE/LOCKED.
