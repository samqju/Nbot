# NBOT V5.1 — Your Plain-Language Development Roadmap

**Roadmap version:** 1.9 (G10 offline Challenger/promoter 400 two-VPS tests and 100+100 LAB demo PASS; real paper contest HOLD)  
**Date:** 15 October 2026  
**Status (current, 15 October 2026):** **G0–G3 fully accepted. G4–G9 remain [ ] because actual original market feed continuity, Research evidence, economic data, 2,000 genuine mature Learning trials, frozen qualified Champion and signed owner PAPER release are still pending. G10 built/tested OFFLINE: 400/400 tests on EACH actual VPS, plus 200 common simulated market events and separately settled 100 Champion LAB +100 Challenger LAB book trades, with every actual decision HOLD/no promotion.** G10 parent [ ] because genuine additional 2,000 source-qualified Research outcomes, separately approved Challenger PAPER test and owner Promoter review are absent. G11–G12 [ ] future; all NBOT services remain stopped, NO paper or real orders or model routing authority.
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

### Milestone 0 — Assess old NBOT and establish a clean start (legacy backups waived)

**Completed 15 Oct 2026:** We first inventoried the previous version without changing it, then the owner explicitly waived backups of old NBOT VPS-only data and performed targeted manual cleanup. Independent SSH evidence shows the known old NBOT directories/service are absent on both VPSs, with SSH preserved — **81dadf68a9949b847fd8f38336c5d532eab861cd**. Historical GitHub branches remain reusable sources; no old-data backup was made. This cleanup gives no paper/real trading authority.

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
- [x] **Milestone 0 — Old NBOT assessed and owner-approved fresh start verified** (engineering G0)
  - [x] Identify the important historical branches, files and tests without changing them — initial read-only GitHub inventory, 15 Oct 2026; reuse register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; documentation/source inspection, no tests run.
  - [x] Confirm which old components may be useful or risky — 27 preliminary candidates reviewed, 15 Oct 2026; same register/commit; source and test-file review only.
  - [x] **G0-03 assessment:** Inspect both VPSs, preserve old data, record stopped services, storage/RAM, proof files and backup gaps; document rollback steps — completed 15 Oct 2026, assessment commit **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28**; **no cleanup or backup restoration conducted**.
  - [x] **G0-03-R1 owner decision:** Old NBOT VPS backups/restoration **explicitly waived as NOT NEEDED** — **not performed, not falsely passed**. Owner accepts loss of old SQLite/WAL, paper receipts, V3.9 artifacts and old runtime data; recorded 15 Oct 2026, waiver commit **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**.
  - [x] **G0-03-R2 owner decision:** Permission to discard old NBOT-only material from both VPSs without backup granted 15 Oct 2026; **no cleanup was executed in G0-03**. Avoid OS, SSH, non-NBOT files and historic GitHub branches.
  - [x] **G0-CLEANUP-01/02:** Owner submitted PuTTY cleanup success logs for both VPSs on 15 Oct 2026.
  - [x] **G0-CLEANUP-03/04:** Assistant independently verified old NBOT application paths, reset markers and retired systemd unit absent on both hosts; name-scoped services/processes absent; SSH still functioning.
  - [x] **G0-CLEANUP-05 / G0-03-CLEANUP-EXEC:** Owner's manual cleanup independently VERIFIED PASS for both VPSs; [evidence and timestamps](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_CLEANUP_COMPLETION_20261015.md), commit **81dadf68a9949b847fd8f38336c5d532eab861cd**. Old-version backups were waived, not made.
  - [x] **Approve first selected safe port:** The exact selected pure functions have a pinned source/risk audit, and the owner directed G0-04 scope finalization in parallel with manual cleanup, 15 Oct 2026. G0-04 scope commit **7c624de187e274fe40172e64d03b8697f6e1f7aa**. **Other 27 candidate assessments remain task-by-task and are not blanket approved.**
- [x] **Milestone 1 — Initial source reuse register and first component scope complete** (engineering G0)
  - [x] List old V4 detectors, market-data tools, research evidence checks, paper book and risk protections with pinned source links — 15 Oct 2026, register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**.
  - [x] Give each an easy choice: **COPY / REWRITE / DISCARD / REFERENCE** with the reason — register entries R01–R27; source inspection only.
  - [x] Identify conflicts between previous NBOT and Vision V1.9 — conflict register C01–C12, including obsolete V3/V3.9/V4/V5 runtime references.
  - [x] Verify the selected **pure first helpers**: exact old source/test blob hashes, complete selected-function imports/calls, excluded SQLite/old-version side effects and missing/required *future* tests — 15 Oct 2026, audit commit **2ebcc62f9f13aa4c7ed532cca108d9c359c77363**. This is an inspection PASS, not a code/test execution PASS.
  - [x] **First safe component and package plan approved:** V5.1-only five-minute clock, source HOLD evidence, canonical version-scoped hash and no-order authorities; precisely three new files and T01–T12 tests, 15 Oct 2026 — **7c624de187e274fe40172e64d03b8697f6e1f7aa**. This approves the **G1-01 code scope**, not old app copy or a test pass.
- [x] **Milestone 2 — Our new SAFE OFFLINE foundation works** (engineering G1), **15 Oct 2026**. Fully verified 67/67 tests locally and independently on both VPS Python3.12.3 instances, no trading service or live source — [G1 final proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), commit **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **First G1 layout approved:** `nbot_v5_1/__init__.py`, `nbot_v5_1/core.py`, `tests/test_v5_1_core.py` as the only first-code files; G0-04 scope **7c624de187e274fe40172e64d03b8697f6e1f7aa**, 15 Oct 2026.
  - [x] **G1-01-A:** Created three new, clean GitHub files only: `nbot_v5_1/__init__.py` (version 5.1), `nbot_v5_1/core.py` (five-minute clock, source HOLD and safe unique IDs) and `tests/test_v5_1_core.py`. Code commits **`e22b55abcc0631b603b5357a8be9122008bb1ef0`**, **`5d9fc0e22e0cc113353cd20593cce0cb687be2c1`** and **`f859f7f92a9614267fd4e7bfbc5cb6701bdb5288`**; 15 Oct 2026. Nothing old copied wholesale.
  - [x] **G1-01-B:** Actually ran all **12 offline safety tests**, **12 PASS, 0 failed**, 15 Oct 2026, Python 3.13.5; checked bad and premature timestamps, missing BTC/source evidence, invalid digests, unchanged result IDs and no order entry. **Synthetic testing only**, not live market evidence.
  - [x] **G1-01-C:** Inspected code dependencies: only harmless Python standard-library modules; no old `nbot`, SQLite, network, Binance SDK, service startup or order code. Python 3.12 **syntax** checked; 3.12 runtime not tested. No VPS deployment.
  - [x] **G1-01-D:** Independently checked all three GitHub file hashes against exact locally tested files; only three new code/test files in the commit comparison. **G1-01 completed**; [engineering test evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md).
  - [x] **G1-02-A — Operating modes protected:** The default is OFFLINE, with no data-network or order authority. Future virtual/paper/challenger/real names are defined but **cannot be switched on**. 15 Oct 2026; [G1-02 evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md), commit **88c0f8acfec85eaf75b80529fd22b1274922baac**.
  - [x] **G1-02-B — Evidence honesty:** A market/source identity or synthetic fixture cannot automatically become verified real original trade data or profitable after-cost proof; attempted grade upgrade is rejected.
  - [x] **G1-02-C — Independent guardian says NO TRADE:** Missing BTC/source information, invalid proposals, expired inputs or unapproved model fingerprints never unlock an order; all directions are vetoed at this stage.
  - [x] **G1-02-D — Small audit journal created:** Appends immutable-intent audit records to a capped file, with hashes, disk synchronization and protection from accidental rewriting or duplicate actions. **Not a Binance price archive.**
  - [x] **G1-02-E — Recovery failure tests:** Detect altered data, broken/truncated records, unsafe file permissions/links, full audit disk quota, restarts and concurrent writers; every unsafe case fails closed.
  - [x] **G1-02-F — Full offline tests passed:** **45 of 45 passed**, including the previous 12 G1-01 tests, 15 guardian tests and 18 journal tests. Python 3.13.5 test execution; Python 3.12 syntax-only check.
  - [x] **G1-02-G — Exact GitHub source checked:** All five changed source/test files match the verified local test versions; no old bot code or VPS deployment.
  - [x] **G1-02-H — Fixed old core test interaction:** Original import safety check now uses a separate isolated Python process so old and new tests do not interfere.
  - [x] **G1-02 — Foundation components DONE:** Two new nontrading modules, two new test files, one prior test-harness correction. **88c0f8acfec85eaf75b80529fd22b1274922baac**; 45/45 synthetic offline tests pass; paper/real trading still locked.
  - [x] **G1-03-A:** Created a narrowly scoped source route/candle clock/epoch interface. Even a healthy-looking source does **not** count as original authenticated evidence (source HOLD). **bb0df4b727e5817d47fe693206baba91e2706456**; G01–G05 PASS.
  - [x] **G1-03-B:** A restart always returns OFFLINE/HOLD/NONE authority, even if the audit log verifies; a damaged log blocks evidence recovery, and a restart HOLD record is idempotent. G06–G09 PASS.
  - [x] **G1-03-C:** Hardened journal: synchronizes the new file AND its containing directory; retry after an interrupted directory sync repeats both synchronizations. G10–G11 PASS.
  - [x] **G1-03-D:** Simulated partial write, corrupted record, wrong schema and full audit quota all fail closed, with no hidden overwrite/rotation. G12–G15 PASS. Actual electrical outage was NOT attempted; the future original-source durability gates remain.
  - [x] **G1-03-E:** Verified guardian/source/journal/restart integration, subprocess restart, locked future operating modes and secure journal directory. G16–G22 PASS.
  - [x] **G1-03-F:** Combined **67/67 offline tests PASS** under Python 3.13.5; Python3.12 syntax check on 10 files PASS.
  - [x] **G1-03-G:** Exact four changed GitHub source/test file hashes match local tested copies; source/test changes stay on `nbot-v5.1`.
  - [x] **G1-03 COMPLETED:** Source and restart interfaces, audit durability and 22 new integration/failure tests finished, [G1 final report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md).
  - [x] **G1-04-A:** Observation-VPS independently ran the committed version's **67 tests under Python 3.12.3: all PASS**; temporary test files removed afterward.
  - [x] **G1-04-B:** Execution-VPS independently ran the **same committed version's 67 tests under Python 3.12.3: all PASS**; temporary test files removed afterward.
  - [x] **G1-04-C:** Confirmed no permanent NBOT install or application service was started on either VPS; no Binance account, password or exchange order accessed.
  - [x] **G1-04-D:** Recorded limitations plainly: these are OFFLINE tests only, not real market-source custody, real host power outage, 100-coin load or paper/live execution.
  - [x] **G1-04 FINAL / COMPLETE G1 OWNER MILESTONE 2:** All G1-01, G1-02, G1-03 and final G1-04 checks passed **within the safe, nontrading G1 scope** — proof **bb0df4b727e5817d47fe693206baba91e2706456**; every trading mode remains LOCKED.
