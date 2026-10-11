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

Superseded work:
- PR #18 — closed/superseded; old ranking/calibration-only design.
- branch `feature/v4-ranking-calibration` is obsolete and may be deleted after confirming no needed unique work remains.

Merged V4 research factory:
- PR #19 — merged to `main`.
- merge commit: `215305ea55a288b14b5176fea7e11c781c127f15`.
- included clean V4 research factory, generation training, Telegram/status staging, and WSS continuity fixes.
- WSS fix regression: workflow `selective-ml-tests` run #142 — **success**.

Merged V4 paper contest:
- PR #20 — merged to `main`.
- tested head: `299f69400864b4c93d6f9813187d24a83e83b674`.
- merge commit: `856dedfdbadea87dec2af67247b3bd0d8794964b`.
- workflow `selective-ml-tests` run #147 — **success**.
- adds frozen-model paper examination, fresh contest epochs, explicit review, service wiring, and queue-safe generation semantics.

Current key V4 files:
- `nbot/observation/v4_research.py`
- `nbot/observation/v4_generation.py`
- `nbot/observation/v4_paper_contest.py`
- `deploy/observation/run_v4_research.py`
- `deploy/observation/run_v4_training.py`
- `deploy/observation/run_v4_paper_contest.py`
- `deploy/observation/v4_status.py`
- `deploy/observation/v4_paper_admin.py`
- `deploy/systemd/nbot-v4-research.service.in`
- `deploy/systemd/nbot-v4-training.service.in`
- `deploy/systemd/nbot-v4-training.timer.in`
- `deploy/systemd/nbot-v4-paper-contest.service.in`
- `tests/test_v4_research_factory.py`
- `tests/test_v4_paper_contest.py`

## Verified runtime milestone

The Observation/Learning VPS successfully reached the first V4 training threshold.

Verified research/training state after Batch #1:
- resolved valid virtual research trades: **1008**
- unresolved research paths: **492**
- active virtual research target: **100**
- Batch #1: closed and trained
- next training trigger: **2000 resolved**
- order authority: **NONE**

The unresolved total includes intentionally failed-closed paths from the earlier WSS continuity defect and one deliberate V4 service stop/restart. These records must remain preserved and excluded from valid training outcomes.

The repeated WSS bulk-invalidations were traced to shard-wide invalidation behavior. The merged fix:
- prevents bookTicker disconnects from destroying aggTrade research paths;
- scopes symbol-local market-data gaps to the affected symbol;
- retains fail-closed behavior for actual aggTrade continuity failures;
- logs WSS reconnect/error reasons explicitly.

After deployment of the fix, a live WSS reconnect occurred while the research cohort was active and:
- valid resolved outcomes continued increasing;
- active capacity returned to 100;
- no new `GAP_UNRESOLVED` event was recorded in the observed verification window.

## Generation 1

Verified Gen-1 record:

- generation: **1**
- batch: **1**
- training rows: **881**
- training events: **39**
- validation events: **8**
- validation mean net R: **-0.5581845994248907**
- validation positive rate: **0.25**
- qualification: **BASELINE_READY**
- artifact digest: `4e31059f5647d7961a46ca7c7873fbdc0e3881fefcaca610d54d3afee5ab0b46`

Verified generation state:
- `challenger_generation = 1`
- `champion_generation = None`

Interpretation:
- `BASELINE_READY` means Gen-1 is the first frozen provisional baseline eligible for paper examination.
- It does **not** mean the model is profitable, broadly validated, or a Champion.
- The validation sample is small and its observed metrics are weak.
- No automatic live-money authority follows from this state.

Generation qualification was corrected so:
- only Gen-1 may receive `BASELINE_READY`;
- Gen-2+ must pass the held-out Challenger gate even while no Champion exists;
- training a newer generation cannot overwrite an active Challenger paper exam.

## V4 paper Champion-vs-Challenger implementation

The paper examination layer is separate from the 100-slot virtual research factory and remains Observation-side with no exchange order authority.

Storage:
- `data/observation/v4/paper_ledger.db`
- `data/observation/v4/paper_contest.db`

Contract:
- frozen generation artifacts are loaded exactly from `generations.db`;
- all models use the same forward completed five-minute candidate universe;
- each examined model has at most one open paper position;
- public WSS manages the active paper path using after-cost integer-R trailing semantics;
- process/WSS discontinuities become unscorable and do not count toward the checkpoint;
- Gen-1 first runs a `BASELINE_EXAM`;
- once a Champion exists, each qualified Challenger starts a fresh `HEAD_TO_HEAD` epoch;
- Champion and Challenger both start each head-to-head epoch at 0 completed contest trades;
- old Champion results are never reused as its 100-trade proof against a new Challenger;
- each model requires **100 completed scored paper trades** in that contest;
- a model that reaches 100 first stops opening fresh paper positions while the other completes its checkpoint;
- when all required models reach 100, contest state becomes `REVIEW_REQUIRED`;
- promotion/rejection is explicit through `v4_paper_admin.py`;
- paper review never grants real exchange order authority;
- newer qualified generations remain queued behind the active contest.

The first Gen-1 baseline exam has not been claimed as completed or as a Champion in this handover. Deployment/runtime verification of the new paper-contest service remains the next operational step.

## Current operational boundaries

Confirmed intended services:
- `nbot-observation-live.service`
- `nbot-v4-research.service`
- `nbot-v4-training.timer`
- `nbot-v4-paper-contest.service` after its next Observation deployment

Old V3 two-tier research inside the raw Observation collector remains disabled with:
- `NBOT_TWO_TIER_RESEARCH=0`

