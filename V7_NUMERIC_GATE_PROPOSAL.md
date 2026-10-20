# NBOT V7 — Proposed Numerical Acceptance Gates and Test Matrix (NOT YET OWNER-FROZEN)

**Date:** 2026-10-20 IST  
**Status:** **RECOMMENDATIONS FOR OWNER APPROVAL**, not a change to the frozen V7 roadmap and not authority to launch G1, paper, live, or VPS jobs.  
**Evidence:** [G0 GitHub audit](V7_G0_GITHUB_AUDIT.md).  
**Scientific caution:** Exact economic cutoffs must be fixed before examining the intended evaluation period. A 95% test-confidence gate may require substantially more unseen data than the initial three-month prototype. Insufficient data => INCOMPLETE/NO-GO, **not** relaxing cutoffs after seeing results.

## A. Founder parameters already agreed (do not confuse with profit thresholds)

| Parameter | Starting contract |
|---|---|
| Market | All historically eligible Binance USD-M **USDT-settled PERPETUAL** contracts, including retired markets if recoverable |
| Historical prototype | 3 months: M1 initial universe/strategy study; M2 parallel candidate training histories; M3 chronological review (not called blind if previously inspected) |
| Strategy families | Research 10–15 independent families, not 10–15 slight variations of a single indicator |
| Detailed watch capacity | Up to 20 pair symbols; do not force entries |
| Signal clock | Initial 5m closed-candle research decisions; proposal review every 8h (provisional) |
| Trading capital capacity | At most 1 concurrent main paper/real position; all other eligible hypotheses simulated without capital |
| Research VPS constraint | Approximately 2 vCPU / 8 GiB; serialize heavy model jobs |
| Promotion | Owner authorization required for paper and separately for live; NO TRADE always allowed |

## B. Suggested acceptance rules, with test type and exact pass criterion

