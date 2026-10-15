# NBOT V5.1 — Your Plain-Language Development Roadmap

**Roadmap version:** 1.1  
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

### How we will actually copy the useful parts from older branches

**Yes, we must deliberately copy proven, necessary code from older NBOT GitHub branches into new V5.1 files**, rather than re-create everything for no reason. But **we will NEVER bulk-copy the whole old application**.

For each reusable item we will:

1. **Find it:** Record its old branch, exact GitHub commit and original filename/function.
2. **Understand it:** Check what the code really does, whether it depends on abandoned files, whether it touches trading/accounts, and whether its old tests were trustworthy.
3. **Choose:** Mark it **Copy and adapt**, **Rewrite simply**, **Discard**, or **Keep only as reference**, explaining why.
4. **Bring over only what is needed:** Put approved code into **new, clean V5.1 files** on our new branch. Do not change or delete the original.
5. **Prove it works:** Run safe offline tests, including errors/restarts and the new Vision V1.9 requirements.
6. **Tick it:** Immediately mark that small task complete **[x]** once its evidence passes, record its new GitHub commit, and then move to the next task.

**Example:** We might inspect a V4 pattern detector, copy the useful detection logic into a newly designed V5.1 pattern module, remove unused strategy/order dependencies, and prove it uses only completed candles. The original V4 file stays unchanged. The checkbox for that *one detector's reviewed transfer* can be ticked as soon as its tests pass—even if the full Exploration milestone is still incomplete.

### Our rule for ticks — every small task and every big milestone

- **[ ] Not complete.** Includes in progress, awaiting review and HOLD; a separate note explains blockers.
- **[x] Completed and verified.** Record the exact GitHub code commit, relevant test/review evidence and date.
- **Never wait for a big stage to finish** before ticking each successfully completed little task.
- **Never tick a big milestone** until its required smaller tasks AND the milestone's final acceptance tests have passed.
- **Never inherit a PASS** solely because something worked in an old V4/V5 branch.
- At the end of every development session, update **both roadmaps**, explain changes in ordinary language, and name the next unticked task.
- If a past PASS later proves wrong, reopen and untick it with a clear reason; do not hide a regression.

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

**Historical initial instruction, updated 15 Oct 2026:** We began without touching old code or data. The owner now explicitly **waives backups of old-version NBOT files on both VPSs and accepts their permanent loss** as part of a fresh start. No backup or cleanup was actually performed in G0-03. Keep historical GitHub branches as reusable source references. Never damage SSH/OS/unrelated files, or infer paper/real trading authority from this waiver.

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

## 4A. Your live NBOT V5.1 checklist — small jobs and big milestones

**This is the main owner-facing progress tracker.** The detailed engineering roadmap contains matching technical **G0–G12** tasks, all with their own tick boxes and proof register. Add any newly discovered small task to both appropriate roadmaps. A tick is only legitimate when its test/review evidence is recorded.

### Initial branch and documentation

- [x] **START-01:** New nbot-v5.1 branch created with **only three documents**, no imported old application files — verified from GitHub tree on 15 Oct 2026 (commit **472c3f54415e06715f8b28673eee7d3b545338d4**).
- [x] **START-02:** Complete Vision V1.9 copied unchanged and both roadmaps created — GitHub verified on 15 Oct 2026 (same commit).
- [ ] **Milestone 0 — Old NBOT preserved and safely assessed** (engineering G0)
  - [x] Identify the important historical branches, files and tests without changing them — initial read-only GitHub inventory, 15 Oct 2026; reuse register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; documentation/source inspection, no tests run.
  - [x] Confirm which old components may be useful or risky — 27 preliminary candidates reviewed, 15 Oct 2026; same register/commit; source and test-file review only.
  - [x] **G0-03 assessment:** Inspect both VPSs, preserve old data, record stopped services, storage/RAM, proof files and backup gaps; document rollback steps — completed 15 Oct 2026, assessment commit **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28**; **no cleanup or backup restoration conducted**.
  - [x] **G0-03-R1 owner decision:** Old NBOT VPS backups/restoration **explicitly waived as NOT NEEDED** — **not performed, not falsely passed**. Owner accepts loss of old SQLite/WAL, paper receipts, V3.9 artifacts and old runtime data; recorded 15 Oct 2026, waiver commit **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**.
  - [x] **G0-03-R2 owner decision:** Permission to discard old NBOT-only material from both VPSs without backup granted 15 Oct 2026; **no cleanup was executed in G0-03**. Avoid OS, SSH, non-NBOT files and historic GitHub branches.
  - [ ] **G0-03-CLEANUP-EXEC (separate action):** Actually remove specifically verified old NBOT VPS-only files/services if needed for deployment, then record exact before/after results. Not required to call G0-03 assessment complete.
  - [ ] Present final component-by-component risk review and obtain specific approval before the first V5.1 application-code port; G0-01 approved documentation only.
