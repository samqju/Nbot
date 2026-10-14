# NBOT V5 — G1–G7 Source Integration Audit and Stopped Deployment Contract (2026-10-14)

## Scope and immutable ancestry

The controlled integration is a separate **unmerged** branch derived from:

1. **PR #39** `feature/v5-g4-offline-contract-20261014` at
   `8de8b999465aaf1e75eac3d518dd3eedcfbb3fe8`, the operator-selected last stable G1–G3 integrated foundation and G4 offline contract.
2. **PR #42** repaired G1–G3 code at
   `391d423a2dbd2a2a45d15ba1d0b1f221991af914`, including source epoch repairs, single-directory runtime and 40k synthetic no-tick-SQL test.
3. **Pinned latest locked G7 branch** `deploy/v5-execution-g7-locked-20261014`
   at `33a9c825db304e56628b1959582d350147915e5b`, including PR #40 G4–G7 science and paper simulation plus later release refinements.

GitHub source-diff review found **no overlapping modified paths** between G1–G3 recovery files and the later pinned G4–G7 source files. Combined through a two-parent Git tree merge; no force-push or merge into main/governance branches.

## High-priority older integration defects

**Old directory topology invalid:** The historical G4 research unit expected a deleted `/home/ubuntu/nbot_v5_continuous_release_20261014`, separate removed `nbot_v5_research_20261014` and a `nbot-backups` G4 source. Historical G7 expected a removed `nbot_v5_paper_20261014`. Both set `Restart=on-failure`. The integrated templates now point **only to the canonical `/home/ubuntu/Nbot` tree**, use separate private subdirectories beneath its `runtime`, are **Restart=no**, have **no [Install] section**, and require named absent owner-release marker files. They remain **TEMPLATES ONLY, NOT INSTALLED OR STARTED**. The single installed Observation G1 unit is disabled and inactive.

**G3 HOLD caused G4 bridge crash:** The original G3 source schema allows an immutable `status=HOLD` with `feature_evidence=null`. The earlier G4 research bridge dereferenced `feature_evidence.btc` and could crash instead of processing the 50-coin/100-direction original denominator. Integrated fix routes the event through explicit candidate HOLD with `regime=UNKNOWN`, zero fabricated feature values/outcomes, and no G5/G6/G7 release.

**G4 source vault differs from G1's storage contract:** G1 uses in-memory coalesced last quotes/trades and never writes every tick into SQLite. The historical G4 `ForwardSourceVault` **does append each original public WSS frame as immutable `raw_frame BLOB`**. Its default bounded pilot cap is 256 MiB/100,000 frames/3,600 seconds; sustained pilot opt-in historically allowed up to 8 GiB/20 million frames/six hours. This is **not an approved sustained 50-market operational storage design**. Batching transactions alone does not solve growth or disk-write pressure. G4 raw capture therefore remains **disabled and blocked from deployment** pending capacity/retention redesign; never run a six-hour sustained raw pilot or claim original 4-hour source continuity from incomplete retained frames. A redesigned source pipeline must either preserve verifiable, bounded decision/path-specific receipt evidence with explicit integrity/gaps, or isolate capped, integrity-manifested archival outside SQLite with independent as-of replay and tested rollover. Discarded frames cannot be retroactively counted as observed stop/target/fill events.

**G4 economic-source and G5–G7 scientific holds:** No new matured, independent after-cost outcomes were created by this code merge. G4 requires original forward path, entry/exit quotes and genuine fees, funding/slippage, held/censored denominator, source continuity and prospective policy; synthetic tests cannot replace proof. G5 champion >=2,000 UNIQUE qualified settled after-cost outcomes plus dependence/effective sample, cross-coin/regime/side quality and peer acceptance; G6 challenger a separate additional >=2,000 nonoverlapping settled outcomes and independent calibration. G7 zero-exchange-order locked paper health remains disabled. Earlier Champion-only versus two-model unlock governance tension must be resolved explicitly before **any** G7 activation; the current GuardedPaper implementation requires both separately qualified roles.

## Real original source read-only audit

On the preserved Observation SQLite database, original BTCUSDT LONG event `1791996000000` is `SOURCE_BOUND` in the G1→G4 offline binder: exactly 50-coin/100-side original population, contemporaneous original G2 witness and G3 original context/feature digests. **0 scored outcomes and 0 order authority**. Later interrupted event `1791996600000` is **HOLD**, as required, and its absent/held evidence has not been rewritten. The user's planned service stop may explain a missing 5-minute slot; chronology alone cannot replace the evidentiary HOLD.

## Release and test plan

- Keep both VPS Git trees identical and clean on this integration branch; protect historical G1–G3 DB, WAL and off-host rollback archives.
- Run every `tests/test_v5_*.py` regression on BOTH hosts without starting any NBOT service. Additional tests cover G3 null feature HOLD, all 100 G4 held candidates, zero G5 science acceptance, G6 fitting blocked, two-book G7 initially locked, no order routes, and no auto-start/restart service templates.
- Offline imports, original-data read-only binding, static service review, targeted malformed/absent-source, coalescing, immutable DB and full regression runs are engineering evidence only.
- Never enable G1/G4/G7 units, G4 network capture, simulated fill engines or any Binance order API during integration.
- Subsequent owner-approved coordinated go-live can be considered only after G4 raw-source storage capacity risk, missing economic labels, science gates and release design are resolved; 24h real G1 source and forward market qualification cannot be simulated.

**Current decision:** G1–G7 source integration and cross-gate offline safety can be engineered and regression tested while remaining `scientific_release=HOLD`, `execution_authority=NONE`, `services=STOPPED`.
