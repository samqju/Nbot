# NBOT V7 — Multi-Strategy FreqAI After-Cost Challenger on BTC / ETH / SOL

**Recorded:** 2026-10-20 IST  
**Owner direction:** Proceed with one research-only multi-strategy FreqAI + V7 Trading Brain system that compares BTC, ETH and SOL opportunities at the same time and may select **NO TRADE**. Owner specifically asks what its deployment will test/teach.  
**Current status update:** This initial status was recorded while the laptop/PuTTY connector was temporarily OFFLINE. **Subsequent same-day implementation resumed on VPS and the FreqAI LightGBMRegressor.fit API was actually used for three-coin net-after-cost candidate models and one-slot 3+3+3 replay.** See [V7_FREQAI_V7_MULTISTRATEGY_AFTERCOST_INITIAL_RESULTS_2026-10-20.md](V7_FREQAI_V7_MULTISTRATEGY_AFTERCOST_INITIAL_RESULTS_2026-10-20.md) and Roadmap §20 for actual audited results. **Learning gate remains HOLD; no native FreqAI rolling orchestration, paper/live deployment, or proven profitable AI.** Prior offline note is retained in the chronological handover.  
**Permission:** Offline historical research only; no perpetual paper/live service, private API keys, orders, automated model promotion or whole-universe download.

## 1. What makes this different from the tested FreqaiExampleStrategy?

The earlier upstream FreqAI 2026.9 demonstration model targets averaged future closes and enters on predicted ±1% price movement. It does not compare V7's independently generated strategy/family opportunities or estimate their **trade net under V7's explicit exit and cost policy**. It lost **238 USDT on a separate $10,000 sleeve during the continuous Apr–Sep 2026 three-coin test**; see [source authority](V7_OFFICIAL_FREQAI_NATIVE_COMPARISON_2026-10-20.md).

New candidate: strict **after-cost supervised targets**, all 20 V7 research families (including the 8 inherited V6 controls and independent generators), both LONG/SHORT sides when a setup is eligible, per BTC/ETH/SOL and per common 5m decision instant. FreqAI will be a forecasting implementation, not the ultimate execution/risk authority. The V7 single-slot replay chooses the highest **confidence-adjusted absolute expected net** among ALL valid candidates, or none.

The model must **never** use post-decision BTC, MAE, MFE, outcome net or the best-hindsight coin as input features. Such fields are **label and later audit data only**.

## 2. Implemented in V7 in this phase

Source: [nbot_v7/freqai_research_bridge.py](nbot_v7/freqai_research_bridge.py). Tests: [tests_v7/test_freqai_research_bridge.py](tests_v7/test_freqai_research_bridge.py).

- Defines an explicit `after_cost_trade_net_fraction` target and requires the exact V7 research label policy `LABEL_POLICY`, not the upstream FreqAI example `&-s_close` future-price label.
- Each input model forecast is addressed by **(5m decision bar, symbol, LONG/SHORT, strategy family)**, binds a 64-hex-digit model digest and a 64-hex-digit original source digest and strictly rejects unknown field names (including leaked realized outcome fields).
- Corrects timestamp language: V7's `decision_ms` refers to the opening timestamp of the observed 5m bar, even though that bar's close is used. Consequently the feature-known time is **`decision_ms + 5 minutes`**, not the bar opening. The contract explicitly records and checks this; a future bar is rejected. Training target availability cutoff must be no later than the decision bar timestamp. Validate exchange order timing before calling any simulated fill native-equivalent.
- Unavailable/mismatched predictions cause abstention/fail-closed, not invented profits or default `0` outcomes; duplicate predictions are rejected. An unknown/nonpositive opportunity is not automatically traded.
- Three-coin watch layer includes all three fixed symbols without forward-selection bias or pretending a top-20 coin selector has been validated. No pair-specific price-ranked proxy substitutes for after-cost regression.
- Opportunity evaluation: `risk_adjusted_expected_net = model_expected_after_cost_net − uncertainty_weight × uncertainty_net − extra_cost_stress` (all in fractions of trade notional). This value is used both for positive/negative trade eligibility and cross-coin ranking; **not** LambdaRank scores that may be uncalibrated between coins. Setting the uncertainty penalty or cost stress should be preregistered on development-only windows.
- Uses existing `decision.choose` and single-capital-slot `experiment.replay` once the FreqAI model output is generated. The bridge **does not** currently train or run FreqAI by itself and cannot infer valid after-cost forecasts from the official future-price example.