| ID | Gate | Proposed quantitative criterion | Failure handling |
|---|---|---|---|
| G0-01 | Legacy inspection | 100% of the explicitly shortlisted code/evidence modules have source path, ref, reusable/rewrite verdict, known risks; private VPS artifacts marked UNVERIFIED | Incomplete documentation does not create a validation pass |
| G1-01 | Historical market inventory | 100% of the *discoverable archive candidate directories* enumerated and recorded with scan time/errors; **no claim this equals every historic live exchange listing** | Unenumerated / unknown status excluded or explicitly marked unknown |
| G1-02 | Data completeness | >=99.9% 5m OHLCV coverage per selected symbol across a required continuous evaluation window | Exclude affected windows or symbols until repaired |
| G1-03 | Integrity | **0** duplicate timestamps, reversed intervals, nonpositive prices or impossible OHLC used in features/outcomes | Fail data gate for affected samples |
| G1-04 | Per-trade chronology | **100%** complete entry-through-exit candles or verified finer path for labels admitted to training/evaluation | Mark unresolved, NEVER fabricate a favorable fill |
| G1-05 | Historical as-of eligibility | **100%** of admitted candidate decisions carry an as-of contract eligibility record or defensible provenance evidence | Exclude uncertain pairs at affected times; report coverage rather than claim completeness |
| G1-06 | Historical funding/cost source | Every evaluated trade has fee assumptions, modelled slippage and known funding where possible; unverified items explicit with stress sensitivity | No 0-funded shortcut if materially unverified; keep unknown status |
| G2-01 | Family research | Evaluate **10–15** economically distinct families with independent signal definitions | 8 inherited V6 families remain negative controls, not automatic approved signal generators |
| G2-02 | Valid signal reproducibility | **100%** evaluated signals reproducible from entry-time known features; **0** future fields in feature matrix | Fail causality |
| G3-01 | Comparable learning size (prototype readiness) | >=**500** matured shadow candidate examples, over >=**100** decision times with 2+ simultaneously eligible candidates, with >=**10** contributing coins and >=**3** distinct signal families | More history required; do not force trades |
| G3-02 | Candidate ledger integrity | **100%** known qualifying accepted and rejected opportunities recorded; **0** duplicate IDs or mismatched decision timestamps | Fail data gate |
| G3-03 | Out-of-universe audit | Each universe-review time stores full excluded-pair eligibility counts and a predeclared sampled outside-universe comparison cohort | Unknown market misses explicitly tracked; no claim full market alpha coverage |
| G4-01 | ML chronology | >=**5** development-era chronological folds where feasible, with >=**20%** of development decision-time groups allocated to validation and purging/embargo at least as long as maximum outcome-observation horizon | Incomplete if time spans insufficient |
| G4-02 | Leakage | **0** known future-outcome features, training-label overlap, model fit after prediction time or illegal as-of universe changes; independent audit required | Hard stop |
| G4-03 | Baselines | Compare NO TRADE, V6, random matched-trade-frequency (multiple fixed seeds), liquidity-only, momentum/simple strongest score and V7 under same costs, dates and slot rules | Fail comparator fairness |
| G4-04 | Ranking calibration | Test top-1 selection uplift, expected net calibration per score band, cohort size/coverage, downside and abstentions; pass requires feasible economic edge in G5, **not** a chosen win-rate cutoff | Mark diagnostics and do not train to the metric |
| G5-01 | Untouched sample duration | >=**90 calendar days** of genuinely uninspected later market observations, ideally across >=**3** independently defined regimes; extend history if insufficient | Incomplete/NO-GO; July–September 2026 not pristine |
| G5-02 | Realizable portfolio sample | >=**100** *closed one-slot* native/equivalent trades in independent temporal conditions; NO TRADE not forcibly overridden | Incomplete; cannot manufacture trade count |
| G5-03 | Returns | Portfolio must have **positive** after-fee/funding/net cost PnL AND beat strongest comparable simple strategy on the same period | No promotion |
| G5-04 | Conservative cost stress | Repeat with additional **+0.25% of executed notional per completed round-trip** above modelled base fees, *without double counting*; resulting PnL still **positive** | No promotion |
| G5-05 | Confidence in improvement | 95% **block-resampled** confidence interval for incremental after-cost portfolio return vs strongest predeclared simple comparator has **lower bound >0**; blocks must respect serial/cross-coin dependence | If sample too small/inconclusive, extend unseen validation; no retroactive score tweaks |
| G5-06 | Max risk | Peak-to-trough drawdown of the **dedicated trading sleeve** <=**10%**, with fixed sleeve definition and capital notional; no worse than predeclared allowed risk envelope | No promotion |
| G5-07 | Data/execution discrepancy | **0** unexplained mismatches in sampled decision identities, fill timestamps, slot occupancy, fees or stop chronology in independent reconciliation. Any unknown real fills marked assumed | Fail until resolved |
| G6-01 | Prospective 20-pair shadow monitoring | >=**30 consecutive calendar days**, >=**99%** scheduled evaluation cycles accounted for with explicit gap events, **100%** frozen prediction IDs persisted | Extend observation if insufficient coverage |
| G6-02 | Forward comparison data | >=**500** matured prospective candidate outcomes and >=**100** distinct decision cohorts with two or more eligible alternatives | More data; no forced signals |
| G6-03 | Model governance | At least **one** frozen champion and **one** separately versioned challenger; **0** automatic challenger promotion on model fit completion | Hard stop |
| G7-01 | One-slot forward paper | >=**60 calendar days** AND >=**100** completed selected one-slot paper trades; remaining candidates keep shadow labels | Continue rather than force trade frequency |
| G7-02 | Forward economic decision quality | Positive paper net PnL, improvement vs prespecified comparator and NO TRADE, and still positive under extra **25bp** modelled roundtrip stress | No live consideration |
| G7-03 | Paper drawdown | <=**10%** trading-sleeve peak-to-trough drawdown, zero unauthorized live orders | No live consideration |
| G8-01 | Live authority | **0** live orders before owner's separate explicit approval, eligibility checks, exchange-permission and risk readiness | Hard stop |
| G8-02 | Initial live risk budget (proposal) | **1** open position maximum; <=**1x** leverage; <=**0.25%** dedicated trading sleeve planned loss at stop **including projected costs** | Stop/reduce sizing; not a guarantee against gaps |
| G8-03 | Automatic loss halts (proposal) | Suspend new entries on **-1% daily**, **-3% trailing seven-day**, or **-5% peak-to-trough** trading-sleeve loss, whichever comes first | Resume only with separately authorized review |
| ALL-01 | Journal & reproducibility | **100%** material steps/decisions reflected in `V7_CHAT_HANDOVER.md`; source ref, data hashes, model versions, run identity and pass/fail/unverified state | Step not complete until GitHub update verified |

