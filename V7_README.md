# NBOT V7 — Runtime and historical evaluation

V7 contains a reusable auto-learning trading core and a separate historical laboratory. **Production readiness is not established.** Real exchange credentials and orders are not authorized or enabled. Owner authority is preserved in `V7_OWNER_AUTHORIZATION_2026-10-20.md`; older roadmap prohibitions describe earlier scope.

## Reusable bot

`nbot_v7/runtime/` provides persistent one-slot coordination, independent immutable risk, paper fills, durable order intents/reconciliation, outcome memory, parallel selected/rejected/control shadows, scheduled matured-outcome challenger fitting, versioned registry, review receipts, paper-promotion approval and rollback. `decision.py` is shared with the lab, keeping strategies as proposal engines and the brain as ranking/abstention authority. The hourly neutral long/short grid is independent of family signal rules.

`runtime/public.py` observes current public USD-M USDT perpetual contracts, synchronized completed candles and public quotes. Current exchange information never supplies historical survivor filtering. `runtime/stream.py` accepts recorded events or explicit bounded public paper cycles. No bot service has been automatically installed or started.

```sh
python -m nbot_v7.runtime.stream --events /data/events.jsonl --memory /data/paper.sqlite --model-registry /data/registry.sqlite --challenger-artifacts /data/challengers
```

The model registry must first contain locally generated, hash-verified model artifacts. Never deserialize untrusted joblib files. Training does not grant promotion authority. `GuardedLiveBroker` is an interface requiring separately authorized, independently tested venue transport; V7 currently has neither a live permit nor an implemented exchange-specific live transport. Full production venue integration remains a gap.

## Fixed historical experiment

- January–March 2026: fit/freeze A from matured labels.
- April–June: evaluate frozen A; then fit/freeze adaptive B plus same-architecture B1 on matured January–June labels.
- July–September: independent A/B/B1 one-slot accounts on identical history. This is an **exploratory engineering baseline**, since V6 inspected some dates.
- A subsequent B2/C trained using July–September needs later independent evaluation. It cannot pass on its own training period.

```sh
python -m pip install -r requirements-v7.txt
python -m unittest discover -s tests_v7 -v
python -m nbot_v7.archive --start-month 2026-01 --manifest /data/archive-index.json
python -m nbot_v7.archive --existing-manifest /data/archive-index.json --manifest /data/archive-index.json --download --archive /data/archives --max-gib 20
python -m nbot_v7 build --archive /data/archives --registry /data/registry.csv --db /data/v7.sqlite --start-month 2026-01
python -m nbot_v7 experiment --db /data/v7.sqlite --out /data/experiment-001 --start-month 2026-01
```

Acquisition verifies exchange-published SHA256 checksums, caps planned bytes and preserves 8 GiB free disk. An incomplete dataset build cannot enter evaluation. Output includes coverage, immutable model components, source/dependency/config hashes, content hash of the labeled dataset, hash-chain decision logs, trades, costs, account completeness and diagnostic confidence intervals. `nbot_v7.artifacts.verify_run` verifies output integrity.

A historical registry CSV requires `symbol,from_ms,to_ms,evidence_sha256,source_grade`. `SOURCE_ATTESTED` is a caller attestation requiring independent audit, not cryptographic proof of historical listings. When historical lifecycle evidence is unavailable, explicitly construct a provisional cohort:

```sh
python -m nbot_v7.registry --archive /data/archives --start-month 2026-01 --out /data/archive-observed-registry.csv
python -m nbot_v7 build --archive /data/archives --registry /data/archive-observed-registry.csv --db /data/exploratory.sqlite --start-month 2026-01 --allow-archive-observed-universe
```

These rows retain `ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`; the default loader rejects them. Missing/suspended/delisted-contract evidence remains unresolved, even if archives are present. Do not describe this mode as source-verified historical eligibility.

## Execution and scientific limits

The V3 label policy uses the **same incremental paper broker** as the bot: next-open entry, modeled 1 bp slippage per fill, 0.05% fees on actual entry/exit notional, 2% protective stop, 3% target and 60-minute horizon. Both-touch candles stop first; gaps fill at worse open. Labels and runtime have explicit parity tests for both sides. This is paper-bar equivalence, **not exchange/native tick-fill equivalence**. MFE/MAE and extremum times are bar bounds. The old failed exact 1% trailing rule is not adopted.

Funding archives are a signed entry-notional approximation, not verified payable mark-notional settlements; missing archives are flagged. Orderbook queue/spread, partial fills, liquidation, historical filters and genuine forward proof remain unresolved. Proxy results cannot authorize paper promotion/live orders. Missing selected future paths block reuse of the slot and mark the account incomplete; ambiguity never removes a candidate ex ante.

Simple comparators share calendar/capacity/cost/slot conventions, but entry frequencies are not matched. Bootstrap intervals remain diagnostics. Full V6 native-control reproduction, rigorous calibration/drift analysis, resource stress and independently verified lifecycle completeness remain required before readiness claims.

## Legacy reuse and continuity

Audited V3 ledger/replay, V5 accounting/exit and V5.1 governance modules are selectively preserved. V4 groupwise ranking is adapted in `brain.py`; V6 source/evidence remains intact. No blanket legacy merge. See `V7_G0_LEGACY_AUDIT_2026-10-20.md` for provenance and `V7_CHAT_HANDOVER.md` for every implementation step and verified result.

## Audited production execution reuse (2026-10-20)

`V7_EXECUTION_PORT_MANIFEST.json` pins the selective legacy execution and guarded public/paper/live transport dependency closure. `runtime/venue.py` integrates it with V7 intents and fixed exits; the mainnet transport is code only and retains independent arm/account/reconciliation controls. No real account has been connected. Linux verification: 530 original execution fault tests and 32 V7 tests pass. Windows POSIX execution-port compatibility is not established.

Exact V6 signal functions are now additional frozen negative-control proposal advisors (`V7_V6_SIGNAL_PORT.json`). The V6-signal benchmark shares V7 fills; it is not a reproduction of the old V6 trained/native policy. Current label policy is V4 and feature/model schema V3; rebuild older datasets/models.