- [ ] **Milestone 1 — Detailed list of code to copy/rebuild finished** (engineering G0)
  - [x] List old V4 detectors, market-data tools, research evidence checks, paper book and risk protections with pinned source links — 15 Oct 2026, register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**.
  - [x] Give each an easy choice: **COPY / REWRITE / DISCARD / REFERENCE** with the reason — register entries R01–R27; source inspection only.
  - [x] Identify conflicts between previous NBOT and Vision V1.9 — conflict register C01–C12, including obsolete V3/V3.9/V4/V5 runtime references.
  - [x] Verify the selected **pure first helpers**: exact old source/test blob hashes, complete selected-function imports/calls, excluded SQLite/old-version side effects and missing/required *future* tests — 15 Oct 2026, audit commit **2ebcc62f9f13aa4c7ed532cca108d9c359c77363**. This is an inspection PASS, not a code/test execution PASS.
  - [ ] Agree on the first safe, approved component to copy into V5.1; G1-01 pure contracts are recommended but not yet individually approved.
- [ ] **Milestone 2 — Our new clean program foundation works** (engineering G1)
  - [ ] Approve a simple new directory/module layout.
  - [ ] Copy/rebuild just the required first helpers, not their old unused dependencies.
  - [ ] Pass offline smoke, source and no-trading safety tests.
- [ ] **Milestone 3 — Observe up to 100 coins** (engineering G2)
  - [ ] Choose eligible high-volume, top-gaining and top-losing coins with no duplicates and BTC always included.
  - [ ] Reliably record completed five-minute candles and detect missing/old information.
  - [ ] Test on simulated 100-coin market data and measure resource requirements.
- [ ] **Milestone 4 — Explore structures and directions** (engineering G3)
  - [ ] Verify/copy the required original **24 pattern detectors** safely, one reviewed item at a time.
  - [ ] Describe BTC conditions and each coin's trend and price structure using information known at the time.
  - [ ] Produce honest LONG, SHORT, unavailable and skipped-capacity labels; pass the accuracy tests.
- [ ] **Milestone 5 — Select the 20 deeply researched coins** (engineering G4)
  - [ ] Write fair selection rules based on tradability, structure, previous evidence and variety.
  - [ ] Keep BTC and record why every chosen or excluded coin was selected or rejected.
  - [ ] Check original market/quote sources and prove source quality plus storage capacity.
- [ ] **Milestone 6 — Rolling maximum-40 virtual-trade pool works** (engineering G5)
  - [ ] Freeze each experiment's direction, entry, exit, stop, trailing and duration policy.
  - [ ] Track stops/targets at the actual price-event time without storing every message in SQLite.
  - [ ] Every five minutes, verify which trades finished and reuse ONLY genuinely available slots for suitable new opportunities.
  - [ ] Pass limits, simultaneous exits, no-opportunity, restart and trailing-stop tests.
- [ ] **Milestone 7 — Crash recovery and true after-cost results work** (engineering G6)
  - [ ] Verify original price, quote, fee, slippage and funding evidence needed to score research.
  - [ ] Recover trusted history after failures; never invent wins from missing seconds or unsupported 1-second candles.
  - [ ] Verify compressed source storage, archive/restore and safe disk quotas.
