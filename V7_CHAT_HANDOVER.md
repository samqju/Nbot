# NBOT V7 — Master Chat Handover and Continuity Journal

**Created:** 2026-10-19  
**Authority:** Owner-approved continuity process. This document is the restart point for a new ChatGPT conversation if this chat is deleted, reaches context limits, or development changes hands.  
**Canonical GitHub repository:** https://github.com/samqju/Nbot  
**V7 active implementation branch:** [V7](https://github.com/samqju/Nbot/tree/V7) — new implementation from the preserved planning branch. Historical roadmap remains on [roadmap/v7-comparative-learning-20261019](https://github.com/samqju/Nbot/tree/roadmap/v7-comparative-learning-20261019).  
**Frozen roadmap:** [V7_ROADMAP.md](V7_ROADMAP.md)  
**Archived discoveries:** [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md)  
**Legacy code parent:** [prototype/v6-freqtrade-freqai-20261016](https://github.com/samqju/Nbot/tree/prototype/v6-freqtrade-freqai-20261016)  
**Current stage (verified 2026-10-20):** V7 `LEARN-3C` learning gate **HOLD**. Three-coin autopsy DONE. **Bounded method trial DONE:** unchanged Brain A trained Jan–Mar; April matured labels used only for offline forecast/reward-policy overlays; May–June 2026 development replay compared unmodified A, FreqAI-inspired bias correction, 25bp conservative abstention and FinRL-inspired contextual NO TRADE. Loss fell from **−$423.31 (196 trades)** to **−$26.40 (69 trades)** using extra buffer, but **did not turn positive; NO TRADE at $0 remains best**. Actual River v0.22.0 ADWIN drift diagnostic had 0 alerts across 255 A selected trade residuals. **41/41 V7 Linux tests pass**. Microsoft Qlib/FreqAI/FinRL packages were **not installed**; their ideas only tested. No model promoted and no 20–50 coin expansion. Next: selection-conditioned payoff calibration and truly prospective test, maintaining no-trade as a legitimate benchmark.
**Owner's latest technical refinement (2026-10-20):** Strategy-aware **all-market** universe selection has priority: calculate strategy signals for every eligible coin, use a causal comparative LightGBM ranker to shortlist up to 20, and preserve labeled MFE/MAE/BTC-at-entry and future-path trade outcomes, including sampled outside-top20 controls. Recorded as a **design refinement proposal** in [V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md](V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md); existing frozen roadmap and numerical gates have not been silently changed or approved.

**Owner decisions pending:** [V7_NUMERIC_GATE_PROPOSAL.md](V7_NUMERIC_GATE_PROPOSAL.md) proposes G0–G8 numerical gates; [V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md](V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md) proposes an adaptive/replacable brain replacing static strategy authority. **Neither proposal is finally frozen or deployment-authorized.**  
**Current deployment state:** Isolated research workspace **/opt/nbot-v7-20261020/** exists on authorized 8GB Observation VPS. Public Binance monthly inventory complete and 54 pilot ZIPs already downloaded/checksum-audited; 3-coin training/evaluation and corrected replay ran without exchange orders. **No persistent V7 bot/paper/live deployment, private API credentials or real orders authorized/used.** Existing NBOT versions/services remain untouched.

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

## 2026-10-20 IST — Reproducibility and expanded owner scope (step 2)

- Owner supplied updated implementation authority, preserved verbatim in `V7_OWNER_AUTHORIZATION_2026-10-20.md`. Full bot architecture required; lab is removable. VPS development/public history acquisition now authorized, with no real credentials/orders and isolation from legacy deployments. Roadmap addendum records precedence; old no-VPS statements are historical.
- Fixed Jan–Mar A training, Apr–Jun A evaluation/B and B1 training, Jul–Sep A/B/B1 exploration. Renamed adaptive six-month challenger to B (`B_ADAPTIVE_6MONTH_FROZEN`) so a post-September B2/C cannot be confused with a pre-July fit.
- Added streaming hash-chain decision logs, logical dataset hashes, package/source/config/artifact run manifests and verification, read-only experiment DB access and mandatory completed-build marker. Added per-symbol candle/funding coverage, missing registry/archive cohorts, and complete source bundles including BTC/contract provenance. Bounded training preserves entire synchronized groups within row budget.
- Local **17/17 tests pass** with real LightGBM, manifest verification and synthetic 3+3+3 artifacts. Initial Git commit failed for missing local author identity; corrected using repository's verified existing public noreply identity; step 1 is published as `43a17ff`.
- Authorized read-only VPS check via PuTTY succeeded: 2 CPUs, 7,940 MiB RAM, ~7,588 MiB available, 96 GiB filesystem almost empty, no running NBOT process in process/service inventory and no matching root NBOT directories. No existing service stopped/modified. No V7 process or download started in this step.
- Next: isolated VPS workspace and bounded public source inventory; integrated reusable bot runtime, risk/recovery, paper/live boundary and governed learning lifecycle. Native precision, historical lifecycle completeness and actual financial results remain unverified.

## 2026-10-20 IST — Reusable trading runtime and isolated VPS bootstrap (step 3)

- Added shared causal `decision.py` used by historical replay and reusable `runtime/` core; historical lab can be removed without deleting the engine, broker, risk, memory or learning modules.
- Runtime includes persistent one-slot coordinator, paper broker with side-aware fills, protective stops/targets, gaps, fees/funding and horizon; independent frozen risk checks; stale/source holds, kill switch, daily-loss/drawdown/capital limits; durable intents, restart recovery, atomic account/outcome settlement, immutable outcome conflicts and hash-chain journal validation. Live broker interface defaults disabled; no real venue transport/keys were loaded.
- Added matured-memory periodic challenger training, hash-verified model registry/loading, forward-evaluation review receipts, explicit paper-promotion method and rollback. Training alone never changes champion. Numeric promotion policy must be supplied before evaluation; current proxy artifacts cannot satisfy verified-forward-source gates. Source-specific live transport and production recovery parity remain unverified.
- Local **24/24 tests pass**, including seven runtime recovery/risk/idempotency tests; evidence saved in `evidence/v7-step3-tests-2026-10-20.txt`.
- VPS isolated workspace `/opt/nbot-v7-20261020/{code,venv,data,runs}` created from step-2 Git commit. Clean server lacked pip and OpenMP; pip installed in project environment, only system `libgomp1` added (no service restart). VPS rerun **17/17 passed** at step-2 revision. No legacy service modified or private trading credentials accessed.
- A bounded 1,800-second public Binance archive inventory for Jan–Sep 2026 is running in the isolated workspace. No claim of completed download/registry/economic test yet. Next: checksum-verified acquisition, lifecycle/coverage qualification, runtime feed/shadow integration and full archive-through-model system validation.

## 2026-10-20 IST — Integrated feed/shadows, checksum acquisition and paper parity (step 4)

- Shared historical labels now call the SAME incremental `PaperBroker` as the reusable runtime, including actual entry/exit-notional fees, modeled fill slippage, worse-open stop gaps and both-touch stop-first. Predeclared label policy bumped to V3 before actual historical training. Exact exchange/tick/native execution remains unverified.
- Added bounded recorded/public paper stream entry point, public-only current USD-M feed, parallel independent shadow memory (including sampled outside-watch controls and inclusion probability), matured challenger integration, MFE/MAE bar bounds, immutable model approval/rollback controls and disabled-live boundary. No paper/public bot process started on VPS.
- Archive downloader now verifies exchange `.CHECKSUM` files for downloaded AND cached ZIPs, prevents manifest destination escape, preserves 8 GiB disk reserve, and supports saved inventory acquisition. Official source reference: https://github.com/binance/binance-public-data#checksum
- Added explicit archive-observed provisional cohort mode to permit honest exploratory engineering when lifecycle evidence is unavailable. Grade remains `ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`; default source-gated loading rejects it. This is NOT historical eligibility certification. No invented SOURCE_ATTESTED registry.
- Local **30/30 tests pass**, including generated nine-month CSV archives through registry/database/A-B-B1 models/artifacts, byte-identical repeated decision logs, tamper rejection, long/short historical-to-paper fill parity, all-shadow maturity, governed-learning HOLD and cached ZIP checksum corruption rejection. Transcript in `evidence/v7-step4-tests-2026-10-20.txt`.
- Rewrote `V7_README.md` around actual bot/lab split and current authority. Remaining blockers: actual market acquisition and quality audit, resource workload proof, verified lifecycle/funding/tick/venue fills, full V6 control and prospective production promotion. Inventory is still running in its bounded isolated job; no economic success claimed.

## 2026-10-20 IST — Audited execution reuse, V6 controls and whole-universe inventory correction (step 5)

- Selectively ported **19 execution/exchange/common/config modules** through their required dependency closure from immutable `origin/main` commit `d497e961e2891c43669d64f2a16d210011d703a4`. `V7_EXECUTION_PORT_MANIFEST.json` records exact source Git blobs and 12 unchanged original fault/recovery test files. This is not a blanket legacy merge.
- Ports include durable entry, independent risk, protection, one-slot state, authoritative reconciliation, emergency flattening, local paper exchange, public feed and guarded mainnet/testnet transports. No API credentials were read, no live/testnet account connected, no arm file created and no real order submitted.
- V7 `runtime/venue.py` bridges brain intents into the audited lifecycle and preserves V7's fixed 2% stop/3% target/60-minute policy; it does NOT silently enable the legacy integer-R trailing manager. Runtime consumes authoritative close outbox records transactionally and acknowledges them after durable accounting. Mock/local-paper integration verifies protected entry, target close and exactly-once equity reconciliation.
- Original Windows execution suite attempt: 531 tests, failed with 556 errors (including cleanup errors), chiefly POSIX `fchmod`/`fcntl` assumptions and one out-of-scope Observation public-client import. This was NOT accepted. Excluded the unrelated Observation suite rather than porting its whole runtime; retained dedicated Exchange public adapter. First Linux attempt: 530 tests, four missing `nbot.exchange.limits` dependency errors. Added its exact original compatibility module. Final Linux: **530/530 legacy tests PASS**; **32/32 V7 tests PASS**, no skips. Transcripts saved under `evidence/v7-step5-linux-*`. Legacy execution targets Linux; Windows production parity is not claimed.
- Extracted exact V6 eight-family pure indicator/signal functions (no Freqtrade classes) with `V7_V6_SIGNAL_PORT.json` provenance; integrated as frozen negative-control candidate advisors, resetting at source gaps. Added matched V7-fill V6-signal control; this is explicitly NOT original V6 native ranker reproduction. Added bounded ranking-error/family/regret diagnostics. Model schema V3 and label policy V4 require fresh datasets/models.
- Public source inventory found 1,056 archive directories, including Unicode symbols; only directories matching USDT-perpetual-style names belong to the candidate scope. Fixed ASCII-only exclusion in all readers/registry/discovery. Replaced earlier own inventory PID 1779 only after verifying its exact isolated command; it lacked checkpoints/progress and had not produced a final manifest. New inventory is Unicode-aware, three-worker, per-symbol checkpointed, time-bounded; first progress reports 900 matching directories. This is a coverage correction, not a completed all-market data validation.
- GitHub workflow now includes the legacy execution fault suite. Run manifests include runtime source and the full installed dependency versions. Current bot source is substantially integrated, but real data/economic validation, lifecycle/funding precision and production readiness remain unproven. Next: actual checksum-verified pilot then all-market acquisition, bounded resumable dataset build, frozen A/B/B1 baseline and explicit readiness report.

## 2026-10-20 IST — Step 6 continuation from prior Work limit: negative real-data pilot preserved; causal boundary fixed

- **Owner instruction:** "Proceed" after original Work conversation reached its limit. The previous Work output supplied by the owner established that the 3-coin real-data pilot had already run and had detected an unresolved end-of-September entry issue. New chat therefore **did not re-download** the 54 pilot archives or re-create prior completed code; reconciled GitHub `V7` and the authorized isolated VPS.
- **Verified previous work from VPS, not assumption:** `runs/pilot-btc-eth-sol-2026/` contains 54 SHA-audited Binance BTC/ETH/SOL monthly 5m candle/funding ZIPs, 249,685 candidate labels, 2,454 universe review records, trained A/B1/B adaptive artifacts, hash-chain decision/trade logs and an actual negative nine-month engineering pilot. Initial results had incomplete July–September A/B1 portfolios owing to selected labels missing near test end. Original output preserved under `experiment/`.
- **All-market inventory finished:** SHA256 `09b61797a094a16b7bc46c69308097426dafbdb2b1d3a4d5f49760072c8f8c22` for `data/archive-index-v2.json`, which reports 1,056 S3 directories, 900 USDT-style symbol directories, 876 with Jan–Sep archive objects, 12,234 ZIP objects / declared compressed 1,791,265,945 bytes. **This is NOT verified historical eligible contract coverage**. No bulk nine-month download was started in this step.
- **Source correction:** In `nbot_v7/experiment.py`, a new trade is now refused whenever the known decision timestamp plus frozen 12×5m maximum holding window exceeds the predeclared evaluation end. It logs `EVALUATION_END_ENTRY_HORIZON`. The model decision **never** tests whether the future label exists or whether a stop hit early to admit a borderline trade. `nbot_v7/science.py` refuses paired uplift computation if either account is incomplete. New adversarial tests demonstrate the boundary and uphold missing-label fail-closed state.
- **GitHub commits:** `5bcbe611` `e450e35a` `75ee892b` `63027a43` `69e3e26c` for source/test corrections; final source commit `69e3e26c0dc67aba6846b0195a41b4d1a47d7665`. Isolated VPS checkout updated by fast-forward, no other branch touched.
- **Actual Linux tests:** 34/34 V7 tests passed after fix, log at `/opt/nbot-v7-20261020/runs/step6-boundary-v7-tests.txt`, SHA256 `1f5cb40595decd2c3bd4d54c74885b4335b4203dd25f8094790b9b4bbae8b19c`. Previous Step 5 530/530 legacy execution suite remains documented; not re-run in Step 6.
- **Corrected replay:** Existing labeled SQLite reused; new output `runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed/`, exit code 0; all stage B / stage C A, B1 and B adaptive now `account_complete=true` and 0 unresolved selected paths. Stage B A: 255 closed, −497.7071 USDT. Jul–Sep: A 233 trades, −340.6883 USDT; B1 377 trades, −660.0041 USDT; B adaptive 630 trades, −953.6469 USDT. These are **negative three-coin proxy outcomes**, not proof of AI economic adaptability. End-boundary entry suppressions: 7 Stage B, 6 per Stage C model.
- **Reproducibility hashes:** New `summary.json` SHA256 `7e6097bac1e3565863e6d1f5d017c8df722e808738ae03323a13ae1b5734dae0`; new `run_manifest.json` SHA256 `77457166e61d86e8cb30d609a5c41d140a603cca90775fb92c8b1bf958341da7`. Original summary SHA256 `0a48ea6a008bde25a2d78ac90fa14ba1a3e7129545f3f950bddd857129827942` preserved. The labels are only `ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`, using 5m bar fills and modeled funding/costs; not certified native exchange fills.
- **Committed report:** [evidence/v7-step6-real-pilot-boundary-audit-2026-10-20.md](evidence/v7-step6-real-pilot-boundary-audit-2026-10-20.md), commit `9d77cde3a51517b01c9ee6e449142a50db03dc7c`; [V7_ROADMAP.md](V7_ROADMAP.md) Section 13, commit `307b04689da3457530815e78df8a5f3acff80906`.
- **Technical blocker / resource safeguard:** 3-coin labeled database ~344 MiB, 96 GiB VPS available total disk ~94 GiB free at inspection, and ~900 source directories. Do **not** naïvely build a 900-symbol giant SQLite label set that can fill disk. Need explicit database bounds, resumable checkpointed ingestion and/or compact storage; validate exchange historical listings/delistings and real cost assumptions.
- **Authority:** Owner-approved isolated public-market data research on VPS, but **no live API keys, paper orders, dry-run service or real trading authorization**.
- **Next bounded step:** Implement safe resumable storage quotas and point-in-time contract eligibility/source-grade controls, then a larger **finite** acquisition/replay cohort. Numeric G5 paper/live promotion gates remain separate and not passed.


## 2026-10-20 IST — Step 7: resumable, disk-budgeted dataset ingestion VERIFIED on real Binance archives

- **Why:** Nine-month BTC/ETH/SOL pilot already used ~344 MiB SQLite. A 900-directory archive-observed scale-up could exhaust the 96 GiB VPS. Previous builder refused to resume partial DBs and had no active DB-disk ceiling. The owner requires fully working, safe scalable bot development; no more repeated work or unbounded storage.
- **Actions (V7 source):** Added `build_progress` table; in `nbot_v7/lab.py` transactionally commit each complete symbol's candidate/opportunity rows together with label/source receipt and interval coverage; only set `meta.build_complete=true` once ALL symbols are validated. Strict resume checks dates, policy, contract registry digest, period months, symbol set, BTC source bundle, and per-symbol source ZIP bytes. SQLite main+WAL/SHM byte usage and available filesystem capacity checked before/after each symbol. `nbot_v7/cli.py` exposes `--resume --max-db-gib --min-free-gib` (defaults 12 GiB database quota, 8 GiB filesystem free reserve). Fail-closed incomplete DB cannot be trained as a complete experiment.
- **Git commits:** `1e2dfc92b6150734a5073349bb845a7e3bb7ca26` (builder), `4a91b00b15b4c7418e1b8e3ea7857565cae4215d` (CLI), `24475a212b09cd48b113ad4001e437c9cc7460f2` (crash/recovery/budget tests).
- **Tests:** After isolated VPS git fast-forward, **36/36 V7 tests PASSED** (no skips), `runs/step7-dataset-checkpoint-tests.txt`, SHA256 `cc2a2b19af39fc0c53a36b3bdf977e096ea650c60e9fc39f8f06c17e2f7ecd06`. The previous 530 legacy execution fault tests were not rerun during Step 7; their prior pass remains recorded.
- **Actual source interruption/restart test:** Reused original Binance checksum-verified 54 ZIPs; intentionally set `--max-db-gib 0.08 --min-free-gib 8` on NEW `checkpoint-real.sqlite`. As designed, first command failed (`quota_first_exit=1`) on `DATASET_DB_BUDGET_EXCEEDED_INCOMPLETE` after first symbol checkpoint, leaving database incomplete. Explicit `--resume --max-db-gib 1 --min-free-gib 8` succeeded (`quota_resume_exit=0`), **one** prior symbol checkpoint reused, **three** complete, **249,685** historical conditional labels and **2,454** universe reviews, all 3 funding archive cohorts present.
- **Real replay parity:** Ran `nbot_v7 experiment` on the resumed database into a NEW folder, exit 0. C_A and C_B decision-chain hashes are *exactly identical* to Step 6's corrected original data: `95ef4f80ea716eb629825101bd228cb0d087cfc8c8856cc5b5347c9e8de62099` (A) and `2c57a65da51a6e8f4545b3e6d11387ded040ab1bd76d5c4a8190ad48adc82d26` (B adaptive). Resumed experiment summary SHA256 `40850278d4962039025e2aba00c07e49d3279579e6196e3461d83e69b98a08c8`. The original and prior corrected pilot reports are preserved unchanged.
- **Documentation/evidence:** [Step 7 report](evidence/v7-step7-checkpointed-dataset-real-replay-2026-10-20.md) committed `ce7dcd80aa6864e66ced32daf54e728b8bd9ef06`; [V7_README.md](V7_README.md) bounded builder examples committed `e787f6fa6bde31617e1a1b930c6b6b78c343f4d3`; [V7_ROADMAP.md](V7_ROADMAP.md) Step 7 Section 14 committed `9d2b25f3fc93c3689e68752b5ba1002ea927c3a6`.
- **Critical limitations:** Three-coin and archived price proxy only. 900 USDT-style archive directories are not proof of 900 live/eligible perpetual contracts. Quota checks happen between symbol transactions and may permit one transaction-size overshoot; minimum free-space reserve remains mandatory. No new full universe archive download, 20–50-market source-coverage stress, tick/native price fills, positive after-cost economic result or model promotion.
- **Permissions/state:** Authorized isolated VPS research only; no private Binance credentials accessed, no standing V7 paper/real bot started, no real orders, old NBOT versions untouched.
- **NEXT bounded action:** Preflight 20–50 historically diverse archived USDT candidates with a compact normalized per-timestamp feature/label schema and proven-source eligibility where possible; quantify disk/CPU per market, collect necessary archives under checksum+quota controls, and only then scale the full Jan–Sep universe without guessing.


## 2026-10-20 IST — OWNER HARD GATE — PAUSE all market expansion until Trading Brain learns better

- **Owner's exact concern:** “Why expand to complete Binance market when AI is not improving its trading decisions? If fixed 3 coins' trading is not improved no way I can trust to choose better coins from entire Binance Universe.” Owner then instructed: **update these findings and remarks; no benefit in expanding horizon to entire market until AI learns better; research how other open-source bots learn**.
- **Decision adopted:** **DO NOT start the previously proposed 20–50 coin source/download or full-USDT-market jobs.** The earlier expansion was prematurely prioritized; user specifically requires a working **adaptive learning brain** and improved entry/NO TRADE decisions on the current BTC/ETH/SOL cohort **first**. Existing V7 broad-market capability is an eventual goal, not canceled. This is an **owner-authorized priority/gate change**, not merely an assistant suggestion.
- **Prior pilot preserved (source Step 6):** On Jul–Sep 2026 independent $10,000 sleeves: A frozen Jan–Mar **233 trades, −340.6883 USDT**; B1 same model architecture Jan–Jun **377, −660.0041 USDT**; B adaptive six-month **630, −953.6469 USDT**; **NO TRADE = 0 USDT**. A/B1/B portfolios were all marked complete after end-boundary causal repair. The **5m proxy** fills and previously studied calendar window mean no independent profitability proof. B traded ~2.7× A but lost more; further training/model adaptation changed behavior but did **not** demonstrate useful learning.
- **Next test, not yet run:** **`LEARN-3C` three-coin learning autopsy**: evaluate predicted vs actual conditional economic payoff, calibrated net score/abstention, regret and sampled excluded opportunities (oracle diagnostic only), BTC market state at entry vs later BTC path, MFE/MAE and source-grade distinctions, strategy/family mix, family-wise actual vs predicted net, trade frequency/occupancy/cost burden, downside and drawdown, train/label maturity and chronological leakage. Hold exit policy fixed while diagnosing entry/brain to avoid repeating past V6 exit experiments. Need script/test/evidence on existing source-hashed data, and a preregistered challenger compared with unchanged champion and NO TRADE.
- **Meaning of 'learning':** Better after-cost decisions under **matched** one-slot and signal availability, with increased quality of abstention and calibrated predicted outcomes, on **properly unseen** chronological observations. Merely fitting a new model, repeating 2026 months hundreds of times, gaining raw ranker NDCG or trading more does not pass. The 2026 July–September sample is inspected; no claim of clean holdout from it. Preserve owner control over model/paper/live promotion and numeric cutoffs not previously frozen.
- **Upstream verified sources researched 2026-10-20 (docs only, no packages installed):** FreqAI supervised rolling retrain/prediction expiry and caveat of naïve `continual_learning`; Microsoft Qlib market adaptation, rolling training and ranking; River online ADWIN drift detection; FinRL and updated FinRL-X modular design and simulated reinforcement learning; Stable-Baselines3 evaluation guidance; FreqAI-RL five actions/custom rewards and warning that simplified RL environment may not represent true fills/callbacks; Hummingbot Quants Lab officially **not actively maintained**. These are **techniques, not ready-made profitable bots**, and do not justify rebuilding V7 from scratch or bypassing existing V4/V5.1.
- **Documents committed:** [V7_LEARNING_FIRST_GATE_AND_OPEN_SOURCE_REVIEW_2026-10-20.md](V7_LEARNING_FIRST_GATE_AND_OPEN_SOURCE_REVIEW_2026-10-20.md) created at `893e334d66be4b4f8e31daefac5353329453bdd1`; [V7_ROADMAP.md](V7_ROADMAP.md) Section 15 mandatory LEARN-3C gate added at `a001b2cfc057c86208da7d805241eee693a6e32d`. This handover entry is the authoritative next-chat continuation.
- **User-visible next bounded step:** Audit existing three-coin historic decisions without retraining first, write reproducible autopsy report and decide a minimally changed challenger. Future-dated fresh observations are needed for true forward verification; fresh 90 days after September 2026 are not yet present as of 2026-10-20.
- **What was and was not executed this turn:** Github documents and upstream public documentation read/written ONLY. No VPS access, no new model training, no fresh historical data downloaded, no tests run, no services changed, no paper/live order or new deployment.
- **Current NEXT task priority:** `V7_THREE_COIN_LEARNING_AUTOPSY.md` **BEFORE** any broader market storage/scanner scaling. Old handover entries with Step 7 “Next 20–50 cohort” are now **superseded** by this new owner-approved decision, retained only as chronology.


## 2026-10-20 IST — Step 8 LEARN-3C completed — overconfidence and exposure autopsy, MARKET EXPANSION STILL HOLD

- **Owner request:** “OK go ahead and perform a three-coin learning audit.” Prior owner-approved priority rule still applies: no 20–50 or full Binance market expansion until real evidence the adaptive brain makes better choices on new data. Authorized investigation of **already downloaded** BTCUSDT/ETHUSDT/SOLUSDT historical evidence and GitHub documentation only. No market data acquisition/real or paper trading needed.
- **Git branch/source:** Active `V7`; inherited frozen three-coin `labeled.sqlite`, corrected `experiment-boundary-fixed/` run artifacts, model manifests and hash-chain JSONL were reopened **read-only** on the isolated VPS. Reported source code/label math and policy consulted; **no model retrained, no stop/exit changed, no run artifacts overwritten**.
- **New reproducible forensic script:** [scripts/v7_three_coin_learning_audit.py](scripts/v7_three_coin_learning_audit.py), commits `daa67ddb8df970bd038d547ad5ec79e0bd47edff` and `711594b3857d10995ffb0636afced40ed51d529e`. It checks saved run manifest file hashes, every event chain's links/hashes, source-label equality for every selected executed virtual trade, source-context rows and net-PnL reconciliation. It also samples explicitly NON-executable hindsight oracle labels at abstention instants; never credits a wallet for them. No joblib model deserialization.
- **Test addition:** [tests_v7/test_learning_autopsy.py](tests_v7/test_learning_autopsy.py), commit `488abf927e08347bdc84c9cca388f8f99971f2e0`. Catches altered decision-chain hashes, invalid score-band aggregation and BTC entry-time regime bucket mistakes. Entire Linux V7 test suite **39/39 passed**, exit code 0, log SHA256 `cba7a8491cb42d5513b488c70f96d73df974a47e8441da68024a90fb973dd3f7`. Prior 530 legacy execution tests were NOT rerun in Step 8.
- **Saved result:** `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/learning-autopsy-v2.json` SHA256 `f2ce95529bdfe6728c6e60cc655156111a6cb2b9aeb1b3ff9a7fbc8a641212bc`. Corrected `summary.json` SHA256 remains `7e6097bac1e3565863e6d1f5d017c8df722e808738ae03323a13ae1b5734dae0`. An initial v1 autopsy is also retained; v2 verifies more source and maturity evidence.
- **NEW FINDING — conditional selected-trade prediction overoptimism:** on July–September model-selected 1,000-USDT-notional proxy trades: **A 233** forecast avg **+16.6632bp** vs realized **−14.6218bp**, error **+31.285bp**; **B1 377** +15.1143bp vs −17.5067bp, error +32.621bp; **B adaptive 630** +13.1746bp vs −15.1373bp, error +28.3119bp. All selected predictions positive due existing trade gate; real selected net averages negative. This is selection-conditioned miscalibration, not all-opportunity calibrated error.
- **NEW FINDING — adaptive policy turns abstentions into losing trades:** A abstained on 15,981 of the 18,131 common decision instants; B1 on 14,782; B adaptive on only 12,607, while B executed 630 vs A 233. **522 B trades occurred at A BRAIN_ABSTAIN timestamps**, accounting for **−657.4179 USDT** of B's total **−953.6469 USDT** loss. Another 78 B trades at A's occupied-slot timestamps lost −218.7878; another 30 simultaneous A-selected instants lost −77.4412. Since accounts have separate position occupancy, do not treat them as directly substitutable trades.
- **NEW FINDING — extra B choices specifically involve regime experts:** the saved B1 and adaptive B model SHA256 for the BASE TRADE and WATCH heads are identical. Adaptive B adds `down`, `range`, `up` specialist heads and conditional routing. Distinct outcomes are due to using those extra experts in the test configuration; we have not established that their value generalizes. Adaptive B 349 SHORT trades lost **−725.6696 USDT**; 288 SOLUSDT trades lost **−534.5729 USDT**; `range` regime 395 trades lost **−678.5398 USDT**. These slices overlap, don't sum; no hindsight banning family/short/coin.
- **NEW FINDING — time-thinning severely limits training use:** A fitted only **18,142 of 90,235** available matured historical conditional trade rows (20.1%, 2719 grouped rank events). B1/B fitted **18,903 of 171,482** eligible rows (11.0%, 2921 groups) — six-month eligible history almost doubled yet fitted rows grew only **761**. Cause in `nbot_v7/brain.py::rows_before` default max comparison groups / time-group stride. Hypothesis: poor regime coverage / underutilized new data, NOT proof simply training all rows will help.
- **DATA CHECK:** **249,693** candidate rows, **249,685** matured outcomes, **8** unresolved paths, **0** label_available_ms at/before decision and **0** missing outcome_context rows. **11** ambiguous stop-first 5m bar proxy labels, rest coarse proxy; **3/3** archive-observed **unverified lifecycle**. Funding based on monthly rate proxy, actual fill, spread, queue and mark-notional settlement still unverified. Does not prove all leakage absent.
- **Current code policy diagnosis:** `nbot_v7/decision.py::choose` enables trade when predicted net **>0** and then chooses maximum *relative rank score*, with NO calibrated uncertainty/extra cost margin. Many small positive predictions were wrong. Without a dependable absolute-value/abstention confidence measure, more training or more coins can generate worse losses.
- **Written full scientific report:** [V7_THREE_COIN_LEARNING_AUTOPSY.md](V7_THREE_COIN_LEARNING_AUTOPSY.md), created commit `ce779dfd62272d60d02ea6ecee8cad50ef8733c0`. Updated [V7_ROADMAP.md](V7_ROADMAP.md) Section 16 on LEARN-3C verdict and next stage, commit `8c9910cdb5d22b6b7334df0623ab0da471051a09`.
- **Gate conclusion:** `LEARN-3C HOLD / FAIL TO DEMONSTRATE IMPROVEMENT`. No positive AI learning evidence, no justification for market-expansion costs, no champion promotion or paper/live authority. ALL data and negative results preserved.
- **NEXT exact step:** Stay within BTC/ETH/SOL and existing 2026 market archives; use previously defined development-only April–June evaluation for a **full-candidate predicted/realized calibration vs NO TRADE analysis**, then preregister minimal hypotheses (forecast/uncertainty margin, abstention, expert router ablation, training group-thinning stress) for further genuine unseen verification. Do **NOT** use July–September retrospective tuning to declare improvement; need later untouched time once available.

## 2026-10-20 IST — Step 9 four open-source learning framework approaches tested under strict 3-coin data cap

- **User request:** “Do you have solution for this? the 4 open source you mentioned can be used anywhere to make things better? if yes try them.” Proceeded only with isolated, read-only-to-existing-artifacts V7 research using existing BTC/ETH/SOL 2026 data; no automatic external open-source bot merge or private trading permission.
- **Actual upstream review:** Official FreqAI rolling supervised/outcome maturity principles, Microsoft Qlib chronology/workflow, FinRL action/reward framework, and River ADWIN online drift. External packages often use different markets, latency, fill and reward assumptions; no plug-and-play profitable futures brain exists.
- **Precisely what ran vs was adapted:** **River 0.22.0 installed and run** in `/opt/nbot-v7-20261020/research-packages/river` via isolated `--no-deps --target`; existing production V7 environment was NOT changed. **FreqAI/Qlib/FinRL packages were NOT installed or run.** Instead a reproducible V7-native experiment was written to test mature-label calibration, split governance and reward-sensitive NO TRADE on the exact existing one-slot simulator. The FinRL analogy was a **one-step contextual action reward estimator**, not PPO/RL or an actual FinRL implementation.
- **GitHub code:** [scripts/v7_three_coin_challenger_methods.py](scripts/v7_three_coin_challenger_methods.py), commit `4e43aede5803f1e3ab930c71acbebac69b0a5afd`; [tests_v7/test_learning_challenger_methods.py](tests_v7/test_learning_challenger_methods.py), commit `6e144af9b2695bd64e703ef94cdd1c7abaacbf19`. No production brain, protected execution, costs/exits or risk policy changes.
- **Learning dates and source:** Original trained A model (model SHA checked against its frozen manifest) ends Mar 31. Calibration/reward data strictly April 1–30 on **5,606** hourly-sampled source-matured full candidate rows, label `available_ms < 2026-05-01`. Each overlay frozen before May–June validation. No May/June outcomes were used to fit or choose among methods. Prior 2026 general inspections mean May–June is **development-only, not a genuinely unseen promotion holdout**.
- **ACTUAL RESULT May 1–June 30, independent $10k one-slot 5m-proxy portfolios:** Frozen A **196 trades, −$423.3050**; FreqAI-*inspired* April residual correction **212, −$382.1335**; residual correction plus **25bp additional prediction hurdle** **69, −$26.4029**; FinRL-*inspired* context action/no-trade policy **0 trades/$0** (same as NO TRADE). Buffer lowered absolute loss ~**93.8%** but **still not net positive**. Do not compare Apr–Jun 3-month original $−497 figure to May–Jun 2-month figures.
- **Critical science:** April all-candidate residual mean = **−0.0001249266** or **−1.2493bp** (raises candidate scores when subtracted), **opposite sign** to the earlier +28–33bp selected-trade model overconfidence. Thus selection-aware/portfolio-conditional calibration and NO TRADE are the next target, not naïve global offset fitting. With extra +25bp hurdle on top of that correction, effective raw hurdle ~23.75bp. The trade reductions are portfolio-replay results, not a profitable new model; no improvement on a pristine future period shown.
- **Reward context limitations:** April positive predicted candidates at selected hourly groups: range 62, down 22, up 18. Only range had >=50 examples and was itself negative (~−10.77bp mean actual). Bandit proxy rightfully chose to abstain all May–June, but **this is not genuine successful action-learning in a wallet-aware RL environment**.
- **RIVER actually tried:** ADWIN(delta=.002) on **255** A Apr–June selected trade residuals sorted by exit-maturity UTC: **0 drift alarms**. Zero drift alarms do not imply correct net forecasts; stable prediction errors can be consistently wrong. No control decisions, warnings or model promotions based on drift.
- **Checks and artifacts:** Full **41/41 V7 Linux tests PASSED**, SHA256 `9a38c0b948214ba3812ad7f0700f6e6d5d19db9ca3a92ee3a5c974140fe43a30`, log `/opt/nbot-v7-20261020/runs/learning-methods-apr-jun-tests.txt`. Original nine-month raw ZIPs and all previous reports unmodified. Research output `runs/pilot-btc-eth-sol-2026/learning-methods-river-v2.json` SHA256 `a8ac6768062d621c780a09a59f4b060ad5e35f755468998042cc600c755f65e4`; earlier v1 without River separately retained.
- **Full report:** [V7_THREE_COIN_OPEN_SOURCE_METHODS_TRIAL_2026-10-20.md](V7_THREE_COIN_OPEN_SOURCE_METHODS_TRIAL_2026-10-20.md), commit `103f68afba175834f3067879052b5cdc67862216`. Roadmap Step 17 added, commit `7de0e874ab3a1c20bc8723951ccda8cc0c4b4141`.
- **Gate verdict / next:** `LEARN-3C HOLD` remains. The lower-loss buffer is a useful **NO TRADE safety hypothesis**, not evidence of profitable AI. Next implement/test selection-aware model-confidence calibration on blocked chronological development folds with wallet-accurate after-cost reward, and require fresh as-yet-unseen future period and owner approval before promoting. Do not scale to 20–50 or entire Binance universe under this evidence.
- **Operational safety:** No new Binance download, no paper/live trading, no FreqAI/Qlib/FinRL installation, no changes to original champion/strategy code, stops, risk boundaries, old NBOT services or production venv. VPS research-only package River in isolated directory.
