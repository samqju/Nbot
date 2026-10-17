# M2R — Native FreqAI 2026.9 historical train-cutoff source audit (2026-10-17)

**Scope:** Static examination of the tagged upstream Freqtrade `2026.9` sources and the existing private V6 branch, plus new offline regression tests. **NOT** a rerun of the pinned V6 VPS Docker image. The owner-authorized `8GB-Observation` saved PuTTY SSH session did not complete noninteractive host-key verification (batch mode refused an unknown host key). We did **not** auto-accept it, ask for credentials, reach the VPS or run any fresh market-data downloads/model fits/backtests. Do not report the new tests as passed until CI confirms.

## Source-verified outer 12-candle label boundary — encouraging, but not full runtime certification

Read exact upstream source tag `freqtrade/freqtrade@2026.9`:

1. `freqtrade/freqai/freqai_interface.py`, `start_backtesting()` approx lines 340–373: FreqAI first slices `dataframe_base_train = dataframe[date < tr_train.stopdt]`, next invokes `strategy.set_freqai_targets(dataframe_base_train, ...)`, then slices the training range and invokes the model's `train()`. **This is cutoff BEFORE label generation** for a historical backtest.
2. `freqtrade/freqai/data_kitchen.py`, `filter_features()` approx lines 234–253: removes rows with NaN features or labels from the training data.
3. NBOT `user_data/strategies/nbot_trade_outcome.py`, `training_labels()` and `training_labels_for_family()`: require 12 COMPLETE future 5-minute OHLC bars; leave the last 12 dataframe rows as NaN.
4. Consequently, if the tagged implementation and these functions run as inspected, the last 12 decisions before the rolling **outer** training cutoff are not trained with labels from the following model-backtest week. This is a **source-based positive finding**. It does NOT certify all real fitted artifacts, cross-pair data assembly or the installed immutable Docker image at runtime.
5. In contrast, computing the complete trade target on the full historical dataframe **before** slicing to the model fitting cutoff would import the next 12 prices into training. A separate [new regression test](../../tests/test_m2r_native_cutoff_contract.py) preserves this adverse counterexample as well as the intended correct behavior.

## Other model-validation boundary is not purged

The existing `user_data/config.json` sets FreqAI `data_split_parameters: {"test_size":0.2,"shuffle":false}`. Upstream `freqtrade/freqai/data_kitchen.py`, `make_train_test_datasets()`, invokes sklearn's `train_test_split` on previously filtered labels; `freqtrade/freqai/prediction_models/LightGBMRegressor.py` supplies that latter portion as `eval_set`.

Thus approximately the earliest **80% of eligible training examples** fit LightGBM and the later 20% are internally evaluated. As written, this split does **not** explicitly purge training examples whose future label completion overlaps the early rows of the internal 20% validation block. The last 12 possible labels immediately before that internal split should be embargoed (or independently checked for earlier stop/target completion) if this internal validation score is to be treated as clean evidence. **This is a real methodological limitation, not evidence that the NEXT outer backtest week leaked into training.** No new modification to native FreqAI fitting was deployed here. Internal heldout metrics remain non-acceptance evidence.

The outer 30-day setting does not mean the model fits on all 30 days: with test_size=0.2 and filtered indicator/setup rows, fewer fit samples are used. Any later 30/60/90/180 comparison must hold internal-split rules fixed and use separate identifiers and equal timestamps.

## Official `has_bias=Yes` is not resolved

Earlier official 2026.9 diagnosis on Oct 1–8, 25 markets: `has_bias=Yes`, **8 signals** probed, **0 explicitly biased entry signals, 0 explicitly biased exit signals**, but changed `&-forward_return`, `do_predict`, `DI_values`, and some entry/exit/enter_tag columns. See [recorded diagnostic](../m2/2026-10-17-ai-lookahead-and-signals.md).

Upstream Freqtrade lookahead documentation states `&-` FreqAI target indicator false positives are expected and that diagnostics compare a whole-pair run against replayed one-pair slices. Pair-specific feature context, refitted models, reused/shifted model caches or different analysis execution may produce non-equal predictions; **these are hypotheses**, not a verified root cause. Changed actual prediction/entry columns still fail the model-integrity gate. Next authorized VPS experiment must capture exact as-of feature/prediction arrays and model IDs at every 25-pair vs one-pair replay and classify first mismatching candle, holding train cutoffs/model artifacts fixed; include new Challenger and original AI. Never dismiss the warning because `&-` targets can be false positives.

## Next steps/gates

1. Safely re-establish the known PuTTY session's host-key trust through the owner's usual trusted channel; never disable host-key checking or auto-accept an unverified key.
2. Check branch/VPS git state, 2026.9 installed image digest and Docker idle status; run offline CI/tests and a focused native backtesting boundary/prefix integration proof; compare actual model training rows and 12-candle labels to source prediction.
3. Reproduce/isolate the lookahead warning with as-of controlled features, FreqAI model IDs, disabled model-reuse confounders, all 25 coins, and sufficient true signals. If an actual future leak emerges, fix and rerun full chronology with distinct identifiers.
4. Only after boundary certification and a defensible cost method, inventory/public-download January-onward candles and pre-registered month blocks, compare 30/60/90/180 windows where correctly warmed up. Preserve frozen original AI/no-AI/matched-exit/no-trade.

**Decision:** This audit narrows a suspected outer-label problem but does **NOT** pass M2, unlock M3, make any trading safe, or resolve lookahead/fill uncertainty. M4 paper up to 20 virtual positions remains inactive, M5A 8-hour dynamic up-to-25 candidate selector unbuilt, M7 real money locked.