- [x] **Milestone 3 — Read-only lightweight Observation of up to 100 coins COMPLETE (engineering G2), 15 Oct 2026.** Actual public USD-M 100-coin history/snapshot and 103 source receipts tested; **120/120 tests passed on BOTH VPSs**, 100-symbol performance budgets met; [G2 proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), commit **005d82324d7cb009e4939075b49e00e41e25f271**. **No permanent collector service or trading permissions released**.
  - [x] **G2-01-A:** Only actual qualified USDT-margined, USDT-quoted, TRADING perpetual Binance USD-M symbols; bad liquidity, spread, history or source rejects with visible reason — test group U01–U10.
  - [x] **G2-01-B:** Correct 50 highest USDT turnover + 25 biggest gainers + 25 biggest losers with category overlaps preserved, no duplicate count, qualified BTC mandatory and deterministic liquid fallback to 100 if possible.
  - [x] **G2-01-C:** Frozen as-of selection manifest, triple raw source response SHA-256, independently checked three-source reception times (15s spread/60s age max), rejection reasons and selected cohort identity — group R01–R10.
  - [x] **G2-02-A:** Finished 5-minute candles only, exact boundaries, strict receive-as-of clock and OHLCV validation; never insert open/unfinished candle.
  - [x] **G2-02-B:** Maximum 96 historical five-minute candles ×100 coins in a bounded in-memory ring, checked contiguous history and route/source epoch; disconnection or unknown history becomes HOLD.
  - [x] **G2-02-C:** Up to 100 one-row-per-coin event snapshots with BTC health, observed market breadth, exact evidence/meta ID and reasons for every missing, lagging or future symbol; O01–O12 PASS.
  - [x] **G2-03-A:** Small durable, owner-private selection/event receipt journal with checksums, file/directory synchronization, disk limits, restart replay and strict corruption HOLD; S01–S07 PASS.
  - [x] **G2-03-B:** Independently test public HTTP **raw source bytes** with gzip receipt archive, source response SHA/clock/route, replay checks and finite quota, A01–A10 PASS. Original trade/quote/funding proof is a **different G4 obligation**.
  - [x] **G2-04-A:** Opt-in only-public Binance USD-M HTTP GET adapter; disabled by default, limited rate/time/body/URLs, cannot access API keys, balances or place/cancel orders, P01–P04 / R09 PASS.
  - [x] **G2-04-B:** Actual one-time public probe: **100 qualified markets, 100 complete 96-bar histories, BTC included, 100 valid as-of observations, 0 HOLD**, 103 original public response receipts (~793 KB compressed) hash replay, 246 public weight and NO orders, 15 Oct 2026.
  - [x] **G2-05-A:** New 53 G2 positive/negative/source-failure tests, all older 67 G1 tests; **120/120 PASS** on Python3.12.3 Observation-VPS (3.308s) and Execution-VPS (3.377s), source commit `4ba07385bb06ad8cde2460d83953448386f1a751`.
  - [x] **G2-05-B:** Independently measured both VPSs with 100 coins ×96 closed bars, 120 events, 10 injected disconnects and full 100-row accounting: p99 event latency **51.867ms Observation**, **60.326ms Execution**, peak test RSS ~37 MiB, compact disk 2.71 MB; all limits PASS.
  - [x] **G2-05-C:** Tested byte-bound source integrity and negative cases, fixed all observed test/code faults, independently compared G2 source files/commit scope; old V3/V4/V5 runtimes never imported and all paper/live controls remain locked.
  - [x] **G2-06 — Entire G2 parent acceptance:** Full completed public read-only Observation engineering gate; all small tasks have test/source/resource proof **005d82324d7cb009e4939075b49e00e41e25f271**. No always-running service, scientific after-cost label, original tick stream or order access is implied.
- [x] **Milestone 4 — Explore structures and directions (entire engineering G3 COMPLETE, 15 Oct 2026)**. All **157 offline tests passed on BOTH VPSs**; 100 coin ×2 sides ×24 historical pattern detectors processed within measured RAM/CPU/disk budgets, and actual read-only public source gave 200 honest capacity-masked records. [Full G3 evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), commit **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**.
  - [x] **G3-01-A — Historical 24 detectors all identified:** The original 24 V4 pattern IDs, their original meanings and their reference source hashes were verified; five describe general conditions and nineteen are mathematical candle patterns. The historical source was not copied wholesale.
  - [x] **G3-01-B — Each original rule checked:** All 19 technical rules pass original positive fixtures for BOTH LONG and SHORT; all five original condition labels pass golden examples; missing BTC, flat markets, bad bars and unconfirmed swings do not create fake matches.
  - [x] **G3-01-C — Safe code transfer:** Only required pure detector formulas copied/adapted; old database, paper trading/model-selection and original fixed-50 implementation are not imported. The new V5.1 wrapper has a separate version.
  - [x] **G3-02-A — Time-safe coin market understanding:** Uses only verified finished five-minute candle history, BTC/overall market/coin trend and price structures; structures described as forming, confirmed, failed or uncertain where measurable.
  - [x] **G3-02-B — Missing/old sources handled honestly:** Missing BTC never silently equals zero BTC movement; missing/gapped bars, uncertain market breadth and stale universe membership are unavailable/HOLD.
  - [x] **G3-02-C — Source and costs not exaggerated:** Original volume/gainer/loser/BTC group tags, source checks and declared liquidity recorded; fees, funding, slippage and independent quote truth explicitly NOT VERIFIED. These are pattern descriptions, not successful trades.
  - [x] **G3-03-A — Full 200 LONG/SHORT alternatives:** All 100 coins have both directional records, exactly 24 detector statuses per direction. No coin or opposite side disappears because of capacity or poor source.
  - [x] **G3-03-B — Distinct missingness/statuses:** Separately record MATCH, NO_MATCH, UNAVAILABLE, NOT_EVALUATED_SOURCE, NOT_EVALUATED_CAPACITY and independent NO_TRADE. Missing BTC-specific information cannot be counted as a losing pattern.
  - [x] **G3-03-C — Evaluate only when reported research capacity exists:** Default no vacant research slot => heavy pattern work skipped. A declared simulated vacant slot permits safe read-only rule checks, with fair/transparent deterministic selection and a recorded source-ready inclusion fraction.
  - [x] **G3-03-D — Never treat patterns as orders:** Every candidate retains NONE order authority and NO_TRADE disposition, even when several patterns match. It cannot create virtual, paper or real positions.
  - [x] **G3-04-A — Small compressed G3 evidence records:** Versioned private, finite, hash-checked, disk-synced and replayed 200-direction records preserve detector/source/capacity status with no silent deletion.
  - [x] **G3-04-B — Negative tamper/restart checks:** Tests detect fake LIVE authorization, forged original/after-cost claims, masked rule changes, corrupted gzip, full disk, unsafe permissions, conflicting same-event evaluations and interrupted synchronization.
  - [x] **G3-05-A — Full older and new tests on BOTH servers:** 67 G1 + 53 G2 + 37 G3 = **157/157 PASS on Observation-VPS AND independently Execution-VPS** (Python 3.12.3) at identical code revision `5d9707fe8521bbe17e96036aef0a5ec44a784a96`.
  - [x] **G3-05-B — Genuine measured small-VPS capacity:** Each VPS tested 100×2×24 over 12 simulated events (2,400 complete records): 1,240 evaluated, 1,020 skipped for capacity, 140 skipped for gaps. Worst measured p99 **571.799ms Observation**, **549.342ms Execution**, ~42 MiB memory, 198,781 bytes compressed receipt disk. All budgets PASS.
  - [x] **G3-05-C — Code and test results pinned:** Exact GitHub code revision/file hashes and test failures/fixes are documented. All revised functionality re-tested before G3 acceptance.
  - [x] **G3-06-A — Real public read-only market integration tested:** On Observation-VPS, 100 qualified Binance USD-M markets including BTC had valid 96-candle public history; G3 reported **200 full direction rows**, zero source missing, **200 capacity-skipped** (since research slots have NOT been approved), all NO_TRADE, 24 detector state slots each. 103 public HTTP source receipts and G3 output replayed, no orders.
  - [x] **G3-06-B — Strictly no trading/services:** No permanent VPS program or NBOT service installed, no trading API keys, original fee/quote/profit proof or live/paper trade; temporary public test receipts were removed afterward.
  - [x] **G3-06-C — Entire G3 PASS:** All source lineage, test/negative fixtures, causal 200-way denominator, resource benchmarks, read-only real market receipt evidence verified. **G4 next; all trade permissions still LOCKED**.
