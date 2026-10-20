# NBOT V7 — Actual FreqAI After-Cost Multi-Strategy Three-Coin Challenger (FIRST RESULTS)

**Executed:** 2026-10-20 IST on authorized isolated 8GB-Observation VPS  
**Research status:** **FULL RESEARCH EXPERIMENT EXECUTED; NO ECONOMIC LEARNING GATE PASS.**  
**Financial outputs:** All simulated, USD-M USDT perpetuals, no exchange trade credentials, no paper/live orders, no model promotion.  
**V7 branch:** `V7`. Only BTCUSDT/ETHUSDT/SOLUSDT, 20 V7 candidate families (including the 8 V6 inherited controls), both sides when applicable, same single slot.  
**Separate mandatory scope:** `LEARN-3C`, NO whole-Binance expansion.

## 1. What actually ran

This work builds on the [real installed upstream Freqtrade/FreqAI 2026.9 baseline](V7_OFFICIAL_FREQAI_NATIVE_COMPARISON_2026-10-20.md). It is NOT a rerun of the official future-price-example strategy.

- [research/freqai_v7_net_fit_and_replay.py](research/freqai_v7_net_fit_and_replay.py) **imports and directly invokes the real upstream `freqtrade.freqai.prediction_models.LightGBMRegressor.LightGBMRegressor.fit()` API** (pinned Freqtrade 2026.9 environment). It uses an intentionally lightweight custom research data dictionary and saved V7 after-cost candidate labels, **not** FreqAI's full `start_backtesting` model-orchestration or default future-average-close target. Distinguish these modes explicitly.
- Each training example has only the V7 as-of feature vector (including as-of BTC context), LONG/SHORT indicator, one-hot strategy family and one-hot fixed coin. Regression target is **actual V7 virtual trade net-after-cost** with fixed 2% stop/3% take/60m holding limit and base modeled fees/slippage. No future MFE/MAE/BTC path is used as a decision feature.
- [nbot_v7/freqai_research_bridge.py](nbot_v7/freqai_research_bridge.py) demands candidate-level net forecasts with matching source SHA, family, side, exact 5m candle timestamp and model label cutoff. It scores EVERY simultaneous eligible candidate across all three coins at a common decision time, selects maximum **absolute after-cost estimate minus uncertainty and optional cost buffer**, or NO TRADE. All three fixed coins are watched without hindsight exclusion. Missing forecast and mismatched provenance fail closed. It does **not** use arbitrarily scaled per-pair rank scores.
- The historical replay is the **existing V7 one-slot 5m OHLC proxy**; it is NOT a native Freqtrade independent order-fill replay. The original 2026.9 example used a different stop/exit/economic policy and is **not an apples-to-apples portfolio comparison**.
- All training/replay uses the previous three-coin V7 dataset, no additional market pair downloaded, no exchange credentials, no changes to the protected execution/runtime core, zero paper/live orders.

## 2. Causality and data/reproducibility rules

- Model A eligible Jan–Mar matured opportunity labels; calibration 14 days before Apr1; predictions from Apr1 onward. Model B eligible Jan–Jun matured labels; calibration 14 days before Jul1; predictions from Jul1 onward. Cutoffs enforced `decision_ms < cutoff`, `label_available_ms < cutoff`; fit/calibration mutually chronological.
- Original v1 used V7 group-time thinning inadvertently giving A `39,135` and B `39,415` fitted examples despite six months of B evidence. **THIS WAS DETECTED AND CORRECTED**, not silently deleted. Source revision `ed3a7e90830bc33416b2c466db64c2ce8bfc996d` uses **ALL** three-coin matured rows subject to an explicit 350k capacity fail-closed guard, producing substantially different training sizes. The v1 and v2 findings must not be interpreted as independent additional unseen experiments.
- **Final v3:** A **78,008** training records; B **157,783** training records. Pre-cutoff (last 14d) calibration examples are separated and not fitted into each respective model. 75th-percentile absolute candidate residual from the calibration segment yields A uncertainty **59.277 basis points**, B **66.447 basis points**. **This is all-candidate empirical error, not a proven selection-conditioned confidence interval.**
- Three **prespecified** decision policies were replayed for each: RAW (predicted net >0), UNCERTAINTY (predicted net minus calibration 75th-percentile absolute error >0), STRESS (same uncertainty margin plus an additional 25bp hurdle). For clarity, `stressed_pnl_usdt` **also** deducts an extra 25bp per executed trade in outcome accounting. Never equate an entry hurdle with actual extra filled costs.
- `nbot_v7.experiment.replay` was executed with one $1,000-notional trade slot and separate $10,000 wallets, historical stop-first proxy and same fixed policy for A and B. The bridge uses timestamp-known 5m bar close; beware that a candle with opening label `t` only reveals its OHLC at `t+5m` and the next-open fill is a proxy, not genuine fill certainty.
- The entire July–Sep 2026 period has been studied earlier in V6 and V7. **None of these models or policies is a pristine untouched forward validation.** Numeric promotion gates not approved. Sampling-capacity revision after v1 observation makes the v3 series additional *development evidence* only.

