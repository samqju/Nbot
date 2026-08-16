# Phase 7.5D.2B.3 — Liquidity-Conditioned Cross-Sectional Momentum Signal

## Scope

B.3 introduces only the signal-reproduction boundary for the first externally
documented benchmark family. It does **not** create NBOT candidates or virtual
trades yet.

The frozen reference rules are:

- 14-day cumulative return;
- 14-day Amihud illiquidity = mean(abs(daily return) / daily traded value);
- upper 30% by momentum = winners;
- lower 30% by Amihud illiquidity = liquid;
- research signal = intersection of liquid and winners;
- first benchmark direction = LONG only;
- minimum listing/history age = 26 weeks;
- stablecoins excluded.

## NBOT adaptation boundary

This is not claimed as an exact replication of Begušić & Kostanjčar (2019).

The paper used daily cryptocurrency price, volume and market-cap data and a
market-cap inclusion rule. NBOT uses its point-in-time Binance USDT perpetual
research universe and Binance futures quote volume. The 26-week history rule,
14-day momentum/illiquidity formation period and 30/40/30 cross-sectional
sorting logic are retained.

## Safety

B.3 signal-only code:

- writes nothing;
- does not instantiate StrategyCandidate;
- does not enroll a virtual trade;
- does not change the legacy candidate generator;
- does not change RULE_SYSTEM_V1;
- does not train or activate a model;
- has no paper or real-order authority;
- does not modify Execution.

After the signal calculation is proven live, a later phase will define a
separate research outcome/holding protocol before these signals are permitted
to generate virtual evidence.
