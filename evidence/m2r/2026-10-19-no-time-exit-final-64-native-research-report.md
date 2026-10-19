# NBOT V6 — Final A/B Report: Remove 60-minute trade exit

**Completed:** 19 October 2026, **05:33:49 UTC (11:03:49 IST)**.  
**Economic decision:** Marked improvement in historical standalone monthly strategy economics and turnover, **but none of the 16 continuous three-month portfolios profitable after hypothetical extra 25bp execution-cost stress**. No live or paper trading, no strategy promotion, no main/V5 merge.

## What exactly was tested?

The user requested: **Remove the forced 60-minute exit**, keep **+5% ROI target**, **−2% initial stop**, and when enabled the *original* **trailing stop activated after +2% and trailing by 1%**. Exactly these two frozen exit variants were compared while retaining the original eight strategy entry signals unchanged.

- Official Freqtrade **2026.9** native backtesting, original 25 Binance USDT perpetual futures pairs, five-minute candles, 1× leverage, 1,000 USDT nominal position, **one open slot globally**, simulated initial wallet 100,000 USDT, original protections and funding, fees set to **0.05% per side**. Results additionally tested with an *unobserved hypothetical* extra **25 basis points per roundtrip**.
- Fixed exit: 5% ROI or −2% protective stop; **no 60-minute `custom_exit`**. Original trailing: same stop/ROI, plus +2% activation / 1% gap; also no 60-minute `custom_exit`.
- Eight technical entry strategies (EMA Cross, Donchian Breakout, Bollinger Reversion, RSI Reversion, MACD Momentum, Stochastic Reversal, ATR Breakout, Volume Trend) × two policies × **July, August, September monthly tests and a continuous July–September test** = **64 new ZIP-archived backtests**. Compared all **48 existing original 60-minute native/trailing July/Aug/Sep ZIPs**.
- Exactly one Freqtrade Docker job at a time, source pinned to clean `0a954bea03e2f65a023d44da00fde7a68df2895b`, original entry `NbotV6LibraryResearch.py` unchanged vs source SHA `aa97a32c9af73ae63503f5dbff63d98a7fe32200`.
- The finite dataset necessarily requires **end-of-period forced closure** for any trade still open: every one of the 48 new monthly simulations had one forced end, while each of the 16 uninterrupted tests had one forced end. Those are simulated data-boundary artifacts **not discretionary time-exit rules**.

## Main A/B — Exactly matched original monthly periods

Amounts are USDT after Freqtrade fees **and additional hypothetical 25bp per roundtrip**. Each row is the arithmetic sum of three **independent monthly single-family** backtests, not a composite executable portfolio.

| Strategy | 60m fixed | No-time fixed | 60m trailing | No-time trailing |
|---|---:|---:|---:|---:|
| EMA Cross | −5,814.72 | **−452.76** | −5,928.88 | **−296.12** |
| Donchian Breakout | −6,643.09 | **+193.27** | −7,452.68 | **−133.03** |
| Bollinger Reversion | −7,017.46 | **−306.14** | −6,951.77 | **−664.54** |
| RSI Reversion | −7,254.23 | **−332.49** | −7,002.59 | **−143.92** |
| MACD Momentum | −7,111.96 | **+462.55** | −7,285.19 | **−484.10** |
| Stochastic Reversal | −8,050.81 | **−192.24** | −8,045.21 | **−376.13** |
| ATR Breakout | −7,355.37 | **−426.85** | −7,551.88 | **−205.34** |
| Volume Trend | −6,793.37 | **+21.92** | −7,469.28 | **−477.06** |

**Result:** 16/16 new matched-month combinations had a better cumulative stressed total than their 60-minute counterparts. **3/16** were positive sums: Donchian fixed, MACD fixed, Volume Trend fixed. **13/16** still lost money on cumulative monthly results. Because a monthly backtest forcibly closes and reinitializes any open position, this apparent profitability must NOT be presented as three months of continuous executable performance.

**Trade frequency impact:** Summing independent family-month trade counts solely as a descriptive metric, fixed exits dropped from **15,982** to **450** trades, and trailing exits from **16,274** to **1,021**. This directly reduces modeled transaction costs and changes the portfolio's opportunity set because its one slot remains occupied much longer. It is not simply the same list of trades with a later exit.

## Critical monthly-boundary control: continuous July–September backtests

Amounts include **native fees + extra hypothetical 25bp stress**. These are independent **uninterrupted July 1–October 1** tests for the new no-time policy; do NOT compare their exact dollar result directly to a sum of three separate original monthly portfolios as if periods were identical.

