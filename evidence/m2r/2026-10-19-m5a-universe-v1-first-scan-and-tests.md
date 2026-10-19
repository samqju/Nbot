# NBOT V6 — M5A Universe Selector V1: Code, Public Binance Snapshot and Validation

**Date:** 19 October 2026. **Classification:** working **offline/shadow research prototype**, **not** a trained economic universe selector, a live FreqAI pairlist manager or a trading system. The initial public snapshot was fetched directly from Binance futures public REST on the owner's research VPS at **06:22:13 UTC**. Original Nbot V5, original V6 63/120/12/64/16 studies and active 25 watchlist remain unchanged. No paper/live trading, no keys, no orders, no automatic model promotion and no main merge.

## Delivered code on the V6 branch

- [m5a_universe_selector.py](../../scripts/m5a_universe_selector.py): deterministic, source-timestamp-aware 25-of-N screening and score; **UTC 00:00/08:00/16:00 schedule boundaries**, up to three-minute public snapshot capture, exactly 25 unique candidates, BTC and open-position pins, **0–10 rotations per review**, at least 15 original incumbents retained, mandatory replacement of unsafe incumbent only if **verified, unprotected, model-ready** substitute exists; HOLD on unsafe protected pairs or inadequate ready markets. Material-score improvement **≥0.15**, minimum verified incumbent tenure **24 hours**; absent tenure means **no discretionary rotations**. Never changes any FreqAI pairlist.
- [m5a_snapshot_binance.py](../../scripts/m5a_snapshot_binance.py): sequential, bounded **public GET-only** `exchangeInfo`, `ticker/24hr`, `ticker/bookTicker`, `premiumIndex`, timestamped as actually observed. No API keys, authentication, order endpoints, candlestick downloads or VPS live mode. Snapshot outside 00/08/16 review start is a **diagnostic** rather than backdated to a fake earlier review.
- [m5a_shadow_comparison.py](../../scripts/m5a_shadow_comparison.py): a read-only comparison of quality eligibility for 25 fixed pairs vs the *public-quality* top 25 for one genuine market observation. Scores **do not** estimate profitable expected trade returns.
- [m5a_shadow_cycle.py](../../scripts/m5a_shadow_cycle.py): one-shot review, immutable files, fail-closed **HOLD without independent as-of history/model validation receipt**; does not touch a running FreqAI process.
- [m5a_shadow_replay.py](../../scripts/m5a_shadow_replay.py): strictly chronological 8h **shadow-only**, deterministic separate fixed25/liquidity25/quality25 replay over future genuine point-in-time observations and verification receipts, with full churn, quality and hold metrics, and no trading P&L claims.
- Optional [systemd one-shot](../../deploy/nbot-v6-m5a-shadow.service) and [8-hour UTC timer](../../deploy/nbot-v6-m5a-shadow.timer) definitions in GitHub. **Installed and enabled 2026-10-19 at 12:55 UTC** after a VPS relay reconnection. See the later actual VPS follow-up below; the initial record described the earlier state before installation. Avoid claiming the timer is running.
- [Fail-closed unit tests](../../tests/test_m5a_universe_selector.py), [as-of replay and 300-cycle synthetic randomized stress](../../tests/test_m5a_shadow_replay.py) and [shadow-cycle contract tests](../../tests/test_m5a_shadow_cycle.py). CI also exercises the existing Nbot V6 tests and official Freqtrade strategy discovery. All coded selectors are inert without actual model readiness and operator-approved safe restart.

### Initial public market-quality filter

The *research-only* thresholds for the first screen (not optimized for ROI): USDT-settled/quoted trading PERPETUAL with ≥45d verified listing age, ≥20 million USDT 24h turnover, best visible bid/ask level ≥1,000 USDT **on each side**, quoted spread ≤20 bps, absolute reported recent funding rate ≤0.15% and 24h high/low range 0.6–30%. Quality score uses 40% normalized traded liquidity, 25% narrow spread, 15% best-level depth, 10% moderate range, 10% low funding; separately transparent liquidity-only score. Every input must be timestamped, finite and from the current public market observation. **24h ticker turnover is not executable trading depth; one best level is not the whole order book; funding-rate snapshots are not long-term funding cost forecasts**. Prices, spreads and order sizes can change immediately.

### Actual Binance public snapshot measured on VPS — 2026-10-19 06:22 UTC

