# Nbot V6 — Historical 8-hour M5A Proxy Replay (2026-10-19)

**Operational state at last direct VPS verification: historical data acquisition IN PROGRESS, not verified complete.** Research remains offline. The user's Windows laptop/Desktop Commander bridge became **offline** before the downloaded 75-market data could be finally checked or replayed. Do **not** claim a completed 75-market comparison or profit results.

## Why this replay is necessary

The previously completed V6 market, strategy, stops and ML studies used the original fixed 25 futures markets, while M5A is intended to dynamically screen a wider market every 8 hours. The VPS had native 5m strategy, funding and mark data for **only those original 25**. Replaying "dynamic 25" against those same 25 would be circular. Existing 06:22/12:54 UTC *current* Binance snapshots cannot retroactively prove historical spreads/depth or listing status.

## Exact work performed on VPS

- At 2026-10-19 **13:28 UTC**, verified clean isolated `global-next-source` V6 branch, active public-only M5A eight-hour shadow timer, no known active trading commands; original native history 5m files cover only 25 markets.
- At approximately 13:31 UTC, created isolated one-off service `nbot-v6-m5a-history-20261019.service` using `systemd-run`, running [public Binance historical downloader](../../scripts/m5a_historical_1h_download.py) with **75 current survivor-biased candidate symbols** (always including original 25), requesting **closed 1h Binance futures klines from 2026-06-01 to 2026-10-19 00:00 UTC** (so only June–October 18 candles). No exchange keys, no orders or exchange configuration changes. The downloader stores independent per-symbol immutable `*-1h.json` and then `historical-download-manifest.json` with SHA256 checks.
- **Last direct verification 13:33:41 UTC**: download had completed at least **44 of the 75** symbol files, active service, each observed candle record validated as closed. Output directory `/root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/`. **The downloader may have progressed further after 13:33:41 but it cannot be independently confirmed while the relay is offline.**
- Committed [pure read-only historical M5A proxy replay](../../scripts/m5a_historical_ohlcv_proxy_replay.py) and [deterministic Markdown report](../../scripts/m5a_historical_proxy_report.py). Replay code has tests for no future candles and stop-first ambiguous 1h target touches. Latest GitHub CI unit test job succeeded; full actual replay was **not yet executed on the VPS**.

## Experiment predeclared BEFORE viewing results

Three counterfactual *shadow* universes, all at the same historical **UTC 00/08/16** boundaries, with 25 symbols, BTC pinned, 0–10 changes per review and 24h minimum incumbent tenure:

1. `fixed25`: original 25 always remain selected.
2. `liquidity25`: rotate incumbents using their immediately preceding 24h closed-hour *quote turnover*, no future indicators.
3. `quality25`: rotate incumbents using 65% 24h turnover + 35% moderate 24h high/low range score as an **hourly OHLCV market-quality proxy**.

Start comparison **2026-08-01 to 2026-10-18**, with >=45 days observed previous hourly candles required for eligibility. At each review: compare candidate count, scored quality, number of rotations, and a **simplified non-Nbot 8h momentum probe** for a single opportunity: if strongest eligible 8h absolute momentum >=0.7%, mark LONG/SHORT in that direction and label whether a following **24-hour** hourly price sequence first touched +2% / +3% target versus −2% protective stop. Same-hour both touched is marked STOP FIRST. All selection inputs exist before the reviewed candle; future data is used only for evaluation labels.

**These 24h candidate outcome labels overlap when reviewed every 8h. They are NOT a one-slot portfolio, not the original 8×5m signal strategies, not real exchange fill P&L, not AI model readiness or trading profitability.** No historical orderbook bid/ask or funding is downloaded. The **75 contracts were sampled using October 19 public ranking**, creating *selection and survivorship bias* when applied to August and September, even if individual hourly candles are chronological. Neither one day of current market data nor one historical OHLCV panel can certify the original M5A eligibility contract.

## Reproduction — once the owner's laptop bridge returns

Read-only verify download has actually completed:

```bash
systemctl show nbot-v6-m5a-history-20261019.service -p ActiveState -p Result -p ExecMainStatus
journalctl -u nbot-v6-m5a-history-20261019.service -n 20 --no-pager
test -f /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/historical-download-manifest.json
```

Once manifest file exists and confirms 75 attempted symbols, complete unique original 25 hashes, and adequate historical coverage, run the **immutable independent analysis**:

```bash
cd /root/nbot-v6-m1-20261016/global-next-source
git fetch origin prototype/v6-freqtrade-freqai-20261016
git merge --ff-only FETCH_HEAD
python3 -m unittest tests.test_m5a_historical_ohlcv_proxy_replay -q
python3 scripts/m5a_historical_ohlcv_proxy_replay.py \
 --data /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019 \
 --out /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/replay.json
python3 scripts/m5a_historical_proxy_report.py \
 --replay /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/replay.json \
 --out /root/nbot-v6-m1-20261016/m5a-historical-proxy-20261019/historical-replay-report.md
```

Review the full `summary_by_month` as well as aggregate. Reject any lookahead or suspicious test fixture. The upcoming result may be better, equal or worse than fixed25; no claimed gain before observing it.

## What genuinely profitable evaluation would still require

A real historical broad-market M5A with point-in-time contemporaneous contract listing and trading status (including delisted markets), bid/ask spreads, orderbook depth, funding/mark, 5m OHLCV and matured exit-matched models for all newly admitted coins, and a ONE SLOT native Freqtrade portfolio comparing the same eight strategy signals/exit policies across both selected universes on a genuinely unseen period. Until then, a better OHLCV ranking or 2% touch rate **is an opportunity proxy only**.

**No live/paper trading, no V5/main merge, no promotion and no alteration of original 63/120/12/64/16 native study archives.**
