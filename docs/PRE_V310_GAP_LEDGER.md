# NBOT V3 Pre-V3.10 Gap Ledger

Status: ACTIVE CHANGE-CONTROL LEDGER

Baseline audited: `887f3b5fa135a5e58961fcc580be7372fdd04695`

This ledger tracks non-economic cleanup while V3.9 evidence accumulates. It does not modify frozen research definitions, reset challenger history, or authorize V3.10.

## A — MUST CLOSE BEFORE V3.10

- [x] Replace stale README/OPERATIONS active-phase reporting with truthful V3.9 economic-wait wording while preserving historical evidence.
- [x] Replace `docs/EVIDENCE_LINEAGE_CONTRACT.md` V3.0 placeholder with implemented V3 lineage.
- [x] Update `nbotctl` phase reporting without claiming economic proof.
- [x] Ignore generated `NBOT_CURRENT_FULLSOURCE_*.txt` review artifacts.
- [x] Remove stale V3.8 phase numbers from active LIVE_PAPER/research systemd descriptions without changing service behavior.
- [x] Integrate real Observation database integrity into `nbotctl doctor` using read-only SQLite integrity, foreign-key and lineage checks.
- [x] Integrate local protocol/profile contract validation plus authenticated Execution-to-Observation control-link compatibility into operator `nbotctl doctor`, while excluding the remote network probe from Execution worker startup/reconciliation.
- [ ] Implement `nbotctl cluster doctor/start/stop/status` with fail-safe ordering, same-release/profile/protocol checks, and no SSH dependency in OPEN management.
- [ ] Validate/install the final cleanup release on both VPS roles as applicable and prove same-release runtime state.

## B — SHOULD CLOSE BEFORE V3.10

- [x] Remove historical V3.2 wording from the active `requirements.txt` header.
- [ ] Complete maintenance/recovery/operator discoverability audit after mature doctor/cluster tooling lands.

## C — CORRECTLY DEFERRED UNTIL V3.10+

- Binance LIVE real-order adapter.
- LIVE real-capital arming/credential authority.
- Real-capital regression/validation.
- Automatic rollback authority explicitly gated on a mature paper stage.

## D — HISTORICAL ONLY — DO NOT CHANGE

- V3.2 Testnet mechanical-canary records and procedures.
- V3.7 LONG/SHORT and C–V physical operational proof.
- Historical exception/defer/closure records in the canonical roadmap.

## E — ECONOMIC EVIDENCE — CANNOT BE CODE-CLOSED

- Three consecutive qualifying Research Champion PASS windows and every other frozen Research Champion eligibility gate.
- Genuine Research Champion promotion boundary.
- Sustained LIVE/PAPER Paper Champion evidence under `V39_PAPER_CHAMPION_GATE_V1`.
- Required elapsed time, UTC dates, independent trades/events, market regimes and after-cost economics.

V3.10 remains hard-blocked until genuine V3.9 Paper Champion proof, regardless of this maintenance ledger.