Do not deploy the staged Telegram changes merely because the code is now in `main`; the prior decision remains to deploy those operator-surface changes with the first Champion deployment window unless the owner explicitly changes that decision.

## Next checkpoints

1. Deploy current `main` to the Observation/Learning VPS and install/start only the new V4 paper-contest service without disturbing the running V4 research/training services.
2. Verify Gen-1 begins a `BASELINE_EXAM`, with one-position paper behavior, WSS continuity, durable status, and `order_authority=NONE`.
3. Keep virtual research running independently toward 2000 resolved trades / Batch #2.
4. Do not promote Gen-1 merely for reaching 100 paper trades. At `REVIEW_REQUIRED`, inspect after-cost R, positive rate, drawdown, worst trade, side balance, elapsed future time, and regime coverage.
5. Only after explicit review may Gen-1 become the first paper Champion.
6. Future Gen-2+ candidates must pass research qualification before entering the queue.
7. Every later Champion-vs-Challenger comparison uses a fresh forward head-to-head epoch.
8. Real-money execution remains out of scope until explicit future authorization after substantial paper proof.

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

## Current small-VPS training safety limits

For the current ~1 GiB Observation VPS, V4 training is intentionally capped at:

- `CPUQuota=35%`
- `MemoryHigh=256M`
- `MemoryMax=384M`
- `Nice=10`

These limits protect the continuous Observation/WSS research process. If a future generation cannot train within these limits, prefer moving training to a separate VPS rather than starving real-time research.


## Telegram operator contract for the first Champion deployment

Do not deploy these Telegram changes to the VPS until the first V4 Champion deployment window.

The Execution Telegram surface remains intentionally small:

- `/status` — execution state, position, daily PnL, trade count, risk halt if any.
- `/position` — current position, entry, stop, risk, MFE/MAE.
- `/recent` — most recent completed trade, PnL/R, holding time, exit reason.
- `/pnl` — today's realized paper PnL, closed-trade count, halt status.
- `/learning` — V4-only research/model progress when V4 databases exist; legacy fallback only for an older deployment.
- `/enable` — allow new entries only after existing Execution safety/reconciliation checks.
- `/disable` — block new entries while open-position management continues.
- `/help` — concise command list.

Only `/enable` and `/disable` mutate entry state. Status and learning commands have no order authority.

### Force Telegram output to the channel

Use one bot token, but separate its input and output destinations:

```text
EXECUTION_TELEGRAM_CHAT_ID=-100<CHANNEL_ID>
EXECUTION_TELEGRAM_COMMAND_CHAT_ID=<PRIVATE_OR_OPERATOR_CHAT_ID>
EXECUTION_TELEGRAM_OPERATOR_USER_ID=<AUTHORIZED_USER_ID>
```

`EXECUTION_TELEGRAM_CHAT_ID` is the single outbound destination and must be the target Telegram channel. The bot must be an administrator of that channel with permission to post messages.

`EXECUTION_TELEGRAM_COMMAND_CHAT_ID` is input-only. Commands may be typed in the private/operator chat, but command responses are deliberately routed through the main channel dispatcher. Alerts, trade panels, command results, errors, and learning/status responses therefore all go to `EXECUTION_TELEGRAM_CHAT_ID`, not back to the command chat.

The command listener continues to require both the configured command-chat ID and authorized operator user ID, so posting to the public/output channel does not expand command authority.

### V4 /learning output

When V4 data exists, `/learning` reports only the useful V4 state:

- active virtual research slots / 100;
- completed outcomes and progress to the next 1,000-trade trigger;
- unresolved count;
- current batch / training-ready batch;
- Champion and Challenger generation IDs;
- latest generation qualification and compact validation summary;
- last persisted 5-minute cycle: closed, opened, active;
- `Order authority: NONE`.

The research factory persists only the latest bounded cycle summary for this operator view; it does not retain extra raw Telegram telemetry.


## V4 paper Champion-vs-Challenger implementation

The paper examination layer is implemented separately from the 100-slot virtual research factory.

Files:
- `nbot/observation/v4_paper_contest.py`
- `deploy/observation/run_v4_paper_contest.py`
- `deploy/observation/v4_paper_admin.py`
- `deploy/systemd/nbot-v4-paper-contest.service.in`
- `data/observation/v4/paper_ledger.db`
- `data/observation/v4/paper_contest.db`

Contract:
- frozen generation artifacts are loaded exactly from `generations.db`;
- no V4 paper component has exchange order authority;
- all models see the same completed five-minute candidate universe;
- each examined model has at most one open paper position;
- active paths use public WSS evidence and the same after-cost integer-R trailing policy;
- WSS/process discontinuities are recorded as unscorable and do not count toward the checkpoint;
- Gen-1 first runs a `BASELINE_EXAM` by itself;
- after a Champion exists, every qualified Challenger starts a fresh `HEAD_TO_HEAD` epoch;
- Champion and Challenger counters restart at zero for each head-to-head epoch so old Champion trades are not reused against a new Challenger;
- each model must complete 100 scored paper trades in that contest before the contest becomes `REVIEW_REQUIRED`;
- a model that reaches 100 first stops opening new paper trades while the other model finishes;
- promotion is never automatic and does not grant live order authority;
- explicit paper review uses `v4_paper_admin.py promote` or `reject` only after the contest is review-ready;
- newer qualified generations remain queued while a current Challenger is under examination.

Generation qualification is also frozen correctly:
- only Gen-1 may be `BASELINE_READY`;
- Gen-2+ must pass the held-out Challenger gate even if no Champion has been named yet;
- training a newer generation never overwrites an active Challenger slot.
