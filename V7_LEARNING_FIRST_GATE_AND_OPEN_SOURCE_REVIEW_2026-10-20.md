# NBOT V7 — Mandatory Learning-First Gate and Open-Source Learning Design Review

**Recorded:** 2026-10-20 (Asia/Kolkata)  
**Owner decision:** **FREEZE broad-market expansion (20–50 cohort and 150–900 archived-symbol acquisition/training) until the existing BTC/ETH/SOL V7 Trading Brain demonstrates meaningfully improved decisions on new out-of-sample evidence.**  
**Authority:** Versioned design/priority decision, **NOT** a claim that diagnostics have run, models have changed, or that paper/live trading is authorized. No VPS operations in this documentation step.  
**Source:** [G0 audit](V7_G0_LEGACY_AUDIT_2026-10-20.md), [Step 6](evidence/v7-step6-real-pilot-boundary-audit-2026-10-20.md), [Step 7](evidence/v7-step7-checkpointed-dataset-real-replay-2026-10-20.md), [V7 roadmap](V7_ROADMAP.md), [V7 handover](V7_CHAT_HANDOVER.md).

## 1. Why the owner changed priorities

V7 already has an isolated research environment, source-attested BTC/ETH/SOL nine-month **engineering-only** sample, 249,685 candidate labels, trained A/B1/B models, 5m proxy one-slot replay and deterministic logs. It has NOT produced evidence that additional training improved its choices. Expanding to the entire Binance market would multiply data, compute, disk and statistical opportunities to cherry-pick before we know whether the decision rule and rewards work.

**Verified corrected pilot** (July 1–September 30, 2026; separate 10,000-USDT simulated sleeves):

| Model | Train evidence | Trades | After-cost 5m-proxy net | Approx. sleeve return |
|---|---|---:|---:|---:|
| A frozen | January–March | 233 | −340.6883 USDT | −3.4069% |
| B1 same architecture | January–June | 377 | −660.0041 USDT | −6.6000% |
| B adaptive/context experts | January–June | 630 | −953.6469 USDT | −9.5365% |
| NO TRADE | None | 0 | 0 USDT | 0% |

B increased trade count and loss. The experimental reports were from **three coins only** and approximate 5-minute bar fills, with unresolved historical tradability provenance. July–September was previously explored during V6, hence not a new pristine holdout. Brain B is **NOT accepted**. No automatic champion replacement, paper or live promotion.

**Scientific nuance:** Underperformance on 3 coins does not logically prove wider cross-sectional selection can never help, because selection is a different hypothesis. But **as an owner-imposed engineering priority and spend constraint**, broader market data work is paused until a brain learning/abstention improvement is demonstrated under fair testing. Do not present this pause as universal mathematical evidence about 300 coins.

## 2. New HARD ORDERING — V7 learning gate before broader universe

**Immediately authorized by this decision:** Github-only code/data/model review, causal diagnostics and a small, bounded existing-three-coin investigation using existing artifacts, when appropriately executed and logged. No new bulk market download and no trading service activation.

