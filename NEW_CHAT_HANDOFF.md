# NBOT V6 — NEW CHAT HANDOFF / CONTINUATION PROMPT

**Canonical continuation record:** October 17, 2026.  
**Repository:** [samqju/Nbot](https://github.com/samqju/Nbot) — PRIVATE owner-controlled project  
**Work branch:** `prototype/v6-freqtrade-freqai-20261016` — DO NOT work on default branch  
**Draft PR:** [#50](https://github.com/samqju/Nbot/pull/50) — keep DRAFT/UNMERGED  
**Latest verified CI at creation:** [run 39002032960](https://github.com/samqju/Nbot/actions/runs/39002032960), successful.  
**Milestone state:** M1 technical integration PASSED; M2 historical economic/release gate **NO-GO**; M2R new after-cost ML research built and compared, **not accepted for trading**; M3 formal multi-regime acceptance NOT STARTED; M4 paper daemon NOT STARTED; M5A universe selector NOT BUILT; M7 real money **LOCKED**.

> **This file is written for a fresh ChatGPT conversation. It has the instructions, actual measured results, links, environment and next priorities needed to resume work without relying on an old conversation. GitHub source/evidence is more authoritative than an assistant's recollection. Read the current branch before touching files.**

## A. COPY-PASTE STARTER PROMPT FOR A NEW CHAT

> I own NBOT V6 in private GitHub repository `samqju/Nbot`, research branch `prototype/v6-freqtrade-freqai-20261016`, draft PR #50. Continue the **same careful, evidence-driven Freqtrade + FreqAI LightGBM cryptocurrency research project**, NOT a new bot or an unrelated redesign.
>
> **First read the entire `NEW_CHAT_HANDOFF.md`, `ROADMAP.md` (especially M2/M2R/M3/M4/M5A), `M2R_RESEARCH.md` and `evidence/m2r/2026-10-17-aftercost-model-learning-results.md` from that exact branch; check the current GitHub PR/CI status and the latest commits.** Then tell me plainly what has been done, what remains unresolved and the highest-value **next offline research step**. Do not make me repeat previous decisions. Speak in **simple English**, distinguish fact from assumptions, and show actual test evidence.
>
> I want FreqAI to learn **which entire trading setups succeed after fees, estimated slippage and risk**, including opportunities it skipped; to understand when **NO TRADE** is preferable; and later to safely choose among qualified fixed strategies and a dynamic 25-candidate universe. I want thorough independent chronological, model and cost validation—not promising profits from one winning week. **Do NOT automatically promote a strategy or move to M3 unless M2 integrity/release prerequisites are demonstrably met.**
>
> **Permissions and safety:** You may examine and update only the isolated V6 research branch and do bounded offline/historical tests on the owner-authorized 8GB-Observation V6 research VPS, using public Binance history and no credentials. **Never touch legacy V5 bots/VPSes; never merge PR #50, run a persistent trading service, start M4 virtual paper mode, enable exchange orders, ask for keys, or unlock M7 live money without fresh explicit owner authorization.** One global 1,000-USDT, 1× historical position is the current benchmark; future approved M4 paper mode may hold **up to 20 virtual positions** (not the same as 25 candidate assets), and planned M5A selector should reassess eligible Binance USDT-M markets about **every eight hours** and choose up to **25**. These two future milestones must not be forgotten.
>
> **Current priority:** First audit FreqAI's *actual* training-boundary handling for 12-candle future complete-trade labels and root-cause the official `has_bias=Yes` lookahead diagnostic. Then strengthen realistic execution/funding treatment and pre-register several **fresh, previously uninspected, time-held-out multi-regime tests**, retaining NO TRADE and the frozen original AI/non-AI as baselines. Test the already-built separate breakout/pullback after-cost LightGBM models; do not interpret 29,033 counterfactual opportunities as executed trades. Keep M2 release **NO-GO** until proven otherwise.
>
> **Continue the existing roadmap; check off only work actually verified, publish reproducible logs/evidence in GitHub, and explain the results without financial hype.** If a connected tool or VPS is unavailable, say so; never invent execution or results.

## B. Owner's actual intended system (do NOT simplify it away)

- NBOT V6 uses **Freqtrade** for Binance USDT-M futures history, entries/exits, exposure and risk accounting, and **FreqAI LightGBM** for market prediction and retraining. V6 is isolated from the owner's functioning V5 bots on different VPSes.
- Owner expects genuine **adaptive intelligence**: learn which complete setups and market regimes work, understand predicted *net results* (fees/slippage/funding/risk), prefer **NO TRADE** when expected results are weak, and **eventually** select among multiple approved strategies. FreqAI does not automatically do all of this; our custom labels/models/router supply the learning objective. Do NOT claim it can magically self-invent/profitably switch strategies.
- **M5A intelligent universe selector is REQUIRED LATER:** approximately every eight hours examine eligible Binance USDT-M markets using liquidity, execution cost, market state/volatility, statistical robustness, historical readiness, FreqAI model readiness, safe turnover/hysteresis and risk constraints; choose up to **25** candidates. A fixed 25-pair backtest is NOT this module.
- **M4 paper may hold UP TO 20 simultaneous VIRTUAL positions** with appropriate total exposure, leverage, margin and diversification protections. This is not a goal to force 20 trades. M1/M2/M2R historical tests used **one** global position. M4 must NOT start merely because research code exists.
- **M7 real money is separately owner-locked.** Never enable live trading, keys or real orders. Never alter any V5 machine, configuration, data or services.
- Explain everything in **plain, simple English** and do not treat profit on a short period as proof.

## C. Research infrastructure and strict operating discipline

- V6-only research VPS: Ubuntu 24.04, about **7.8 GiB total RAM**, two CPUs, 96 GiB disk. Historical tests use official `freqtradeorg/freqtrade:stable_freqai` Docker image, recorded Freqtrade **2026.9** and Python 3.14. The `--memory=6g` flag is a **cap, not observed usage**. No reliable full-run peak RAM profile has been certified.
- Owner-authorized workstation connection: `Sameer-Laptop` with a saved PuTTY session named **`8GB-Observation`** and Desktop Commander. Use only the existing authorized connection; never request or disclose SSH keys, passwords or exchange API secrets, and do not need the public VPS IP.
- **Source checkout:** `/root/nbot-v6-m1-20261016/source`; local market data under `user_data/data/binance/futures`, trained model artifacts under `user_data/models`, archived trades under `user_data/backtest_results`. Independent research logs are under `/root/nbot-v6-m1-20261016/`.
- Use bounded one-shot `docker run --rm` **backtesting** or offline analysis, no always-on container, no `freqtrade trade`, no services, no API/Telegram, no exchange keys, no V5. Investigate Docker state and git working tree before new runs. The last documented V6 VPS state was **no running containers**, but VERIFY it in the new chat; do not claim it based only on this record.
- Make source changes only on branch `prototype/v6-freqtrade-freqai-20261016`, keep PR #50 **DRAFT**, preserve original strategy and evidence, give experiments distinct `freqai.identifier` names, run unit tests and official Freqtrade strategy discovery, save genuine machine-readable evidence. Never silently select the winning asset/threshold/window after seeing data.
- If an artifact/result did not actually run, label it **PLANNED**. If training/labels are incomplete, do not tick success. Do not conflate simulated PnL, hypothetical opportunity-label sums, and realized net order execution. No proven live edge.

## D. Completed milestones and financial evidence — DO NOT RE-RUN JUST TO RECREATE FACTS

**M1 technically complete:** Genuine Binance public USD-M 5m + 1h history/mark/funding loaded for 25 original markets, original 30-day LightGBM fitting worked; candle audit 25/25 passed. This established infrastructure, **not profitability**. Historical Oct 1–7 initial price AI 34 trades **−135.640 USDT**.

**M2 original September 1–30, 2026 (30 days):** July/August earlier history was downloaded so September was not an in-sample initial training period. Real rolling **125 LightGBM fits**, no runtime errors; 25/25 candle audits passed. Same 25 fixed markets, **100,000-USDT simulated wallet**, **1,000-USDT per position**, **1× leverage**, one simultaneous trade, baseline **0.05% modeled fee per side**.

| September original frozen controls | Trades | Simulated net |
|---|---:|---:|
| Original price-only FreqAI | 137 | **−444.980 USDT** |
| Simple no-ML | 163 | **−242.894 USDT** |
| NO TRADE | 0 | **0** |

At double the fee (0.10%/side): original AI **−576.688**, no-ML **−388.318**. Non-ML occupied a position **99.641% of the month**; original AI **40.637%**. The apparent non-AI Oct 1–7 +169.849-USDT gain was NOT robust in September. See [M2_EVIDENCE.md](M2_EVIDENCE.md) and [September details](evidence/m2/2026-10-17-september-full-month-analysis.md).

**M2 honesty blockers:** Native Freqtrade/FreqAI `lookahead-analysis` flagged **`has_bias=Yes`** on changing model/indicator/entry/exit columns. Controlled BTC/ETH as-of prefix invariance passed, but DOES NOT resolve all signals or certify native label-boundary purging. Real historical best bid/ask spreads, queues, market impact, stop fill gaps are NOT independently reconstructible for every trade; 2026 Binance historical 30s depth matched **113/130** trade-side events (17 stale/unverified). Two September month-boundary funding discrepancies each approximately 0.10 USDT remain noted. Result: **M2 release gate FAILS / NO-GO**.

**M2R new learning target:** Four frozen causal candidate setups: trend breakout LONG/SHORT, EMA pullback LONG/SHORT. At candle-close decision, hypothetical enter at NEXT 5m OPEN, 2% stop, 5% target, maximum 12 future 5m candles, pessimistic stop-first on bar ambiguity and gap stops. Hypothetical roundtrip training label subtracts **0.05% fee on each side**, **0.05% extra assumed slippage on each side**, plus **0.01% funding reserve**: **0.21% total modeled reserve**. The `&-trade_net_return` label uses future for the **target only**; `%-` features should be past-only. Samples without a candidate or complete future horizon are NaN. Setups originally rejected by one-slot portfolio are also training examples. These are **assumptions**, not measured execution or account PnL. Real `NbotV6TradeOutcomeResearch` Challenger and `NbotV6BreakoutResearch`/`NbotV6PullbackResearch` fit per-pair LightGBM models. Never auto-promote.

**The September 29,033 statistic:** An offline audit counted **216,000 coin/candle decisions** and **29,033 OVERLAPPING hypothetical setup outcomes**, **32.332%** positive after above assumed reserves; mean labeled net **−0.246% per opportunity**. These are **training labels**, NOT 29,033 actual trades and NOT 32.3% of trades the AI actually selected.

**Real M2R September comparison (25 pairs):**

| September approach | Simulated trades | Net PnL |
|---|---:|---:|
| New combined after-cost LightGBM | 332 | **−442.471 USDT** |
| Original price-only AI | 137 | **−444.980 USDT** |
| Frozen simple no-ML | 163 | **−242.894 USDT** |
| NO TRADE | 0 | **0** |

The new AI achieved a higher win rate, **39.76% vs original 31.39%**, but still LOST money, so no verified September profitability or generalized selection improvement. See [M2R final evidence](evidence/m2r/2026-10-17-aftercost-model-learning-results.md).

**Pre-registered later Oct 8–15 (October 8 inclusive to October 16 exclusive) full 25-pair one-slot comparison:**

| Official historical strategy | Trades | Net simulated USDT | Max drawdown |
|---|---:|---:|---:|
| Original price-only FreqAI | 45 | **+205.976** | 87.259 |
| New pullback-only after-cost AI | 68 | **+146.237** | 41.277 |
| New combined after-cost AI | 98 | **+113.046** | 77.036 |
| New breakout-only after-cost AI | 83 | **+62.552** | 72.076 |
| Original no-AI (DIFFERENT exits) | 52 | **+24.135** | 139.634 |
| Matched breakout-only no-AI (same 60m exit) | 178 | **−34.227** | 189.605 |
| Matched pullback-only no-AI (same 60m exit) | 177 | **−88.489** | 147.978 |
| Matched combined no-AI (same 60m exit) | 189 | **−141.359** | 225.476 |
| NO TRADE | 0 | **0** | 0 |

All modeled trading results are Freqtrade official trades with base 0.05%-per-side fee (and its existing funding accounting); NOT actual fills. The new AI's stronger performance than **matched-exit** no-AI controls suggests the AI filter helped during this short interval. **Original price-only FreqAI still earned more**, and September remains a negative counterexample.

**What LightGBM actually learned in Oct 8–15 — based on SAVED historical forecast outputs, joined to future labels only for retrospective scoring:**

| Model | All eligible *hypothetical* candidate outcomes | Favored by AI (`do_predict==1` and predicted net >0.4%) |
|---|---|---|
| Combined | 7,732; 33.148% positive, mean −0.1430% | **302**, 45.364% positive, mean +0.0153% |
| Breakout-only | 4,295; 34.109% positive, mean −0.1203% | **235**, 43.404% positive, mean +0.0608% |
| Pullback-only | 3,437; 31.946% positive, mean −0.1714% | **154**, 44.156% positive, mean +0.0602% |

**This supports genuine SELECTIVITY in the recorded predictions:** models favored a small subset with higher hypothetical win rate under the 0.21% assumed cost training rules. It does **not** prove causal ML reliability under all native FreqAI train-boundary cases, actual fills or long-term profitability. These 302/235/154 are overlapping counterfactual examples, **not portfolio trades**. See [M2R model-learning report](evidence/m2r/2026-10-17-aftercost-model-learning-results.md), [Oct saved forecast audits](evidence/m2r/2026-10-17-oct08-16-combined-prediction-selection.json), [breakout](evidence/m2r/2026-10-17-oct08-16-breakout-prediction-selection.json) and [pullback](evidence/m2r/2026-10-17-oct08-16-pullback-prediction-selection.json).

**Crucial cost fragility:** Additional *hypothetical fixed-trade* execution haircuts beyond the engine's base fee:

| Oct 8–15 | Engine base outcome | +10bps extra roundtrip | +25bps extra roundtrip |
|---|---:|---:|---:|
| Original price AI | +205.976 | **+161.003** | **+93.542** |
| New pullback AI | +146.237 | **+78.293** | **−23.625** |
| New combined AI | +113.046 | **+15.112** | **−131.788** |
| New breakout AI | +62.552 | **−20.367** | **−144.745** |
| Original no-ML | +24.135 | **−27.521** | **−105.005** |
| NO TRADE | 0 | 0 | 0 |

At +15bps, combined is already **−33.855**. These are extra assumed deductions on unchanged original simulated trades; NOT observed bid/ask execution or fresh replays with different fills. [Full sensitivity report](evidence/m2r/2026-10-17-oct08-16-full-cost-sensitivity.json).

**BOTTOM LINE:** FreqAI **did** learn some differentiation among technical setups in the small October validation: better hypothetical hit rates and higher conditional average net labels. But **this is NOT a proven durable edge**, did not outperform original price AI there, lost all September, and is fragile to missing real-world execution costs. NO TRADE and no auto-promotion remain safety defaults.

## E. Files and components to pick up (use EXACT existing paths)

- [ROADMAP.md](ROADMAP.md) — controlling milestone/checklist and acceptance gate.
- [M2R_RESEARCH.md](M2R_RESEARCH.md) — implementation notes; read [final model-learning report](evidence/m2r/2026-10-17-aftercost-model-learning-results.md) for later verified status if older sections sound preliminary.
- [NbotV6.py](user_data/strategies/NbotV6.py) — original price-return LightGBM strategy; preserve unchanged.
- [NbotV6NoML.py](user_data/strategies/NbotV6NoML.py) — original no-ML control; preserve unchanged.
- [nbot_trade_outcome.py](user_data/strategies/nbot_trade_outcome.py) — causal setups, next-open after-cost labels, per-family label functions, past-only decision features.
- [NbotV6TradeOutcomeResearch.py](user_data/strategies/NbotV6TradeOutcomeResearch.py) — combined after-cost LightGBM backtest-only subclass.
- [NbotV6FamilyResearch.py](user_data/strategies/NbotV6FamilyResearch.py) — breakout/pullback LightGBM research subclasses, individually trained.
- [NbotV6MatchedNoMLResearch.py](user_data/strategies/NbotV6MatchedNoMLResearch.py) — exit/risk-matched non-AI controls (critical for fair attribution).
- [nbot_strategy_router.py](user_data/strategies/nbot_strategy_router.py) — **OFFLINE ONLY** deterministic regime-aware model-score, uncertainty, liquidity and cost gated route to one fixed setup or NO TRADE; NOT connected to Freqtrade order entry or automatic strategy deployment.
- [m2r_purged_split.py](scripts/m2r_purged_split.py) — **OFFLINE test utility only**, not yet native FreqAI training model-data split.
- [m2r_forecast_quality.py](scripts/m2r_forecast_quality.py) — match SAVED model predictions to later outcomes; never use future outcomes as forecast input.
- [m2r_compare_variants.py](scripts/m2r_compare_variants.py), [m2r_cost_sensitivity.py](scripts/m2r_cost_sensitivity.py), [m2r_opportunity_audit.py](scripts/m2r_opportunity_audit.py) — reproducible independent evaluations.
- [Frozen Oct 8–15 protocol](evidence/m2r/2026-10-17-preregistered-setup-comparison.md), [full official eight-strategy backtest evidence](evidence/m2r/2026-10-17-oct08-16-eight-strategy-official-backtests.json), [full forecast findings](evidence/m2r/2026-10-17-aftercost-model-learning-results.md), [fee sensitivity](evidence/m2r/2026-10-17-oct08-16-full-cost-sensitivity.json).
- [M2_EVIDENCE.md](M2_EVIDENCE.md) — historically important unresolved no-leakage/fill gate.
- [tests/test_m2r_trade_learning.py](tests/test_m2r_trade_learning.py), [tests/test_m2r_purged_split.py](tests/test_m2r_purged_split.py) — source unit tests. Last recorded V6 offline suite **90 tests passed**, all **nine** Freqtrade strategy classes discovered in framework. Recheck CI after future commits.

## F. EXACT NEXT RESEARCH WORK (do this FIRST, in order)

1. **Refresh state:** Read current branch `NEW_CHAT_HANDOFF.md`, `ROADMAP.md` M2R section, final October/September evidence, PR #50 and latest CI. Confirm isolated V6 VPS and Docker idle state; no uncommitted important files. Summarize exactly what new evidence exists, including failed cases. Do **not** restart from M1, rerun September just to fabricate progress, or claim M2 accepted.
2. **Highest-priority correctness/causality audit:** Inspect the real installed FreqAI 2026.9 LightGBM training/data pipelines, specifically handling of `&-trade_net_return` labels needing **up to 12 future 5m bars**, split/window cutoff, retraining/test_size=0.2, indicator startup, correlation pair feature time alignment, NaNs, and any future label that spills beyond a model fit's as-of cutoff. Compare raw decision features and predictions with future bars truncated, all 25 if feasible; root-cause the previous official `has_bias=Yes` indicators, rather than dismiss them as a framework false positive. If a leak exists, correct it in a new isolated strategy/identifier, add failing-then-passing tests, and **retest** chronology. Never call original fitted results leakage-cleared without evidence.
3. **Execution realism:** Research feasibility of order-cost estimation using archived public Binance depth/trades, prospective **read-only** quote capture if explicitly approved, maker/taker/fees, funding, slippage, stop gaps, size and concurrency. Do not claim archives yield exact realized order fills. Flag/rescue two September boundary funding mismatches. Update cost sensitivity and gate; keep NO TRADE in every comparison.
4. **Additional truly independent periods:** With rules/thresholds frozen and rationale pre-registered **before** seeing outcomes, select **several not-yet-inspected monthly or multi-week windows and market regimes**. September and Oct 1–15 have been seen and cannot qualify as untouched blind test anymore; October 16+ was not part of the recorded tests but, as of October 17, may not offer sufficient future observations. Older past windows might require public May/June/July history and complete training warmup; validate exact availability and avoid choosing favorable windows. Continue comparing original price AI, after-cost combined/breakout/pullback AI, matched no-AI and NO TRADE using same exposure/accounting.
5. **Evaluate whether adaptation has a real edge:** Use per-setup score calibration, trading frequency, drawdown, confidence bounds, actual after-cost economics and abstention. A learned higher hit rate is useful but the ultimate benchmark is sustainable **risk-adjusted net result on genuine unseen time**, not a pretty October week. If adverse outcomes persist, record **NO-GO**. Do not auto-tune the threshold of 0.4% on the Oct validation set and then call it out-of-sample.
6. **Strategy switching LAST:** Once candidate-specific models and risk data pass independent controls, test offline regime classification and deterministic router against honest benchmark without knowing future results. Use one selected setup or NO TRADE per relevant decision, enforce model-age, costs, liquidity, diversification and confidence; do not activate a Freqtrade runtime pairlist/strategy router until owner explicitly approves paper milestone after all gates. Preserve future 8-hour M5A universe rotation and maximum-20-position M4 paper design in the roadmap, without conflating them with current one-slot backtests.
7. **GitHub discipline:** Commit only the needed isolated branch changes, run tests+CI, link exact source and timestamped evidence in `ROADMAP.md`, `M2R_RESEARCH.md`, draft PR #50. Tick only proved checklist items, leave unresolved ones unchecked, and explain in simple English. The current result is a **research insight + NO-GO**, not an investment recommendation or permission to trade.

## G. Nonnegotiable operating gates / forbidden shortcuts

- **DO NOT** merge the draft PR or write to default/main.
- **DO NOT** touch any of the owner's V5 bots, VPSes, files, configurations, deployed strategies or trading activity.
- **DO NOT** connect exchange keys, request secrets or place any real, paper or simulated persistent exchange orders. One-shot historical backtests are authorized; M4 persistent paper is NOT.
- **DO NOT** change economic assumptions/feature thresholds midway through an experiment without creating a new, pre-registered experiment and discarding the old period as final blind validation.
- **DO NOT** confuse **25 candidate assets**, the **one global simultaneous position** used in historical research, and the future M4 **up-to-20 concurrent paper positions**.
- **DO NOT** claim measured bid/ask spread or actual slippage from a funding file or a 30-second depth band; don't infer true deployment costs from synthetic model reserves.
- **DO NOT** pretend that FreqAI automatically learns strategy switching, online reward reinforcement or autonomous self-rewriting. It retrains supervised models to predict the targets **we define**. The regime router is offline and still unvalidated as an integrated system.
- **DO NOT** label research profitable from one favorable eight-day period, or ignore September's losses, model/native lookahead, small portfolio sample size, cost sensitivity or NO TRADE.
- **NEVER** silently turn the M2 research completion checkbox into **M2 RELEASE PASS**; M2 must be explicitly accepted only on strong, audited evidence. M3 formal gate isn't approved by these exploratory M2R trials.

---

**How to restart:** Open a new ChatGPT chat, connect the same authorized GitHub and desktop environment if supported, and paste the section **A** prompt (or just the GitHub URL to THIS file plus "Read this entire handoff and continue the documented M2R plan"). In the new chat, treat `ROADMAP.md` as current milestone authority and update this handoff whenever substantive results change.