## C. How to interpret numbers

- **Research readiness thresholds are NOT profitability thresholds.** A candidate dataset with 500 rows and 100 comparison events establishes a minimal prototype, not statistical confidence or trading permission.
- **Win rate is not a promotion gate.** A 40% win rate can be profitable and a 75% win rate can lose money; net after-cost expectancy and uncertainty dominate.
- **Matched comparisons:** Always evaluate V7 and simple selectors on the same available capital, costs, trade slots, trigger times and liquidity constraints. The hindsight-best trade is only a diagnostic ceiling.
- **Statistical gate:** A 95% CI requirement must be specified by resampling **time blocks** and preserving group correlation; individual coin-trade bootstrap samples are not independent. If confidence cannot be established at 90 days or 100 trades, increase duration rather than tune thresholds to pass.
- **Sleeve vs wallet:** Drawdown/risk limits refer to the explicitly reserved capital for the trading strategy, not to an arbitrarily oversized 100,000 USDT backtest wallet and 1,000 USDT per-trade stake. Declaring the sleeve value is mandatory.
- **25bp = 0.25%** *additional roundtrip* notional stress, on top of estimated execution fees, funding and slippage. This is a scenario, NOT proof of true historic fill/queue costs.
- **0 identified leakage** means every specified audit passes; it does not mathematically prove the complete absence of all bias.
- **One V7 research model may still choose no trades.** A zero-trade result is an honest no-go/incomplete economic sample, not something to fix by automatically lowering thresholds.
- **1x max leverage and loss limits are conservative proposed safety governance**, not legal or execution authorization; actual permitted leverage/venues depend on owner and exchange rules.
- All thresholds labelled **proposed** remain subject to explicit approval before an evaluation programme is preregistered. Numbers may be changed during planning **before** the holdout is exposed, with versioned documented rationale. They cannot be loosened retroactively in response to seeing target-period results.

## D. Historical V4 numeric settings — SOURCE FACTS, NOT V7 GATES

Original V4 source `main/nbot/observation/v4_policy.py`: **1,000** resolved outcomes per early generation; **5,000** for later generations; baseline paper exam **100 trades**; challenger head-to-head **50 trades**.

Original `main/nbot/observation/v4_promotion.py` included: at least **72 elapsed hours**, **3 UTC days**, **6 four-hour blocks**, **20 trades per direction**, mean net **+0.10R**, positive rate **>=50%**, max drawdown **10R**, worst trade >=**-3R**, max unscorable share **20%**, **2** volatility regimes with >=**10** trades each, and head-to-head mean lift >=**0.10R**. These may be historically useful governance defaults, but do NOT independently prove that a 50% win rate or +0.10R is appropriate for V7.

## E. Decision still required

The owner requested numerical specificity. **This document supplies a complete initial test/progression proposal but does NOT itself freeze or authorize it.** Once accepted, issue a numbered, owner-approved `V7_NUMERIC_GATES_V1.md` or a versioned roadmap amendment before training/inspecting the target holdout. Maintain the handover journal for this decision.