**Before any expansion to new coins, require:**
1. **Reproducible diagnosis of bad selections**: For A/B1/B, inspect at common timestamps the predicted after-cost return, actual post-entry path/outcome, calibrated error, MAE/MFE, BTC regime-at-entry, strategy or proposal family, source-quality flag, trade frequency, and portfolio occupation. The original replay's one-hour horizon, costs and labels must be held fixed during initial debugging.
2. **Separate learning from more trades**: Compare frozen A, same-architecture B1, adaptive B, NO TRADE and a cost/risk-matched simple baseline. Report not just win %, but selected conditional net, realized after-cost portfolio result, predicted-vs-realized calibration and abstention/coverage. More trades, different trades, higher training score or a new weight file do not by themselves show learning.
3. **Evaluate the core `NO TRADE` decision**: At each common decision time the model must explicitly compare projected after-cost value and uncertainty with zero entry, preserving an admissible abstention. Diagnoses should identify if overtrading comes from score magnitude drift, optimistic predicted utility, family imbalance, badly scaled rewards, incorrect tail-loss modeling or label/exit mismatch.
4. **Label integrity inspection**: Confirm decision feature timestamps precede entry and BTC state; MFE/MAE and future BTC changes remain outcome-only; model train labels are matured before fit cutoff; funding/spread/slippage assumptions are defensible; ambiguous bar paths handled conservatively. This is a code+data audit, not an assertion that existing 5m proxies are verified fills.
5. **Propose, then freeze** limited challenger hypotheses before seeing their evaluation data. Examples: calibrated expected-net abstention, uncertainty-adjusted reward, cost-aware trade-count penalty, downside-sensitive objective, market-regime-conditioned champion/router, and explicitly source-quality-weighted data. Do NOT blindly rewrite stop or exit policies or refit to win the already-inspected July–September test.
6. **Independent chronological evidence**: Build walk-forward folds on strictly development-only periods with purging/embargo, and ultimately secure truly later untouched BTC/ETH/SOL forward observations to distinguish generalization from reoptimization. Because the current date is 2026-10-20, sufficiently long post-September fresh data has not yet accrued; an exploratory replay on 2026 months **cannot** be marketed as untouched forward proof. No arbitrary deadline or forced trade count.
7. **Learning gate verdict**: For any brain to count as having improved, require matched one-slot after-cost improvement vs frozen prior champion and predeclared simple policies, meaningful improvement in net calibration/abstention rather than raw action count, controlled drawdown, adequate independent market/time coverage and uncertainty analysis. Positive vs **NO TRADE**, and robustness under additional +0.25% notional roundtrip stress, remain proposed economic promotion expectations in `V7_NUMERIC_GATE_PROPOSAL.md` pending separate owner freeze. Inconclusive evidence = **HOLD**, not a pass. Do not change numeric gate cutoffs after reading evaluation results.

**Broader universe unlock condition:** Owner explicitly reviews a versioned **Learning Gate Report** summarizing new, independently evaluated improvement. Until then, no 20–50 coin next-stage download, full archive batch or top-20 trained deployment merely because the tooling is ready. Research still may require small additional *historical time on the same 3 coins* for an agreed diagnostic, but do not expand coin count.

## 3. How successful open-source trading systems actually 'learn'

No generic trading package discovers profitable futures strategy automatically. Frameworks differ:

- **Supervised periodic retraining** (FreqAI, Qlib): The developer defines causal inputs and **future outcomes/rewards as targets**. After labels mature, the system fits a newer model; improvement is not guaranteed. Usually a separate entry policy interprets forecasts and is responsible for abstention/cost gating.
- **Relative ranking/context-aware forecasting** (Qlib and V4 LambdaRank): Models estimate relative quality across candidates or times. A higher ranking can still correspond to a *negative* expected net opportunity. A separate **absolute cost-calibrated NO TRADE** rule and actual occupied-slot model are essential.
- **Reinforcement learning** (FreqAI-RL, FinRL, Stable-Baselines3): Agent learns a policy from sequential actions and a **developer-defined reward** in a simulated environment (e.g. enter long, enter short, hold, exit). Repeating an episode may improve *simulator reward* while overfitting execution errors or unrealistic paths. Costs, partial fills, funding, reward penalties, zero-position choice, episode boundaries and slippage must be consistent with the real execution engine.
- **Online update / drift diagnostics** (Qlib rolling retrain, River ADWIN): Monitor changes in model error/regime, retain a champion and test challengers. Drift alerts alone are not orders to trade or permission to auto-promote; naïve updating can forget previous useful patterns.

**A Trading Brain 'learns' when newly matured outcomes change its policy and those changed decisions have objectively better prospective performance than an unchanged comparator**, not just when a file is retrained or 100 backtests are run on identical dates.

## 4. Verified open-source candidates — recommended prioritized exploration