## 3. FINAL V3 economic results (all simulated, not live fills)

**A trained Jan–Mar. B trained Jan–Jun. One-slot $10,000 wallet each.**

| Research portfolio | Apr–Jun closed trades | Apr–Jun net USDT | Jul–Sep closed trades | Jul–Sep net USDT | Jul–Sep net under +25bp per filled trade |
|---|---:|---:|---:|---:|---:|
| FreqAI After-Cost A RAW | 142 | **−164.8916** | 110 | **−246.1232** | **−521.1232** |
| FreqAI After-Cost A UNCERTAINTY | 10 | **+2.0805** | 7 | **−10.0655** | **−27.5655** |
| FreqAI After-Cost A STRESS hurdle | 4 | **+32.9731** | 3 | **−2.8785** | **−10.3785** |
| FreqAI After-Cost B RAW | n/a: not yet trained | n/a | 58 | **−14.9518** | **−159.9518** |
| FreqAI After-Cost B UNCERTAINTY | n/a | n/a | **5** | **+5.6678** | **−6.8322** |
| FreqAI After-Cost B STRESS hurdle | n/a | n/a | **1** | **−3.7156** | **−6.2156** |
| NO TRADE | 0 | **0** | 0 | **0** | **0** |

**Essential interpretation:**
- B RAW lost **$14.95 vs A RAW −$246.12** across the same July–September calendar, under matched one-slot/exit-cost policies. This is a meaningful **exploratory reduction of losses**, **NOT** proof of economically profitable learning. Both are negative, NO TRADE beats both, and the period was already inspected.
- B UNCERTAINTY gave a nominal **+$5.67** net across ONLY **five trades**; the additional 25bp/trade stress yields **−$6.83**, so NO TRADE remains superior under stress. Not enough independent samples for inferential confidence, and results may reflect fortunate handful of entries.
- B STRESS selected just **one losing trade**. A STRESS had isolated April–June +$32.97 from only four trades, but lost money on its July–September three trades. Nothing here proves it can reliably choose profitable entries.
- The B RAW Jul–Sep audit recorded predicted mean **+15.923bp** vs realized mean **−2.578bp** on selected trades; forecasts **remain optimistic** by ~18.5bp. It is inappropriate to compare directly with original V7's earlier +28–33bp optimism as though samples, policies and trade counts were matched.
- Source data still 5m OHLC stop-first/proxy with modeled funding/fees/slippage, historical listing lifecycle archive-observed/unverified, no real order-book fill chronology. Positive small $ amounts can disappear with costs and slippage.

## 4. Candidate families and ranking actually used

- The saved prediction export contains one explicit record per **available** historical candidate, including BTC/ETH/SOL, eligible family and side; the external after-cost regressor uses a common fractional net target and common feature schema rather than coin-specific uncalibrated arbitrary rank scores.
- The audit of **B UNCERTAINTY's five selected trades** confirms BTC **2**, ETH **2**, SOL **1**: **4** from `V6_donchian_breakout` and **1** from `pullback`, with selected mean predicted +14.954bp vs actual +11.336bp after base modeled costs. This group is too small for strategy-selection claims and historical-selection hindsight must not be used to over-promote those families.
- Across the same Jul–Sep 2026, B RAW selected **58** trades, source-hash-verified in immutable decision/trade ledgers: predicted mean +15.923bp, actual −2.578bp. Remaining optimism is a target for calibrated NO TRADE, not proof of profitability.

## 5. Verification and exact artifact references