- **878** USDT-suffixed exchange contract records examined.
- **30** satisfied all these preliminary public-market-quality filters. This is not **30 models ready**: the number of new certified candidate models is **zero**, and the screenshot was outside the exact 8h review window.
- Original hard-coded 25: only **16** passed this strict *instantaneous* market quality screen. **9** incumbent markets failed one or more exploratory gates: ATOM, BCH, DOT, ETC, HBAR, INJ, OP, SUI, UNI (USDT perpetual form). Insufficient 24h volume flagged ATOM and ETC; limited instant best-level quoted depth flagged most others. This does **not** mean these coins are permanently untradeable or poorly performing; book quotes move quickly.
- Preliminary top-25 public market-quality shortlist contained **10 markets absent from the original 25**: 1000PEPE, ENA, HYPE, ONDO, PAXG, PUMP, TRUMP, WLD, XAUT, ZEC (USDT-M perpetual symbols). **These are NOT trading recommendations** and do not have approved Nbot AI models. Newly seen assets require history/data/contract/model/validation preflight; no coin was activated.
- Top 25 by observed market quality was different from the old 25, but **no after-cost trade P&L was calculated or implied**. The quality mean over only the 16 eligible old pairs is not directly comparable with the quality mean of a full 25 selected list; avoid denominator selection bias.
- Full public snapshot was written only to the VPS under `/root/nbot-v6-m1-20261016/m5a-shadow-20261019/public-20261019-initial.json`. No private API keys or order request were used.

## Engineering experiment: seven synthetic eight-hour reviews (NOT market performance)