- [ ] **Milestone 5 — Select and independently source the 20 deeply researched coins (G4 PARTIALLY BUILT; real source HOLD, NOT COMPLETE)**. See [exact G4 evidence/blocker report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**.
  - [x] **G4-01-A — Qualified 100-coin starting universe:** Source-checked G2/BTC universe and both G3 directional records used at decision time; missing/future/unqualified inputs rejected.
  - [x] **G4-01-B — Only 20 coins, BTC compulsory:** Up to 20 unique, frozen selected coin list and all remaining exclusions. Selection is NOT a trade and every new coin says WARMUP_HOLD.
  - [x] **G4-01-C — Fair policy and controls:** Include volume/gainers/losers/controls with transparent membership, deterministic rotating sampling and recorded prospective selection probabilities. Do not rank by 24 pattern matches or pretend scientific profitability.
  - [x] **G4-01-D — 8 independent shortlist tests PASS:** BTC, duplicates, wrong source time, full 100 denominator, missing slots, inclusion fairness and smaller cohort.
  - [x] **G4-02-A — Correct public USD-M feeds identified:** Binance routes for public bid/ask, actual aggregated trades and mark-price/funding indicators checked against October 2026 official docs. No private data/order endpoints.
  - [x] **G4-02-B — Byte-exact source gate implemented:** Verify raw stream, route, coin, epoch, time, bid/ask, mark and separate aggregate IDs for EACH coin; fail closed on gaps. Multi-coin interleave tests PASS.
  - [x] **G4-03-A — Small bounded compressed source receipts:** Hash-chained gzip, raw message bytes, source epochs, disk limits and strict replay; no expensive per-frame SQLite writes or silent evidence pruning.
  - [x] **G4-03-B — Failure, replay and restart tests:** Corrupted/torn writes, quota, file ownership, bad source frames, multiple coin cursors, restart SOURCE_HOLD tested.
  - [x] **G4-04-A — Funding honesty:** Mark stream's estimated next funding rate is not settled funding. Separate public BTC settled-funding response verified, but this is not proof of real or virtual account charges. Five funding-specific tests PASS.
  - [x] **G4-05-A — Full G1–G4 tests on BOTH VPSs:** **186/186 PASS EACH** on Python3.12.3, exact tested GitHub source `07186992fdfc8b2fc1b66e39b6d78513ee23891e`.
  - [x] **G4-05-B — Bounded synthetic 20-coin stress on both VPSs:** 3,600 raw frame fixtures, 60 compressed source segments, 20 restart HOLDs, complete hash replay. p99 **53.325ms Observation /60.251ms Execution**; ~35.5MiB RSS and 243,436-byte compressed receipts, all declared budgets PASS.
  - [x] **G4-05-C — Actual public Binance source test completed honestly:** 100 source-qualified symbols, selected real 20 with BTC, 103 raw public REST receipts then **3,077 public WSS frames replayed**. All 20 have quote and mark frames; aggregate trades valid for only 19, and **47 trade-ID gaps/rejections** occurred. Exact original source readiness therefore **NOT ACCEPTED**.
  - [ ] **G4-06-A — All 20 must have clean original trade/quote/mark history:** The actual sample did NOT meet the clean 20/20 trade-source requirement. Missing prices cannot be replaced by 5-minute candles.
  - [ ] **G4-06-B — Real sustained 20-source bandwidth/disk/endurance:** Simulated CPU/RAM/disk passes do not prove genuine peak trade traffic, reconnects, 24-hour operation or long-run segment headroom.
  - [ ] **G4-06-C — Independent source/economic quality:** Locally received public TLS WSS data is not exchange-signed, public last funding not actual position-specific funding, and sample quotes do not prove executable trade fills.
  - [ ] **G4-06-D — Real separate-host backup/restore:** Temporary replay of local gzip receipts passed; independent source archive off-host retention, verified restore and real interruption qualification remain to prove.
  - [ ] **G4-06-E — PARENT G4 ACCEPTANCE remains HOLD:** Do NOT tick this or advance G5 until every original-source and long-run restore gate above is proved. No VPS bot services or trade permissions are enabled.
- [ ] **Milestone 6 — Rolling maximum-40 virtual-trade Research (G5): offline software built and tested, full parent HOLD**. [G5 complete progress and actual blockers](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G5_OFFLINE_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), commit **79ff4da7fc3967e19df1f8b9a86db384ab6e847d**; 224/224 combined tests on BOTH VPSs, 24-cycle 40-slot performance PASS. All hypothetical Research outputs currently SYNTHETIC and unqualified while G4 source remains HOLD.
  - [x] **G5-01-A:** Audited safe design bits from five historical V4/V5 research/path/ledger modules (R11/R12/R15/R16/R18); refused to copy the old 100-slot engine or legacy database.
  - [x] **G5-01-B:** Each laboratory intent freezes its LONG/SHORT direction, observation/decision and activation clocks, entry reference, initial stop, target, maximum time, trailing and non-zero-cannot-be-assumed cost policy BEFORE future movements.
  - [x] **G5-01-C:** Laboratory source marked SYNTHETIC_OFFLINE_TEST_ONLY; an original/Binance or paper/real simulation authority cannot be manufactured while G4 real-data checks are pending.
  - [x] **G5-02-A:** Exactly at most 40 active across 20 source-budget coins, at most one coin+direction, no extra trade for extra detector tags, BTC included in deep cohort.
  - [x] **G5-02-B:** At each completed five-minute boundary only truly free positions can take qualified new hypotheses; an empty slot stays empty and the heavy new-opportunity supplier is not called if all slots occupied. No eight-new-per-candle quota.
  - [x] **G5-02-C:** Every eligible or unavailable coin-direction is explicitly accounted for, including a fair/prospective K/N selection probability, rather than disappearing when capacity is exhausted.
  - [x] **G5-03-A:** Read-only synthetic trade-path stream tracks actual individual simulated event timestamp (e.g. stop at 10:03, not 10:05), both LONG and SHORT using one shared coin feed; no per-frame SQLite.
  - [x] **G5-03-B:** Trailing stop only tightens in the safe direction; stop and target checked before advancing trail, correctly handles simultaneous direction closures and horizon uncertainty.
  - [x] **G5-03-C:** Source gaps, trade ID sequence breaks, new epochs and interrupted RAM are HOLD. Even a valid simulated exit becomes COST_PENDING_UNQUALIFIED and **does not count as a real profitable Research outcome**.
  - [x] **G5-04-A:** Durable limited-size private G5 journal with file/directory synchronization, chained hashes, duplicate/restart/trailing-guard tests, no hidden auto deletion.
  - [x] **G5-04-B:** Source gaps persist even with no active experiment; a restart does not silently free a pending virtual slot or invent a forgotten trailing-stop winner. Full history must be independently checked again.
  - [x] **G5-05-A:** 38 G5 tests plus 186 earlier tests **224/224 PASS on Observation-VPS AND Execution-VPS** at identical Python3.12.3 source revision `2efea2cccb086a1f292ae90c1eaac414620f342b`.
  - [x] **G5-05-B:** Actual small-VPS OFFLINE capacity measured independently: **40 peak virtual hypotheses**, 600 simulated entries/600 cost-pending closures over 24 candle reviews; p99 **197.077/194.434 ms**, RAM ~40MiB, journal ~1.25MB, quotas met on BOTH VPSs.
  - [x] **G5-05-C:** Stronger full-40-slots-occupied crash/restart test harness added to GitHub; initial passing benchmark had ended with 0 occupied and was insufficient as a full 40-restart proof. The strengthened test remains **unexecuted**, and has its own unchecked line below.
  - [x] **G5-06-A — Improved crash with ALL 40 slots occupied PASSED on BOTH VPSs.** Same source SHA `029cda1d75138fc1bf96f3502021ca5a236693c9`; **40/40 still occupied RESTART_HOLD**, no false reopened slots, no qualified returns, both 24-review synthetic journal benchmarks within p99/RSS/disk limits (p99 186.430ms Observation /195.132ms Execution). [G6 evidence and independent retest](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G6_OFFLINE_ENGINEERING_ACCEPTANCE_AND_SOURCE_HOLD_20261015.md). Previous blocked launch superseded by completed authorized tests.
  - [ ] **G5-06-B — Real original-source Research test later at controlled startup:** G4 must first pass true continuous original trade/quote/mark and off-host evidence. Synthetic price-path results cannot be called genuine Research outcomes or used for Learning.
  - [ ] **G5-06-C — Entire parent G5 not yet accepted:** Keep this milestone unchecked until both open checks above pass. All virtual/paper/real runtime modes remain LOCKED.
- [ ] **Milestone 7 — Recovery and true after-cost results (G6): OFFLINE SOFTWARE BUILT AND TESTED; actual source/off-host acceptance remains HOLD**. [Detailed G6 254-test/two-VPS source and limitations report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G6_OFFLINE_ENGINEERING_ACCEPTANCE_AND_SOURCE_HOLD_20261015.md), tested SHA `029cda1d75138fc1bf96f3502021ca5a236693c9`.
  - [x] **G6-01-A:** Reviewed historical source/candle recovery, segment recorder and cost-accounting code and kept only necessary safe design pieces; did not transplant old expensive SQLite or old unstable 50-market code.
  - [x] **G6-01-B:** Recover only authenticated-in-format, truly finalized five-minute public Futures candles; missing/duplicate or not-yet-closed prices HOLD. A corrected candle cannot pretend to reconstruct each trade or bid/ask.
  - [x] **G6-01-C:** Checked official USD-M Futures history endpoint's supported interval list and **did not invent 1-second Futures candles**. An OHLC candle crossing both target and stop cannot tell which happened first and remains unresolved.
  - [x] **G6-02-A:** Verified public Binance Futures aggregate-trade recovery rules (up to 1,000 records per page, recent ~48-hour source horizon) and wrote an explicit limit/clock contract. No API keys, no order or private endpoints.
  - [x] **G6-02-B:** Original-shaped trade-ID and individual underlying trade ID gap checks reject missing, duplicate, future or reordered records. Even complete public aggregate trades alone do NOT establish executable quotes/cost or profit.
  - [x] **G6-03-A:** Entry and exit bids/asks, clock freshness, independently declared fees/slippage and settled funding coverage now have strict typed evidence contracts; never silently assume a missing cost equals zero.
  - [x] **G6-03-B:** Model LONG/SHORT net-return after quote, slippage, both sides' fees and signed funding using Decimal. **This is LAB MODELED ONLY, not genuine after-cost trading profit** until actual original data is independently verified. Zero training-qualified outcomes are generated.
  - [x] **G6-04-A:** New finite sealed and owner-private G4 compressed segment archive, raw byte/size SHA checks, no silent overwrite, reject partial/corrupt/unsafe/over-quota files.
  - [x] **G6-04-B:** Verified restored source file integrity locally with an independent replay and hash chain in a fresh temporary directory, while correctly recording that off-host/source-origin restore has NOT been proved.
  - [x] **G6-05-A:** **254/254 regression tests passed on EACH VPS** — Observation 15.779 seconds; Execution 16.514 seconds; 30 new G6 tests plus 224 old, both Python 3.12.3.
  - [x] **G6-05-B:** Tested 20 coins ×3 market sources ×24 rounds = **1,440 synthetic raw frames** and 24 compressed segments, all independently replayed from sealed local archive; 24 candle context/24 modeled cost checks. p99 **50.938ms/61.420ms**, ~29MiB RAM and ~198KB archive+source disk, both VPS budgets PASS.
  - [x] **G6-05-C:** In same acceptance retest, G5's upgraded 40 occupied crash-restart/40 held test PASSED separately on both hosts; no false virtual win or freed slot.
  - [ ] **G6-06-A — Genuine original source after-cost outcomes:** Requires truly gap-free original G4 trade+bid/ask/mark; complete G5 first touch; verified fees, slippage and settled funding during hypothetical holding period. Existing modeled outcomes count **zero** as genuine profitable evidence.
  - [ ] **G6-06-B — REAL independent second-host source archive and restoration:** Verified local temporary source copy is not second VPS restore. Need independently check actual sealed original source archive and recovered source epochs during allowed future startup.
  - [ ] **G6-06-C — Real continuous-market throughput and crash/endurance:** The short simulated 24-cycle benchmark is not sustained 20-market source rates, disk rollover, fresh reconnects or physical loss of unsynced memory. Verify these at the approved startup.
  - [ ] **G6-06-D — Parent G6 remains unchecked:** Wait until real G4 original source, G5 original first-touch and the three G6 checks PASS; user explicitly asked to postpone verification, NOT to waive it. No service or trading enabled.
- [ ] **Milestone 8 — Reliable Learning (G7): full OFFLINE SOFTWARE ready, real Learning evidence HOLD**. [G7 full two-VPS 285-test and 2,000-example laboratory report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G7_OFFLINE_LEARNING_ACCEPTANCE_AND_GENUINE_EVIDENCE_HOLD_20261015.md), commit **225bc79f289ee93b2845061e7022c0d883507bff**.
  - [x] **G7-01-A — Reviewed old Learning/Research source safely:** Audited R20 and R21 historical code, took only time-safe evaluation ideas; did not copy legacy V5 DB, old trained models or anything that could trade.
  - [x] **G7-01-B — Join what was known THEN to what happened LATER:** Versioned identity and timestamps for BTC environment, overall market, coin structure, LONG/SHORT, original detector names, prospective frozen experiment, after-cost result and source lineage; future information cannot leak into old features.
  - [x] **G7-01-C — Keep synthetic data out of genuine learning:** Only marked SYNTHETIC laboratory cases are accepted for current TESTS. Forged “original”, paper and real results refuse scientific qualification; data hashes alone do not prove exchange authenticity.
  - [x] **G7-02-A — Account for ALL Research opportunities:** Preserve valid, pending, incomplete, censored, missing-source and restart-HOLD separately. No pretending missing results are good or bad; counting three detectors on one experiment never becomes three independent trades.
  - [x] **G7-02-B — BTC market correlation correctly grouped:** Trades over the same BTC-driven movement and overlapping LONG/SHORT tests are grouped, not treated as 2,000 independent successes.
  - [x] **G7-02-C — Record fair source-selection probabilities:** Include frozen K/N probability for sampled alternatives and distinguish unchosen/no-capacity and invalid-source records, without treating unobserved returns as measured profits.
  - [x] **G7-03-A — Separate earlier and later market experience:** Entire shared-movement groups are chronologically separated for simulated train vs untouched later tests; overlapping horizons and near-boundary examples are purged rather than leaked.
  - [x] **G7-03-B — Evaluate BTC/market/side differences and confidence:** Calculate simple conditional laboratory cost result and uncertainty against a NO_TRADE=0 benchmark with reproducible group-bootstrap tests. Positive synthetic sample DOES NOT mean profit in real markets.
  - [x] **G7-03-C — Always choose NO_MODEL without qualified proof:** G7 has no ability to appoint a Champion, place an order or turn a simulated gain into a real approved strategy.
  - [x] **G7-04-A — Preserve a small private Learning snapshot:** Finite 4MiB cap, content-hashed, disk-synced, owner-private test evidence and independently verified replay. Tamper, size, unsafe permission and false model approval are rejected.
  - [x] **G7-04-B — Reject forged Learning report objects:** Even if a module fabricates a “verified” dataset object, G7 reconstructs and validates its complete source/maturity/digest before analysis.
  - [x] **G7-05-A — Whole system tests on BOTH VPSs:** Previous 254 G1–G6 cases +31 new G7 = **285/285 PASS** on each Python3.12.3 VPS; same exact tested GitHub revision `49cb90bc35a8e6c79dcf4cebf8db0edc1f0cfc4d`.
  - [x] **G7-05-B — Tested 2,000 hypothetical laboratory outcomes on BOTH:** 2,000 synthetic cases represent **only 100 correlated market-event groups**, NOT 2,000 genuine trials; 49 earlier/48 later LAB groups and 3 purged; 134,381-byte snapshot verified, both measured p99/memory/disk budgets passed. Correct decision: **NO_MODEL / NO_TRADE**.
  - [x] **G7-05-C — No service or orders were started:** Tests were on isolated temporary GitHub checkouts; no permanent NBOT, paper, testnet, live stream worker or account actions.
  - [ ] **G7-06-A — First 2,000 genuinely independent matured virtual-trade outcomes:** Still **0/2000** today. We need real qualified G4 market records, G5 forward paths, and G6 after-fee/slippage/funding evidence first. Lab examples will NEVER count.
  - [ ] **G7-06-B — Independently validate genuine market/regime advantage and uncertainty:** After enough original evidence, compare against doing nothing on untouched later BTC/market periods, check diversity, losses and repeated strategy trials. Having 2,000 outcomes alone NEVER guarantees a qualified strategy.
  - [ ] **G7-06-C — Entire parent G7 cannot be marked passed yet:** Offline Learning engine is done/tested; genuine scientifically proven Learning release requires both open checks, plus G4–G6 accepted sources. No qualified Champion/paper/real authorization.
- [ ] **Milestone 9 — First qualified trained strategy (G8): Offline model system tested, original-source Champion acceptance HOLD**. [G8 detailed 319-case both-VPS test and genuine science HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G8_OFFLINE_TRAINING_ACCEPTANCE_AND_ORIGINAL_SCIENCE_HOLD_20261015.md), commit **6d467c2f9b17c1eaea94347ebd3fe060005dfbba**.
  - [x] **G8-01-A — Carefully reviewed old Training versions:** Audited old R21 science, R24 V4 ranking, R25 V4 model factory; rebuilt only necessary ideas, no old model/database/unsafe rank-is-profit code copied.
  - [x] **G8-01-B — Freeze every training rule BEFORE looking at results:** New prospective cutoff, earlier and later evaluation periods, embargo, one simple model family, minimum sample groups, finite CPU/RAM/disk and explicit nonzero economic cost buffer with SHA/version.
  - [x] **G8-01-C — Source truth cannot be bypassed:** G8 accepts ONLY synthetic laboratory data in current tests. A fabricated original verified status, changed data hash, or artificially high profit can never unlock a true Champion or paper/real model.
  - [x] **G8-02-A — Small reproducible model with bounded cost:** One easy-to-understand BTC market regime + overall market regime + LONG/SHORT conditional model, maximum 10,000 evidence rows and 32 condition variants, conservative return confidence. Unseen conditions say NO_TRADE.
  - [x] **G8-02-B — Never train on future outcomes:** Only matured earlier BTC-event groups train; skip overlapping market-event periods and verify untouched later market blocks independently, no random split of correlated data.
  - [x] **G8-02-C — No forced trading from relative rankings:** Hypothetical decisions require positive lower-bound return above a realistic economic buffer; but actual authority always NO_TRADE. Missing data, unknown regimes, insufficient independent cases abstain.
  - [x] **G8-03-A — Fair later laboratory test:** Compare selected one-at-a-time synthetic alternatives against always NO TRADE, include drawdown/worst case/abstentions/participation and horizon occupancy, not merely winning percentages.
  - [x] **G8-03-B — Repeatable freeze/version record:** Every model includes original dataset SHA, earlier train-row digest, cutoff, protocol hash, condition coefficients and immutable model hash, qualification=0. Same data generates EXACT same model hash on both VPSs.
  - [x] **G8-04-A — Private safe model card:** Small, versioned, non-executable JSON, hash/owner-private folder, 1MiB single and 4MiB total cap, file+directory sync, no silent overwrite, failures on tamper/paper authorization.
  - [x] **G8-04-B — Independent restore verification:** Rebuilds frozen training policy and model after reading card; checks model/data/holdout fingerprints again. Even a changed model object cannot bypass safety.
  - [x] **G8-05-A — 319/319 TESTS PASS BOTH VPSs:** 34 G8 new tests and 285 previous regressions, Observation 20.229 seconds, Execution 19.110 seconds, Python3.12.3 and source SHA `12ef09ebdf0d1bdfa6903f4dc8f1759110a41e68`. Initial 3 path-type test errors corrected before full pass.
  - [x] **G8-05-B — Tested 2,000 laboratory examples and froze/reopened model on BOTH VPSs:** 100 shared BTC blocks, 49 earlier trained, 49 later tested, 2 purged; artificial portfolio +36.40R vs NO_TRADE=0R is **NOT** genuine money/profit. Exact same frozen model SHA on both; 2,128-byte card verified; p99 48.991/29.691ms, RAM ~25MiB; budget PASS. Financial/order authority NONE.
  - [x] **G8-05-C — NBOT services remain stopped:** No exchange account, real position, API keys, observation market collector or paper mode started; tests in isolated temporary GitHub clones.
  - [ ] **G8-05-D — Temporary folder housekeeping:** Execution-VPS test checkout safely removed; Observation-VPS isolated test folder `/tmp/nbot-g8-c0qNaV` still requires confirmed removal using approved access (tool cleanup command blocked). Do not delete other directories or claim cleanup complete.
  - [ ] **G8-06-A — Truly matured 2,000 independent original Research outcomes:** Current actual qualified Learning count remains **0/2000**. Only genuine G4 market feed → G5 Research original paths → G6 verified costs → G7 independent science can qualify this.
  - [ ] **G8-06-B — Genuine after-cost Champion proved on later market periods:** Need strong independently source-verified positive edge relative to NO TRADE with uncertainty, regimes and drawdown; synthetic scores do not qualify.
  - [ ] **G8-06-C — Parent first real Champion model approval:** HOLD pending 06-A/B, G7 source checks and later independent owner paper release (G9). No approved Champion today.
- [ ] **Milestone 10 — FIRST Champion PAPER (G9): OFFLINE safety engine proven, real owner-approved PAPER stage HOLD.** [Detailed G9 completed code/tests and real RELEASE check list](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G9_OFFLINE_CHAMPION_PAPER_ENGINEERING_AND_RELEASE_HOLD_20261015.md), commit **0b23bf38096509aafd61096039b78be4bb06b662**, tested code SHA `fa2111e32bd0da4c36bf4fe58a7da14f4936c815`.
  - [x] **G9-01-A — Old two-model-before-first-paper mistake FIXED in new design:** Compared original V5 old guarded_paper and competing V5 execution engine. FIRST paper experiment eventually needs only one **independently qualified Champion** and YOUR separate paper-only approval. Challenger can arrive later. No unsafe legacy SQLite or second paper engine copied.
  - [x] **G9-01-B — Freeze independent Champion-only rules:** The new safety policy limits risk to 2% maximum upper bound, at most one simulated paper-like position, exposure at most 1× cash, drawdown and stop controls, clock and quote limits; present mode is LAB_ONLY and CANNOT activate PAPER or REAL.
  - [x] **G9-01-C — Tamper-proof LAB proposal identity and authentication:** Model version, policy/source SHA, market proposal ID, coin/side, stop/target, expected lower-after-cost benefit, idempotency and expiry are signed with a LAB-only HMAC. A modified or stale message, unqualified model, fake owner signature or real/paper claim is rejected. This is **NOT** a production paper release key.
  - [x] **G9-02-A — Independent price/source/cost/risk vetoes:** Fresh bid/ask, spread, stop/target and risk geometry, size/leverage, evidence SHA, fee/slippage and FULL simulated holding-interval funding coverage start and end are required; invalid/unknown source remains HOLD and is never counted as profitable.
  - [x] **G9-02-B — Exactly one Champion LAB position, no forced trade:** Even 100 attempted second positions were rejected in measured tests; different coin, direction, matching pattern cannot evade the single-position book limit. No Challenger required for first LAB mock, but true PAPER still locked.
  - [x] **G9-03-A — Realistic simulated LONG and SHORT paper-like accounting:** LAB-only entry at LONG ASK/SHORT BID and exit LONG BID/SHORT ASK, plus slippage, both fees and signed funding, fixed stop/target, frozen risk size, all labeled hypothetical, NEVER actual exchange orders or approved paper fills.
  - [x] **G9-03-B — Protective stops and source uncertainty:** Check stop/target before moving trailing, LONG trails only rise, SHORT trails only fall; missing/ambiguous source, stale quotes or funding period records remain occupied HOLD and cannot fabricate a win or released trading slot.
  - [x] **G9-03-C — Audited cash/fee/funding/drawdown:** Every LAB admission/close/trail/hold and censored restart is replayed and balances independently recalculated. Repeated rounding and censure entry-fee reconciliation failures were found and fixed before final 355-test run, without hiding failed initial test runs.
  - [x] **G9-04-A — Private small permanent-ready audit mechanics, currently LAB only:** Separate bounded 16MiB G9 LAB journal with chained SHA, file-and-directory disk sync, owner-private access, no per-raw-tick SQLite and strict policy/model/grade checks, no silent deletion.
  - [x] **G9-04-B — Unresolved position never vanishes on restart:** One interrupted position remains exactly one occupied RESTART_HOLD; an explicitly audited LAB censure records the opening fee and creates no fake profit. No paper release persists across reboot.
  - [x] **G9-05-A — All 355 tests PASS on BOTH VPSs:** 319 prior G1–G8 plus 36 G9 checks P01–P36, Observation 18.826s and Execution 19.385s on Python3.12.3 and identical GitHub source revision.
  - [x] **G9-05-B — Measured full 100-cycle Champion LAB paper-like benchmark PASS on BOTH:** 100 simulated entries/settlements, 100 second-position veto, max 1 occupied at once, one restart-held and censored; p99 **113.381ms Observation /108.130ms Execution**, RAM ~23MiB, journal 209,048B, quotas PASS, genuine qualified Champion 0, actual paper or exchange orders 0.
  - [x] **G9-05-C — Safe temporary test cleanup and NO service startups:** All G9 temporary source/test trees were removed from both VPSs with separate success confirmations. NBOT remained stopped. Separate old G8 Observation temporary file housekeeping still open.
  - [ ] **G9-06-A — Produce a TRULY qualified initial Champion:** Actual source-qualified G7 Learning outcomes remain **0/2,000**, and genuine G8 Champion missing until G4–G8 source/economic/scientific acceptance passes.
  - [ ] **G9-06-B — Owner's explicit PAPER-ONLY approval and independently signed live-grade release:** Still NOT authorized. New LAB HMAC cannot be used to unlock real PAPER and a production release guardian must independently authenticate original verified quotes/costs and the qualified Champion.
  - [ ] **G9-06-C — Actual approved Champion-only PAPER field trial and reconciliation:** No authorised running paper engine, no true 100 paper settlements or full live-source fault acceptance. Synthetic G9 ledger results do not count as actual PAPER results.
  - [ ] **G9-06-D — G9 parent cannot be checked yet:** Must pass A/B/C plus separate owner paper-only authorization; no automatic paper/real mode or unapproved Champion.
- [ ] **Milestone 11 — Champion versus Challenger (G10): complete OFFLINE fair-comparison machinery tested; REAL PAPER model competition not yet authorized.** [Permanent G10 acceptance/HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G10_OFFLINE_CHALLENGER_PROMOTER_ACCEPTANCE_AND_GENUINE_PAPER_HOLD_20261015.md), final full tested source SHA `15de49e8bf1a8c363c684021ec34db61293881f4`.
  - [x] **G10-01-A — Reviewed historical paper competitions:** Old V5 insisted on two models even before first PAPER. Fixed in G9/G10 separation. Old V4 used only 50 head-to-head paper trades; new Vision V1.9 recommends review after at least 100 genuine settled PAPER trades EACH when possible, plus fair common time/regimes. Did not copy old databases or unsafe trained models.
  - [x] **G10-01-B — Preserve the newly matured 2,000 Research gate, but don't fake it:** New G10 lab cohort correctly treats 2,000 simulated rows from 100 related BTC market episodes as SYNTHETIC, **not another 2,000 independent real returns**. Any forged original-quality claim rejected, and real Challenger not yet trained.
  - [x] **G10-01-C — Freeze competition rules before it begins:** Separate Champion SHA and Challenger SHA, shared source/fee/risk policies, declared data cutoff/forward time window, cost and drawdown comparison margins, at least 100 original-paper settlements each *when possible*, source/approval locks.
  - [x] **G10-02-A — Two separately managed LAB PAPER-LIKE books:** One simulated position each, completely separate identities, keys, cash, stops, fee/funding and journals. Never two real exchange positions, never a Challenger controlling actual trade decisions.
  - [x] **G10-02-B — Same market conditions for a fair comparison:** Both models receive identical prospective test event, original-shaped bid/ask and costs, BTC/market regime, but can independently LONG/SHORT/NO_TRADE. Both proposals checked before either ledger can change. Not the old unfair different historical periods.
  - [x] **G10-02-C — Independent no-forced-trade guardian:** Each book vetoes unsafe size/stop/fee/funding/stale quote, permits abstention, and never assumes unavailable evidence equals a win. One LAB active position maximum per book, no paper or real money authority.
  - [x] **G10-03-A — Count opportunities fairly:** Record every common five-minute event, active/abstained/vetoed/settled status per model, event BTC/market condition and selection, not just attractive winning trades.
  - [x] **G10-03-B — Compare results including risk, not just winners:** Separate net after synthetic costs, same capital/risk/time source, drawdowns, censored/restart-held paths and NO TRADE across common episodes. Artificial-looking return never becomes genuine edge.
  - [x] **G10-03-C — The 100-paper-trade guideline cannot force activity:** Added review checkpoint for enough shared market events, diversity and 100 actually settled PAPER trades per model when meaningful. G10 benchmark's 100+100 lab trades are ONLY a capacity test, not any actual PAPER account outcomes.
  - [x] **G10-04-A — Four clear recommendation outcomes but NO automatic change:** The LAB simulator reports retain incumbent, reject excessive risk, hold inconclusive, or would recommend promotion for review. Every actual routing action is **HOLD** until independently qualified original data and YOUR approved paper/model-routing release. Even a brilliantly winning synthetic Challenger cannot replace Champion.
  - [x] **G10-04-B — Auditable restart and source uncertainty:** THREE independent small private disk-synced SHA-chain journals for Champion, Challenger and their common-period event audit; both books restored and reconciled, stale/wrong source and half-completed event cannot silently pass/restart.
  - [x] **G10-04-C — Fault and security vetoes:** Tested switched model keys, duplicate model/book, made-up independent outcomes, original/source regrading, expired/duplicated event, partial-book writes, damaged journal, wrong capital/missing sample and fake promotion; all reject/HOLD.
  - [x] **G10-05-A — Every old and new test passed on BOTH VPSs:** Previous 355 tests +45 new G10 cases = **400/400 PASS on Observation-VPS (19.382s)** and **400/400 PASS on Execution-VPS (19.862s)**, same pinned SHA, Python3.12.3, no NBOT running service.
  - [x] **G10-05-B — Proved both separate books at realistic small-scale load:** 200 shared simulated market events, 100 lab Champion settlements AND 100 lab Challenger settlements, 4 regime combinations, 3 journals hash replayed, LAB recommendation retain but real decision HOLD. p99 processing **123.784ms Observation /118.200ms Execution**, RAM ~25MiB and 592,725 bytes TOTAL journal data each host; all performance caps PASS.
  - [x] **G10-05-C — Clean temporary tests and avoid running the bot:** Exactly three temporary G10 GitHub source checkouts per VPS safely removed with separate success evidence; no Observation feed, PAPER trading or exchange orders started. The separate older G8 Observation temporary folder remains on the existing cleanup list.
  - [ ] **G10-06-A — Newly mature 2,000 additional independently source-qualified Research outcomes and a real frozen Challenger:** Current genuine new additional Research outcomes=0, current truly approved Champion=0, so no qualified Challenger can be claimed today.
  - [ ] **G10-06-B — ACTUAL two-book Champion/Challenger owner-approved PAPER trial:** Not started. Needs original verified source/cost, independently qualified Champion and Challenger, explicit separate paper authorizations, fair risk and shared forward period; **0 real PAPER settlements** today, simulated 100+100 do not count.
  - [ ] **G10-06-C — Genuine independent model selection and YOU approving the new Champion:** There has been no real qualified head-to-head comparison, independent review, promotion request, approved routing signature or rollback of an accepted old model. No automatic switch.
  - [ ] **G10-06-D — Entire G10 parent:** Must stay unchecked until A/B/C, source reliability, genuine paper outcomes, fair model comparison and owner approval all pass.
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
- [x] **G0-04-SCOPE-DRAFT:** Define future three-file V5.1 core implementation, safe imports and 12 required offline tests — [scope document](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_04_FIRST_CODE_SCOPE_V1_0.md), commit **697b55f4201e7d4f76daaa0bde0efc113b3c99f7**, 15 Oct 2026; this is only a **draft**.
- [x] **Cleanup blocker verified:** The deletion operation was blocked before execution; read-only subsequent checks confirmed both legacy directories remain, and the obsolete observation unit is still installed and inactive.
- [x] **Old VPS cleanup execution:** Both named historical NBOT directories and reset markers absent, old Observation unit absent, zero name-matched NBOT services/processes and SSH accessible; verified read-only on both servers 15 Oct 2026. **81dadf68a9949b847fd8f38336c5d532eab861cd**.
- [x] **G0-04-F1:** Exactly three first V5.1 source/test files and new independent `nbot_v5_1` package selected — 15 Oct 2026; scope commit **7c624de187e274fe40172e64d03b8697f6e1f7aa**.
- [x] **G0-04-F2:** Historical helper provenance and excluded older 50-coin, SQLite, V3 package and trading imports approved — same evidence.
- [x] **G0-04-F3:** Exact immutable clock, source evidence/HOLD, digest and no-order authority rules accepted — same evidence.
- [x] **G0-04-F4:** T01–T12 offline tests and required proof for G1-01 defined; no tests executed — same evidence.
- [x] **G0-04 — First-code scope finalized and accepted:** Owner instructed us on 15 Oct 2026 to complete the code-scope review while they handle the manual VPS cleanup. **7c624de187e274fe40172e64d03b8697f6e1f7aa**, [approved scope](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_04_FIRST_CODE_SCOPE_V1_0.md). This is **scope approval only**, not application files or operating authorization.

**LATEST STATE — 15 Oct 2026: G0 [x] COMPLETE.** G0-01 source inventory, G0-02 selected pure-helper safety audit, G0-03 VPS inventory/owner backup waiver, owner-run old-VPS cleanup **independently VERIFIED** and G0-04 exact first-code scope approval are all finished. Both old NBOT checkout and reset paths are absent from both VPSs, and the obsolete Observation unit is absent, as shown in [completion proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_CLEANUP_COMPLETION_20261015.md), commit **81dadf68a9949b847fd8f38336c5d532eab861cd**. **No old backup made (waived).** Old GitHub branches remain reference sources. **G1-01 code/tests NOT STARTED; no paper or real trading authorization.**

### Record of every verified tick

| When (IST) | Small task or milestone | Evidence (GitHub commit and tests) | Meaning in everyday language |
| --- | --- | --- | --- |
| 2026-10-15 | [x] START-01 | 472c3f54415e06715f8b28673eee7d3b545338d4 / verified three-file tree | The clean branch exists and does not carry old code |
| 2026-10-15 | [x] START-02 | Same commit / Vision blob matches original | The approved product vision is safely copied |
| 2026-10-15 | [x] G0-01 legacy register and preliminary source/conflict review | **5d5133766b96ad3b21ab8b4c553e08740c3c7adb** / GitHub verified 27 entries and 12 conflicts; no code tests | We now have a written map of what to keep, rebuild, or leave behind; old code still untouched |
| 2026-10-15 | [x] G0-02 selected pure-helper source/side-effect/test audit | **2ebcc62f9f13aa4c7ed532cca108d9c359c77363** / exact source/test hashes, complete selected-helper call graph, 12 planned negative tests; no application tests | First safe helpers are identified, and outdated V3 initialization is excluded |
| 2026-10-15 | [x] G0-03 live VPS preservation/backup assessment | **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28** / [full live inventory](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_03_VPS_PRESERVATION_BACKUP_ASSESSMENT_20261015.md); old SQLite read-only quick_check=ok; data/file counts and SHA verified; backup readiness HOLD | We know what is on both servers and why it must not be erased |
| 2026-10-15 | [x] G0-03 legacy backup waiver and old-code discard approval | **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc** / explicit owner's instruction; no backups or deletion performed | We will start fresh without protecting outdated VPS-only NBOT files; any actual cleanup gets a separate checkmark |
| 2026-10-15 | [x] G0-04 preliminary three-file scope written | **697b55f4201e7d4f76daaa0bde0efc113b3c99f7** / 12 planned tests, no tests run | Our first clean modules are precisely defined but cannot be marked ready before owner-requested cleanup |
| 2026-10-15 | [x] Failed legacy cleanup documented | Same scope / read-only checks on both VPSs | The remote execution safeguard blocked deletion; both old Nbot checkouts and retired Observation-VPS unit remain |
| 2026-10-15 | [x] G0-04 first-code scope completed | **7c624de187e274fe40172e64d03b8697f6e1f7aa** / 3 new file paths, versioned pure API and T01–T12 offline acceptance defined; no code/tests | We know exactly what safe foundation to build first and what must be proved before calling it working |
| 2026-10-15 | [x] G0-CLEANUP-01–05, actual two-VPS legacy cleanup | **81dadf68a9949b847fd8f38336c5d532eab861cd** / owner PuTTY success logs PLUS independent fresh SSH verifier exit 0 | Both old NBOT installations are removed from their checked locations; no backups were made, as you authorized |
| 2026-10-15 | [x] G0 parent and owner Milestones 0/1 | **81dadf68a9949b847fd8f38336c5d532eab861cd** plus G0-01/G0-02/G0-03/G0-04 source/audit proofs | The fresh-start preparation and first-code plan are complete; next comes coding and testing |
| 2026-10-15 | [x] G1-01-A: first three clean V5.1 code/test files | Commits **e22b55a**, **5d9fc0e**, **f859f7f**; all three Git blob hashes verified against locally tested files | Our first small new program is built without copying the old bot |
| 2026-10-15 | [x] G1-01-B: T01–T12 offline safety suite | **12 of 12 PASS**, 0 failures; Python 3.13.5 Linux, strict no-order/known-at/missing-source cases | The new foundations passed the planned synthetic safety checks |
| 2026-10-15 | [x] G1-01-C/D: dependency, version, source and hash audits | 3-file GitHub diff, no old imports, 3.12 syntax PASS, matched exact file hashes; details in Engineering Roadmap | No network or trading capabilities were introduced; results can be reproduced |
| 2026-10-15 | [x] G1-01 overall first-code slice | [Engineering evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md) | First coding step is complete, **but the full G1 engineering milestone is not yet finished** |
| 2026-10-15 | [x] G1-02-A/B/C modes, evidence grades and guardian | **88c0f8acfec85eaf75b80529fd22b1274922baac**; 15/15 guardian tests PASS | The bot can describe different modes, but cannot accidentally activate trading or promote unsupported evidence |
| 2026-10-15 | [x] G1-02-D/E audit journal and recovery negatives | **88c0f8acfec85eaf75b80529fd22b1274922baac**; 18/18 journal tests PASS | Basic private, bounded audit records detect tampering, gaps, duplicate retries and unsafe files |
| 2026-10-15 | [x] G1-02-F/G/H combined test and GitHub checks | **45/45 tests PASS**, all five GitHub code blobs match the tested files; Python 3.13.5 | First and second foundation parts work together without importing legacy runtime or order functionality |
| 2026-10-15 | [x] **G1-02 child milestone complete** | [Detailed G1-02 acceptance and limits](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md), commit **88c0f8acfec85eaf75b80529fd22b1274922baac** | Safe nontrading building blocks exist; **the full G1 milestone is not yet done** |
| 2026-10-15 | [x] **G1-03-A/B/C** source, restart and journal first-file durability | **bb0df4b727e5817d47fe693206baba91e2706456**; G01–G11 PASS | Source evidence stays uncertain after any restart; journal records survive verified append and deny unauthorized orders |
| 2026-10-15 | [x] **G1-03-D/E/F/G** failure injection, integration, hash/test review | **bb0df4b727e5817d47fe693206baba91e2706456**; G12–G22 PASS, combined **67/67 PASS** Python3.13.5 | Broken records and invalid clocks cannot be silently converted into trades or source proof |
| 2026-10-15 | [x] **G1-04-A/B** independently run on both VPS target interpreters | **bb0df4b727e5817d47fe693206baba91e2706456**; Observation and Execution Python3.12.3, each **67/67 PASS**; clean temporary checkouts | Both servers can run exactly the same safe foundation version without enabling a service |
| 2026-10-15 | [x] **G1-04-C/D + entire G1 parent DONE** | [Final full G1 acceptance](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), commit **bb0df4b727e5817d47fe693206baba91e2706456** | Nontrading foundation and all its subphases are complete; market-data and paper/live acceptance are still future stages |
| 2026-10-15 | [x] G2-01 eligibility, 50/25/25 and 100-coin cohort | **005d82324d7cb009e4939075b49e00e41e25f271**, U01–U10/R01–R10 PASS | Qualified BTC included, 100 unique, complete source/rejection/known-at proof, future/leaked market information cannot enter |
| 2026-10-15 | [x] G2-02 safe finalized candles/history/BTC breadth | **005d82324d7cb009e4939075b49e00e41e25f271**, O01–O12 PASS | Only finalized five-minute market history; 96×100 bounded memory, missing/gap/disconnected symbols marked HOLD |
| 2026-10-15 | [x] G2-03 verified private receipts and public raw source archive | **005d82324d7cb009e4939075b49e00e41e25f271**, S01–S07/A01–A10 PASS | Small bounded local snapshots and exact public raw-byte receipts replay with disk/permissions/tamper guards |
| 2026-10-15 | [x] G2-04 one-time actual public USD-M Observation | **005d82324d7cb009e4939075b49e00e41e25f271**, 103 replayed public GET receipts, 100/100 qualified symbols | BTC and all selected symbols had 96 closed candles and a valid common as-of event, 100 healthy/0 HOLD and no account access |
| 2026-10-15 | [x] G2-05 all source safety tests on TWO VPSs | **005d82324d7cb009e4939075b49e00e41e25f271**, both Python3.12.3, **120/120 PASS** | Previous G1 safeguards still pass plus every newly tested G2 missing/stale/unknown/unsafe-data case |
| 2026-10-15 | [x] G2-05 both 100-coin VPS stress measurements | **005d82324d7cb009e4939075b49e00e41e25f271**, 120 events, 10 disconnected simulated sources, p99 51.867 / 60.326ms, RAM ~37MiB, disk 2.71MB | Broad lightweight Observation meets the measured synthetic capacity of both small VPSs |
| 2026-10-15 | [x] **G2-06 Owner Milestone 3 COMPLETE** | [Complete G2 acceptance report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), commit **005d82324d7cb009e4939075b49e00e41e25f271** | Engineering source/selection/finality/host tests passed; continuous deployment and any trading remain separate permissions |
| 2026-10-15 | [x] G3-01 original 24 detector source review | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, historic SHA and 5+19 golden fixtures | Exactly 24 old pattern descriptions are retained as **hypotheses**, not profitable strategies |
| 2026-10-15 | [x] G3-02 real-time-causal BTC/market/coin structures | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, strict G2 known-at bar export and 18 E-case tests | No future candle, missing BTC, old universe or fake verified cost silently becomes valid |
| 2026-10-15 | [x] G3-03 all 100×2 alternatives and research-vacancy masks | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 200 rows ×24 detector states, no-source and no-capacity checks | Both LONG and SHORT remain visible even when there are no research slots |
| 2026-10-15 | [x] G3-04 compressed full record and replay security tests | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 12 P-case tests | Tampered source/profit/order claims, disk full and corrupt entries are blocked |
| 2026-10-15 | [x] G3-05 actual tests and 200-direction performance on both VPSs | **157/157 PASS each**, p99 **571.799/549.342ms**, memory ~42MiB | Stage fits the measured synthetic small-VPS work budget |
| 2026-10-15 | [x] G3-06 one-time real public market intake 100→200 | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 100 eligible BTC-including public histories, 200 capacity-mask rows, 103 raw-source receipts replayed | Tested full G3 public integration while refusing fake trade capacity |
| 2026-10-15 | [x] **Owner Milestone 4 / all G3 COMPLETE** | [Full G3 report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1** | Safe descriptive exploration accepted; no profitable model or paper/real order |
| 2026-10-15 | [x] G4-01 frozen 100→20 BTC+control selection | [G4 evidence report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b** | 8 selection tests PASS, source-qualified cohort and honest pending warm-up, complete inclusion/exclusion/fair probabilities |
| 2026-10-15 | [x] G4-02 and G4-03 public source parser/segment recorder | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, verified 11 segment and 5 route test cases | 20-source quote/trade/mark contract, raw compressed byte SHA and restart HOLD, no orders |
| 2026-10-15 | [x] G4-04 settled public funding contract | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, 5 tests + actual BTC 2 settled events | Never confuse indicative funding with settled history or position-specific trading cost |
| 2026-10-15 | [x] G4-05 two-VPS engineering tests and deep-20 stress | **186/186 PASS each**, exact `07186992...` code SHA | Both 3,600-frame benchmark PASS; latency, RAM and compressed source receipt budget measured |
| 2026-10-15 | [x] G4-05 actual public source audit run | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b** | 3,077 real WSS frames replayed; 20/20 quote+mark, 19/20 trades and 47 gap HOLDs recorded rather than hidden |
| *Next review* | [ ] **G4-06-A real 20/20 original-source gap-free evidence** | **HOLD — actual live-source deficits** | Source epochs/trade gaps, sustained rates, separate-host restore and independent custody must PASS before G4 parent can complete |

**Use [ ] and [x] on the individual subtasks throughout development.** Owner milestones 0 and 1 (engineering G0) are now completed; **the first application development milestone (G1) and all trading stages remain open.**

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


**CURRENT latest gate truth, 15 October 2026:** Milestones 0–4/G0–G3 PASS. Milestone 5/G4 **[ ] HOLD** despite many completed [x] G4 components. New **186/186 tests passed independently on EACH VPS**, real public source capture **3,077 WSS messages** with **47 unresolved trade-ID gap reports** and only **19/20 markets with valid trade frames**. Source grade/24h rate/off-host restore are **NOT** independently accepted. [G4 progress/HOLD proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**. G5–G12 and all service/trading modes remain LOCKED.


### G1-01 — First clean code and offline test completion (15 Oct 2026)

- [x] **G1-01-PACKAGE:** The entirely new independent `nbot_v5_1` package identifies itself as V5.1; no old V3 package loader used.
- [x] **G1-01-CLOCK:** Five-minute events cannot be evaluated before their candle closes, and unsafe timestamps are rejected.
- [x] **G1-01-HOLD:** Missing BTC/symbol, stale/future sources and malformed route/digest metadata have explicit HOLD reasons, never invented price/economic proof.
- [x] **G1-01-DIGEST:** Stable, version-scoped identifiers reject unsafe numeric encodings and cannot imply a valid trade.
- [x] **G1-01-NO-ORDER:** Only NONE observation authority exists; no paper, testnet or real exchange order interface.
- [x] **G1-01-T01/T02/T03/T04:** Side-effect-free imports, correct 5.1 identity, candle-close rule and invalid-timestamp rejection PASS.
- [x] **G1-01-T05/T06/T07/T08:** Missing-source HOLD, no false original-source qualification, stable unique IDs, reject malformed JSON/float values PASS.
- [x] **G1-01-T09/T10/T11/T12:** Stable reason codes, no-order-only states, clean stdlib-only dependencies and offline deterministic repeatability PASS.
- [x] **G1-01-HASH:** GitHub commit and file hashes match the local test set: [package](https://github.com/samqju/Nbot/blob/nbot-v5.1/nbot_v5_1/__init__.py), [core](https://github.com/samqju/Nbot/blob/nbot-v5.1/nbot_v5_1/core.py), [12 tests](https://github.com/samqju/Nbot/blob/nbot-v5.1/tests/test_v5_1_core.py).
- [x] **G1-01-COMPLETE:** All first-code scope checks performed and verified. Detailed exact SHA/command/results in the [Engineering Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md).
- [ ] **Parent G1 acceptance and later application steps:** Journal/mode/recovery/integration tasks and engineering qualification not yet done. Trading stays locked.

**Scope guard:** 12 synthetic unit tests only, **not** market observation, actual trade or model-performance proof. Historical *old* backup waiver does not apply to newly generated V5.1 evidence. No change to either VPS and no permission to run services yet.


### G1-02 — Second safe foundation milestone, completed 15 Oct 2026

- [x] **Modes locked:** Defaults remain offline/no network/no orders; proposed virtual/paper/real mode values are only descriptors, not operating permissions.
- [x] **Source grades honest:** Synthetic/metadata-only input cannot become qualified original market and after-cost evidence.
- [x] **Guardian veto:** Any proposal yields NONE authority and NO_TRADE, including healthy-looking source metadata and unapproved model IDs.
- [x] **Small metadata journal:** Hash-linked capped append-only records and verified replay, not raw WebSocket prices.
- [x] **Negative/failure cases:** Torn record, changed evidence, unsafe file links/permissions, duplicate retry, restart, quota and concurrent writers tested.
- [x] **45 offline tests PASS:** 12 G1-01 + 15 foundation + 18 journal, no failures. Local Linux Python 3.13.5; 3.12 syntax parsing only.
- [x] **GitHub proof:** [G1-02 detailed report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md), commit **88c0f8acfec85eaf75b80529fd22b1274922baac**, matching hashes for all five changed files.
- [x] **G1-02 COMPLETE** as the second narrow code milestone; no trading permission or VPS deployment.
- [x] **Later G1 parent completion (15 Oct 2026):** G1-03 simulated outage/write-loss and restart HOLD, journal directory durability and source causality, plus actual target-Python tests on both VPSs **67/67 PASS**; [final proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), **bb0df4b727e5817d47fe693206baba91e2706456**. **Physical power cut and future ORIGINAL source custody are not G1 acceptance claims** and remain separate stricter G2/G4 operational qualifications.

**Remaining lock:** This basic journal cannot replace a high-frequency original market archive, host backups or evidence-grade scientific qualification. The old VPS backup waiver applies solely to the **old deleted installations**, not to new NBOT V5.1 source evidence.


### Complete G1 owner sign-off — 15 October 2026

All small checks documented in this roadmap and the [Engineering Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md) now have test- and commit-backed proof:

- [x] **G1-01:** Pure new V5.1 source clock/ID/metadata HOLD core and 12 offline tests.
- [x] **G1-02:** Operating modes locked, evidence grades conservative, independent guardian NO_TRADE, bounded private append-only audit journal, 15+18 offline tests.
- [x] **G1-03:** Causal versioned source envelope; restart always OFFLINE/HOLD; file/parent directory durable fsync/retry; 22 new no-order, power-failure-simulation and integration tests.
- [x] **G1-04:** Actual committed source tested on **both** target Linux VPSs running Python3.12.3; each ran all **67 tests with 0 failures**, no services/deployment.
- [x] **Entire owner Milestone 2 / engineering G1:** **PASSED** for nontrading foundation. See [complete G1 report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), commit **bb0df4b727e5817d47fe693206baba91e2706456**.
- [ ] **G2: actual public market observation** is next, requiring independent permissions, source-grade validation, 100/20 scale, crash-consistent original-source archive and benchmarks before its own gate passes.

**No live observation, paper or real trading released by this milestone.** Synthetic unit tests and hash-linked metadata cannot establish profitable trading strategies, market data authenticity or protection against actual power loss. Those later safety tests will not be waived merely because the owner previously declined backups of the old abandoned installation.


### Entire G2 owner handoff — 15 October 2026

- [x] **G2-01 — Discover:** Source-qualified USD-M PERPETUAL markets and exact 50 turnover/25 gainers/25 losers deduplicated 100 with BTC, point-in-time three-source digest and honesty about rejected symbols.
- [x] **G2-02 — Observe:** Only finalized five-minute candles, strict 96×100 bounded historical bootstrap, chronological as-of event snapshots, BTC/breadth, explicit HOLD for disconnect/lag/time gaps and no fake data.
- [x] **G2-03 — Preserve:** Private finite fsynced compact universe/event receipt store and separate byte-exact public-source capture/replay; neither auto-discards evidence or claims high-frequency original-grade custody.
- [x] **G2-04 — Genuine public read-only check:** A one-time HTTPS GET-only smoke sampled 100 actual qualified contracts with 96 confirmed finished five-minute bars each, BTC and 100 valid common-as-of states. **103** raw public source receipts hash-matched through temporary replay; **NO API keys or orders**.
- [x] **G2-05 — Prove scale/safety:** 53 new G2 tests plus 67 prior G1 regressions = **120/120 PASS on EACH VPS Python3.12.3**. 100-coin ×120-event resource stress measured p95/p99/CPU/RSS/disk independently on both hosts, all budgets met.
- [x] **G2-06 — COMPLETE G2:** [Complete final source/test/evidence report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), **005d82324d7cb009e4939075b49e00e41e25f271**. G2 is a **read-only ENGINEERING acceptance**, not permission to start a production system or paper/live trading.
- [x] **G3-01 through G3-06 COMPLETED after this earlier handoff note:** Original 24 V4 detectors individually audited, 100×2 causal full denominator, missing BTC/source/capacity masks, audited G3 record replay, **157/157 tests on both VPSs** and real read-only public 100→200/103-receipt evidence passed. Current [G3 full report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**. **G4-01 now next, still unchecked.**

**For next chats:** Open the G2 report and current Owner & Engineering Roadmaps in `samqju/Nbot` branch `nbot-v5.1`. Actual G2 code under `nbot_v5_1/{universe,observation,observation_store,public_market,source_archive}.py` was tested at commit `4ba07385bb06ad8cde2460d83953448386f1a751`. Do not return to old bot code as the running application. No permanent V5.1 VPS installation/service yet; full source-grade scientific research remains G4/G6 and paper/real releases locked. The owner's old-backup waiver never applies to new V5.1 market evidence.


### Permanent continuation pointer — 15 October 2026

- [x] **Living chat handoff maintained for G3 completion:** [Current Status / Next-Chat Handoff](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md) now pins **G0/G1/G2/G3 all [x]**, final G3 evidence **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 157 passing tests on BOTH VPSs, original 24 rules, exact code SHA `5d9707fe...`, read-only 100→200 public mask proof; **G4 next [ ]**.
- [x] **G1 final acceptance report clarified:** It now says **ENTIRE G1 PASSED** prominently and distinguishes historical G2-next wording from current G3-next status. No original G1 results were rewritten or reclassified as production/trading authorization.


### G3 owner 24-detector individual checklist (15 October 2026)

Every line is a descriptive setup **hypothesis**, not permission to enter a trade or proof of profitability. [Exact individually reviewed source and test details](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_LEGACY_COMPONENT_REUSE_REGISTER_V1_0.md) and [G3 final engineering acceptance](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md) (**fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**):

- [x] **Detector 01: `TREND_CONTINUATION_V1`** — old source identity and context positive example tested; NO_TRADE remains mandatory.
- [x] **Detector 02: `TREND_PULLBACK_V1`** — old source identity and context positive example tested; NO_TRADE remains mandatory.
- [x] **Detector 03: `STRETCHED_REVERSAL_V1`** — old source identity and context positive example tested; NO_TRADE remains mandatory.
- [x] **Detector 04: `VOLATILITY_EXPANSION_V1`** — old source identity and context positive example tested; NO_TRADE remains mandatory.
- [x] **Detector 05: `RELATIVE_STRENGTH_V1`** — old source identity and context positive example tested; NO_TRADE remains mandatory.
- [x] **Detector 06: `DONCHIAN_BREAKOUT_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 07: `BREAKOUT_RETEST_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 08: `FAILED_BREAKOUT_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 09: `RANGE_EDGE_REJECTION_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 10: `BOLLINGER_REENTRY_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 11: `RSI_RECLAIM_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 12: `EMA_CROSS_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 13: `EMA_PULLBACK_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 14: `MACD_CROSS_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 15: `SQUEEZE_BREAKOUT_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 16: `VOLUME_BREAKOUT_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 17: `VWAP_RECLAIM_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 18: `INSIDE_BAR_BREAKOUT_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 19: `OUTSIDE_BAR_REVERSAL_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 20: `ENGULFING_REVERSAL_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 21: `PIN_BAR_REJECTION_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 22: `MULTITIMEFRAME_TREND_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 23: `CONFIRMED_SWING_CONTINUATION_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.
- [x] **Detector 24: `BTC_RELATIVE_MOMENTUM_V1`** — old source identity and LONG & SHORT positive examples tested; NO_TRADE remains mandatory.

- [x] **All 24 individual V4 detectors audited and individually checked.** A detection does NOT mean a good strategy or a valid trade.
- [x] **G3 full completion:** 157/157 tests on both VPSs; G3 public 100×2 source/capacity records replayed; 100×2×24 speed/memory/disk benchmark PASS. **Owner Milestone 4 [x].**
- [ ] **G4 deep-20 research source selection and custody, next:** still awaits actual original source, selection and future offline engineering acceptance. G5+ all locked.


### Later G4 source engineering checkpoint and unresolved next item — 15 Oct 2026

- [x] **G4 partial documentation persisted:** [G4 completed subtasks plus live-source HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), commit **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**. 100→20 BTC freeze and prospectively recorded controls; three public USD-M source routes, segment SHA/gzip replay and independent public settled-funding validation built; 186/186 Python3.12.3 tests on EACH VPS and 20×3×60 benchmark PASS.
- [x] **Actual public 20-source trial and limitation recorded:** 3,077 raw public WSS frames replayed, 20/20 quote and mark but 19/20 trade, **47 aggregate-ID/underlying trade continuity gaps** and insufficient sustained original source retention. This is source HOLD, not G4 pass.
- [ ] **G4-06-A currently NEXT:** prove clean source warm-up for every one of the frozen 20 coins including BTC. Do not compensate for gaps with REST candles, retroactive detector matches or artificial trades.
- [ ] **G4-06-B/C/D/E:** independent long-term public WSS throughput/disk, source evidence custody/settled funding and actual off-host restore, then final G4 parent acceptance only if all PASS.

**Permanent status:** G0 [x], G1 [x], G2 [x], G3 [x], **G4 [ ] HOLD**, G5–G12 [ ]. No services started; no virtual, paper or real trading opened.


### Milestone 6/G5 later offline code completion and remaining checks (15 Oct 2026)

- [x] **G5 implemented separately from unfinished G4 live-source work:** [Source, 38-case G5 test and two-VPS 224-case acceptance report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G5_OFFLINE_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **79ff4da7fc3967e19df1f8b9a86db384ab6e847d**, source SHA `2efea2cccb086a1f292ae90c1eaac414620f342b`. 40-slot/source-masked Research code and fsynced original-intent/path journal were developed; 224/224 tests on BOTH VPSs, independent 24-review/40 max tests and p99/RSS/disk benchmark PASS.
- [x] **Future research cost honesty protected:** All 600 hypothetical path closures in benchmark are SYNTHETIC_PATH_ONLY_NOT_EXECUTABLE, **0** qualified after-cost outcomes; no G6 Learning label, API order, paper account or real money authority.
- [x] **Bench blind spot identified and code amended:** The passing crash replay benchmark had zero occupied at restart and could not prove 'restart with 40 live'. New forced-40 code is committed, but not yet independently run.
- [ ] **G5-06-A next offline test:** Rerun forced-40-active-at-restart benchmark on BOTH VPSs, collect separate exact outputs; launch was blocked, not pass.
- [ ] **G5-06-B deferred priority startup test:** First close G4-06 genuine 20-source continuity/endurance/custody/off-host restore, then qualify true G5 original market first-touch/fee/funding path with complete source. Owner explicitly asked to defer live testing until safe overall startup; do NOT invent original-path success.
- [ ] **G5 parent / Owner Milestone 6 final signoff:** HOLD until both unverified checks PASS. **Offline coding can continue into G6 while these checks remain tracked; does not unlock virtual/paper/REAL runtime.**

**Current status:** G0–G3 complete; **G4 [ ] source HOLD**, **G5 [ ] full acceptance HOLD (offline code/test implemented)**; G6–G12 not yet accepted. All services and exchange order permissions remain disabled.


### Milestone 7/G6 new engineering progress and later full-40-restart verification (15 October 2026)

- [x] **G6 offline software, tests and measurements:** [Final G6 recovery/economics/archival evidence and HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G6_OFFLINE_ENGINEERING_ACCEPTANCE_AND_SOURCE_HOLD_20261015.md), exact tested GitHub revision `029cda1d75138fc1bf96f3502021ca5a236693c9`. **254/254 PASS on BOTH target VPSs**, 20×3×24 =1,440 market-source fixtures and exact segment replay, p99 **50.938/61.420ms**, source+sealed archive disk **198,169 bytes**, RAM **29,744/29,628KiB**. Zero source-qualified trades/economic training labels; no Binance order.
- [x] **G5-06-A full40 crash restart test updated to PASS:** 40/40 active virtual lab hypotheses restored occupying SOURCE/RESTART HOLD on BOTH independent hosts; p99 186.430/195.132ms, journal 1.30MB; older earlier "unexecuted" narrative is superseded.
- [ ] **G4 live original data** remains prerequisite for future market-source acceptances; initial 20-market public WSS capture had 47 trade gaps and only 19/20 valid trade-source symbols.
- [ ] **G5 original-scientific first-touch** remains unqualified; no lab model is a real bid/ask execution or after-cost win.
- [ ] **G6 original economic/independent off-host and true resource proof** remains startup priority. A locally restored synthetic archive is NOT a physical second-host source backup.
- [ ] **G6 parent** remains HOLD. Continue offline engineering of G7–G11 only, without calling synthetic results scientifically qualified or starting NBOT services or paper/real trading.

**Verified current state:** G0 [x], G1 [x], G2 [x], G3 [x], **G4 [ ] original market source HOLD**, **G5 [ ] source-integrated virtual Research HOLD** (full40 crash now PASS), **G6 [ ] original economics + off-host restore HOLD** (offline code/test PASS), G7–G12 [ ].


### G7 owner-facing final offline Engineering evidence and genuine Learning HOLD (15 October 2026)

[Permanent G7 complete evidence report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G7_OFFLINE_LEARNING_ACCEPTANCE_AND_GENUINE_EVIDENCE_HOLD_20261015.md), commit **225bc79f289ee93b2845061e7022c0d883507bff**, exact tested G7 source SHA `49cb90bc35a8e6c79dcf4cebf8db0edc1f0cfc4d`. New clean G7 code `learning_contract.py`, `learning_science.py`, `learning_snapshots.py`, 31 direct tests and a 2,000-example capacity benchmark. Both VPSs independently **285/285 PASS** Python3.12.3 in 17.310/17.401 seconds; synthetic 2,000-row /100 shared-BTC-market-block benchmark PASS p99 row creation **50.129/9.070ms**, RSS **24,308/24,196KiB**, disk **134,381B**, CPU 1.787/1.890s. Every result NO_MODEL / NO_TRADE and zero genuine after-cost training rows. The test includes positive-looking fake market wins to prove these still cannot unlock a model.

- [x] G7-01 full decision-time BTC/coin/regime/detector/frozen-plan features and source grade plus honest maturation HOLDs, old science audit.
- [x] G7-02 pending/held/censored status denominator, fair prospective inclusion fractions, correlated BTC/coin/direction grouping and no duplicate 24 detector labels.
- [x] G7-03 earlier/later market separation with dependence purging, reproducible uncertainty, model-vs-no-trade comparator that always abstains without qualified originals.
- [x] G7-04 finite owner-private hashed/fsynced laboratory evidence and corruption/forged “passed” object rejection.
- [x] G7-05 all **285/285** combined G1–G7 tests and measured 2,000 synthetic row /100-cluster stress PASS separately on both authorized target VPSs.
- [ ] **G7-06-A REAL first 2,000 independent source-qualified matured virtual outcomes:** **0/2000**; source-genuine evidence must be collected after controlled startup and G4/G5/G6 independent data-check release.
- [ ] **G7-06-B genuine conditions/edge stability and time-forward uncertainty:** no original-price/fee/funding historical sample yet; no automatic assumption of profitable strategies.
- [ ] **G7 parent Milestone 8:** HOLD, cannot check genuine Learning even though all coding/testing stages [x].

**Current:** G0 [x] G1 [x] G2 [x] G3 [x] FULL. G4 [ ] original-source HOLD, G5 [ ] original-path HOLD, G6 [ ] source after-cost/off-host HOLD, **G7 [ ] genuine source-qualified scientific Learning HOLD (offline fully coded and tested)**. G8/G9/G10/G11/G12 [ ] next offline development. NBOT permanently stopped, no virtual source engine, PAPER or REAL mode activated.


### Milestone 9 / G8 offline model Training development report (15 Oct 2026)

[Permanent G8 code, 319 regressions, 2,000 LAB freeze/test and pending real Champion acceptance](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G8_OFFLINE_TRAINING_ACCEPTANCE_AND_ORIGINAL_SCIENCE_HOLD_20261015.md), commit **6d467c2f9b17c1eaea94347ebd3fe060005dfbba**; tested SHA `12ef09ebdf0d1bdfa6903f4dc8f1759110a41e68`. No future-data use, 34 new G8 M01–M34 tests plus 285 earlier = **319/319 on both target VPSs**, 2,000 synthetic/100 BTC dependent market-block workload and independent SHA model-card replay PASS; 49 train/49 untouched LAB holdout/2 purged, 0 real qualified outcomes, +36.40R simulated laboratory only, no money or scientific model claim.

- [x] G8-01 safely audit old Training/R24 ranking and freeze predeclared training, independent source/maturity/cost gates.
- [x] G8-02 bounded BTC/market/side condition model and leak-free purged earlier/later data, positive lower bound required for *LAB hypothetical* only.
- [x] G8-03 test against doing nothing in separate later LAB periods, fair one-hypothesis occupancy and drawdown/abstention.
- [x] G8-04 owner-private finite fsynced, non-executable JSON frozen LAB-only model card with SHA independent replay and tamper/false-authority rejects.
- [x] G8-05 both-VPS 319 tests+benchmark positive/negative PASS; no services or actual orders.
- [ ] G8-05-D small cleanup: isolated Observation-VPS temp source folder `/tmp/nbot-g8-c0qNaV` requires authorized removal after tool safety block; Execution test tree removed.
- [ ] G8-06 actual 2,000 genuinely matured independent after-cost virtual outcomes **0/2000**; original source regime/scientific Champion edge and owner approval unavailable, so do NOT check entire parent G8.

**Current owner status:** G0–G3 [x], G4–G7 original source/science [ ] HOLD, **G8 original Champion [ ] HOLD despite completed offline 319-case engineering**, G9–G12 [ ]. NBOT stopped; next optional offline G9 paper guardian DESIGN may proceed without enabling paper mode or claiming a qualified Champion. All legacy V5 two-model-first-paper conflict must be reviewed in G9.


### Milestone 10/G9 latest Champion-first paper guardian engineering and real release HOLD (15 October 2026)

[Permanent dated G9 complete tested offline paper-ledger/guardian and independent PAPER release HOLD report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G9_OFFLINE_CHAMPION_PAPER_ENGINEERING_AND_RELEASE_HOLD_20261015.md), commit **0b23bf38096509aafd61096039b78be4bb06b662**, tested code/source SHA `fa2111e32bd0da4c36bf4fe58a7da14f4936c815`. Old R22 two-model release mistake reconciled: **one QUALIFIED Champion alone can later be owner-approved for first PAPER**, no Challenger initially, one position/book, G10 Challenger later. New pure LAB-only HMAC paper-guardian and fee/funding/cash ledger, restart/source HOLD, at most one position and true no-paper-release lock, **355/355 tests EACH VPS**, benchmark 100 LAB settles/100 blocked second opens/1 crash-held, p99 113.381/108.130ms; all synthetic, zero financial or owner paper authority.

- [x] G9-01 reviewed conflicting historical paper engines, new frozen initial Champion-only policy, safe LAB signature and model/mode/session identity.
- [x] G9-02 independent quote/source/date, fee/slip/full funding interval/risk/leverage/spread, single-position and NO_TRADE guardian.
- [x] G9-03 hypothetical bid/ask based LONG/SHORT book, stop/target/trailing protection, reproducible cash/fees/funding and true restart cash audit.
- [x] G9-04 owner-private bounded fsynced SHA ledger, torn/concurrent/duplicate/source HOLD and independently replayed position on crash.
- [x] G9-05 **355/355 tests** and 100 LAB settlement stress, 100 duplicate-position veto, 1 restart hold PASS on BOTH hosts; all G9 test temp trees removed; ZERO NBOT service startup.
- [ ] G9-06-A genuine independently qualified G8 Champion: 0/2000 truly qualified Learning outcomes; no Champion yet.
- [ ] G9-06-B separate authentic OWNER PAPER-only authorisation and original-feed source/cost qualified risk guardian: no approval yet.
- [ ] G9-06-C genuine owner-approved first Champion paper simulation on Execution VPS with paper-account/stop/restart monitors: not started.
- [ ] G9-06-D entire G9 actual PAPER stage: HOLD despite offline engineering success.

**Owner release status:** G0–G3 [x]; G4–G9 parent original-source/scientific/PAPER activation [ ] HOLD; G10–G12 next for offline code, paper and real funds LOCKED, services STOPPED. The old G8 Observation test-only `/tmp/nbot-g8-c0qNaV` is still a separately documented cleanup concern and was not falsely ticked.


### Milestone 11 — Latest G10 evidence and future real-paper priority (15 October 2026)

[Detailed 400-case/two-VPS G10 LAB comparison and genuine PAPER HOLD record](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G10_OFFLINE_CHALLENGER_PROMOTER_ACCEPTANCE_AND_GENUINE_PAPER_HOLD_20261015.md), code/test SHA **`15de49e8bf1a8c363c684021ec34db61293881f4`**. Clean one shared market-event stream + two separate signed, hash-journaled LAB books, one simulated position each, no account or trading release. **400/400 tests PASS each actual Python3.12.3 VPS** (355 baseline +45 new G10), suite 19.382/19.862s. Two independent simulated 100-trade books on 200 shared BTC/market events; same costs and policies; original qualified new independent outcomes **0**, genuine settled PAPER trades **0**. Hard bounds PASS: p99 shared event **123.784/118.200ms**, ~25MiB RSS, **592,725B** across 3 SHA journals, both hosts. Four outcome classifications tested, but actual promotion/paper authority NONE and route HOLD. All six G10 temp checkouts removed from both VPSs; NBOT STOPPED.

- [x] G10-01 frozen synthetic-only new Challenger evidence/one fair predeclared evaluation protocol; no fake additional 2,000 independent original Research cases.
- [x] G10-02 true independent laboratory Champion and Challenger accounts, shared synthetic common period, separate risk/position/fee/funding and no forced trades.
- [x] G10-03 fair time-aligned event, abstention and source/missingness accounting, modeled costs, risk/drawdown and 100-per-model later genuine PAPER guideline (not miscounted).
- [x] G10-04 RETAIN/REJECT/HOLD/hypothetical RECOMMEND_PROMOTE diagnostic but ACTUAL HOLD, 3 durable/replayable audit journals, fail-closed partial restart.
- [x] G10-05 **400/400 tests** and 200-event/100+100 settlement benchmark PASS on EACH authorized VPS, no trades or services, all G10 test trees removed.
- [ ] G10-06-A another **2,000 newly matured independent true Research outcomes**, independently qualified new Challenger and frozen evaluation; not available.
- [ ] G10-06-B actually signed/owner-permitted two-books prospective PAPER with genuine source/fees/risks and ≥100 honest settled PAPER trades per model *where possible*; none performed.
- [ ] G10-06-C independent owner reviewed model routing/rollback after genuine evidence; not attempted.
- [ ] G10-06-D whole G10 parent remains HOLD, no auto-promotion or paper/real release.

**Owner current status:** G0–G3 [x] full; G4–G10 [ ] source/scientific/owner-PAPER parent HOLD despite completed tested G10 offline machinery. G11 next offline integration; G12 never authorized. All NBOT services stopped. An unrelated isolated G8 Observation test directory `/tmp/nbot-g8-c0qNaV` remains pending separate cleanup after prior tool block.
