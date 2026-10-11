# NBOT V4 Handover — Final Architecture and Deployed State

Last updated: 2026-10-11

## Purpose

This document is the continuity record for NBOT V4. It captures the architecture agreed with the user, what is already deployed on the Observation/Learning VPS, and what remains to be proven before later Champion/Challenger or live-trading stages.

## Core architecture

NBOT V4 is a continuous research-and-learning system with two asynchronous clocks:

1. Research/training continuously collects and learns from virtual research trades.
2. Promotion/evaluation separately decides whether a newly trained model is good enough to challenge or replace the current Champion.

Research never stops because a Champion exists.

## Virtual research book

- Target capacity: **100 concurrent virtual research trades**.
- Entries/refills occur only at a completed **5-minute candle boundary**.
- WSS manages all active virtual research paths continuously.
- If trades close during the candle, they are **not refilled immediately**.
- At the next 5-minute boundary:
  1. Count currently open research trades.
  2. Compute free slots = 100 - open_count.
  3. Generate fresh candidates from the completed 5-minute snapshot.
  4. Exclude already-running symbol+side combinations.
  5. Rank remaining eligible candidates.
  6. Open only enough to fill available capacity.
- Never open a fresh full batch of 100 every candle.
- If fewer eligible candidates exist than vacancies, unused capacity is acceptable.
- LONG and SHORT for the same symbol may coexist.
- Same symbol+side may not be duplicated while already running.

Example:

100 active -> 4 close -> remain 96 until next 5-minute boundary -> open 4 fresh candidates -> return to 100.

## Research-trade semantics

A **virtual research trade** is not a paper trade and not a live trade.

Virtual research trades:
- are counterfactual/hypothetical;
- may overlap freely;
- are not constrained by real portfolio capital;
- use real observed public market/WSS data;
- are used for learning.

A **paper trade** is a strategy-selected trade passed through realistic paper portfolio constraints.

A **live trade** is an actual exchange order and remains Execution-VPS-only after separate future authorization.

## Research outcome memory

Each completed virtual research trade should preserve compact long-term research evidence, including as applicable:

- symbol / side
- entry decision timestamp
- generation/model/criteria version
- rank / selection metadata
- immutable entry feature vector or digest
- market regime / broader context
- entry price
- stop and 1R definition
- MFE / MAE
- path timing metrics
- exit timestamp / exit reason
- fee/slippage/funding assumptions
- final after-cost net R
- source/evidence digest

The permanent ML memory is the compact completed research record, not unlimited raw WSS tick history.

## Training cadence

- **1,000 completed V4 virtual research trades = one retraining trigger.**
- Reaching 1,000 does not automatically create a Challenger.
- Each 1,000-trade batch trains a candidate generation.
- Candidate must pass protected research validation to become a Challenger.
- Generation 1 is the first provisional baseline model.
- Later generation numbering should use Gen-1 / Gen-2 / Gen-3 or V4_MODEL_GEN_001 style, avoiding old V1/V2 naming confusion.

Research batches and model generations do not have to map 1:1 if a candidate fails qualification.

## Challenger qualification

A newly trained candidate should only become a Challenger if protected validation shows meaningful improvement or meaningfully broader competence.

Relevant criteria include:
- better ranking of winners vs losers;
- better after-cost expected R;
- fewer bad selections;
- better positive-outcome rate;
- better behavior across regimes;
- no collapse on LONG or SHORT;
- no apparent improvement caused by one lucky time block;
- acceptable drawdown / tail-loss behavior;
- sufficient calibration/support.

A model can also qualify because it handles a newly observed important regime materially better than the Champion.

## Champion vs Challenger

- Primary paper comparison checkpoint: **100 completed strategy paper trades per model**.
- 100 trades is a checkpoint, not an automatic promotion trigger.
- Promotion should also require enough elapsed future time, independent market periods/regime diversity, after-cost performance, drawdown/tail behavior, consistency, and robustness.
- Champion and Challenger may maintain separate realistic paper books.
- They do not need identical entry timestamps; abstention and holding time are part of the strategy.
- Both should still log decisions against the same candidate universe/timestamps when possible for paired decision-quality analysis.
- Challenger is frozen during its exam.
- Research continues while the exam runs.
- Newer candidates may queue behind the current Challenger.
- A newer model never gets authority merely because it is newer.

## Asynchronous generation/promotion

Expected pattern:

Champion: Gen-1
Testing: Gen-2
Waiting/research-qualified: Gen-3, Gen-4, ...

Research/training can move faster than promotion/evaluation.

## Early-regime limitation

The first 1,000 research trades may occur in a narrow regime, e.g. a bullish period.

This is acceptable because:
- Gen-1 is provisional, not final truth;
- continuous research later adds sideways/bearish/high-vol/low-vol experience;
- later challengers are trained with broader accumulated evidence;
- Champion-vs-Challenger lets newer brains replace older regime-biased ones;
- abstention under weak regime support is desirable.