**Nothing currently authorizes use of the bridge in the actual order runtime.**

## 3. Implementation steps still required before a valid V7 experiment

1. **Native FreqAI target producer** in isolated Freqtrade/FreqAI 2026.9 environment: use V7 source-matured `opportunity` outcomes with full side/family identity and strictly as-of permitted features, rather than generic future-price labels. Resolve per-pair FreqAI time-series rows versus many strategy candidates at each timestamp without treating an absent family as zero reward or training on hindsight-selected best outcomes. Pin and hash all source ZIPs, feature schema, exact model artifacts and label policy.
2. **Causal prediction exporter:** For the target bar, coin, family and direction, emit the 15-field net-forecast contract above, including `training_labels_available_before_ms` and `features_ready_ms`, model digest, source digest, and an uncertainty estimate calibrated on *past-only* folds. Produce matched coverage and missing-data statistics. The model and its label calibration **must** be fitted before the scored test bar.
3. **Single chronological replay:** Run the unchanged V7 one-slot simulator with candidate scores across all 3 symbols and strategy families, using the same frozen **2% stop / 3% target / 60-minute limit** and declared fee/slippage/funding-proxy assumptions as existing V7 baseline. No pair-iteration order may allocate capital before global ranking; no future outcome lookup prior to winner choice.
4. **Research A/B/B1 comparison:** train forecast A on Jan–Mar; examine A prospectively within Apr–Jun; fit challenger B and same-architecture B1 only after Apr–Jun matured outcomes; evaluate A/B/B1 with new fixed instances on Jul–Sep along with unmodified V7 A, published upstream FreqAI example (different economics, shown in separate context only), and NO TRADE. Monthly rolling retrain **must** account for label horizon embargo. **Do not** claim the upstream FreqAI published strategy is a matched economics control.
5. **Data science & confidence:** Measure all-candidate calibration vs *selected* top-net calibration, relative coin/family ranking vs absolute utility, frequency/cost/drift, false-positive entries, NO TRADE opportunities, selected regret, net aftercost one-slot PnL and drawdown, extra +25bp cost stress, separated train/validation/final windows, dependence-block bootstrap; report model prediction coverage and source eligibility. Any oracle best hindsight is a *diagnostic ceiling*, not executable opportunity.
6. **Learning proof:** V7 LEARN-3C does not pass merely because a new model differs, trades fewer times or loses less on already inspected 2026 periods. Need robust improvement vs **NO TRADE** on new truly untouched forward data, with economic/stress checks and owner review before even expanding beyond 3 coins. Keep original negative results immutable.

## 4. What questions will this answer?

- **Are any of the 20 V7 candidate families predictably profitable on BTC/ETH/SOL under a constant outcome policy,** or are all choices below after-cost break-even?
- **Do additional expert/strategy forecasts add value compared with the same frozen baseline?** Is apparent coin ranking useful when all three expected after-cost results are negative?
- **Can FreqAI's estimator rank cross-coin *absolute net value* correctly,** not just forecast a +1% price move or provide an arbitrary pair-specific classifier probability?
- **Does NO TRADE actually recognize losers?** What fraction of prior A and adaptive B loss would it reject without blindly refusing all opportunities?
- **Does the next model improve decisions with newly matured labels**, with matched one-slot capital constraints? Where is prediction overconfidence (previously observed +28–33bp on selected candidates) reduced rather than displaced?
- **Does economic improvement survive different regimes, model retrains, +25bp cost stress, proper holdout contamination notes and block-bootstrap dependence?** If not, identify why and stay flat/hold.

## 5. Operator next step when the authorized laptop link is back

The first validation after restoring VPS access is to fast-forward the `V7` code checkout, run the complete `tests_v7` + audited legacy tests, verify that the new bridge's GitHub CI is green, then inspect actual saved FreqAI prediction feather/metadata and implement target-producing native FreqAI strategy in **isolated** directory. No private keys or trade services. Save a source-hashed manifest and evidence in GitHub before any financial conclusions.

**This document is a build and evaluation contract, not a claim the new challenger has been trained, deployed or economically tested.**
