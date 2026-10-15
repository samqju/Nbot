# NBOT V5 — V4 Recovery Port and Research Pipeline Engineering Audit (14 Oct 2026)

**Status: offline-engineering progress, coordinated service release HELD.**

## Reviewed references and ancestry

- Original `nbot/observation/research_replay.py`: V4 incremental `_TickState` uses one mutable stop/peak/trough, aggregate-trade ID/time cursor and a gap latch, not a giant tick list. The original V4 time/stop policy and candidate selector **must not** migrate as economic authority.
- Original `nbot/observation/catchup.py`: no double processing, bounded batches, source freshness and worker locks. The original V4 training/selection quality contract is not imported.
- Original `nbot/observation/retention.py`, `epoch.py`: compact sealed evidence and per-epoch disposable workspace; **the V4 `prune_raw()` deletion of original events is expressly forbidden in V5.**
- Original `nbot/observation/v4_paper_contest.py`: immutable review outbox to recover across database boundaries, stale approval refusal and on-restart paper position reconciliation. G7 `GuardedPaper` currently keeps a default/restart LOCKED state and reconciles append-only paper books independently.
- V5 pinned base PR #44 `8296249fbe7546a19e0bdb665d9d5baa48bf1fd4`, derived from PR #39 `8de8b999465aaf1e75eac3d518dd3eedcfbb3fe8`. New branch `integration/v5-v4-recovery-bounded-pipeline-20261014`. Draft PR to be held unmerged.
- All 24 original V4 candidate hypotheses remain present in frozen `nbot/observation/candidate_setups.py` and V5 `pattern_adapter.py`. V4's incorrect premise of "more tags / highest relative rank => economically good entry" remains rejected.

## This branch — engineering changes

1. **Bounded G1→G4 original event catch-up:** `bounded_original_event_batch` selects up to three immutable five-minute event manifests through a persistent chain-of-custody cursor; an interrupted event is retried without duplicate candidates, and missing older historical events fail closed. `bounded_research_catchup` limits work to eight cycles and 120 seconds per invocation. G1 observation can continue independently.
2. **Bounded G4 maturity queue:** `bounded_pending_path_page` uses a durable indexed seek cursor rather than fully materializing a potentially enormous pending label population; at most 250 pending intents examined per page. Interrupted cursor advancement cannot imply economic scoring.
3. **V4-inspired constant-memory incremental original G4 trade replay:** `original_segment_price_path` independently verifies every compressed source segment, aggregates ID/trade-clock continuity, risk/stop/target/horizon, and returns only GROSS ORIGINAL PRICE PATH evidence. Gapped/restarted/tampered original data is held; no net return, fill, training authority or order.
4. **Independent original G4 quote streaming:** `VerifiedSegmentQuotes` checks original compressed public WSS receipts for up to 300 frozen candidate as-of requests without a 100,000-frame temporary SQLite materialization cap. A separate real-market-independent bounded small-view bridge remains as a fallback.
5. **Research stage integration:** The G4 candidate-intent registrar uses independently verified as-of quote witnesses and the streaming gross-path verifier when the temporary RAM SQLite view exceeds its cap. All 100 full two-sided original candidates are retained or explicitly HELD. Scored source-qualified after-cost outcomes remain zero until separately authenticated proof exists.
6. **Manual-only G4 public collector template:** New `deploy/v5/nbot-v5-g4-source-capture.service` depends on the active G1 observer, requires an *absent by default* owner-release marker, and uses a strict read-only frozen G1 cohort + compressed archive preflight. `Restart=no`, no `[Install]`, no private exchange credentials. **Not installed, enabled or started.**
7. **No forced six-hour disconnect:** The G4 source runner supports explicit owner-approved continuous observation with `--continuous-observe --max-seconds 0 --max-frames 0`, but *only* public, segmented, sustained acquisition, still bounded by disk quota, 750,000 frames/5min and finite reconnect/checkpoint guards. This is not infinite unbounded storage, scientific acceptance or a guarantee of 24-hour survival.
8. **Regression fixtures:** 25k-event catch-up pagination, partial candidate crash/restart; 550 active intent seek/wrap; 50-coin incremental no-tick-SQL replay and stop/target before/after missing original source; tainted gzip/epoch HOLD; complete-100-candidate quote admission beyond legacy RAM replay cap; frozen G1 cohort and owner-gated G4 manual unit; continuous WSS mock checkpoint/rate/reconnect HOLDS.

## Scientific qualifications still pending (not engineering PASS)

- A production-capacity / rollover and off-host evidence custody plan beyond the hard 8GiB original G4 compressed archive cap. Never silently purge or compact original source into unverifiable summary. 50-coin full-rate throughput must be measured once owner-approved without destroying gaps.
- Independently proven original EXIT bid/ask, fee tier, contemporaneous spread/slippage and settled funding, plus independently authenticated export/reviewer process. Current G4 price-path replay **is gross-only**; existing `accept_verified_export` requires reviewed original full economics. Its absence means **no genuine qualified G5 labels are generated automatically**. Do not weaken proof to meet a sample target.
- Declarative G4 prospective risk policy/activation clock, G5/G6 original protocol, cohort manifest and release-pinned config files still need checked owner adoption. No retrospective parameter fitting.
- G1 actual 24h continuous-source soak, G2/G3 prospective integrity, G4 4h+ original path maturation, G5 first 2,000 independent mature after-cost qualified events, G6 additional nonoverlapping qualified Challenger evidence and G7 authenticated paper release can begin only through staged scientific/operational qualification.
- Authoritative owner-approved roadmap §§17–26 allows an initial baseline paper Champion after the FIRST qualifying 2,000 outcomes, with Challenger after a separate 2,000. Current locked `GuardedPaper.unlock` requires two qualified models. This governance/design mismatch needs explicit reviewed disposition; **do not reduce the two-model authentication requirement silently**.
- G1 installed Observation service currently disabled/inactive and its approved-code SHA pin points at an OLD commit. New source release must be separately pinned and its supplied config/protocol validated before manual startup.
- G4/G7 research and paper service templates are not installed; no owner-release markers, G4 frozen manifest, approved research registry or protocol are presently provisioned. No observer should start prematurely under an incorrect pin, incomplete source cohort or lack of prospectively declared policy.

## Release and data-protection rule

This is *source-only deployment*, no activation. Both VPS source paths are canonical `/home/ubuntu/Nbot`; preserve immutable original G1/G2/G3 data, V4 archives and protected `/home/ubuntu/nbot-final-reset-20261014` off-project snapshots. No resetting databases, force merging PRs, unreviewed `main` updates, installing legacy V4 systemd units, auto training authority, paper orders or live Binance orders.

Once code passes the final full V5 suite and production preflight, an **owner-controlled observation/research startup** may proceed with a separately approved SHA + prospective policy and capacity plan. G7 health can remain LOCKED, but paper submissions and all real order capability remain independent, explicit future authorizations. Passage of a 24-hour window is not itself acceptance.
