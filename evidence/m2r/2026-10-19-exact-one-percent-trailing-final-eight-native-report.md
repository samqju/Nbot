# NBOT V6 — Final Exact 1%-Activation Trailing Stop Research

**Owner request:** Test a final tight trailing policy historically: at +1% favorable movement, lock 0% gross (entry); +2% => lock +1%; +3% => lock +2%; original initial stop −2%, native +5% ROI, no 60-minute forced exit, then **stop tuning trailing stops if results remain poor and shift to entry-quality AI**.

**Completed:** 19 October 2026, **14:39:56 UTC / 20:09:56 IST**. All **8/8 official native Freqtrade backtests completed successfully**, the isolated research systemd unit `nbot-v6-exact-one-trail-20261019.service` finished `inactive / Result=success / ExecMainStatus=0`, no running research Docker. SHA-256 independent verification of **16 native Freqtrade archives** (8 exact-new + 8 original-control) passed. Everything is offline-only, original 63/120/12/64/16 prior studies preserved, no trading or activation.

## What changed, precisely

- Frozen technical signals from the original eight entry strategies, unchanged.
- Frozen 25 Binance USDT perpetuals, original 5-minute candles and existing funding/mark history. **NOT** the proposed M5A rotating 25-of-N coin list and **NOT** any trained 25×8 entry-quality AI.
- Each native strategy runs its **own** $1,000 1× position in a **single global slot** with simulated starting wallet $100,000, same original protections and **native fee 0.05% each side**. No aggregation of the eight standalone portfolios into one deployable portfolio.
- Frozen initial stop **−2%**, Freqtrade native take-profit **+5%**, no forced 60-minute custom exit, same uninterrupted **2026-07-01 to 2026-10-01** backtest range.
- **Original baseline:** built-in Freqtrade trailing activates after **+2% gross favorable movement**; then a native 1% trailing distance *relative to highest price*. 
- **New exact policy:** implemented as `use_custom_stoploss=True` with built-in `trailing_stop=False` to avoid conflicts. Calculate gross favorable entry-relative movement `P = (current_favorable_rate/open_rate−1)` for LONG, `P = (1−current_favorable_rate/open_rate)` for SHORT. If P below 1%, retain initial −2%. If P ≥1%, protective stop locks `P−1 percentage points` **of entry price**. Examples: +1% → entry 0%; +2% → gross +1%; +3% → gross +2%; +4% → gross +3%. Actual Freqtrade `stoploss_from_absolute` converts the stop to a price-relative stop, supports shorts and the engine retains monotonic tightening. This changes **both activation timing and the exact trailing distance geometry** (entry-relative 1pp rather than multiplicative 1% of current price), which cannot be causally separated by this single A/B experiment.
- The engine necessarily force-closes each portfolio's last open trade at end of historical October 1 data; each side had one such force exit. Native 5m backtests approximate fills and intra-candle order; neither an exact 0% gross stop level nor its modeled fill guarantees break-even after trading fees, adverse gaps and slippage.
- Hypothetical **additional 0.25% per completed trade** cost stress on top of actual native fees, using recorded native stake/turnover, is an explicit stress *assumption*, not actual historical bid-ask spread. Results below are after **native fees + this extra stress**.

## Full official Freqtrade results (uninterrupted July–September 2026)

Each row compares two distinct independently backtested **single-family, single-position** portfolios. P&L is USDT, no combination of eight family results into one account.

| Strategy family | Original +2% activation +1% trail (stressed) | NEW exact +1% activation, 1pp trail (stressed) | Change using new rule | New trades |
|---|---:|---:|---:|---:|
| EMA Cross | −346.96 | **−764.23** | −417.28 | 172 |
| Donchian Breakout | −189.60 | **−956.12** | −766.51 | 157 |
| Bollinger Reversion | −424.55 | **−669.04** | −244.48 | 141 |
| RSI Reversion | −64.26 | **−799.60** | −735.34 | 249 |
| MACD Momentum | −477.08 | **−709.36** | −232.28 | 150 |
| Stochastic Reversal | −613.84 | **−1,090.34** | −476.51 | 161 |
| ATR Breakout | −526.61 | **−884.41** | −357.81 | 213 |
| Volume Trend | −175.40 | **−828.15** | −652.75 | 189 |

**Verdict: 8/8 were WORSE than the original trailing rule after costs. 0/8 new strategies positive after native Freqtrade fees even BEFORE the extra 25bp stress, and 0/8 positive after stress.** The old policy itself also has 0/8 positive under extra stress; any slight native positive old-family P&L should not be treated as a robust edge.

## Why it worsened