- Actual offline training/replay successful exit status **0** on the authorized VPS, initial v1 (bad sampling) preserved at `runs/pilot-btc-eth-sol-2026/freqai-v7-aftercost-v1/`, corrected v2 preserved at `.../freqai-v7-aftercost-v2-all-matured/` and final source-hashed decision-ledger v3 at `.../freqai-v7-aftercost-v3-ledger/`.
- Final `summary.json` SHA256 **`d95de895cd69e9424705e0c838cb4d9971b59a7c2ce925c8bf0f2df1d7c4963f`** (133–175 MiB research directory; source model/prediction files retained separately).
- Source SQLite file SHA256 **`7905734e03ed74380d6fc477ebe11c96dc6de3e34fe6d9cf21ea85184fe8bd43`**.
- Model A joblib SHA256 **`6f3b658b4e115c0e9bb39f59678b289cba8db41dc087d01561151860561449ba`**, B **`9952e626ba7bb6dd8d7ff231b1da9f5dab93bb9e58fd39f66bb7b0ffa0883672`**. Both trained from official FreqAI `LightGBMRegressor.fit()` API in the isolated Freqtrade 2026.9 virtualenv, *not* native FreqAI per-pair start_backtesting.
- [research/freqai_v7_aftercost_audit.py](research/freqai_v7_aftercost_audit.py) independently verified the model-file digests, **ALL** exported prediction, trade and hash-chain decision ledgers for nine examined accounts against SHA256 receipts and exact summed portfolio PnL. Audit exited **0**. Audit file `.../freqai-v7-aftercost-audit-v3.json` SHA256 **`c369a10b7c84ea8616bfd90ae3bf65273023de89cf368e69ab6b45e35b53e330`**. Every July–September account recorded **18,131** decision events and `account_complete=true`.
- V7 GitHub Actions synthetic bridge suite [39393819091](https://github.com/samqju/Nbot/actions/runs/39393819091) **48/48 V7 and 530/530 legacy execution tests PASS** (commit `ffdae0cc9d5502c47766b7f60d674c98c3eba696`); source source compilation pass. The **specific native FreqAI research harness** was executed on VPS instead; it is not installed in V7 CI's minimal non-FreqAI dependencies.
- Research source commits: [bridge](nbot_v7/freqai_research_bridge.py) `13008a37e228de1a173dfe920dcb4ad858613cda`, [tests](tests_v7/test_freqai_research_bridge.py) `ffdae0cc9d5502c47766b7f60d674c98c3eba696`, [FreqAI fit/replay script](research/freqai_v7_net_fit_and_replay.py) `e4a4d4f525c03f8f6c28afed40d85ed2b53457ce` then all-label repair `ed3a7e90830bc33416b2c466db64c2ce8bfc996d` and immutable log+source receipt `bd59226aa47252bb8f4fc564f24db347a5bc9603`, [independent auditor](research/freqai_v7_aftercost_audit.py) `1ade2bfe70b0174676558c2788a6907799db011a`.

## 6. Learning gate verdict and next bounded experiments

**`LEARN-3C = HOLD (some exploratory promise, still FAILS robust profitability stress)`.** The experiment answers that a genuine FreqAI-provided supervised LightGBM head CAN be fitted on many matured V7 family/coin/side opportunities and used for *global* after-cost ranking with a real one-slot replay. It does NOT establish that FreqAI's automatic rolling learning is working, that any family has real positive alpha, or that the after-cost expectations are reliably calibrated.

**Priority next:**
1. Compare against simple **NO TRADE / frozen A / V7 B1 / V7 B** controls in matched chronology and execution assumptions. Upstream published FreqAI example is not a matched strategy target or exit policy. Verify FreqAI learner with group/time-block calibration instead of current **all-candidate** global 75%-error margin; inspect selected-trade false positives and family-level coverage.
2. Analyze the 5 B UNCERTAINTY selected trades and the 53 B RAW trades rejected by uncertainty **as future-only audit**; do not blacklist families or set a better winning threshold using inspected Jul–Sep labels.
3. Validate the 5m V7 paper-proxy against Freqtrade's native after-fee and funding stop chronology, and stronger unmodeled spread/mark/partial-fill stress before attempting promotion.
4. Require unseen prospective BTC/ETH/SOL observations once available, sufficient independent trades and positive after-cost (including 25bp stress) performance, plus owner-reviewed gate; if no edge, abstain. **NO VPS live service, no paper orders, no automatic champion swap or expansion beyond 3 coins.**

**Important clarification:** This research uses **FreqAI's actual LightGBMRegressor.fit() code** inside a custom offline multi-strategy data adapter. It is NOT equivalent to deploying or testing FreqAI's entire native retraining scheduler with family-conditioned targets. That would be a further independent test before production integration.
