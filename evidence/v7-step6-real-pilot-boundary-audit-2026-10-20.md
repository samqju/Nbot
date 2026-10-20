# NBOT V7 Step 6 — Actual Binance Three-Coin Pilot, End-Window Causality Fix, and Full-Market Inventory

**UTC:** 2026-10-20  
**Research authority:** VPS research-only; no live credentials/orders, no real-paper trading, no service installation or changes to other NBOT versions.  
**Branch:** `V7`  
**Final code commit for this step:** `69e3e26c0dc67aba6846b0195a41b4d1a47d7665`  
**VPS workspace:** `/opt/nbot-v7-20261020`  
**Research classification:** **ENGINEERING-ONLY / NO ECONOMIC PROMOTION / INCOMPLETE ALL-MARKET EVALUATION**.

## 1. Exact resumed source state

- Recovered GitHub implementation branch `V7` at `09072aa2f6d0bc5fa4dbcaa4f714131734bd80c0` and canonical `V7_CHAT_HANDOVER.md`.
- Confirmed isolated VPS workspace and historical pilot existed. Prior Work chat's description of the pilot was **ahead of its most recent GitHub handover**; preserve both sources and append this reconciliation. No previous work was reset.
- VPS free storage at resumed observation ~94 GiB, RAM available ~7.4 GiB. Existing isolated V7 code checkout was behind GitHub head; updated it by `git pull --ff-only origin V7` without touching other services.

## 2. Nine-month public Binance archive inventory and original pilot (verified readback)

The completed public monthly archive inventory at `data/archive-index-v2.json`, SHA256 `09b61797a094a16b7bc46c69308097426dafbdb2b1d3a4d5f49760072c8f8c22`, reports:
- **1,056** archive directories observed, **900** USDT-style symbol directories under `um/monthly/klines`, **876** symbols with January–September 2026 archived objects. These are **NOT independently certified historical active perpetual contracts**.
- **12,234** month/source ZIP objects (6,566 5m klines + 5,668 fundingRate); declared compressed sizes total **1,791,265,945 bytes**. Do not assume these represent a fully tradable historical universe; source-tradeability and delisting evidence absent.
- Downloaded BTCUSDT/ETHUSDT/SOLUSDT-only engineering pilot has **54** monthly kline/funding ZIP archives with exchange-published SHA256 checksums checked and **249,685** labels, **2,454** symbol-review records. Historical lifecycle grade **`ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`** and simulated outcome authority **`OFFLINE_5M_PROXY_NOT_ACTUAL_NATIVE_EXECUTION`**.
- Model A fit on Jan–Mar 2026; frozen A evaluated Apr–Jun; B1 and B adaptive fit on Jan–Jun labels; independent model accounts examined July–September 2026. All nine months are development-only for promotion as V6 previously inspected portions of this data.
- The original pilot reported `account_complete=false` for A and B1 July–September, each due to a selected opportunity whose label was unavailable near the hard period end. The original simulated PnL values were A −340.6883 USDT / B1 −660.0041 USDT / B adaptive −953.6469 USDT on independently allocated 10,000-USDT research sleeves. Original report SHA256: `0a48ea6a008bde25a2d78ac90fa14ba1a3e7129545f3f950bddd857129827942`. It remains intact at `runs/pilot-btc-eth-sol-2026/experiment/`.

## 3. What changed, and why the fix is causal

**Problem:** V7's portfolio replay could select an entry at the end of a predeclared April–June or July–September examination even when the frozen 60m holding horizon no longer fit inside the evaluation period. Since candidate formation properly cannot look at future labels, the selected opportunity could have an unresolved path; the subsequent model comparison nevertheless emitted bootstrap statistics.

**Fix:** Before model selection and without inspecting any future label, at decision time `t` refuse *new* entries where `t+12*5min > period_end_ms`. The same boundary applies to A, B1, B adaptive and simple selectors. Entries exactly one full fixed horizon before end are allowed. This does **not** choose best hindsight exits and does **not** falsely treat unobserved trades as losers. A non-boundary missing label still locks capital and marks account **incomplete**.