Research should continue indefinitely rather than stop after a month or after a Champion exists.

## Resource strategy

Resource assumptions:
- Champion/Challenger inference is relatively light.
- 100 active WSS research paths should be comparatively light if managed centrally.
- Data storage is primarily disk/I/O.
- Feature generation is moderate CPU.
- Model training is the main burst CPU/RAM workload.

Rules:
- Do not create one WSS/thread/process per trade.
- One central public WSS feed should update all active research paths.
- Real-time research/WSS capture has priority over training.
- Training runs separately and is resource-limited.
- If training begins interfering with Observation, move training to a separate VPS before enlarging Execution.
- Do not train future generations from unlimited raw tick history.
- Keep long-term compact research records and use bounded/stratified training memory as data grows.

## Safety / authority

- Observation/Learning VPS has **no Binance order authority** for V4 research.
- Current V4 research/model state uses `order_authority = NONE`.
- Execution VPS remains the only future component allowed to place real orders.
- Real-money trading requires a separately proven Champion and explicit future authorization.
- Do not infer real-money authorization from paper/research success.
- Current user authorization remains paper/research only.

## Storage

V4 clean namespace:

- `data/observation/v4/research_ledger.db`
- `data/observation/v4/research_meta.db`
- `data/observation/v4/generations.db`

Existing V2/V3 databases are retained for audit/rollback and are not V4 model-training inputs:

- `data/observation/live/observer.db`
- `data/observation/live/decision_outcomes.db`
- `data/observation/live/research_memory.db`

Do not delete/reset these databases.

## GitHub / deployment state

Repository: `samqju/Nbot`

Old draft:
- PR #18 — closed as superseded.

Current V4 branch:
- `feature/nbot-v4-research-factory`

Current replacement PR:
- PR #19 — V4 clean-slate research factory.

Known-good branch head after import-path fix:
- `afa01c70bc290198ad7b19dd4968fa39eec4f61f`

GitHub CI for that exact SHA:
- workflow `selective-ml-tests`
- run #129
- conclusion: **success**

Key V4 files:
- `nbot/observation/v4_research.py`
- `nbot/observation/v4_generation.py`
- `deploy/observation/run_v4_research.py`
- `deploy/observation/run_v4_training.py`
- `deploy/observation/v4_status.py`
- `deploy/systemd/nbot-v4-research.service.in`
- `deploy/systemd/nbot-v4-training.service.in`
- `deploy/systemd/nbot-v4-training.timer.in`
- `tests/test_v4_research_factory.py`

## Deployed Observation/Learning VPS state

Confirmed deployed and enabled:
- `nbot-observation-live.service`
- `nbot-v4-research.service`
- `nbot-v4-training.timer`

Confirmed active:
- all three above.

Old V3 two-tier research inside the raw Observation collector is disabled with:
- `NBOT_TWO_TIER_RESEARCH=0`

V4 initially demonstrated the exact intended refill behavior:

- first cycle opened 100 virtual research trades;
- next observed cycle matured 4;
- exactly 4 fresh research trades were opened;
- active book returned to 100.

Latest user-reported V4 status in this conversation:

- capacity: 100
- open_pending: 100
- resolved: 35
- unresolved: 0
- next_training_at: 1000
- research_batches: []
- Champion: none
- Challenger: none
- order_authority: NONE

Therefore, at this handover point:
- **35 V4 virtual research trades have completed successfully**;
- **100 virtual research trades are currently open**;
- **0 are unresolved**;
- no V4 model generation exists yet because the first 1,000-trade threshold has not been reached.

## Next checkpoints

1. Keep V4 research running; avoid unnecessary Observation restarts because active WSS research paths are in-memory and restart breaks their exact chronology.
2. Monitor:
   - resolved count;
   - unresolved count;
   - whether active book stays near 100;
   - CPU/RAM;
   - WSS stability;
   - DB growth.
3. At `resolved >= 1000`:
   - verify Batch #1 closes correctly;
   - verify resource-limited training runs;
   - inspect Gen-1 training/validation artifact;
   - do not assume Gen-1 is automatically a broadly proven Champion.
4. Only after Gen-1 exists should the paper Champion stage be wired/validated.
5. Subsequent 1,000-trade batches train candidate generations; only research-qualified candidates become Challengers.
6. Champion-vs-Challenger paper comparison target remains ~100 completed strategy trades per model plus time/regime/risk robustness gates.
7. Real-money execution remains out of scope until explicit future authorization after substantial mainnet paper proof.

## Useful status commands

V4 status:

```bash
cd /home/ubuntu/Nbot
/home/ubuntu/Nbot/.venv/bin/python deploy/observation/v4_status.py
```

Recent V4 cycles:

```bash
journalctl -u nbot-v4-research.service --since "1 hour ago" --no-pager | grep V4_RESEARCH_CYCLE
```

Service health:

```bash
systemctl is-active nbot-observation-live.service
systemctl is-active nbot-v4-research.service
systemctl is-active nbot-v4-training.timer
```
