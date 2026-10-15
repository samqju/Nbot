# NBOT V5.1 — Your Plain-Language Development Roadmap

**Roadmap version:** 1.0  
**Date:** 15 October 2026  
**Status:** A new beginning — planning and safety checks only; no trading authorization  
**Product blueprint:** NBOT Complete Product Vision **V1.9** (separately copied **unchanged** into this branch)  
**Companion:** NBOT V5.1 Engineering Roadmap V1.0  
**Repository/branch:** samqju/Nbot / nbot-v5.1

## 1. The plan in one minute

We want to build one reliable crypto-perpetual trading system that can **watch, investigate, learn, train, compare strategies, and make selective decisions** without carrying old, unused NBOT code into the new project.

Our agreed loop:

1. **Observation:** Look at the market, especially BTC and the overall conditions.
2. **Exploration:** Study coin movements and price structures; note what the 24 original detectors find.
3. **Research:** Run scientifically controlled virtual trades to find out what actually happened afterward, after realistic costs.
4. **Learning:** Discover which conditions have genuine evidence of better or worse outcomes.
5. **Training:** Turn trustworthy findings into a frozen, testable trading model.
6. **Promoter / Retainer:** Fairly compare the existing Champion and any Challenger; recommend which to keep.
7. **Trading Decisions:** Select LONG, SHORT or NO TRADE, subject to independent safety checks.

**Feedback** brings verified results back to Research and Learning. It is not an eighth heavy service.

**Most important promise:** A model cannot create its own permission to trade real money.

## 2. The simple numbers we are designing for

| Item | Our preferred target | What it really means |
| --- | --- | --- |
| Broad watchlist | **Up to 100 coins** | Light market scanning, not a heavy tick archive for all 100 |
| Sources of interest | **Top-volume, top-gaining and top-losing coins** | Discovery categories, not automatic buy/sell signals |
| Deep research watchlist | **Up to 20 coins including BTC** | Reliable detailed prices and evidence for scientific research |
| Exploration directions | **LONG and SHORT** | As many as 40 distinct deep-coin directional possibilities |
| Active virtual research | **Maximum 40 at a time** | A rolling pool, not 40 new trades every five minutes |
| New virtual research | **Only when a verified slot opens** | Review completed five-minute candles and fill with suitable candidates; no fixed eight-new-trade limit |
| Model/paper portfolios | **Champion and Challenger, separately** | Two paper books, normally at most one simulated open position in each |
| Future live exposure | **At most ONE actual position globally** | Pending/unknown orders may also occupy the slot |
| Fast trade monitoring | **Lightweight, while a trade is open** | Stops and trailing stops react to incoming valid prices without storing every message as a database row |
| Detailed new decisions | **After a completed five-minute candle, when a relevant slot is available** | Do not force a trade; heavy Exploration can rest when unnecessary |

These are design goals, **not claims that the old program already supports them**. We will measure if the two small VPSs can reliably handle them.

## 3. How this new branch stays clean

**We are not copying the previous NBOT program into V5.1.** The new branch begins with only the product Vision and two roadmaps.

The earlier branches and GitHub history remain available as a library of examples. We may later bring across only an individually inspected and tested component, such as a useful V4 detector or a V5 source-validation function. That component must earn its place in V5.1.

We will avoid: unused experiments, old competing strategy engines, duplicate price collectors, mixed virtual/paper/real accounts, and code that secretly connects to real trading.

**Baseline means taking an inventory of the old system, not copying it.**

## 4. The roadmap you can follow without being a developer

The boxes below start uncompleted. **No stage is marked DONE merely because some old V4/V5 code or tests already exist.**