- [ ] **Milestone 8 — Reliable Learning works** (engineering G7)
  - [ ] Separate valid matured outcomes from pending, synthetic, incomplete or ambiguous observations.
  - [ ] Check results under different BTC/market conditions while accounting for overlapping coin moves.
  - [ ] Meet and review independent evidence-quality checkpoints or explicitly record HOLD.
- [ ] **Milestone 9 — First qualified trained strategy works** (engineering G8)
  - [ ] Train only on earlier qualified outcomes with a frozen data cutoff.
  - [ ] Test the model on later untouched periods and against doing no trade.
  - [ ] Record a repeatable model version or reject it if evidence is weak.
- [ ] **Milestone 10 — First approved Champion PAPER testing works** (engineering G9)
  - [ ] Resolve the old V5 conflict requiring two models before a first Champion paper trial.
  - [ ] Build an independent paper guardian that rejects unsafe or unauthorised proposals.
  - [ ] Approve paper-only mode separately, test one paper position and reconcile its accounting.
- [ ] **Milestone 11 — Champion versus Challenger comparison works** (engineering G10)
  - [ ] Qualify and freeze a Challenger only after appropriate additional research.
  - [ ] Run fair, separately accounted paper portfolios on the same forward market period.
  - [ ] Produce an understandable KEEP / REJECT / HOLD / RECOMMEND CHANGE report with no automatic promotion.
- [ ] **Milestone 12 — Whole loop and VPS load are proven** (engineering G11)
  - [ ] Demonstrate all seven stages with authentic contract boundaries in offline scenarios.
  - [ ] Test errors, interruptions, source-grade limitations and safe NO TRADE choices.
  - [ ] Show the real CPU/RAM/disk/headroom numbers before considering any permitted operational rollout.
- [ ] **Milestone 13 — Optional future REAL trading (NOT APPROVED)** (engineering G12)
  - [ ] Obtain a separate explicit authorization from the owner.
  - [ ] Independently verify single-real-position, protective stops, exchange-order reconciliation and emergency controls.
  - [ ] Carry out a separate real-money release review; until then, keep real execution LOCKED.

### G0-01 — Documentation-only legacy register (approved 15 October 2026)

- [x] **G0-01:** Commit the initial Legacy Component Reuse Register with 27 source candidates, pinned historical branch/commit links, preliminary test quality, 12 key conflicts and explicit V5.1 modernization rules — completed **15 Oct 2026**, commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; confirmed by reading the new GitHub file. **Verification:** GitHub file-content/source review, not a code test, model result or VPS acceptance.
- [x] **G0-02:** Independently audit the first proposed **pure-function** port's full static dependency chain, obsolete `nbot/__init__.py` version **3.0.0**, potential I/O/credential/order reachability, historical synthetic tests and missing negatives; specify the new `nbot_v5_1` package and 12 tests. **15 Oct 2026; register audit commit 2ebcc62f9f13aa4c7ed532cca108d9c359c77363.** No code copied and no tests run.
- [x] **G0-03:** Complete live, read-only assessment of Execution-VPS and Observation-VPS; recorded 253 paper receipts, old disabled observation service, 15-table SQLite+WAL source (read-only quick_check=ok), disk/RAM and absent verified local NBOT backups — **15 Oct 2026**, [report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_03_VPS_PRESERVATION_BACKUP_ASSESSMENT_20261015.md), commit **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28**. **Assessment complete, safe cleanup NOT approved.**
- [x] **G0-03 legacy backup/cleanup decision CLOSED BY OWNER WAIVER:** Backups intentionally **NOT MADE**, restoration **NOT TESTED**, and potential irreversible loss of old-only evidence accepted; no prerequisite to G0 completion. **15 Oct 2026**, waiver commit **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**; original assessment retained.
- [ ] **Old VPS cleanup execution (separate from G0-03):** If needed, run only a scoped documented NBOT-only cleanup, record actual changes; none performed yet.
- [ ] **G0-04:** Final owner review of G1-01 exact scope and first application-code transfer; G0-02 identified/recommended it but did not execute G1-01.

