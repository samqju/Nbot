# V3.9.5 Operational Regime Evidence Contract

Current applicability (2026-10-01): historical evidence retains its original
release and scope. The recent synthetic small-VPS benchmark is not a physical
test of both live collectors, free-provider throttling, or long-term disk growth.
Use [current operations](OPERATIONS.md) and verify current-release behavior on
the actual servers. Explicit first promotion is implemented by the
[promotion contract](V3_9_RESEARCH_CHAMPION_PROMOTION_CONTRACT.md); its applicability
depends on actual eligible/pointer state, not code completion.

Version: `V39_OPERATIONAL_REGIME_LEDGER_V1`

V3.9.5 does not erase previously accepted physical fault evidence and does not
repeat destructive capital/network failures merely to create a newer timestamp.
It makes the evidence status explicit and keeps future requirements visible.

The canonical V3.9.5 regimes are Observation restart, Execution restart,
network interruption, public-feed recovery, large database growth, heavy
training CPU, disk-pressure alert, model promotion, model rollback, and
operator/Telegram failure.

## Evidence classes

`ACCEPTED_HISTORICAL_PHYSICAL` carries forward a physically accepted V3 fault
proof whose safety contract is unchanged. `ACCEPTED_HISTORICAL_RELEASE_REGRESSION`
carries forward accepted release-level operator resilience evidence.
`DETERMINISTIC_EQUIVALENT` is deliberately not relabeled as physical proof; it
must be rechecked on the current release before Paper Champion closure.
`DEFERRED_BY_AUTHORITY_BOUNDARY` means the condition cannot truthfully occur yet.

The current Observation feed is request/cycle based rather than a persistent
public WebSocket, so the roadmap's public-feed reconnect condition maps to a
transient public-request failure followed by bounded retry and a successful next
collection cycle.

Disk-pressure testing must not fill the production filesystem merely to prove an
alert. The current doctor `DISK_FREE_TOO_LOW` gate can be exercised through a
safe deterministic threshold equivalent.

Model promotion and model rollback remain not applicable while V3.9.2/.3 has
automatic promotion disabled, the Champion pointer is null, and rollback is
`DISABLED_NO_RESEARCH_CHAMPION`. Those regimes become mandatory when the
corresponding authority is actually enabled.

Nothing in this ledger grants Research Champion, Paper Champion, Execution, or
order authority. V3.9.6 remains separately gated by sustained economic and
operational evidence.