| Milestone | In plain English | What you should see before we call it complete |
| --- | --- | --- |
| **0. Protect what exists** | Preserve our old NBOT; agree on permissions and the new clean documents. | Old branches/services/data unchanged, new branch documents verified |
| **1. Examine the old tools** | Inspect V4 and V5 and decide what is useful. | A simple KEEP / REBUILD / DISCARD / UNKNOWN list with reasons |
| **2. Make the clean skeleton** | Create simple boundaries for data, research, models and safety. | Small reviewed new files, tests passing, no order or VPS authority |
| **3. Observe 100 coins lightly** | Gather trustworthy completed candles and BTC/market conditions. | Source times, missing-data flags, and measured CPU/RAM use |
| **4. Explore opportunities** | Apply causal price-structure observations and the 24 original detectors. | Clear coin, BTC, LONG/SHORT and detector records; no hidden guesses |
| **5. Select 20 research coins** | Choose a mix that can actually be investigated properly. | Transparent reasons for the 20 selections and their source readiness |
| **6. Run the rolling 40 virtual pool** | Follow up to 40 hypothetical trades and replace proven vacancies after each five-minute close. | No extra active trade; no invented wins; accurate stop/trailing-stop timing |
| **7. Protect data and recover** | Handle internet outages, crashes, source gaps and full disks without misleading Learning. | Restart tests showing what was recovered, what remains unknown and why |
| **8. Learn from verified evidence** | Identify trustworthy conditional after-cost advantage; admit NO TRADE. | Research findings with uncertainties, sample sizes and evidence sources |
| **9. Train the first model** | Produce a frozen candidate strategy from truly qualified outcomes. | Version, independent validation and explanation of when it abstains |
| **10. Start approved PAPER-only testing** | Let the first qualified Champion make simulated decisions behind safety checks. | Paper results, correct fees/risks, no real orders |
| **11. Test a Challenger** | Compare two frozen models on the same later market period. | Fair paper books, risk comparison and a retain/promote/hold recommendation |
| **12. Verify end-to-end behavior** | Show the entire loop works under mistakes and heavy loads. | Transparent test evidence and a written GO/HOLD review |
| **13. Consider live trading — only if you explicitly choose it** | Decide whether the system may someday use real funds. | A completely separate consent, risk review, release and rollback plan |

### Milestone 0 — Preserve what exists

**First:** No deletion or cleanup of older code, data or evidence. Do not touch the laptop. Do not start or restart VPS services or place paper/real orders. The clean development branch contains documentation only until you authorize new code work.

**Finished when:** The documents are present, their contents are verified, and the new branch's current file list contains no legacy program files.

### Milestone 1 — Examine, don't import

Examine the earlier V4/V5 pattern detectors, exchange data collectors, database/evidence checks, paper accounting, risk controls, experiment results and release gates. Make a short recommendation for each useful piece.

**Finished when:** You understand what will be reused and what will be freshly written, with no silent copying.

### Milestones 2–5 — Build the eyes and research shortlist

Start with safe read-only data and realistic interruptions. Observe up to 100 liquid and source-qualified coins chosen from high volume, gainers and losers. Explore structures and both directions without concluding that the biggest gainer is a BUY or a match among the 24 detectors proves profit. Research then selects up to 20 coins (including BTC) for deeper original-source evidence.

**Finished when:** We can reproduce who was eligible, who was selected, every observation's timing, which source was missing and why a coin was rejected.

### Milestone 6 — The 40 active virtual-trade pool

This is your corrected design:

- At most 40 simultaneously active virtual experiments, initially at most one per coin and direction.
- Prices are watched cheaply while a trade is active. Stops and trailing stops may be hit before the five-minute close.
- After each completed five-minute candle, reconcile actual closures and free slots.
- Research fills only free slots for which a new eligible opportunity exists.
- An empty slot can remain empty. No artificial target of eight new trades or 40 new trades every five minutes.
- Original trade and quote evidence, after-cost accounting and interrupted-data labels must be preserved so Learning cannot mistake a simulated guess for a verified result.

**Finished when:** Restart tests and source audits prove the count never exceeds 40 and that a missing price interval cannot magically generate a winning trade.

### Milestone 7 — Recovery and practical storage

The bot should hold only a small rolling state in RAM and avoid one SQLite write per WebSocket price update. It should preserve necessary original evidence in bounded, compressed, independently checked batches.

Historical Binance data can help rebuild closed candles and possibly missing aggregate-trade sequences. **One-second candles, if verified as available for the exact Futures endpoint and period, can aid recovery but cannot always prove which stop or target came first within the second.** Uncertain outcomes must stay unresolved or lower-grade. Record disk quotas and verify a source archive before any indefinite recording.

**Finished when:** A crash, gap or full disk cannot turn missing evidence into fake profit.

### Milestones 8–9 — Evidence and the first model

Start by comparing outcomes with a NO TRADE baseline. Learn by BTC regime, coin structure, side, pattern evidence, liquidity and realistic costs. Avoid counting many correlated coin moves as independent successes.

**The existing vision describes an initial checkpoint of 2,000 genuinely qualified matured research outcomes. This is a review threshold, not a promise of profitability.** Train only after the quality tests pass; validate on later data not used for training. A weak model may be rejected and NO TRADE may remain correct.

**Finished when:** A frozen model has independent scientific evidence—not just attractive historical results.

### Milestones 10–11 — Paper testing, not real funds

The first independently qualified Champion should be allowed into **paper only after a separate approved release**. The earlier V5 implementation has a known mismatch between the intended first-Champion-paper roadmap and a G7 check demanding two models. We must review and resolve that difference before paper release; do not bypass it.