**Current state (15 Oct 2026):** G0-01, G0-02 and **G0-03 in full are complete**: the VPS inventory is documented and the owner expressly waived restoring/backing up old-version VPS contents. **No backup was made or tested; no VPS cleanup was performed.** The G0-03 report preserves the earlier inventory and current owner decision. **G0 parent remains [ ] only for remaining G0-04 first-code scope review and any independent requirements, not historical backup preparation.** V5.1 original-source future retention and paper/real-money safety gates remain unaffected.

### Record of every verified tick

| When (IST) | Small task or milestone | Evidence (GitHub commit and tests) | Meaning in everyday language |
| --- | --- | --- | --- |
| 2026-10-15 | [x] START-01 | 472c3f54415e06715f8b28673eee7d3b545338d4 / verified three-file tree | The clean branch exists and does not carry old code |
| 2026-10-15 | [x] START-02 | Same commit / Vision blob matches original | The approved product vision is safely copied |
| 2026-10-15 | [x] G0-01 legacy register and preliminary source/conflict review | **5d5133766b96ad3b21ab8b4c553e08740c3c7adb** / GitHub verified 27 entries and 12 conflicts; no code tests | We now have a written map of what to keep, rebuild, or leave behind; old code still untouched |
| 2026-10-15 | [x] G0-02 selected pure-helper source/side-effect/test audit | **2ebcc62f9f13aa4c7ed532cca108d9c359c77363** / exact source/test hashes, complete selected-helper call graph, 12 planned negative tests; no application tests | First safe helpers are identified, and outdated V3 initialization is excluded |
| 2026-10-15 | [x] G0-03 live VPS preservation/backup assessment | **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28** / [full live inventory](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_03_VPS_PRESERVATION_BACKUP_ASSESSMENT_20261015.md); old SQLite read-only quick_check=ok; data/file counts and SHA verified; backup readiness HOLD | We know what is on both servers and why it must not be erased |
| 2026-10-15 | [x] G0-03 legacy backup waiver and old-code discard approval | **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc** / explicit owner's instruction; no backups or deletion performed | We will start fresh without protecting outdated VPS-only NBOT files; any actual cleanup gets a separate checkmark |
| *Next review* | [ ] Scoped legacy VPS cleanup if needed | Not run | Remove old-NBOT-only material during a separately logged step, never OS/SSH/unrelated data |
| *Next review* | [ ] G0-04 review of first G1-01 code scope | Pending | Confirm the exact new files and tests before beginning their implementation |

**Use [ ] and [x] on the individual subtasks throughout development.** The roadmap itself should be updated with a new GitHub commit as work is completed. No stage above is yet checked as completed.

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

- **Permission update, 15 Oct 2026:** The owner has authorized narrowly necessary access to existing PuTTY sessions `Execution-VPS` and `Observation-VPS` via their laptop and the local authentication setup for VPS maintenance. Do not browse unrelated personal files, duplicate/read out the private key, or expose secrets in GitHub/logs. **G0-01/G0-02 required no laptop or VPS access.**
- Keep **old GitHub branches, source files, DB evidence and existing pull requests intact**.
- Development belongs to this separate clean NBOT V5.1 branch; do not merge to default without explicit approval.
- The owner has authorized GitHub/VPS maintenance **and, on 15 Oct 2026, explicitly waived backups of unwanted old NBOT VPS-only data**. G0-03 inspection and waiver are complete. Future narrow cleanup of legacy NBOT files may proceed without historic restoration, but record exact targets and effects, avoid OS/SSH/unrelated data and historic GitHub branches, and do not infer any paper or live-money release. **New V5.1 scientific source retention and recovery requirements are NOT waived.**
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

**Updated G0 owner choice:** We understand the legacy and retain historical GitHub source references. The owner has **chosen not to preserve old VPS-only data**, accepting possible permanent loss. No application import is required to complete the G0-03 inventory/waiver.

---

**Owner's guiding statement:** NBOT V5.1 should be **small enough to understand, cautious enough to trust, and able to improve from authentic evidence**. An empty trade slot and NO TRADE are perfectly legitimate outcomes.
