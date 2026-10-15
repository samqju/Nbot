# NBOT V5.1 — Your Plain-Language Development Roadmap

**Roadmap version:** 1.3 (G4 verified partial engineering with explicit source HOLD)  
**Date:** 15 October 2026  
**Status (current, 15 October 2026):** **Milestones 0–4/G0–G3 [x] COMPLETE**. **Milestone 5/G4 [ ] HOLD (partly built)**: G4-01 100→20 with BTC, G4 raw public socket/segment/funding code, **186/186 tests on BOTH VPSs** and 3,600-frame synthetic deep-20 benchmark PASS; actual public sample **3,077 WSS frames** but **47 trade-continuity gaps and only 19/20 trade-stream coverage**, so full original source custody is NOT qualified. **G4 parent unchecked; G5–G12 untouched, no installed services or virtual/paper/real trading.**  
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