Later, create a frozen Challenger and compare both on one common forward period with separate paper accounts, realistic after-cost accounting and comparable risks. Stage 6 may **recommend** promotion, but cannot silently make a model live.

**Finished when:** We have convincing forward paper evidence and independently verified controls, not merely passing unit tests.

### Milestone 12 — Demonstrate the complete loop

Test the whole sequence on **synthetic/offline inputs first**, with that evidence clearly labeled as synthetic. Test source gaps, missing quotes, conflicting candle records, restarts, rate limits, disk pressure, stale model versions and model abstentions. Measure the real two-VPS workload only under a separately approved read-only test plan.

**Finished when:** We can show one understandable report that explains every stage, every failure and the current HOLD/GO status.

### Milestone 13 — Real trading stays locked

The guardian must be able to independently reject a proposal and enforce the one-real-position rule. A good research model or paper result does **not** create real-money permission. A real trading project would need your fresh, explicit approval, suitable risk controls, exchange reconciliation and independent release testing.

**Finished when:** Only if and when you authorize that completely separate phase.

## 5. What happens if something goes wrong?

| Problem | NBOT should do |
| --- | --- |
| Market source, BTC condition or quote is missing | Say SOURCE HOLD / NO TRADE; do not guess |
| The VPS or WebSocket disconnects | Record the gap, recover what can be independently proven, and leave questionable outcomes unresolved |
| Price hits a virtual stop between five-minute candles | Record the evidence-supported time; do not move the exit to the candle close |
| Full virtual pool | Continue cheap tracking; skip unnecessary heavy new-candidate work until a slot is available |
| A virtual experiment closes | Make the slot eligible for reassignment at the next reviewed completed five-minute event |
| No suitable new opportunity | Leave the slot vacant |
| An open paper position exists | Keep its stop and accounting monitored; do not open a second in that paper book |
| Disk, RAM or CPU is under pressure | Stop nonessential investigation first; protect source integrity and position safety |
| A model performs poorly or the two models' comparison is unclear | HOLD/RETAIN/SUSPEND; no forced "winner" |
| Old model or unauthorized code tries to open a real trade | Guardian VETO and no real order |

## 6. How will you know we are really progressing?

At the end of each milestone, request a compact progress report answering:

1. **What changed?** Exact GitHub branch, files and commit, or "nothing changed."
2. **What was reused and why?** Identify exact old source and the tests.
3. **What passed?** Tests and measured results, not optimistic summaries.
4. **What failed or is still unknown?** Especially original-price evidence, source recovery and real costs.
5. **What is our current allowed mode?** Documentation / offline only / separately approved paper / separately approved future real.
6. **What is next?** The smallest safe step, and whether your approval is needed.

**A milestone can be marked PASS only with evidence.** Otherwise it is TODO, WORKING, BLOCKED or HOLD.

## 7. Permissions and boundaries

- **Never touch the user's laptop**, local files, Downloads folder or desktop.
- Keep **old GitHub branches, source files, DB evidence and existing pull requests intact**.
- Development belongs to this separate clean NBOT V5.1 branch; do not merge to default without explicit approval.
- Do not inspect or change VPS state, run remote commands, restart services or read secrets unless the owner separately authorizes those actions. Inspection may be read-only only with that authorization.
- Do not place real orders, enable real execution, access real credentials or assume the owner approved paper trading by approving this roadmap.
- Use GitHub commits with small, testable changes and provide links and plain-English explanations.
- A historical synthetic test pass is not qualified real-market source evidence.
- We do not claim a strategy is proven profitable; we require defensible conditional after-cost evidence and ongoing verification.

## 8. First development session — our actual next action

**The first task after creating this documentation-only branch should be an inventory, not a file import:**

- Read-only review of the existing GitHub V4/V5 files, branch map and relevant tests.
- Draft a **Legacy Component Reuse Register** with columns: function, old file/version, evidence, safe reuse or rebuild recommendation, dependencies and risk.
- Map the V1.9 blueprint to the engineering roadmap's acceptance gates.
- List the very first **new clean** implementation files proposed, without writing them until authorization.
- Report source-fidelity, 100-versus-old-50, first-Champion paper and storage/recovery conflicts clearly.

**Success means we understand the legacy accurately and have preserved it.** No code import is needed to reach this milestone.

---

**Owner's guiding statement:** NBOT V5.1 should be **small enough to understand, cautious enough to trust, and able to improve from authentic evidence**. An empty trade slot and NO TRADE are perfectly legitimate outcomes.