CI [run 39211348540](https://github.com/samqju/Nbot/actions/runs/39211348540) executed a reproducible **seven-review synthetic quality experiment**, with 25 deliberately low-quality incumbent fixtures and 25 deliberately better candidates, all given made-up *valid* historical/readiness records so the rotation algorithm could actually be stress-tested. A 300-review randomized hostile-input test also completed successfully. This does **not** mean current Binance markets have similar future quality or profitability.

| Shadow policy | Total virtual replacements over 7 reviews | Reviews with changes | Mean eligible public-quality score |
|---|---:|---:|---:|
| Fixed original 25 | 0 | 0 | 0.375160 |
| Liquidity-selected 25 | 24 | 3 | 0.872885 |
| Multi-factor quality-selected 25 | 24 | 3 | 0.872885 |

These results demonstrate only that the code rotates *boundedly* and improves its **own predetermined synthetic screen score** when higher-scored candidates are provided; the multi-factor and liquidity policies agreed because the fixture's high-quality coins had both better liquidity and better multi-factor values. It is **not** evidence of economic superiority between selector designs, strategy entry quality or trading P&L. BTC remained pinned, no review rotated more than ten coins, and original FreqAI configuration was never changed.

## Actual VPS follow-up — 2026-10-19 12:54–12:55 UTC

The owner requested that the M5A program be **run on the VPS and the result compared**. Using the owner's authorized PuTTY relay, we fast-forwarded the clean isolated `global-next-source` checkout from `c8e2728` to `88f5719`, reran **30 M5A unit tests successfully**, checked Python compilation, and took a **second actual public Binance screen at 12:54:27 UTC** (6:24 PM IST) against 878 USDT-suffixed contract records. Both 06:22 and 12:54 scans found only **16 of the original 25** passed their **instantaneous** public-quality filters, but that count obscures changing eligibility:

- **Regained screen eligibility between the two snapshots:** BCHUSDT, DOTUSDT, SUIUSDT, UNIUSDT (four original incumbent coins).
- **Lost screen eligibility:** APTUSDT, ARBUSDT, FILUSDT, XLMUSDT (four original incumbent coins).
- **Remained ineligible at both snapshots:** ATOMUSDT, ETCUSDT, HBARUSDT, INJUSDT, OPUSDT (five originals).
- Morning reasons mostly included instantaneous bid/ask first-level depth; afternoon list had several different bid/ask first-level deficits. These are **not** confirmed historical cost/fill measurements and are an explicit demonstration why one observation cannot justify churning the coin universe.

The second observation and comparison were preserved in:

```text
/root/nbot-v6-m1-20261016/m5a-shadow-20261019/public-20261019-second.json
/root/nbot-v6-m1-20261016/m5a-shadow-20261019/second-summary.json
/root/nbot-v6-m1-20261016/m5a-shadow-20261019/second-vs-old25.json
```

**Enabled and tested an actual public snapshot-only systemd scheduler on the VPS:**

- Installed exact read-only `deploy/nbot-v6-m5a-shadow.service` and eight-hour `deploy/nbot-v6-m5a-shadow.timer` definitions; `systemd-analyze verify` succeeded; timer `ActiveState=active`, `enabled`; next automatic run **2026-10-19 16:00 UTC** (9:30 PM IST) as reported by `systemctl list-timers`.
- Manually ran the **oneshot** `nbot-v6-m5a-shadow.service` at 12:55:40 UTC. It completed `Result=success, ExecMainStatus=0`, captured **878** current public contracts and wrote timestamped snapshot and decision under `/root/nbot-v6-m1-20261016/m5a-shadow-20261019/reviews/20261019T125543_426000Z/`.
- The manual run returned **`DIAGNOSTIC_ONLY_OUTSIDE_REVIEW_WINDOW`**, proposed **zero replacements**, confirmed current watchlist unchanged, and no paper/live action. That is the **correct fail-closed result** when time is not near an 8-hour boundary and readiness attestations are absent. The installed timer only gathers public shadow evidence; it **cannot** activate coins or place orders. No async ChatGPT monitoring is claimed.
- The next scheduled 16:00 UTC event was **not yet observed as successful in this session**. Do not claim it already ran. Check `journalctl -u nbot-v6-m5a-shadow.service -n 50 --no-pager` after its trigger.

This follow-up **shows a genuine difference in public-market screening candidates**, not a difference in economic trading performance. No extra historical as-of coin universe and model history has been certified, and no native dynamic-universe portfolio A/B can currently make an unbiased profit claim. The existing original 25 native archives and V5/main were not changed.

**Useful VPS commands:**

```bash
systemctl status nbot-v6-m5a-shadow.timer --no-pager
systemctl list-timers nbot-v6-m5a-shadow.timer --no-pager
journalctl -u nbot-v6-m5a-shadow.service -n 50 --no-pager
find /root/nbot-v6-m1-20261016/m5a-shadow-20261019/reviews -maxdepth 2 -type f
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m5a_shadow_comparison.py --snapshot /root/nbot-v6-m1-20261016/m5a-shadow-20261019/public-20261019-second.json
```

## Test scope and scientific limits

The latest completed GitHub CI for this implementation confirmed **181 total repository unit tests**, including new M5A invariant/stale-market/unsafe-incumbent/atomic HOLD cases plus a randomized 300-cycle **synthetic** timeline and 7-review shadow comparison. These synthetic replays verify logic and low churn; they **are not economic performance measurements**. [GitHub V6 CI](https://github.com/samqju/Nbot/actions/runs/39211120234) completed successfully including official Freqtrade strategy discovery. Subsequent minor reporting changes have their own CI.

**Major missing proof (not hidden):** The VPS Freqtrade 5m/1h/funding/mark history remains the original **25 pairs** only; the one current market snapshot cannot be retroactively treated as historical 8h market data. A credible **point-in-time dynamic 25-of-N** July–September/October future dataset with historical listings, delistings, spreads, order-book depth, funding, full 5m/1h history and fresh per-pair models is not present. **No audited dynamic-universe native one-slot Freqtrade economic A/B has been run.** This project is NOT yet ready to replace the fixed 25 or claim the Universe Selector discovered alpha.

**Next specific steps:**
1. When the authorized VPS relay is reachable, install the isolated optional UTC 00/08/16 **public shadow capture only**, without modifying any existing strategy or enabling orders, to obtain genuine prospective point-in-time snapshots; retain stable version/SHA and uptime logs.
2. Build independently verified per-pair 5m/1h/BTC/mark/funding, matured-label and model prediction-readiness proof for proposed new coins; until that exists every dynamic candidate remains non-tradeable. No fabricated TRUE flags.
3. Construct valid historical eligible market universe *as of each review instant*, including first listing/delisting, avoiding current market symbol survival assumptions, and rigorously document unobservable historic spreads. If historical order-book snapshots unavailable, start with shadow-evaluation rather than inventing fills.
4. Evaluate dynamic25 vs original fixed25 vs liquidity25 on the **same predeclared, genuinely later heldout market dates**. Train the new **exit-matched expected net payoff** selector for 25×8×direction×exit and execute a real Freqtrade native one-slot backtest with base cost, stress cost, drawdown, relative metrics and NO TRADE. Do not assert historical profits without that evidence.

## Do not deploy the selector as a dynamic FreqAI pairlist

FreqAI preloads history at startup and [warns against dynamic pairlists adding unseen pairs](https://www.freqtrade.io/en/stable/freqai/). The M5A prototype emits review proposals only; a future independent stage must prepare models and atomically transition versioned Freqtrade config at an approved safe boundary, protecting every existing position and its stop. There is **NO** automated activation or integration with the original global 25×8 LightGBM selector yet.

**Owner-approved task scope** (this session): Design, code, push on V6 research branch, conduct invariant tests, perform public-market read-only observation, and report evidence and blockers. Do not merge PR50 or turn on paper/live trading.
