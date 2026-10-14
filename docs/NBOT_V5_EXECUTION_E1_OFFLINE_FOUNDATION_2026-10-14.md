# NBOT V5 Execution E1 — Isolated Offline Foundation (2026-10-14 IST)

**Workstream:** Execution only. **Status:** Offline foundation implemented; operational G7 gate remains HOLD.  
**Base:** `v5-clean-restart-20261013` pinned at `cb68ee247cbbb8577238e7d452ac5e79ebc4d089` (roadmap 2.8.1).
**Development branch:** `feature/v5-execution-foundation-20261014`. **Never merge or deploy without review.**  
**Reference:** Authoritative roadmap §§17–26 and acceptance checklist; not a change in Observation authorization.

## Ownership and minimal structure

Observation owns public market evidence, research, model lifecycle and version-locked intent. Execution owns independent market-quality/risk checks, paper fills and accounting. The sole engine core is `nbot/v5/execution_engine.py`. There is **no running service, daemon, scheduler, network client, Binance interface, imported private key or exchange order method**. This is not a functioning trading system.

**One core, two financially isolated books:** `CHAMPION_PAPER` and `CHALLENGER_PAPER` are independently locked to immutable model SHA-256, experiment, contest and cost/risk policy SHA. Each has its own wallet, sequence, positions, limits, immutable decisions, orders, simulated fills, fees, funding debits and settled outcomes. Same symbol and same event are valid in different books; not duplicated inside one book.

**Message contract:** `nbot.v5.paper.recommendation.v1`, canonical UTF-8 JSON with HMAC-SHA256 and domain separation, separate key per portfolio, immutable model SHA, paper-only authority, event/contest identity, monotonic per-book sequence, idempotency key, expiration and as-of clock, side or explicit abstention, versioned strategy/context identifiers, expected-after-cost net R and confidence, quote reference, stop and paper policy version. Synthetic test signing keys are fixtures only; they are *not* remote transport credentials. Unsigned, altered, stale, oversized, wrong-book, wrong-model, reordered and replay-conflicting requests are refused. Exact authorized repeats return their persisted result without another fill.

**Market validation:** Synthetic quotes only. The supplied mock market source must explicitly report fresh known-at quote and BTC context, consistent bid/ask and quote-reference identity. A shared immutable per-event/symbol quote guards against different synthetic prices for the same contest event across books. The engine cannot infer real quote authenticity from caller fields; authenticated independent live feed and proven source quality remain later gates.

**Conservative synthetic economics:** Favor adverse ask entry/bid exit for LONG (reverse for SHORT), default taker charge 5 bps per side and adverse slippage 1 bp per side, with an explicitly assumed adverse funding charge of 1 bp per eight-hour equivalent holding period. These are configurable **test assumptions, not verified exchange fill or funding rates**. Futures wallet does not withdraw notional as spot purchase; initial taker fee and net realized settlement adjust each book independently. Risk sizing uses initial stop distance, cost-to-risk budget, per-trade and total position-risk, position count and a gross-notional/equity cap. Bad or negative-edge signals can do zero trades. A one-way book kill is available, and excessive realized wallet drawdown triggers it. Exits are presently invoked by the offline test harness only; no autonomous stop triggers, tick scheduler or real feeds are implemented.

**Durability:** SQLite WAL + FULL synchronous writes; atomic state updates; immutable trigger-protected decisions, fills, ledger, settled-trade and shared market quote records; restart checks refuse swapped model or economic policy. Crash-fault simulation tests roll back partial changes. Persistent path guard refuses known historical Nbot/V3/V4 paths.

**What is explicitly missing:** Real source authentication and independent Binance observation; mature Champion model; network transport and key management; source/clock reconciliation and down-feed management of already open positions; scheduled stop/take-profit exits, partial fills, exchange order states, actual funding schedules, mark-to-market equity/drawdown, configurable correlated BTC exposure, event-time risk reconciliation, complete performance statistics, shared UTC contest start/end and maximum horizon gates, event-blocked statistical review, 100-trade checkpoint, owner paper-promotion cutover, disaster restoration drills, production deployment and ALL real-money order functionality. A missing item is a HOLD, not a default PASS.

## Offline validation evidence and isolation

- Read-only preflight against `nbot-execution`: the legacy `nbot-execution-live-paper.service` and `nbot-control-tunnel-live-paper.service` both **inactive and disabled**; user directories preserved. Observation `base` was not touched.
- Separate new development clone: `/home/ubuntu/nbot_v5_execution_dev` on Execution VPS. No old source path, database, logs or backup modified. Tests use ephemeral system temporary directories and synthetic identifiers.
- Run: `python3 -m unittest discover -s tests -p test_v5_execution_engine.py -v` from isolated dev checkout; CI workflow `.github/workflows/v5-isolated-execution.yml` repeats on Python 3.12.
- Tests cover signed paper-only routing, same/different symbol across books, abstentions, stale/invalid quotes, model/contest/policy identity, signed replay, quote/event mismatch, idempotent restart, fees/slippage/funding, independent losses, immutable ledgers, loss kill switch, legacy path protection, bounded input, atomic failure rollback and refusal to manufacture a settlement.
- E1 final isolated Execution VPS evidence: **23 of 23 synthetic tests PASS**, Python 3, commit `971a46e471079e907008a4f5d3d77c68b41a08fa`, with zero order APIs and no service start. Post-test legacy execution units still **inactive/inactive**.
- GitHub Actions CI: **SUCCESS** at exactly that code commit, run `38508871941` — https://github.com/samqju/Nbot/actions/runs/38508871941 (Python 3.12). No production operation or paper authority follows from this PASS.

## Safeguards and next independent milestone

**E1 outcome:** foundation-only source and synthetic tests; **no service deployment; no paper operations; zero exchange orders and zero real keys**. No integration with Observation until its source-health and later model gates separately pass. Do not merge this branch into Observation work until interface review, additional test coverage and independent isolation check.

**E2 proposal (not operationally activated):** authenticated batch-recommendation boundary with independent qualified quote clock, durable per-event evaluation and signed evidence acknowledgments, synthetic chronological market replay, autonomous mock stop/outage policy and mark-to-market accounting. Freeze contest rules and common-window fairness before a forward competition. **No trade/service authorization is inferred by completing E2 code.**
