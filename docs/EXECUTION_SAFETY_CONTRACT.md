# Execution Safety Contract

Status: V3.1 implementation contract.

The canonical requirements remain `NBOT_V3_ROADMAP.md`. The V3.1 codebase implements the capital-side invariants required before standalone Testnet mechanical validation.

## Permanent capital invariants

- Exactly one capital-bearing position maximum.
- Execution imports no Observation, research, learning, strategy, or training runtime.
- Durable proposal reservation and entry-inflight identity precede the market entry call.
- Ambiguous entry writes are recovered by deterministic identity; they are never blindly resubmitted.
- A filled position is promoted to OPEN only after protective stop verification and post-fill notional/risk/slippage checks.
- A close request is not proof of flatness. Emergency handling succeeds only after independent exchange-flat verification.
- Stop replacement may not intentionally loosen protection; replacement truth is verified.
- Startup/flat cycles reconcile exchange truth before proposal eligibility.
- An OPEN position is managed without ProposalClient or OutcomeClient availability.
- Completed outcomes are durable before local OPEN/inflight state is cleared.
- A pending outcome blocks the next proposal request until the exact outcome ID is ACKed.
- Corrupt/incompatible state fails closed rather than resetting to FLAT.
- Daily risk state survives restart and rolls by UTC day deterministically.
- Testnet host pinning, arm/session limits, and single-instance protection remain safety boundaries.

## V3.1 runtime authority

The V3.1 runtime is intentionally narrow. `testnet-trade` can start only after explicit arming and authenticated Testnet preflight, and it starts with new entries disabled. V3.2 adds the explicit synthetic/manual mechanical-canary proposal path.

`live-paper` does not start until its independent LIVE public market source exists. `live-trade` is forbidden until V3.10. Neither limitation weakens management of a Testnet position already known to the V3.1 runtime.