| Framework | Official source, reviewed 2026-10-20 | Transferable concept | Fit for V7 / caveats |
|---|---|---|---|
| **FreqAI (Freqtrade)** | https://docs.freqtrade.io/en/stable/freqai/ and https://www.freqtrade.io/en/latest/freqai-parameter-table/ | Rich outcome-target generation, rolling supervised retraining, prediction validity/expiry, model persistence; existing Freqtrade/V6 economic runner interoperability | **FIRST audit ideas**, selectively adopt. FreqAI's own parameter table warns `continual_learning` is naïve and can overfit/stick in local minima. Per-pair whitelist limitations make its default model loop unsuitable as a drop-in broad adaptive top-20 system. |
| **Microsoft Qlib** | https://github.com/microsoft/qlib | Rolling retraining, market regime adaptation, learned asset ranking, causal model workflow, multi-model experiments | **FIRST research comparison**: Qlib workflow and rolling folds, not wholesale Qlib dependency or foreign-stock Alpha158 features. Compare with existing V4 LightGBM LambdaRank and independent utility abstention. |
| **River online-ml / ADWIN** | https://github.com/online-ml/river/blob/main/river/drift/adwin.py | Detect changes in forecast residual/realized loss distribution with adaptive windows | **LOW-RESOURCE diagnostics candidate**. Alert/challenger research; no live swapping just because ADWIN detects drift. |
| **FinRL and FinRL-X / FinRL-Trading** | https://github.com/AI4Finance-Foundation/FinRL and https://github.com/AI4Finance-Foundation/FinRL-Trading | Trading-as-Markov-decision environment; train/test/trade separation; risk-overlay and modular executor design | **SECOND-stage RL/design reference** after basic supervised reward/cost errors resolved. FinRL's main repo identifies itself as educational/legacy and points to FinRL-X. FinRL-X reports examples of stock/Alpaca results, NOT Binance USDT-M proof. |
| **Stable-Baselines3** | https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html | Tested policy algorithms (e.g., PPO) and methodologically rigorous separate evaluation environments, seeded experiments | **Only after** one-slot perps environment parity/realistic reward proof; heavy and brittle on 2vCPU/8GiB if built prematurely. |
| **FreqAI RL** | https://docs.freqtrade.io/en/2026.4/freqai-reinforcement-learning/ | Examples of long/short/neutral/exit actions, reward hooks, self-training | **Explore design but do not copy default rewards**. Official docs warn RL training environment omits various full trade callbacks/controls and agents can exploit reward 'cheats'. |
| **Hummingbot Quants Lab** | https://hummingbot.org/quants-lab/ | Backtest/ops separation ideas | **Do not prioritize**. Official documentation says it is *not actively maintained*, and it does not solve V7's supervised/after-cost brain-learning defect. |

No external repository was cloned, installed, merged or run during this note. These are upstream documentation-reported capabilities, not verified profitability or exact compatibility claims. Verify current licenses and API semantics before any selective code port.

## 5. Exact next bounded engineering task: '3-Coin Learning Autopsy' (NO retraining first)

**Input already retained:** BTC/ETH/SOL nine months' `labeled.sqlite`, model A/B1/B artifact manifests, immutable decision/trade JSONLs and corrected replay `summary.json`; use source hashes from [Step 6](evidence/v7-step6-real-pilot-boundary-audit-2026-10-20.md).

**Outputs in GitHub before any challenger:**
1. `V7_THREE_COIN_LEARNING_AUTOPSY.md` (source+score audits, data/label trust, PnL decomposition, risk/exposure and decision calibration).
2. A small deterministic diagnostic script and tests (if needed), operating only on offline records with no live credentials.
3. Prediction/realized net histograms or tables by brain, BTC regime, strategy family and score band; financial metrics normalized by trade count and sleeve, actual abstention/hypothetically available candidates, and explicit missing future-label rates. Label-only hindsight best must be marked unattainable oracle.
4. Specific falsifiable root-cause hypotheses and a preregistered **minimal** challenger experiment on development folds; preserve existing A/B1/B negative reports and freeze the July–September exploratory data as already inspected.
5. Owner-facing recommendation with exactly what changes are justified; do not begin broad-market data work until learning gate has credible evidence and owner agrees to unlock.

**Governance:** The earlier roadmap's "next 20–50 cohort" from Step 7 is now **SUPERSEDED IN PRIORITY**, not deleted. This owner decision is a **new mandatory gating dependency**. The storage/restart implementation remains useful and retained. The 20-coin strategy-aware selection design remains an eventual V7 feature, not canceled. Nothing here authorizes new paper/live orders.
