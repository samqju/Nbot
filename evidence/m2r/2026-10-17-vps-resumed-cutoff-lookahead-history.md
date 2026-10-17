# M2R October 17 — Resumed V6 VPS, native label cutoff, official lookahead repeat, January history staging

**Scope:** The existing private V6 branch `prototype/v6-freqtrade-freqai-20261016`, draft PR #50 and owner-authorized `8GB-Observation` VPS only. **No V5 system, exchange keys/orders, paper service, strategy promotion or M3 release. M2 remains NO-GO.** This is real new **offline execution evidence**, not a claim of profitable AI.

## 1. Authorized VPS connection and isolation

- The saved PuTTY session previously lacked a username for noninteractive Plink. Adding **`-l root`** (using the existing saved session and PPK on F:, without reading keys) authenticated. The V6-only checkout was on the expected research branch, clean; it was safely fast-forwarded from `9f1b57b` to GitHub head `d2ed6e7`, then to the source-audit script commit `dbc1367`. This is **not a PR merge**.
- About **7.8 GiB RAM**, **96 GiB disk**, ~92 GiB initially free, no running containers before or after one-shot experiments. Installed `freqtradeorg/freqtrade:stable_freqai` reports **Freqtrade 2026.9**, image ID `sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535` (image ID is not a registry digest).
- Existing archive before expansion: **25/25 markets**, each with **26,997 5-minute futures candles** July 15 00:00–October 16 17:40 UTC, no missing time intervals. Corresponding 25×1h futures and mark series each had 2,248 hourly rows (through Oct 16 15:00 UTC). Funding is irregular exchange-event history, not to be imputed as hourly settlement observations.

## 2. Real installed-image 12-future-candle label cutoff test

Executed bounded **network-disabled Docker Python**, importing `IFreqaiModel.start_backtesting` from the installed image and `training_labels()` / `training_labels_for_family()` from the V6 strategy source, with actual BTC futures candles truncated to the **October 8 00:00 UTC training cutoff**. Confirmed the installed tagged implementation slices `date < training cutoff` **before** computing `&-` labels.

| 30-day BTC prefix / 8,640 5m candles | Valid hypothetical complete-trade labels | Trailing unlabeled decisions |
|---|---:|---:|
| Combined breakout+pullback | **1,145** | 12/12 |
| Breakout-only | **617** | 12/12 |
| Pullback-only | **539** | 12/12 |

All three explicit suffix assertions **PASSED**; process exit **0**. The official historical lookahead replay also independently logged **"dropped 12 training points due to NaNs in populated dataset 8640"** on original price-target rolling fits. This demonstrates the specific *outer* historical label-boundary contract on real data; it does **not** establish all native training rows, release-grade as-of forecast invariance or unbiased real fills.

Separate **80/20 internal validation warning:** `shuffle=false, test_size=0.2` uses chronological sklearn splitting but **no explicit embargo**. Label-only conservative checks on two real pairs found at most 12-candle label horizons touching the internal evaluation start: BTC combined 1, breakout 2, pullback 1; ETH combined 2, breakout 1, pullback 0. These are **illustrative label-only counts, not actual native fitted rows** (feature NaN filtering can change the split). Those internal validation metrics are *not* accepted as purged time-held-out results. Both outer-boundary/entry forecast tests and true internal-embargo proof still need independent review.

## 3. Repeated official Freqtrade AI lookahead check — warning STILL PRESENT

Bounded one-shot **25-pair** `lookahead-analysis`, original `NbotV6M2Audit` as-of October 1–8, official Freqtrade 2026.9/LightGBM, 0.05%/side fee, isolated identifier `nbot-v6-m2-lookahead-replay-isolated-20261017`, no credentials. Actual run **98.80 seconds, exit code 0**:

| Official diagnostic | Observed |
|---|---|
| `has_bias` | **Yes** |
| Tested signals | **8** |
| Explicit biased entries | **0** |
| Explicit biased exits | **0** |
| Changed indicators | `&-forward_return`, `&-forward_return_mean`, `&-forward_return_std`, `do_predict`, `DI_values`, `exit_long`, `exit_short`, `enter_tag`, `enter_long` |

**Source-level mechanism identified:** Freqtrade 2026.9 `freqtrade/optimize/analysis/lookahead.py`, `LookaheadAnalysis.prepare_data()`, deletes the whole dedicated FreqAI model-identifier directory before preparing every shortened single-pair/entry/exit replay, so the checker can compare independently **retrained** models and differently sliced prediction ranges. It marks `has_bias=Yes` if *any* compared indicator differs, even without an explicitly changed trade entry/exit result. Expected future `&-` label differences are called out by Freqtrade itself. **This explains a genuine diagnostic confounder, but does not prove all changed `do_predict`/entry columns are harmless.** Example official differences: `do_predict 1 != 0`, `DI_values 0.259588... != 0`, `enter_long 1 != 0`. Preserve the official warning; next step is a *frozen-model*, as-of, per-pair/prefix forecast comparison across all 25 with logged model hashes and first mismatching timestamp.