| Strategy | No-time fixed continuous net | Fixed trades | No-time trailing continuous net | Trailing trades |
|---|---:|---:|---:|---:|
| EMA Cross | −513.12 | 68 | −346.96 | 121 |
| Donchian Breakout | −433.51 | 55 | −189.60 | 131 |
| Bollinger Reversion | −217.48 | 59 | −424.55 | 124 |
| RSI Reversion | −434.90 | 69 | **−64.26** | 121 |
| MACD Momentum | **−39.63** | 52 | −477.08 | 131 |
| Stochastic Reversal | −134.99 | 49 | −613.84 | 108 |
| ATR Breakout | −453.26 | 60 | −526.61 | 107 |
| Volume Trend | −61.24 | 37 | −175.40 | 111 |

**Result:** **0/16 continuous native portfolios survived the additional 25bp roundtrip cost stress profitably**; every policy was negative versus NO TRADE (+0). For example, MACD fixed monthly sum was +462.55, yet uninterrupted fixed July–September was −39.63. Donchian fixed monthly was +193.27, uninterrupted was −433.51. These are genuine differences in trade timing, month-end forced liquidation and consequent one-position-slot opportunity, **not rounding errors**. If reduced execution stress is later justified by actual broker liquidity, the native base-fee results may differ, but don't cherry-pick the observed months to assert edge.

## Why removing 60 minutes changes the economics so strongly

1. Original fixed family/month archives had **15,295/15,982** trades closed by the 60-minute timer (~95.7%); original trailing variants had **15,033/16,274** (~92.4%). Those exits created considerable churn, and many happened with small losses or trading-cost deficits.
2. Native no-time rules give the setup room to move until a +5% ROI, −2% initial stop, or +2%-armed / 1%-gap trailing stop fires; all 64 native ZIPs were verified to contain **no `v6_library_60m_exit` or `global_60m_limit` exit reason**.
3. Longer holding **occupies the single global slot** and therefore blocks many would-be new entries. This can reduce losses but also miss better opportunities. Trade sets are fundamentally different, not mechanically identical.
4. Continuous no-time fixed median holding periods ranged from roughly **8 to 21 hours**, trailing from roughly **4.75 to 8.25 hours**; extreme individual trades lasted many days (EMA trailing one ~27 days). Holding indefinitely is not a free lunch: longer open risk, funding exposure, stale signals, capital lock and adverse fill paths remain.
5. The 5m Freqtrade OHLCV simulator does not prove realistic stop/ROI fill ordering on a candle hitting both thresholds; hypothetical extra cost stress is not observed spread or liquidity. The historical July–September dates were already inspected, not pristine OOS.

## Audit and evidence preservation

- Real native research **64/64 jobs complete**, service `nbot-v6-no-time-exit-20261019.service` **inactive / Result=success**, no running research Docker, output isolated at `/root/nbot-v6-m1-20261016/no-time-exit-20261019`, original 63 first-stage, 120 exit-policy and 12 global-AI studies untouched.
- [Read-only final verifier](../../scripts/m2r_v6_no_time_exit_final_audit.py) was **successfully run on the VPS**, independently checked SHA256 of **all 64 new** official Freqtrade ZIPs and **48 original** ZIPs, reconciliation of P&L versus trade ledger and hypothetical cost stress, original 25-pair/global-one-slot risk envelope, and zero 60m exits.
- [Study coordinator](../../scripts/m2r_v6_no_time_exit_batch.py) additionally checked 1× leverage, 0.05% native fee for every trade, the original research-only configuration, no exchange credentials and no paper/live actions. All actual ZIP evidence and `native-audit.json`s retained unchanged.
- [Frozen protocol and first-run evidence](2026-10-19-no-60-minute-exit-ab-research.md). Official GitHub CI for this set of files [passed](https://github.com/samqju/Nbot/actions/runs/39203918550).

**Read-only PuTTY checks:**

```bash
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_no_time_exit_batch.py --status
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_no_time_exit_final_audit.py
systemctl status nbot-v6-no-time-exit-20261019.service --no-pager
```

## Owner decision and next research

**Yes, removing the 60-minute rule changed simulated behavior dramatically and reduced cumulative losses in every matched monthly configuration.** This is valuable evidence that the prior universal 60-minute deadline was poorly aligned with many strategies.

**No, we cannot claim an autonomously profitable no-time bot**: all 16 uninterrupted 3-month aftercost stressed native results remain negative. The positive independent monthly sums are sensitive to month-boundary position liquidation. A fair next challenger would validate no-time or variable-duration exits versus a full *uninterrupted* 60m original reference on a new untouched date window, with realistic fill stress, Freqtrade native one-slot portfolio economics and an explicit downside/capital-occupation metric. The global 25×8 LightGBM selector made no entries previously; this stage tests standalone exits only, **not a newly trained AI exit-matching model**.

Owner must explicitly approve any future change to base strategy behavior or live/paper operation; default NO TRADE remains a valid outcome. No promotion or merge into V5/main.