- Across eight **separate** full-quarter portfolios, previous +2%-activation rule had **954 trades** and **463 trailing-stop exits**; new +1%-activation rule had **1,432 trades** and **947 trailing-stop exits**. These sums are descriptive; they do **not** represent a combined eight-strategy executable portfolio.
- Tightening the trail caused many positions to close earlier, opening the only simulated slot for **more entry signals**, and increasing total modeled trading cost. An earlier protective stop can capture small gains or fee-negative break-evens while truncating longer winner paths. This does **not** prove every individual early trailing exit lost money: changing exit times also changes subsequent entries and trades, and the new rule changes the exact stop geometry.
- EMA Cross native result under the new rule: **172 trades**, **98 winning native exits**, **119 trailing exits**, **52 initial stop exits**, **1 end-data forced exit**, **−335.14 USDT after native fees**, **−764.23 USDT stressed**. Prior original EMA trailing: 121 trades, 65 winners, **−45.28 USDT native**, **−346.96 stressed**. Increasing the count and the nominal winning fraction did not create positive net value.
- Each original entry strategy already showed weaknesses under fixed and trailing variants. Neither a stricter time limit nor no time limit nor hard −1% stop nor this new earlier trailing activation demonstrated a robust positive after-cost edge. Thus **entry selection quality and payoff asymmetry, not another trailing percentage sweep, are the next research priority**.
- These July–September dates have been repeatedly inspected; they are not an untouched OOS confirmation of a future trading rule. Do not assert that +2% is universally optimal; it is only the **less-bad original reference among these two tested settings**, not an approved trading configuration.

## Exact code, reproducibility and hashes

- [Owner's exact stop formula / eight strategy subclasses](../../user_data/strategies/NbotV6ExactOneTrailResearch.py).
- [Isolated eight-job owner-opt-in native batch coordinator](../../scripts/m2r_v6_exact_one_trail_batch.py); source commit used for jobs `e2fd86e5dccead880fdc4ff1025710aca40f7437`.
- [Native code formula and fail-closed unit tests](../../tests/test_m2r_v6_exact_one_trail.py), [batch safety checks](../../tests/test_m2r_v6_exact_one_trail_batch.py).
- [Independent **16 official native ZIP SHA256/ledger/fee/ROI/stop/25-coin/one-position audit**](../../scripts/m2r_v6_exact_one_trail_final_audit.py). **Successfully executed on VPS** after all results saved; verifies every individual strategy trade ledger and cost stress. [GitHub CI for source change](https://github.com/samqju/Nbot/actions/runs/39269837607) passed.
- Evidence written **only** to `/root/nbot-v6-m1-20261016/exact-one-trailing-20261019/`, including status, events, final-comparison, per-family native ZIP and native-audit JSON. Original results remain separately at `/root/nbot-v6-m1-20261016/no-time-exit-20261019/`.
- Backtesting engine from logs: official Freqtrade **2026.9**; `Strategy using use_custom_stoploss: True`, `trailing_stop: False`, `stoploss: -0.02`, `minimal_roi: {'0': 0.05}`, native 0.05% each-side fee, max one open trade. No research API keys, all jobs strictly Docker offline backtest.

Read-only VPS reproduction:

```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_exact_one_trail_batch.py --status
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_exact_one_trail_final_audit.py
systemctl show nbot-v6-exact-one-trail-20261019.service -p ActiveState -p Result -p ExecMainStatus
```

## Owner-approved next decision: FREEZE exit-rule experimentation

As explicitly requested, **DO NOT propose, grid-search, or activate another trailing-stop variant** after this clearly negative final A/B. Retain frozen historical baseline **+2% activation / 1% conventional gap, original −2% stop and +5% ROI, no universal forced 60-minute deadline** as a **research reference only**, NOT a paper/live trading choice. Other exit policies may be reconsidered only if new entry-quality evidence gives a prespecified scientific reason and owner approves.

**Next and only new research priority:** design/test the causally sound **exit-matched entry-quality AI** to choose a *model-ready* universe market, family, direction and prespecified frozen exit, based on **expected net USDT after fees/funding/spread/slippage and opportunity cost**; verify against simple non-ML baselines, NO TRADE, and the original fixed25 / dynamic M5A universe research. Use honest chronological / purged training splits and genuinely fresh held-out market data; compare **actual native Freqtrade one-slot 25-pair aftercost portfolio results**, not first-touch hypothetical +2/+3% labels or isolated strategy monthly sums. No threshold changes solely to force historical profits.

**No new AI training programme has been started by this report.** Original 63/120/12/64/16 research remains archived, M5A public eight-hour shadow timer remains observation-only, PR #50 stays draft/unmerged, Nbot V5 untouched, paper/live OFF.