Full diagnostic log retained only on the V6 VPS: `/root/nbot-v6-m1-20261016/lookahead-boundary-20261017/official.log`. Do **not** infer actual execution/model leakage from an 8-signal diagnostic, but do not waive it either.

## 4. January 1–October 16 public history, new staged archive — 100/100 VERIFIED

Downloaded public Binance USD-M data for the **same frozen 25 markets**, January 1 2026 inclusive to October 17 exclusive (UTC); kept **separate** from the original V6 data/models under:

`/root/nbot-v6-m1-20261016/january-2026-public-history-stage/futures`

Used only one-shot Docker `download-data` with `--timerange 20260101-20261017 --trading-mode futures --data-format-ohlcv feather`:
- 25 × **5m futures** series: exit **0**, ~75 seconds;
- 25 × each of **1h futures, 1h mark and 1h funding_rate**: exit **0**, ~127 seconds;
- total **100/100** Feather files, ~**51 MiB** staged. The initial empty staging directory required its owner to be changed to the container's `ftuser` UID **1000**; first attempt produced permission errors and no files, corrected and cleanly rerun. The original source history, models and research strategy configs remained unchanged.

A separate official-image, network-disabled read-only program [`scripts/m2r_history_stage_audit.py`](../../scripts/m2r_history_stage_audit.py) checked **all 100** staged files against the original 100:
- Expected/missing **100 / 0**; duplicate timestamps **0**; unexpected 5m/1h candle spacing **0**; invalid OHLCV rows **0**.
- January 1 start and final requested day covered for all staged series. Funding is **irregular exchange events**, not artificially filled to hourly observations.
- Original July–October date overlap: **0 missing timestamps** and **0 mismatched OHLCV rows**.
- **Actual JSON audit process exit 0, `integrity_pass=true`**, complete 86-KB audit JSON retained on the authorized VPS at `/root/nbot-v6-m1-20261016/lookahead-boundary-20261017/january-staged-history-audit.json`.
- SHA256 of that complete original JSON proof: `26510558946960794b6f147ee6abd17114025f236cbc683a1f8806e97ffcbba5`. Corresponding compact GitHub [run summary](2026-10-17-vps-history-runtime-summary.json). Source audit commit `dbc13675f1238c53ed0063dc95de3e16bc05d78c`.
- The raw archive is **not committed to GitHub** and **not placed into the original active test directory**. No Jan-based LightGBM model was fitted and none of the pre-registered May–August backtests ran.

Reproducible offline staged file audit on the authorized V6 research VPS (after checking `git status` and Docker idle):

```bash
docker run --rm --network none --memory=2g --cpus=2 \
  -v /root/nbot-v6-m1-20261016/source:/research:ro \
  -v /root/nbot-v6-m1-20261016/january-2026-public-history-stage:/stage:ro \
  --entrypoint python freqtradeorg/freqtrade:stable_freqai \
  /research/scripts/m2r_history_stage_audit.py \
  --stage /stage/futures --original /research/user_data/data/binance/futures \
  --config /research/user_data/config.json --from-date 2026-01-01 --until-date 2026-10-17
```

## 5. Interpretation and next safety gates

**The owner's January-onward history objective has now been achieved at the data download/integrity stage, not the learning stage.** More data does not automatically change `train_period_days=30` to 60/90/180; the 25-pair historical FreqAI results remain the previously recorded September losses and short October gains. **No new PnL, model improvement or promotion** was measured in this run.

Next in existing M2/M2R order: (1) isolate actual original + Challenger all-25 as-of prediction invariance with **frozen model snapshots** and pin all future 12-bar training labels, plus internal split/embargo; (2) improve explicit execution fill/slippage and funding-boundary checks; (3) only then copy/use this audited archive for the **already pre-registered May–August monthly** 30/60/90/eligible 180-day comparisons, preserving original AI, matched non-AI, **NO TRADE**, costs and one global $1,000 1× position. Do not back-fit a winner on those months or call September pristine unseen time.

**M2 release NO-GO; M3 NOT STARTED; future M4 up-to-20 virtual paper positions NOT STARTED; M5A up-to-25 markets reviewed about every 8 hours UNBUILT; M7 LIVE MONEY LOCKED. PR #50 stays DRAFT and UNMERGED.**
