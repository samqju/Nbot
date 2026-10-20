# V7 — 15-hour real-time PUBLIC price observation, FreqAI RAW virtual study

**Authorized October 20, 2026 (IST). Status: STARTED on isolated 8GB Observation VPS, no exchange account, no API credentials, no real or exchange dry-run orders.**

Owner asked: “run it on live data instead of historic data ... virtual trade ... three coins ... No of trades 0 to 3 ... Raw daily training model ... Train ... Last 15 days historic data, using 1 minute candles ... even 15 second candles ... run experiment on VPS and leave it, we will check after 12–15 hours.”

## Protocol frozen before viewing future trades

- **Inputs:** BTCUSDT, ETHUSDT, SOLUSDT USD-M futures **1-minute public OHLCV klines**. Use Binance Vision daily `/data/futures/um/daily/klines/{symbol}/1m/` ZIPs for the 16 complete historical days preceding start. Verify original Binance-published SHA256 .CHECKSUM for every ZIP. Top-up the current incomplete day from public `GET https://fapi.binance.com/fapi/v1/klines`. During the experiment poll 1m public REST every ~12 seconds, **wait at least 90 seconds after every candle closes** before accepting it, and enter only at the first later complete minute OPEN (three 1m candles after the signal candle's OPEN). This prevents a known Binance REST provisional candle revision causing hindsight or false source data. Reject gaps, source rewrites, time skew, stale data and partial bars; no private endpoint.
- **Why 1m, not 15 seconds:** Binance native 1m klines are well specified; 15s would require resampling 1s trades and more complex sequencing/gap verification. 1m gives 5× granularity vs existing 5m research while keeping data causal. 15-second was optional, not tested or claimed.
- **AI:** Installed official FreqAI 2026.9 **LightGBMRegressor.fit() invoked by V7 custom isolated research harness**, fresh initial fit and fresh model after next UTC calendar date begins. It is **NOT full FreqAI native scheduler** and **not the saved old 5m weight file**. One-minute 17-dimensional causal price/volume/BTC-context, symbol and LONG/SHORT features based on each completed 1m candle. Targets are hypothetical 60m net PnL for **both LONG/SHORT on each of the fixed 3 coins**, only from last 15 days of matured historical one-minute price sequences, sampled every 5 minutes to reduce overlapping examples; fitted label future path ends before model cutoff. The new 1m generic directional proposal differs from the earlier 20-strategy-family 5m architecture. This difference MUST be disclosed in comparison.
- **RAW decision:** Every completed common 1m timestamp, score eligible LONG/SHORT for BTC/ETH/SOL and propose only the highest predicted after-fee/slippage return if **strictly positive**. **No uncertainty filter**, no forced trades, no veto/promotion based on earlier 2026 outcomes.
- **Hard trade limit:** **0–3 total** new virtual entries across the full 15-hour experiment, not three forced fills, and at most one position per coin. All entries are paper ledger objects only, at the third 1m bar **OPEN** after the decision candle (allowing the 90s source finality delay), never at retrospective closed-bar prices. Previous decision must be available before entry. 1000 USDT notional per position, $10,000 initial hypothetical wallet. Stop 2%, target 3%, max duration 60m, stop-first if bar touches both. Fee 0.05% and slippage 0.01% **per side** are modeled. **Funding is NOT modeled** in this short diagnostic; quote every PnL as *without funding* rather than complete net after all costs. Execution is coarse OHLC proxy, not exchange bid/ask or mark-triggered stops.
- **Stop/end:** Run **15 hours** from service start. Disallow new trades in the final 72 minutes, so existing trades should mature normally within 60 minutes. If source/model errors persist, **fail closed** and preserve old records; no backfilled favorable virtual decisions, no fabricated terminal fill. Service has `RuntimeMaxSec=16h` watchdog and is **not enabled at reboot**. Max 3 virtual entries regardless of model predictions, then continue observation without taking more trades.
- **Capture:** Immutable evidence root `/opt/nbot-v7-20261020/runs/live-1m-15days-20261020-v2/`, SQLite append-only events `virtual_1m.sqlite`, checked source ZIPs, local joblib model and sha256 manifest, and `status.json` updated periodically. Event types `MODEL_FITTED`, `RAW_DECISION` (all ranked candidate scores/rejections), `VIRTUAL_OPEN`, `VIRTUAL_CLOSE`, `FAIL_CLOSED_SOURCE`, `RESEARCH_END`. Status includes virtual trade count, positions, realized PnL, credentials unused flag and public source timestamp.
- **Failure/caveats:** Historical data for initial 15-day training can still be overfit. Three or fewer live trades in 15h provide almost NO robust estimate of prediction skill. This experiment only tests whether the model can follow actual emerging prices without hindsight, not whether it is profitable. A 2%-stop PnL without historical/public funding and live spread depth is not fully realized futures PnL. No promise any trade will occur. **LEARN-3C HOLD** and no live/paper exchange activation, no broader coin universe, no model promotion.

## Actual running VPS deployment checkpoint

- Source [research/v7_live_1m_virtual_15day.py](research/v7_live_1m_virtual_15day.py), first commit `d3de309058f9235deb8804e4a8cf137ae6e443e8`, safe source restart correction `c3a50d2f814138059e78cda14d58aea36ffa6eb0`.
- [Separate, not enabled systemd unit](research/nbot-v7-live-1m-virtual-20261020-v2.service), commit `e889ab572bec7793c5ef59a36699c754ee405847`. Unit name `nbot-v7-live-1m-virtual-20261020.service`. It invokes bootstrap in `ExecStartPre`, then the daemon with `--serve --hours 15`. Systemd `NoNewPrivileges`, `ProtectSystem=strict`, restricted `ReadWritePaths` to isolated study output, no Binance private network/API or trading service code.
- **VPS confirmed ACTIVE RUNNING** as of 2026-10-20 12:29 UTC, PID 20839, public data source bootstrap completed with 16 days ×3 = **48 Binance Vision ZIPs**, FreqAI first head trained. Model hash `0fc7556cec7487bf11c2e2205c187bbc5fd6f4a33686d1db267db0c2510f9870`; cutoff 1792499220000; **8,616 labeled examples per coin** (25,848 pooled coin+side rows), all matured before cutoff.
- Run launch timestamp recorded in `status.json`: start `2026-10-20T12:14:25.617099Z` (source bootstrap), actual service study `2026-10-20T12:29:07.110Z`. Experiment ends `2026-10-21T03:29:07.110Z` (**08:59:07 IST Oct 21**). Service watchdog maximum 16h after 12:18:54 UTC. After 12–15h owner can check audit, no need ChatGPT to run background work.
- Initial corrected-run check 12:29:35 UTC: status RUNNING, 0 virtual trades, model fit today, 0 orders, no exchange credentials, simulated equity 10000 USDT. **These are initial values only; they are not 15-hour results.**
- Tests [research/test_v7_live_1m_virtual.py](research/test_v7_live_1m_virtual.py), **7/7 PASS** in FreqAI venv, confirming public 1m, three-coin scope, max-three trades, causal feature warmup, source-conflict rejection, no order methods. Regression full V7/legacy pass to be appended after running.

### Check next morning

VPS commands (via existing authorized PuTTY `8GB-Observation`):
```bash
systemctl status --no-pager nbot-v7-live-1m-virtual-20261020.service
cat /opt/nbot-v7-20261020/runs/live-1m-15days-20261020-v2/status.json
journalctl -u nbot-v7-live-1m-virtual-20261020.service --since "2026-10-20 12:18 UTC" --no-pager | tail -n 80
```

Read-only SQLite evidence should be analyzed for all decision-time ranks, signal correctness, actual subsequent candle paths, per-trade MAE/MFE, number of virtual trades, stop/target/hourly exits, source continuity and fee/slippage/funding limitation. Do not claim successful predictive skill from a handful of trades.

**No automated future ChatGPT follow-up has been scheduled**. The service is an explicitly started VPS systemd process that continues independently of this conversation. If systemd is not active or record status is SOURCE_HALTED, report that honestly rather than inventing virtual trades.

## Engineering incident and corrected live observer

The first isolated prototype **v1** initially fitted a valid FreqAI model and started public-feed observation but Binance later **revised a recently closed ETHUSDT 1-minute candle**, causing `PUBLIC_SOURCE_CANDLE_REWRITE_CONFLICT`. Its safety latch logged eight faults and stopped at 2026-10-20 12:21:47 UTC, without any virtual trades or orders. A read-only source diagnostic reproduced a close revision `2390.45 → 2390.44`, volume `2089.923 → 2113.692`, open timestamp 1792498740000. v1 output is retained untouched under `runs/live-1m-15days-20261020-v1` as negative source-incident evidence.

This does **not** justify silently rewriting observed after-the-fact prices. Version **v2** starts a separately source-verified study with **90-second post-close candle finality delay**, and target training labels also use **the matching entry at the third candle after decision-candle open**. This prevents a model trained with immediate next-open fills from being misrepresented as an execution model that must wait for reliable market data. V2 unit [source](research/nbot-v7-live-1m-virtual-20261020-v2.service), creation commit `19661887da895abca990632449df189d8cfe21b6`; updated source commit `622e657548317a8406d4335ec1bab065d6311cc9`.

Service-start first attempt for v2 failed safely with systemd `226/NAMESPACE`, as `ReadWritePaths` requires the isolated run directory to exist **before systemd creates the restricted mount namespace**. Created only the fresh v2 run root, then restarted the v2 unit. **V2 bootstrap PASS**, **V2 FreqAI fit PASS**, **V2 systemd ACTIVE RUNNING** as of 2026-10-20 12:29:35 UTC; separate process PID 20839, initial model SHA256 `0fc7556cec7487bf11c2e2205c187bbc5fd6f4a33686d1db267db0c2510f9870`, 25,848 source-matured simulated examples, 0 virtual trades, zero account keys/orders. End scheduled 2026-10-21 03:29:07 UTC.

The service is designed to remain running on the VPS without a ChatGPT session. It is deliberately NOT enabled to start automatically after a reboot (fail closed, no unexpected new run). Errors are recorded and terminate the service rather than pretending stale input is live. User must return to inspect the actual source logs and result; there is no guarantee any virtual trade occurs.


## 2026-10-20 14:03 UTC — All three live virtual positions CLOSED; independent audit PASSED

**Checkpoint, not the scheduled 15h end:** User reports all three positions closed. Read-only VPS check at 14:01–14:03 UTC verified service `nbot-v7-live-1m-virtual-20261020-v2.service` **ACTIVE**, market data and raw decisions still updated, 3/3 virtual entries used, 3/3 virtual closes, 0 positions open and **0 Binance orders/credentials**. No extra virtual entry can occur after cap reached. `status.json` still says `RUNNING` because observation continues until Oct21 03:29 UTC; do NOT conflate 3 closed trades with observation service completion.

| Coin | Side | Virtual entry price | Virtual exit price | Exit reason | Duration | Net after modeled fees/slip, funding EXCLUDED |
|---|---|---:|---:|---|---:|---:|
| ETHUSDT | SHORT | 2390.440932 | 2385.078484 | HORIZON | 60m | **+1.2444098711 USDT** |
| SOLUSDT | SHORT | 104.379561 | 104.560455 | HORIZON | 60m | **−2.7339069571 USDT** |
| BTCUSDT | SHORT | 81654.433740 | 81614.560640 | HORIZON | 60m | **−0.5114406564 USDT** |
| **TOTAL** | | | | all 3 timed | | **−2.0009377425 USDT** |

Starting research sleeve was 10000 virtual USDT; hypothetical realized wallet now **9997.9990622575 USDT** (shown as 9997.9991 in status). All three triggered exactly the 60-minute time cutoff, not stops or profit targets. The direction of entry-to-exit price change (including paper slippage) was favorable for ETH SHORT +0.22433%, BTC SHORT +0.04883%, but adverse for SOL SHORT −0.17330%. After per-side proxy fees and 0.01% slippage per side BTC's favorable price change was insufficient to cover costs; it lost −0.51144 USDT. **Directional correctness by terminal price 2/3, economic profitability 1/3**. This is only a three-trade diagnostic, not evidence of a transferable edge or a statistical win rate.

**AI raw selected aftercost forecasts versus reality (basis points of $1000 notional):**
- ETH predicted **+3.1077bp**, realized **+12.4441bp**.
- SOL predicted **+0.7119bp**, realized **−27.3391bp**.
- BTC predicted **+4.5429bp**, realized **−5.1144bp**.
- Aggregate aftercost net **−2.0009377425**; the simulated broker includes *fee+slippage*, but NOT real Binance order book fills or funding charges. All three trade forecast signs were positive before selection.

**Independent source-level verification:** Added [research/v7_live_1m_three_trade_audit.py](research/v7_live_1m_three_trade_audit.py) and executed on the VPS, status **`EXACT_THREE_PUBLIC_1M_VIRTUAL_TRADES_CLOSED_INDEPENDENT_REPLAY_PASS`**. Auditor reads only archived run SQLite and recomputes each of the three actual trade paths from contiguous recorded public 1m bars with the original `PaperBroker` and unchanged `RiskPolicy`; **exact matches for model identity, entry-price/slippage, stop, target, exit minute and HORIZON reason, fees, exit-price and aftercost PnL**. Events show 1 MODEL_FITTED, 94 RAW_DECISION at audit timestamp, 3 VIRTUAL_OPEN, 3 VIRTUAL_CLOSE, 0 FAIL_CLOSED_SOURCE in corrected v2. Audited receipt stored `/opt/nbot-v7-20261020/runs/live-1m-15days-20261020-v2/three_closures_audit_20261020.json`. Research v1 provisional-candle source-error evidence is preserved separately; v2 is clean.

**Scientific conclusion:** All three live entries being closed is a *valid program execution result*, not a clean test of AI predictive skill. Three examples are far too few; fitting only last 15d, no funding/real fills, 90-second feed finality delay and lookahead-safe third-candle entry, and different 1m generic model vs old 5m 20-family models prevent broad inference. Keep **LEARN-3C HOLD**. Do not promote or authorize exchange trading. After the planned observation expires, check source health and final data integrity separately.
