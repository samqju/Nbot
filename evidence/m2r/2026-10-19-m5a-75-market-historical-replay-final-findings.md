# Nbot V6 — Historical M5A Universe Selector Proxy: Completed First Study

**Completed / independently verified:** Monday, 19 October 2026, ~13:52 UTC.  
**VPS:** `srv2069046` via authorized `Sameer-Laptop`, isolated V6 checkout, **no orders and no strategy/model promotion**.

## Direct answer

**Yes: dynamically chosen coins changed the historical opportunities. But there is no robust evidence that simple liquidity or market-quality universe rotation improves the chance of useful winning entries.** In fact the simple 24h liquidity-only selector substantially worsened the tested +2% momentum first-touch hit rate. The enhanced hourly OHLCV quality selector improved its **own quality score** but yielded nearly the same 2%/3% favorable-first touch probabilities as the fixed 25 overall. Its September improvement REVERSED in October.

This is a **75-current-survivor, hourly-candle *proxy study***, not a production M5A historical replay or an original 25×8 strategy native Freqtrade economic backtest. Do not claim real aftercost alpha.

## Exact source and experiment

- Binance public `fapi/v1/klines` hourly OHLCV, **75 symbols sampled** from the contemporaneous *October 19 current* Binance USDT-M PERPETUAL universe, with the original fixed 25 always included. History requested **2026-06-01 00:00 to 2026-10-19 00:00 UTC**. This introduces **serious historical survival / candidate-sampling bias**; it is NOT a complete point-in-time historical listing census.
- Download succeeded for **75/75, failed 0**, `nbot-v6-m5a-history-20261019.service` **inactive / Result=success / ExecMainStatus=0**. SHA256-audited one-file-per-pair hourly candles and full immutable download manifest at `/root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/`.
- Predeclared **234 eight-hour review instants** from **August 1 through October 17, 2026** (end October 18 exclusive); each market must have 45 preceding calendar days of hourly recorded candles and minimum observed 24h quote turnover. All inputs for each decision come from **previous completed hourly candles**.
- Three shadow-selected 25-pair universes: **fixed original 25**, **24h historical quote-turnover liquidity-only**, and **65% historical quote-turnover / 35% favorable 24h range quality proxy**. BTC pinned; <=10 changes per 8h review; 24h minimum tenure for discretionary swaps. **None of these supplies historical actual bid/ask spreads, book depth, funding, contract trading status or independently verified matured model readiness**, so the latter two are not the fully specified live M5A.
- To compare *potential entries*, a **SIMPLE NON-NBOT momentum diagnostic** chose the largest absolute past-eight-hour price change, long or short depending on sign, at each review (>=0.7%). Evaluate whether hourly high/low subsequent 24h **first touches +2% or +3% favorable before −2% adverse**. In any hourly bar crossing both limits, count **STOP FIRST**. All three universes use exactly same diagnostic, timestamps and stops. The following 24h observation horizon is **not an executable 24h exit policy**; it bounds the labeling period only.
- The 24h outcome labels **overlap** three subsequent eight-hour reviews and do not respect the original **one-open-position** capital constraint; they are **NOT independent trades, native fills, Nbot eight-strategy entries, actual aftercost profit or equity curves**. Eight original library strategies are not evaluated in this diagnostic. No FreqAI model has been retrained.

## Actual historical result across 234 identical review points

| Historical shadow universe | Virtual coin replacements | Mean chosen hourly market-quality proxy | +2% reached before −2% | +3% reached before −2% |
|---|---:|---:|---:|---:|
| Original fixed 25 | 0 | 0.8294 | **113/234 = 48.3%** | **85/234 = 36.3%** |
| Liquidity-rotated 25 | 186 | 0.8840 | **87/234 = 37.2%** | **71/234 = 30.3%** |
| Multi-factor quality-rotated 25 | 142 | 0.9012 | **114/234 = 48.7%** | **87/234 = 37.2%** |

The dynamic quality policy genuinely made different selections: over the review window it held **48 unique symbols**, including **26 outside the original 25**. Liquidity policy held **66 unique symbols**, including **41 newcomers**; its higher turnover did not translate to higher target-first outcomes.

### Monthly stability: no consistent improvement

| Month | Original +2% | Quality-selected +2% | Original +3% | Quality-selected +3% |
|---|---:|---:|---:|---:|
| August (93 reviews) | 39/93 (41.9%) | 41/93 (44.1%) | 26/93 (28.0%) | 31/93 (33.3%) |
| September (90 reviews) | 47/90 (52.2%) | 53/90 (58.9%) | 39/90 (43.3%) | 42/90 (46.7%) |
| October 1–17 (51 reviews) | 27/51 (52.9%) | **20/51 (39.2%)** | 20/51 (39.2%) | **14/51 (27.5%)** |