**Additional independent confidence rule:** `block_bootstrap_uplift` now returns `INCOMPLETE_ACCOUNTS_NO_UPLIFT`, without a confidence interval, if either account is incomplete. Previously saved confidence estimates involving incomplete A or B1 accounts were **not valid inferential evidence**.

**Code changes:** `nbot_v7/experiment.py` (entry horizon, policy recorded), `nbot_v7/science.py` (paired-completeness guard), `tests_v7/test_causal_replay.py` (new boundary and incomplete-pair adversarial tests), `tests_v7/test_offline_contracts.py` (fixture honors same policy). All are on GitHub V7, commit `69e3e26c0dc67aba6846b0195a41b4d1a47d7665`.

## 4. Readback of corrected, new run (original pilot retained)

New immutable output directory:
`/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed/`

The existing source-hashed `labeled.sqlite` dataset and already-downloaded ZIPs were **reused**. No archive download, training-data revision or entry signal tuning was performed. The model-fitting/replay pipeline re-ran under the corrected boundary.

| Model / period | Closed trades | Net USDT | Account complete | Border entry abstentions |
|---|---:|---:|---|---:|
| A, Apr–Jun | 255 | −497.7071 | yes | 7 |
| A, Jul–Sep | 233 | −340.6883 | yes | 6 |
| B1 same-arch more data, Jul–Sep | 377 | −660.0041 | yes | 6 |
| B adaptive, Jul–Sep | 630 | −953.6469 | yes | 6 |

- All four compared ML accounts are now reported **complete** and have `unresolved_selected_paths=0`, compared with A/B1 formerly **incomplete**. The negative closed-trade PnL is unchanged; no retroactive selection of profitable labels occurred.
- The corrected seven-day block-bootstrap diagnostic records **B adaptive − A: −6.12959 percentage points** of 10,000-USDT research sleeve; **B1 − A: −3.19316 percentage points**; **B adaptive − B1: −2.93643 percentage points**. These are still dependent, three-coin, 5m-proxy, previously inspected historical comparisons and **not** independent statistical/economic acceptance evidence. Baselines are not matched for trade count.
- Rerun exit status **0**, experimental test suite **34/34 PASS** on the authorized Linux VPS (new boundary and completeness tests included). No native Freqtrade or actual exchange order fills were verified in this step.
- Corrected run summary SHA256: `7e6097bac1e3565863e6d1f5d017c8df722e808738ae03323a13ae1b5734dae0`.
- Corrected `run_manifest.json` SHA256: `77457166e61d86e8cb30d609a5c41d140a603cca90775fb92c8b1bf958341da7`.
- VPS V7 unit-test transcript SHA256: `1f5cb40595decd2c3bd4d54c74885b4335b4203dd25f8094790b9b4bbae8b19c`.
- VPS isolated checkout after fixed commit `69e3e26c0dc67aba6846b0195a41b4d1a47d7665`.

## 5. Why this is not G5 or market-wide validation

**No promotion:** All three trained brains lose money in the small three-coin July–September experiment; additional model complexity increased losses. The historical universe was archive-observed, not proven actively listed/eligible at every timestamp. Trading costs are modeled 5-minute OHLC approximations; order-book spreads, partial fills, liquidity, native exchange stop-order chronology, historical exchange filters and funding settlement parity remain incompletely attested.

**Whole-market resource safety:** Source inventory includes 900 USDT-like folders but no verified historical active registry. The pilot labeled SQLite grew to ~344 MiB for 3 coins; naïve all-symbol extrapolation could exceed the 96 GiB VPS filesystem. Before downloading/building the entire 12,234-object universe, implement a bounded/checkpointed per-symbol dataset builder, stronger feature/label storage, preservation of source receipt hashes and disk/memory budget aborts. Do not let a partially built database carry `build_complete=true`.

**Next bounded step:** Implement disk-bounded crash-resumable all-market ingestion and model-training scale gates, establish historic lifecycle source coverage and a quota-controlled download/resume plan; then run a larger correctly qualified non-survivor-inclusive cohort. Every meaningful step must update the same-branch V7_CHAT_HANDOVER.md. This document does not authorize any live or paper exchange operations.
