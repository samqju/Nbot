# NBOT V7 — Master Chat Handover and Continuity Journal

**Created:** 2026-10-19  
**Authority:** Owner-approved continuity process. This document is the restart point for a new ChatGPT conversation if this chat is deleted, reaches context limits, or development changes hands.  
**Canonical GitHub repository:** https://github.com/samqju/Nbot  
**V7 active implementation branch:** [V7](https://github.com/samqju/Nbot/tree/V7) — new implementation from the preserved planning branch. Historical roadmap remains on [roadmap/v7-comparative-learning-20261019](https://github.com/samqju/Nbot/tree/roadmap/v7-comparative-learning-20261019).  
**Frozen roadmap:** [V7_ROADMAP.md](V7_ROADMAP.md)  
**Archived discoveries:** [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md)  
**Legacy code parent:** [prototype/v6-freqtrade-freqai-20261016](https://github.com/samqju/Nbot/tree/prototype/v6-freqtrade-freqai-20261016)  
**Current stage:** G0 legacy source audit complete. **V7 offline G1–G5 engineering implementation IN PROGRESS** (GitHub branch V7). Nine-month A/B1/B2 offline baseline implemented; first source-compile and 9 synthetic CI unit tests pass; historical full-market source and native-economic readiness NOT verified. No VPS or trading operation executed.
**Owner's latest technical refinement (2026-10-20):** Strategy-aware **all-market** universe selection has priority: calculate strategy signals for every eligible coin, use a causal comparative LightGBM ranker to shortlist up to 20, and preserve labeled MFE/MAE/BTC-at-entry and future-path trade outcomes, including sampled outside-top20 controls. Recorded as a **design refinement proposal** in [V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md](V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md); existing frozen roadmap and numerical gates have not been silently changed or approved.

**Owner decisions pending:** [V7_NUMERIC_GATE_PROPOSAL.md](V7_NUMERIC_GATE_PROPOSAL.md) proposes G0–G8 numerical gates; [V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md](V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md) proposes an adaptive/replacable brain replacing static strategy authority. **Neither proposal is finally frozen or deployment-authorized.**  
**Current deployment state:** GitHub research code exists on branch V7 but **has NOT been deployed to VPS**. NO V7 market-data download, native historical backtest, paper trading, dry-run exchange connection or real order has started or been approved. V3–V6 original branches and deployments untouched.

---

## 1. Instructions for the next ChatGPT conversation — READ FIRST

1. Open this file from its **V7 working branch** through the connected GitHub app. Read it fully, especially **Current state, Frozen decisions, Blockers, Next exact step, and Chronological journal**.
2. Read **V7_ROADMAP.md** and **V7_LEGACY_EVIDENCE_LEDGER.md** from that same branch before proposing work or relying on summaries.
3. Check the actual branch head and recent commits; **do not assume this file is current solely because it exists**. If GitHub has changed since the last journal entry, reconcile the changes, capture the missing work and evidence, then proceed.
4. Read the relevant original V3/V4/V5/V6 evidence and code in their original refs. **Never rely on earlier assistant claims where the repository contains more precise test results.**
5. At the start of a new session, report: branch, latest verified commit, current gate, last accepted outcome, outstanding blocker, proposed next one bounded step, and whether any VPS/trading action is authorized.
6. Treat this handover as a **living continuity document**, not as permission to execute trading operations. The roadmap is the design authority; the evidence ledger records prior results; source code and immutable run artifacts prove actual execution.
7. **MANDATORY: Update this handover on the same branch after EVERY project step, discussion that changes a decision, completed or failed experiment, meaningful finding, authorization change or code/document change.** Record the update in GitHub and verify the new commit **before declaring the step finished**.
8. If any write to GitHub cannot be completed, state clearly that the handover **has not been updated**. Provide the exact pending journal text to the owner; do not invent a saved commit or proceed as if continuity were preserved.
9. A future model cannot automatically watch all new chats or perform work in the background without an explicitly configured mechanism. **Each future NBOT working session must perform the GitHub update explicitly as part of that work.** No unsupported promise of unattended synchronization.
10. Before touching VPS, credentials, services, repositories outside this branch, paper trading or real trading, determine exact permitted scope and obtain separate explicit approval when required by project safety gates.

### Copy/paste prompt for a new chat

> Continue my NBOT V7 project. My source of truth is GitHub repository samqju/Nbot, branch roadmap/v7-comparative-learning-20261019. First read V7_CHAT_HANDOVER.md, V7_ROADMAP.md and V7_LEGACY_EVIDENCE_LEDGER.md from that branch via the GitHub connection. Verify the branch head and latest journal state. Tell me the current stage, prior verified findings, unresolved problems and next bounded task. Follow all frozen no-trading and scientific validation rules. After every completed step or important decision, update V7_CHAT_HANDOVER.md and commit the change to the same branch. Never overwrite earlier evidence, assume paper/live permission, or claim tests ran without verifiable artifacts.

---

## 2. Current state — latest verified at creation (2026-10-19)

| Item | Current verified status |
|---|---|
| V7 planning branch | `roadmap/v7-comparative-learning-20261019`, created from V6 prototype branch |
| V7 roadmap | `V7_ROADMAP.md`, committed in initial V7 documentation freeze |
| Legacy evidence ledger | `V7_LEGACY_EVIDENCE_LEDGER.md`, committed in initial V7 documentation freeze |
| V7 handover | This file, created under the new owner-requested continuity rule |
| V7 executable research pipeline | NOT BUILT / NOT RUN for V7 |
| Three-month entire Binance USDT-perpetual historical download | PROPOSED; NOT YET RUN FOR V7 |
| 10–15 independent strategy family universe candidate generator | PROPOSED; V6 has eight older strategy families as documented negative controls |
| 20-candidate synchronized shadow simulation | PROPOSED for V7; G0 reviewed V3 capital-uncapped replay/V6 25×8 candidate generation; integration not built or tested |
| V7 model trained or validated | NO |
| V7 forward paper or real trading | NO — expressly unapproved |
| Other branches and deployed systems | Preserved; **not** modified as a side-effect of V7 planning |
| Decision currently open | G1 historical all-USDT-M perpetual registry, completeness/survivorship and three-month storage/data source design; no downloading/ML/VPS work authorized yet |

**Important precision:** 'No V7 training' does not mean no historical machine-learning research existed. Extensive older V6 25×8 candidate training, official native research and counterfactual labeling already exist; V7 starts by auditing/reusing them.

### Existing GitHub sources discovered

- `prototype/v6-freqtrade-freqai-20261016`: V6 research code, data acquisition, global 25×8 selector, native backtests and archived evidence.
- `v6/review-base-20261016`: earlier V6 review/reference branch.
- `main`: substantial V3 documentation including broad counterfactual replay, V4 research factory, V5 architecture, execution safety and evidence lineage.
- Many V5 feature/integration/deployment branches remain. No dedicated branch name containing 'v3' was returned in the 2026-10-19 branch search. A search for 'v4' found an integration branch, not a standalone V4 branch. **Do not assume standalone historical branches exist unless verified.**
- VPS research paths reported in V6 docs include `/root/nbot-v6-m1-20261016/` with result ZIPs, ledgers and models. The existence of historical paths in GitHub reports is **not** a fresh proof those bytes are still present or trustworthy today.

---

## 3. Why V7 exists — discussion and decisions preserved

### 3.1 The owner's core diagnosis

The owner identified V6's most consequential weakness as **choosing the best trade among many available opportunities**. Selecting one trade for scarce capital is rational, but learning solely from that executed trade risks missing lessons from nineteen rejected opportunities.

**Critical correction based on later GitHub inspection:** V6 was **not** limited to training only on the executed trade. Its global Stage 3 research generated **914,878** historical candidate labels over 25 coins × 8 strategies and simulated a one-slot native portfolio. The trained ranking policy selected **zero trades** in all four forecast windows. Thus the verified V6 problem is broader: original strategies' after-cost weakness, target/exit/payoff mismatches, 50% calibrated-win and conservative gates, calibration/uncertainty, regime eligibility, imperfect historical fills and unseen-data limitations. V7 must examine actual per-candidate training quality, not rebuild labels under a false historical premise.

### 3.2 Initial outside advice incorporated selectively

The owner supplied a separate AI-trading-tools discussion recommending **specialist ML libraries for decisions, Freqtrade/FreqAI or other proven trading infrastructure for backtests/execution, inexpensive market scanning, and ML only for a bounded candidate set**. Owner had indicated about **2 CPU and 8 GB RAM** for VPS research and interest in an ambitious daily portfolio return. V7 **does not promise 1% daily** and does not use an LLM prompt as its live trade decision engine.

Useful: Python/pandas/numpy, scikit-learn/LightGBM, reliable history, causal labels, native realistic backtests, paper before live. Misleading or not approved: arbitrary 75% 'confidence' entry thresholds, treating a model probability as real-world win rate, rigid 15–30 training days, assuming a dynamic FreqAI whitelist is directly supported, or concluding framework installation creates profitable alpha.

### 3.3 Owner's specific V7 concept — approved direction

- Download **three months** of historical data for the **entire Binance USDT-margined perpetual futures** market, including point-in-time eligible/delisted contracts where recoverable.
- Use a broad selector informed by **10–15 genuinely different strategy families** and **Month 1** market structure to choose up to **20 candidate coins**.
- In **Month 2**, independently simulate **all valid trade opportunities** on those 20 pairs under synchronized market conditions. Record winners and losers, competing structure, fees/funding/slippage and time/risk at capital.
- AI learns **which available setup is preferable**, rather than merely whether an isolated coin rises.
- **Month 3** is forward chronological evaluation, but **NOT called untouched proof if inspected during design**. Older July–September 2026 are already contaminated by prior research. Later truly unseen evidence is required.
- After satisfactory historical evaluation, start **20 monitored candidate pairs in prospective paper/shadow trading**, learning from ALL valid qualifying shadow outcomes. This is not an instruction to force 20 simultaneous funded orders.
- Train challengers from **matured** outcomes only, compare with frozen champion on new forward data; do not automatically promote because a training job completed.
- If a model demonstrates economic benefit, reduce active paper capital usage to **one selected trade at a time**, while the remaining roughly 19 candidate pairs keep generating independent virtual outcomes.
- Permit a **separately authorized minimal real-money experiment** only after verified unseen native economic proof and a satisfactory prospective one-slot paper trial.
- Use lightweight broad-market screening then bounded heavy ML/precise-path replay to fit VPS resources.

### 3.4 Assistant refinements accepted by owner

- Separate **(A) whole-market universe eligibility**, **(B) valid entry/opportunity generation**, and **(C) comparative ranker/one-slot portfolio allocation**; measure every stage separately.
- Include a point-in-time sample of **eligible but unselected coins** so the AI team can measure better missed alternatives outside top 20.
- NO TRADE is always valid; assess **after-cost payoff magnitude, risk, duration and opportunity cost**, not just win probability.
- All concurrent eligible opportunities need independent path-specific outcome labels. Never fabricate trades on pairs with no signal; a research ledger may contain many overlapping counterfactuals, but a one-slot real portfolio may not.
- Preserve exact feature-time vs outcome-maturity-time boundaries; chronological purging/embargo; matched fees, funding, slippage, stops and capital; explicit bar-path uncertainty.
- Benchmark V7 against NO TRADE, simple selectors, original V6 and matched portfolio execution; hindsight-best is only a diagnostic upper bound.
- Extend beyond three months and market regimes before trusting edge. No automatic paper/live deployment from passing technical tests.
- Preserve earlier failed tests and reproducible manifests; reuse V3–V6 engineering when verified rather than beginning from scratch.

### 3.5 Exit-policy decision — latest authority

The owner originally requested a tight exit experiment: trailing activates at **+1% favorable underlying move**, locks entry at 0% gross, then at +2% peak locks +1%, etc.; mirrored side-aware for shorts with an explicit protective stop before activation. **V6 later ran eight official native comparisons with that exact rule**. On **2026-10-19**, archived report says **8/8 worse** than preceding trailing variant and **0/8 profitable**. The owner-directed subsequent instruction in that report: **freeze exit-rule experimentation** and focus on entry-edge AI, with locked negative-control exits.

V7 must NOT silently deploy the disproven tight trail. Freeze a versioned common research exit policy before any new comparison; competing policies require separate preregistered evaluations on fresh data.

### 3.6 Why documentation must exist (new owner requirement, 2026-10-19)

The owner explicitly requested a **chat handover document in the same new V7 GitHub branch** so deletion/context limits do not destroy project history. **All discussions, decisions, work and outcomes must be updated there after each step.** This requirement is now part of the project Definition of Done.

---

## 4. Real legacy research results that future chats must not forget

This table summarizes source-reported research outcomes; original documents and raw artifacts remain the higher authority:

| Evidence | Archived outcome | Correct interpretation |
|---|---|---|
| V3 broad counterfactual spec and V4 research factory | Accepted/rejected shadow outcome collection, learning and Champion/Challenger governance documented | Prior ideas and candidate assets exist, implementation must be audited |
| V5 paired exit laboratory | Frozen-policy side-by-side outcomes and execution uncertainty documented | Reuse sound contract rather than churn stops |
| V6 M1 | 25 pair data audit and 25 FreqAI model fits passed technical gate | Technical ability `!=` profitability |
| V6 M2 | Complete benchmark investigation **NO-GO**, unresolved official FreqAI lookahead warnings, imperfect exact execution fidelity | No paper or live acceptance |
| V6 Stage 1 | **63/63** planned jobs completed; all eight strategy families negative in studied after-cost native tests | Weak entries are a real issue |
| V6 Stage 2 | **120/120** original profit-protection study jobs completed as documented in strategy library | Completion does not imply positive economics |
| V6 Stage 3 | **12/12** planned global jobs completed; 914,878 historical labeled candidate rows, **zero selected/portfolio trades** in tested windows | Candidate simulation occurred; conservative selection found no sufficient edge |
| V6 M5A universe proxy | 75 markets downloaded; 234 review points; market-quality proxy advantage was inconsistent across months | Volume/volatility universe changes are not an entry-quality guarantee |
| Exact +1% trailing | 8 native strategy-family comparisons: **0 profitable; 8 worse** than prior trail | Do not re-optimize the same exit theory |
| Historical holdouts | July–September repeatedly inspected; pristine unseen validation unavailable for some comparisons | Historical reported performance cannot count as final blind proof |

Direct sources:
- [M1_EVIDENCE.md](M1_EVIDENCE.md)
- [M2_EVIDENCE.md](M2_EVIDENCE.md)
- [V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md](V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md)
- [V6 Stage 1 final](evidence/m2r/2026-10-19-stage1-final-research-report.md)
- [V6 Global 25×8 final](evidence/m2r/2026-10-19-global-25x8-native-recovery-final-report.md)
- [V6 Global ranking mismatch audit](evidence/m2r/2026-10-19-trailing-exit-and-global-ai-design-audit.md)
- [Exact 1% trail result](evidence/m2r/2026-10-19-exact-one-percent-trailing-final-eight-native-report.md)
- [M5A historical proxy](evidence/m2r/2026-10-19-m5a-75-market-historical-replay-final-findings.md)
- [V3–V5 original references and reuse register](V7_LEGACY_EVIDENCE_LEDGER.md)

---

## 5. Frozen V7 stages and approval state

| Gate | Work | Current status | Approval rule |
|---|---|---|---|
| G0 | Audit V3–V6 source, hashes, tests, negative evidence and safe reuse | **COMPLETE — GITHUB READ-ONLY PASS, 2026-10-20; VPS-only archived result reproduction deferred** | [V7 G0 audit](V7_G0_LEGACY_AUDIT_2026-10-20.md); no fresh executions |
| G1 | Point-in-time entire USD-M USDT perpetual three-month history | **NEXT — design/inventory only, not started** | Data-quality, survivorship and storage controls; permission before any VPS/data jobs |
| G2 | 10–15 genuinely distinct strategy families + entry baselines | Not started | Causality/negative-controls before promotion |
| G3 | 20-pair independent parallel shadow trade paths and excluded-pair controls | Not started | Comparable matured labels, audit fill uncertainty |
| G4 | Cost-aware comparative ML and frozen baselines | Not started | Purged chronological training, no forward leakage |
| G5 | Frozen chronological/native one-slot unseen economic evaluation | Not started | Positive after-cost portfolio improvement; valid untouched periods |
| G6 | Prospective 20-candidate paper/shadow observation | Not approved | Only after evidence + specific owner authorization |
| G7 | One active paper position; all others virtual | Not approved | Forward champion improvement and risk gates |
| G8 | Minimal capital live experiment | Not approved | Separate owner approval + controlled risk/kill switch |

**Not authorized:** starting VPS jobs, deploying V7, merging V6 draft PRs, changing old releases, forcing trades, relaxing gates retroactively or placing live orders.

**Expected scientific stop condition:** If no robust after-cost edge appears, record a NO-GO with exact evidence rather than building another elaborate model. A high historical win rate, completed run count or simulated best-of-twenty result is not itself profitability proof.

---

## 6. Precise technical contracts to keep in every future handoff

1. **Data:** historical contract universe as-of decision time, UTC closed candle features, funding/mark, historical source digest, liquidity and missingness. Past data only in features.
2. **Strategy hypotheses:** pair, side, independent family, valid signal and feature versions. A contract may have zero valid opportunities; number 20 is a *watchlist capacity*, not trade quota.
3. **Conditional labels:** outcome computed later for every valid eligible opportunity, including rejected trades, using fixed identical execution/exit assumptions. Raw OHLC first-touch ambiguity handled conservatively or unresolved.
4. **Comparability:** simultaneous candidates only; net USDT, net percentage of notional, wallet effects and margin/leverage declared separately; correlated trade families not overcounted as independent proof.
5. **Prediction:** expected net value and downside/time risk, calibrated uncertainty, economic chance to abstain. No raw probability threshold without validation.
6. **Portfolio:** enforce one global active slot, actual capital contention, release/reentry timing, fee/funding/slippage, NO TRADE, drawdown and liquidity.
7. **Research vs execution:** research can track unlimited independent counterfactuals; real paper/live wallets cannot spend the same dollar twenty times.
8. **Validation:** causal fits, matured targets, purged overlapping labels and embargo, reproducible model hashes, truly untouched future holdout, paired native after-cost benchmark and failure reporting.
9. **Promotion:** challenger vs champion on fresh forward samples; numerical thresholds preregistered and sufficient regime/sample coverage; explicit approval for paper and live.
10. **Resource/permissions:** 2 vCPU / 8 GiB approximate research budget; scanning all market cheaply; bounded 20 detailed candidates; no heavy ML for every perpetual every few minutes; read-only data acquisition isolated from order authority.

---

## 7. Next exact bounded action (updated 2026-10-20)

**G0 GitHub audit is complete** as a static source-and-committed-evidence inventory. See the [full G0 report](V7_G0_LEGACY_AUDIT_2026-10-20.md). We inspected actual V3–V6 code and unit-test source, captured reusable module hashes, and reconciled V6's prior comparative dataset. **We did not access the VPS, rerun prior tests or independently check private ZIP/data/model artifacts.** Such reproduction is a later evidence-dependent prerequisite, not a reason to repeat the GitHub-only G0 step.

**NEXT — G1 task 1: read-only whole-market historical-data specification and budget.** This first task can start with GitHub sources and public Binance data/archive documentation; no VPS is needed for planning:

A. Design an as-of Binance USD-M **USDT-settled perpetual** contract registry including historical listings, closures, surviving pairs, suspension uncertainty and source provenance. Use the V6 Binance Vision archive-inventory script only as a starting point, not proof of past tradeability.  
B. Inventory existing 25-pair and 75-current-survivor manifests and identify which market-wide historical data pieces are missing. Reuse existing verified caches when possible; do not download the same archive blindly.  
C. Specify 3-month broad coverage (metadata, 5m/1h, funding/mark and BTC) and selective high-resolution replay (1m or tick where available), UTC alignment, checksum, rate limits, disk/RAM/cpu budgets and failure modes.  
D. Specify Month-1 selection as-of boundaries, Month-2 label maturity, truly unseen Month-3/later validation and rules for markets lacking reliable historical liquidity or listing evidence. Already studied Jul–Sep 2026 and inspected Oct segments are not pristine holdouts.  
E. Produce G1 design and bounded download/verification authorization proposal; update this handover with evidence/commit. **Do not start VPS market downloads, ML training, backtests, paper or live mode without separately authorized scope.**

**Branch-lineage warning:** Current V7 branch derives from the V6 prototype (which has no old `nbot/` package); legacy V3/V4/V5 implementations are in `main` and related historical branches, while `nbot-v5.1` contains a **separate** `nbot_v5_1/` package. **No legacy module is automatically imported into V7.** Each reuse needs an explicitly audited selective port and compatibility tests. The supplemental V5.1 and branch-lineage audit is in [G0 report §12](V7_G0_LEGACY_AUDIT_2026-10-20.md).

**Highest-priority inherited code:** V4's already implemented LightGBM `lambdarank` at `main:nbot/observation/v4_generation.py` (grouped candidates); V3 immutable decisions and capital-uncapped replay; V5 paired execution/funding; V6 25×8 labeling/ranking and Freqtrade native research adapters. All are source-backed **reuse candidates**, not prevalidated V7 integrations.

## 8. Mandatory journal update procedure — Definition of Done

**Every step/decision must update THIS exact file in this exact GitHub branch.**

**Before acting**
1. Fetch current V7 handover, roadmap, evidence ledger and branch head; reconcile latest entries.
2. State proposed narrow scope, expected evidence/output, risks and whether owner permission exists.

**While acting**
3. Record what was actually done, exact commands/tools/data range and source/commit/artifact identities. Distinguish **proposal**, **started**, **completed**, **failed**, **accepted**.
4. Preserve all failed runs, warnings, unresolved blockers and negative economic outcomes. Do not retrospectively improve original evidence.

**After EACH step or decision, before claiming it finished**
5. Update Section 2 Current state, Section 5 gate status and Section 7 Next exact step if affected.
6. **Append one journal entry** in Section 9 with date/time + timezone (if known), who approved/what was decided, actions, outcome numbers, proof URLs/SHA, blockers, safety/approval state and the next action. If there was no code or experiment, say **discussion/decision only**.
7. Commit the updated handover to the V7 roadmap branch. Prefer the same commit as the step artifact when feasible; if separate, reference both hashes. Confirm GitHub readback, branch and commit after writing.
8. End each user update with branch, files/commits changed, actual verified result, next blocked/open step. Never imply an edit was saved if connector failed.
9. If an important decision changes the frozen design, create a **versioned roadmap amendment/change record**, linking old and new rules; never silently rewrite the founding roadmap or delete prior conclusions.
10. Do not store secrets, raw API keys, passwords, private account numbers or personal identifying information in this publicly visible repository.

### Required journal entry structure

| Field | Record |
|---|---|
| Timestamp | UTC/IST explicitly, if known |
| Stage | G0–G8 or GOVERNANCE |
| Request / decision | What owner asked and agreed |
| Activity | Exact command/action or `discussion only` |
| Result | Pass/fail/no-go, numerical evidence if available |
| Repo artifacts | Paths, comparison link, commit hash, hashes/manifests |
| Economic proof | Real native/paper/live vs proxy/shadow/none |
| Known risks | Blockers, incomplete controls, missing evidence |
| Execution permission | Read-only / research-only / paper allowed / live allowed |
| Next step | One bounded action |

**Continuity integrity rule:** Prior chronological entries are append-only; if an error is found, append a correction entry pointing to the original rather than erasing history. The short current-state table can be updated, but the journal must retain old decisions and failures.

---

## 9. Chronological decision and action journal

### 2026-10-19 — GOVERNANCE — V7 created from V6 limitations

- **Discussion:** Owner questioned why V6 could not reliably choose the best trade among many candidates. Early working hypothesis was that one active trade deprived AI of comparative outcomes. The subsequent GitHub review corrected this: V6 Stage 3 already generated large candidate-label datasets; its economic evaluation chose no trade due to signals/scores/gates, while original families were losing.
- **Owner decision:** Establish **NBOT V7** as separate comparative-opportunity-learning project. Retain V6 evidence, not the assumption that V6 did no parallel research.
- **Owner architecture:** Three months of market-wide futures history; Month 1 study, Month 2 simulate valid signals on 20 selected pairs, Month 3 forward evaluation; 10–15 strategy families; comparative AI; then 20-candidate prospective paper/shadow experiment; then one paper capital slot while other candidates remain virtual; real money only after verified performance.
- **Refinements accepted:** Historical as-of/unseen constraints; rejected and out-of-universe opportunities; after-cost path-dependent labels; full one-slot capital and NO TRADE; champion/challenger; disallow automatic deployment; reuse V3–V6 prior work.
- **Status:** Owner-approved **design/research roadmap**, not owner authorization to trade.
- **Evidence:** V7 founding roadmap and legacy evidence ledger; preserved V6 original research branch.
- **Next:** G0 legacy audit.

### 2026-10-19 — GOVERNANCE — GitHub V7 roadmap branch freeze

- **Action actually taken:** GitHub connected repository `samqju/Nbot` searched; V6 prototype/review branches and V3–V5 main docs inspected; created `roadmap/v7-comparative-learning-20261019` from `prototype/v6-freqtrade-freqai-20261016`. Added two documentation files.
- **Files:** `V7_ROADMAP.md` and `V7_LEGACY_EVIDENCE_LEDGER.md`.
- **Original commits:** roadmap `9a325579274c8a98b04ba964613392b772e133ef`; ledger `989507fd5cb7aee260412383353ae8089fce8a55`.
- **Verified comparison at freeze:** two commits ahead of V6 base, two added docs, zero original V6 code edits.
- **Execution:** No VPS or trading changes, no new model training.
- **Next:** Owner-requested durable handover protocol; then G0.

### 2026-10-19 — GOVERNANCE — Mandatory durable chat handover

- **Owner request:** Create a handover document in the **same branch** to preserve discussions, decisions, results and work when chats are deleted or context limits are reached. Update after **every step or decision**.
- **Action:** Created this `V7_CHAT_HANDOVER.md` continuity document, including a new-chat prompt, exact branch pointers, V3–V6 correction and outcomes, V7 stage/permissions, next G0 task and a mandatory GitHub journal-write Definition of Done.
- **Status:** Documentation/governance only; no research, paper or live authorization. The GitHub commit that creates this file is the durable evidence of this entry; later sessions must verify branch head rather than trust an embedded future commit.
- **Next:** Add mandatory handover-maintenance reference to `V7_ROADMAP.md`, confirm both files on GitHub, and proceed to G0 only after a new scoped development request.

---

### 2026-10-19 — GOVERNANCE — Roadmap and living handover cross-linked; freeze verified

- **Action actually taken:** Updated `V7_ROADMAP.md` to add Section 11, the binding per-step handover maintenance rule. It explicitly links this handover and requires refreshed status, a dated append-only journal entry, GitHub commit verification, no unverified auto-sync claims, and no trading authorization from documentation alone.
- **Commit:** `7a36d32282fc8300e4ff56c06c036cb28c86b9d8` (roadmap governance amendment).
- **Earlier handover creation commit:** `6de87e20f3a6bfdb7a9014fd64dbac4a68e59288`.
- **Meaning:** The user's new-chat continuity requirement is now both operationally documented here and explicitly frozen in the project roadmap. **No V7 code, VPS processes, paper/live mode or model training was changed.**
- **Economic evidence:** None generated by this documentation step; prior V3–V6 evidence unchanged.
- **Permission status:** Read-only research preparation/governance only; no paper/live authorization.
- **Next bounded action:** G0 V3–V6 code/evidence reuse audit; first verify current GitHub head and exact source state, then create a read-only audit report and update this journal in the same work step.

---

### 2026-10-20 — G0 — Read-only GitHub audit completed, no VPS used

- **Owner request and permission:** Complete G0, audit V3–V6 evidence and reusable code. Owner explicitly asked if VPS access was unnecessary. Scope was **GitHub-only read-only auditing**, with permission to commit V7 documentation.
- **Actions actually completed:** Retrieved GitHub source trees (248 V6 blobs; 311 main blobs), inspected actual V3–V6 Python source and test suites, reviewed committed historical V6 economic reports, mapped concrete reusable modules to V7 components with Git blob SHA IDs. Wrote standalone full findings to `V7_G0_LEGACY_AUDIT_2026-10-20.md`.
- **Major findings:** V3 already implements an immutable approved/rejected decision/outcome ledger, capital-uncapped concurrent replay and point-in-time training checks. V4 already implements groupwise LightGBM **Lambdarank**, chronological purging and paper Champion-vs-Challenger gates. V5 provides paired exit/path-quality/cost/funding replay. V6 has 25×8 historical candidate forecasting (914,878 candidate labels reported), but zero native selected trades across tested global windows, original negative-strategy economics and excessive/uncertain gates; hardcoded 25-pair size and 50%-win filter require redesign. Prior assumption that V6 had no rejected candidate learning is **incorrect**.
- **Archived economic outcomes preserved (NOT freshly rerun):** V6 Stage1 63/63 jobs; 8 families negative; global Stage3 12/12, zero selected; no-time 64/64, zero of 16 continuous stressed portfolios profitable; exact 1% trailing 8/8 worse than prior and 0 positive; 75-symbol M5A proxy inconclusive; M2 lookahead/real-fill uncertainties persist. Historical July–September research dates not blind holdouts.
- **G0 result:** **COMPLETE/PASS FOR GITHUB SOURCE INVENTORY ONLY**, with specific code reuse/adaptation verdicts and residual blockers. No unit tests, live/backtests, private ZIP SHA regeneration or trading economics newly executed or proven.
- **G0 artifact and commit:** [V7_G0_LEGACY_AUDIT_2026-10-20.md](V7_G0_LEGACY_AUDIT_2026-10-20.md), initial commit `b5bdf917cf2c431d68d9b6851df154ac4d94bfb3`. Original source code unchanged.
- **Known limitations:** Private archived VPS model/data/ZIP files have not been checked for current presence or rerun; real historical depth, exchange listing lifecycle, fee/slippage parity, and independent pristine future proof remain G1/G5 blockers. Existing automated test code was read but not run.
- **Trading permission:** **NONE**; V7 still a research-only roadmap; no paper/live/VPS execution authorized.
- **Next bounded step:** **G1 historical full-market point-in-time eligibility and 3-month data design**, plus storage and available-source inventory, before downloading new data. Update handover again when G1 step is discussed or completed.

---

### 2026-10-20 — G0 supplemental audit — V5.1 branch and cross-branch port constraint

- **Activity:** GitHub-only checked `nbot-v5.1` branch contents, source for the V5.1 stratified deep selector, synthetic research book, original-evidence learning boundary, chronological/dependence-aware science, cost/funding HOLD contract and independent two-book challenger LAB. Inspected G10/G11 archived milestones and V5.1 existing legacy-reuse register. Also verified that the V6 prototype branch root does **not** contain the original `nbot/` main package.
- **Major outcome:** Existing V5.1 sophisticated data-science and proof/hold rules must be candidates for selective reuse, but G10/G11 evidence was **synthetic offline engineering**, with genuine source-qualified original PAPER/challenger promotion still **HOLD**. Do not confuse 100-broad/20-deep/40-virtual synthetic integration with validated V7 deployment economics.
- **Cross-branch danger:** V7 descends from the isolated V6 prototype. Legacy V3/V4/V5 modules in `main` and V5.1 modules in `nbot-v5.1` are **not automatically in V7's Python import path**. Explicit version-pinned selective porting and regression is required; avoid blanket merges.
- **Report updated:** [V7_G0_LEGACY_AUDIT_2026-10-20.md](V7_G0_LEGACY_AUDIT_2026-10-20.md) Section 12; supplementary audit commit `283e1ec428c74ca00c1830f339cc88de224c08b4`.
- **G0 status:** GitHub source-and-reported-evidence inventory **COMPLETE**, extra branch lineage captured. Private historic ZIP re-verification, actual unit test execution and full market retrieval were **not** part of G0; no VPS accessed.
- **Risk/authority/next:** G1 point-in-time historical full-market design still next; no VPS/data jobs, no paper/live, no model promotion.

---

### 2026-10-20 — GOVERNANCE — Simple reuse explanation and numerical G0–G8 thresholds PROPOSED

- **Owner request:** Explain in simple language what is reused versus newly coded, and provide numeric tests, approval thresholds and operating limits. This follows the completed GitHub-only G0 code audit.
- **Evidence synchronization:** The existing definitive G0 [legacy audit](V7_G0_LEGACY_AUDIT_2026-10-20.md) and this journal already documented G0 COMPLETE and V5.1 supplementary discoveries; their existing results were preserved. A separate supplemental [G0 code verdict](V7_G0_GITHUB_AUDIT.md) was committed under `1e8bca538b80790ed2e27f7092e80d1f3b260b6f`; it adds code/engineering detail, but does **not** represent a second independent VPS audit.
- **New documentation:** [V7_NUMERIC_GATE_PROPOSAL.md](V7_NUMERIC_GATE_PROPOSAL.md), commit `09056ef21c98cc7d0725cc02e2fbdfe638ceeafb`, specifies proposed G1 data quality 99.9% coverage, complete label-source provenance, G3 500 matured candidates/100 multi-candidate decision timestamps, G5 90+ *truly unseen* days and 100+ one-slot trades, +0.25% extra notional roundtrip execution-cost stress, 95% time-block-bootstrap positive uplift, G6/G7 paper collection and G8 minimal-live safeguards.
- **Reusability verdict:** Selectively port V3 replay/immutable ledger; V4 existing LightGBM LambdaRank and challenger governance; V5 paired-exit accounting; **V5.1 separate-package** source/label authority, purged dependence-aware science and challenger-lab HOLD rules; V6 data bootstrap/M5A candidate scanner/global ranker/Freqtrade backtest harness. V7's main new work is as-of complete market registry, 20-of-N eligibility, integrated high-integrity opportunity labels and one-slot economic selector plus evaluation gates.
- **Critical port caveat:** The V7 roadmap branch descends from V6's isolated prototype and therefore **does not automatically contain the legacy `nbot/` package from main or `nbot_v5_1/` from nbot-v5.1**. Reuse requires explicit version-pinned selective porting and regression tests, not blanket copying.
- **Numbers and approval:** Previously frozen founder parameters (3 months, 10–15 strategies, up to 20 pairs, one active position) remain binding. **New numeric cutoffs in this proposal have NOT been approved by the owner or preregistered as final gate policy.** V4's historical 50% positive rate/+0.10R rule is not automatically applicable to V7.
- **Verification:** No source runtime test, VPS access, historical market download, model retrain, paper trade or live order occurred during this explanation/threshold design. No economic performance is newly proven.
- **Current status:** G0 GitHub review COMPLETE; G1 design NOT started. Next: owner chooses whether to approve/amend numeric proposal, and only then preregister evaluation gates before viewing any target holdout.
- **Permission:** GitHub documentation only; no V7 new runtime/trading authorization.

---

### 2026-10-20 — DESIGN REFINEMENT PROPOSED — Whole-market strategy-based top-20 ranker and high-information labels

- **Owner clarification:** Raw Binance OHLC candles must not become another expensive useless disk collection. Reused V3 simulator/outcome database must carry explicit MFE, MAE and BTC market/price-state labels and meaningful contextual/after-cost evidence. V4 LightGBM groupwise ranker is highest-priority component, trained to evaluate opportunity quality across the **entire eligible Binance futures market**, not just downstream of a volume/volatility shortlist. Overlay existing V6 8 strategy families plus distinct other strategies over illustrative ~150 eligible coins, then select 20 with highest predicted economically viable trade setups.
- **Important design interpretation:** There are two distinct predictions: (a) at the universe review, predict *future availability/quality of setups per coin* and choose top-20 monitor candidates from all eligible coins; (b) at entry time, rank currently valid signals for one capital slot or NO TRADE. Future trade outcomes, MFE/MAE and post-entry BTC regimes may train the ranker only after maturity, and must never enter entry-time feature vectors.
- **Technical safeguards added:** Include at least coarse timestamped, source-attested labels for eligible signals outside top20 plus a sampled higher-resolution excluded-coin control. Otherwise the model cannot learn how often it wrongly excludes better markets. Raw source data must remain reproducible, compressed, partitioned, hashed, bounded in retention, and connected to labeled feature/outcome ledgers. Keep cost/fill and data authority tiers separate, not OHLC proxies misrepresented as real fills.
- **Documentation action:** Created [V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md](V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md), commit `f88e5833428eaa03d4794a7754039e73b55b3a78`. This file is a proposed versioned architecture amendment to be reviewed with the owner, not a rewrite of the frozen roadmap and not new implementation authorization.
- **Source reuse:** V4 code already has LightGBM `lambdarank` with event grouping; V6's original eight trading families proved economically weak in tested conditions. They should be retained as negative research controls rather than assumed to have edge merely when scanned over more markets.
- **Open questions/numbers:** Need establish adequate whole-market learning sample, excluded universe control size, precise MFE/MAE label timing/costs, BTC at-entry regime features, review cadence and sufficient alpha significance. Previous proposed 500 labels/100 times are prototype minima, not robust 150×10 ranker proof. G1 storage/label feasibility precedes large full-market downloads.
- **Result:** Design discussion captured and committed. No new bot source code, tests, VPS data jobs or real/paper trades run. G0 remains complete, G1 next, numeric thresholds pending approval. 
- **Next:** Owner reviews the refinement and numerical gates; if adopted, create a versioned frozen roadmap amendment before G1/G2 integration; G1 begins with point-in-time full market registry, schema and storage feasibility.

---

### 2026-10-20 — DESIGN PROPOSAL — Auto-replaceable adaptive Trading Brain, no fixed-strategy decision lock

- **Owner's new insight:** V7 still risks selecting trade/no-trade **based fundamentally on a fixed strategy list**. Owner wants an **automatically replaceable learning Trading Brain**, not permanent adherence to trend, breakout, reversion or another static mindset when market conditions change.
- **Architecture interpretation:** Existing V6 strategy families remain useful as hypothesis generators and negative research controls, but should **not hold permanent veto/authority over which opportunities the AI may consider**. Include a validated strategy-independent, versioned proposal path and broad-market, off-shortlist shadow research to measure missing/new setups. Ensure neither initial universe selection nor entry choice is secretly limited to 10 old templates.
- **Fast vs slow adaptation:** A frozen champion can **adapt its decisions/weights at each event** using current as-of BTC/coin/market state and uncertainty. A **new model artifact** is a separate challenger trained on matured labeled outcomes, then compared prospectively against the old champion under matched opportunity costs, drawdown and one-slot portfolio rules. Switching a currently approved mixture/router is NOT the same as deploying an unproven retrained challenger.
- **Required boundaries:** Keep ex-ante features apart from future MFE/MAE/BTC path outcome labels; preserve strategy diversity and independent off-policy shadow samples, NO TRADE, static executor/risk authority, versioned schema/hashes and rollback. Do not auto-promote a newly fit model to real trading. Current frozen roadmap still requires separately approved paper and live promotions.
- **File committed:** [V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md](V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md), commit `4e21205fbd799e54339282bb75a191a31331b7fe`. The file documents rationale, modular design, model version/replaceability contract, regime context, entry-free candidate exploration, causal learned labels, qualification tests and unknowns.
- **Status/limits:** This is a **proposed architecture refinement**, not evidence of a winning model, an approved numeric replacement threshold or deployment authorization. V4 LambdaRank and V4/V5.1 champion/challenger systems are technical code seeds, not proven profitable automatically adapting minds.
- **Execution:** GitHub documentation only. No VPS access, code port, new training, new tests, downloading data, paper/live order or old branch modifications.
- **Project status:** G0 remains GitHub source-audit complete; G1 full-market historical data and causal label planning next. Existing G0–G8 numeric threshold proposal is still pending approval.
- **Next:** Review this proposed amendment, choose appropriate model/challenger design and predeclare scored performance and anti-churn thresholds before test-period inspection. Then incorporate by a versioned approved roadmap amendment if adopted.

---

### 2026-10-20 — ENGINEERING — New V7 implementation branch, selectively ported components, offline A/B1/B2 baseline

- **Owner request and authorization:** Create an actual **V7** GitHub branch, selectively copy useful V3, V4, V5, V5.1 and V6 components and code the adaptive research bot; after it is fully coded/tested, separately deploy to VPS to acquire nine months of Binance futures history. The owner offered authorized PuTTY access if future VPS access is needed; **NO VPS or laptop remote session accessed during this step, no private access details stored in repository**.
- **Branch:** Created [V7](https://github.com/samqju/Nbot/tree/V7) starting from the frozen roadmap branch, keeping original project documents and preserving previous versions.
- **Selective code copy commit:** `31d14d4301d90aba413f65c31267236754c712bd`, V3 immutable outcome/replay source, V5 paired-exit/accounting, and V5.1 learning science/source evidence modules, with package imports adapted without blanket merges. V4 LambdaRank group-scoring concepts were implemented as a new self-contained V7 component rather than copied with all transitive legacy dependencies.
- **New package created:** `nbot_v7/{data,features,lab,brain,experiment,cli,archive}.py`, `__init__.py`, `__main__.py`; [V7_README.md](V7_README.md); `requirements-v7.txt`; `tests_v7/` and [V7 GitHub CI workflow](https://github.com/samqju/Nbot/blob/V7/.github/workflows/v7-offline-tests.yml). Branch commits include `eaf89a10`, `86da1675`, `f176f32a`, `9246a03c`, `1aa767ec`, `39d0f577`, `a57e4ed5`, `7b344a6a`, `725430fe`, and subsequent documentation commits.
- **Research functionality:** Source/registry-gated 5m Binance monthly ZIP/CSV archive input, market-wide strategy and independent structure proposals, BTC regime features, SQLite shadow outcome/forecast ledger and MFE/MAE, 8h learned watchlist up to 20 pairs, 5m learned one-slot trading decision or abstention. LightGBM grouped LambdaRank + expected-net regression, optional regime experts; Brain A trained months1–3, frozen exam months4–6; B1 and B2 trained from matured months1–6; independent A/B1/B2 portfolio experiments on months7–9. Model SHA manifests and research report; no order authority.
- **Public archive preparation:** `nbot_v7/archive.py` can inventory all archived Binance USD-M USDT-margined perpetual monthly ZIP candidates and explicitly download into bounded disk space with content SHA hashes. **Only code committed; no download or inventory actually executed.** Archive existence is NOT point-in-time exchange-tradeable listing proof.
- **CI evidence:** Initial V7 workflow runs failed due invalid YAML quoting and then a Python package initializer syntax issue. Both defects were corrected, preserving failure evidence. **GitHub Actions run [39369375300](https://github.com/samqju/Nbot/actions/runs/39369375300) PASSED**, Python compile check and **9/9 offline tests**, including an end-to-end nine-month *synthetic* A/B1/B2 baseline. After adding public archive downloader, [run 39369631315](https://github.com/samqju/Nbot/actions/runs/39369631315) also PASSED.
- **Spec/continuity:** [V7_NINE_MONTH_IMPLEMENTATION_SPEC.md](V7_NINE_MONTH_IMPLEMENTATION_SPEC.md) created to record 3+3+3 and actual code vs pending completeness. Frozen founder docs are preserved unchanged.
- **Honest limitations:** This is **working engineering research code, not a fully complete/validated nine-month Binance trading system**. No real 9-month data or historical active-contract lifecycle verified; 5m stop-first trade outcomes are not native fills, true funding/orderbook/slippage unresolved; fixed proxy exits unproven economically; baseline statistical/no-trade comparisons incomplete; no proof B2 improves A/B1; no actual 200-300 coin disk/RAM benchmark or VPS integration. CI success does NOT authorize deployment/paper/live trades.
- **Security/authority:** No VPS, exchange credentials, PuTTY connection, background jobs, paper or real orders. No existing V6/source deployments touched. Next require continued offline code-validation and archived source science controls before discussing VPS deployment.
- **State:** G0 COMPLETE; offline V7 G1–G5 prototype ENGINEERING IN PROGRESS; numeric gates pending owner freeze; economic/paper/live GO = **NO**.
- **Next bounded task:** Finish hardening source and outcome labeling and meaningful baselines, run a reproducible realistic offline nine-month fixture using verified historical data; record test and go/no-go. Do not call the implementation fully complete until those source and native-execution gaps are closed.

---

## 10. Final handover warning

NBOT V7 is an **unproven research program**. It should never be described as a profitable bot, a deployed AI, or a live-capable trading system at this stage. The purpose of this journal is to stop repeating V3–V6 mistakes, prevent stale chat assumptions from replacing evidence, and make every decision, negative result and future milestone reconstructible from GitHub.

## 2026-10-20 IST — Desktop continuation: causal decision/outcome boundary (step 1)

- Verified existing `V7` head `69d900d`, based on the preserved roadmap implementation; continued it without resetting or duplicating branches. Read roadmap, handover, G0 audit, adaptive proposal and nine-month agreement; retrieved the referenced user agreement. No VPS connection or deployment.
- Found material future-information selection defects: replay excluded future ambiguous paths, and labeling removed candidates whose future data was missing. Replaced decision inputs with separate `candidate` and `watch_candidate` tables containing no outcome fields. Outcomes are looked up only after selection. Missing selected paths lock the slot and flag the account incomplete; ambiguous stop-first paths are retained.
- Added hourly family-neutral LONG/SHORT shadow grid, stale-watch expiry, insolvency prevention, worse-open gap-stop fills, model-cutoff and finite-feature guards. V2 label/model schema requires rebuilding old V1 datasets.
- Initial local baseline: dependency unavailable and sandbox temporary-directory errors; no claim that baseline passed. Created project-local research environment, installed requirements, used workspace temporary directory. Final step-1 verification: **17/17 tests pass**, including LightGBM and synthetic 3+3+3 comparison, six adversarial causality/account tests. Test transcript: `.test-tmp/step1-tests.txt` (local ignored runtime evidence).
- Remaining: persist full decision audit/artifact manifests, source coverage report/build completion gate, archive-through-model integration, governed offline replacement and native execution fidelity. Synthetic success is not source completeness or economic validation. Research implementation remains IN PROGRESS.