Even in this idealized historical price-path proxy, the September advantage vanished and **reversed materially in October**. A market-quality score may capture execution readiness, not whether a given strategy/direction will produce profitable follow-through.

### Paired uncertainty check

An independent [SHA256/decision reproducer](../../scripts/m5a_historical_proxy_independent_audit.py) reconstructed all **234** selections directly from **75 SHA256-matched historical candle files** and their original manifest, enforced BTC pin/25 slots/max10 rotation, then used 2,500 deterministic **UTC day-block resamples** of *paired* review differences as an exploratory diagnostic:

| Selector vs fixed25 | Observed +2% first-touch rate difference | Exploratory 95% day-block interval |
|---|---:|---:|
| Quality25 | **+0.43 percentage points** | **−6.84 to +8.12 points** |
| Liquidity25 | **−11.11 percentage points** | **−18.38 to −3.85 points** |

For +3%, quality improved **+0.86 points**, exploratory interval **−5.13 to +7.27**; liquidity worsened **−5.98 points**, interval **−12.82 to +1.71**. These uncertainty intervals do **not** correct sample survivorship, timestamp ambiguity, historical screen differences, overlapping future labels, dependency of selected coins, or the fact that prior market months were already viewed. They are descriptive, **not valid prospective strategy confidence bounds**.

**Do not infer "the liquidity selector is truly harmful" outside this narrow sampled retrospective diagnostic**, or that quality25 is better merely from +1 additional target hit.

## What this teaches us beyond prior research

1. **New coins definitely change the as-of trade opportunity pool:** the quality selector encountered 26 non-original coins across 234 historical review slots. Prior original 25-only studies could not have evaluated these.
2. **Volume / liquidity is a screen, not an alpha signal.** Improving historical turnover score alone produced *worse* first-touch hit rates in this exploratory sample. Better market-quality screening did **not** noticeably improve conditional opportunities.
3. **Conditional direction and exit-aware expected net payoff must drive rank AFTER eligible-universe preparation.** Do not choose coins merely because they are high-turnover or volatile. Universe and entry selector should be evaluated separately: where market data is safely executable, among eligible choices which coin×strategy×side×exit provides the **best positive risk-adjusted *net* value**? If none, NO TRADE.
4. **Avoid over-rotation:** quality rotated 142 slots (0.61/review) and liquidity 186 (0.79/review). Both respect max10, but meaningful churn can introduce model onboarding, funding, opportunity and execution overhead that this proxy does not price.
5. **We still cannot claim Nbot profitability.** The apparent 40–49% target-first probabilities are for a *preselected single 8h momentum proxy*, not Nbot's actual 8×5m entry triggers or real +2/+3 realized profits. No one-slot Freqtrade economic results were generated.

## Reproducibility and safeguards

Repository artifacts: [download and SHA manifest source](../../scripts/m5a_historical_1h_download.py), [precommitted chronological proxy replay](../../scripts/m5a_historical_ohlcv_proxy_replay.py), [independent SHA256/paired day-block audit](../../scripts/m5a_historical_proxy_independent_audit.py), [source invariant tests](../../tests/test_m5a_historical_ohlcv_proxy_replay.py), [reproduced readable report generator](../../scripts/m5a_historical_proxy_report.py).

Actual VPS outputs:
```text
/root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/historical-download-manifest.json
/root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/replay.json
/root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/historical-replay-report.md
```

Commands (read-only once saved files exist):

```bash
cd /root/nbot-v6-m1-20261016/global-next-source
python3 -m unittest tests.test_m5a_historical_ohlcv_proxy_replay -q
python3 scripts/m5a_historical_proxy_independent_audit.py \
  --data /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019 \
  --replay /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/replay.json
```

## Required before any real dynamic M5A / AI profitability claim

Obtain a historical **point-in-time available universe including delisted contracts**, historic orderbook bid/ask depth and slippage, 5m OHLCV, funding/mark and valid model training for each newly selected coin. Predeclare 25-of-N candidate screening parameters; train exit-matched after-cost win/size/duration predictions using strict walkforward and purged splits, then compare static25 vs dynamic25 in the **same original eight-strategy, one-slot official Freqtrade native engine** on genuinely untouched future data, reporting paid fees, adverse path, average realized P&L, drawdown and NO TRADE reference.

**Status:** a completed historical proxy research result, NOT a profitable algorithm or paper/live activation. The 8h M5A public shadow timer remains separate and safely screen-only; no live trading, V5 changes or merging PR #50.
