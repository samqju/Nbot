# NBOT V5 G3 — BTC Regime / Coin Structure Frozen Feature Contract
**Contract:** NBOT_V5_G3_BTC_COIN_CONTEXT_V1  
**Date:** 2026-10-14 IST  
**Repository:** samqju/Nbot  
**Development branch:** feature/v5-observation-g3-20261014  
**Base branch:** feature/v5-observation-g2-20261014, frozen G2 acceptance reference af6d5a458eeca047c43d0360ce6a8fd3f76ec799.  
**Status:** G3 source-verified, offline feature RESEARCH ONLY. No model, profit, trade, paper book or order authority.

## 1. Branch and deployment isolation (mandatory)

| Branch or directory | Role | Mutation rules |
|---|---|---|
| GitHub `v5-clean-restart-20261013` | Authoritative roadmap v2.8.4 at G3 start and already-running G1f Observation collector code | Roadmap evidence only; do not merge G3 code or restart live observer to claim automatic production qualification |
| GitHub `feature/v5-observation-g2-20261014` | Archived accepted two-live-event G2 source witness/provenance tools | G3 starts from its verified commit, not by editing G2 or Execution |
| GitHub `feature/v5-observation-g3-20261014` | G3 BTC/market structure hypothesis contract, synthetic tests and source-qualified replay | G3 changes only, no dependency on Execution code; merge/diff review before eventual use |
| GitHub `feature/v5-execution-foundation-20261014` | Independent synthetic/paper Execution design | NOT a parent or dependency of G3; remains untouched |
| GitHub `feature/v5-live-evidence-recovery` | Historical separately developed prototype | NOT a parent of this clean-restart G3 branch |
| VPS `/home/ubuntu/nbot_v5_sandbox` | Active original G1f permanent collector | Do not restart, edit code or switch branch for G3 experiments |
| VPS `/home/ubuntu/nbot_v5_g3_audit_dev` | Separate detached G3 development worktree | Read-only access to frozen qualified G2 proof below |
| VPS `/home/ubuntu/nbot_v5_g2_proof_20261014/g2_witnessed.sqlite` | Frozen real, privately stored qualified G2 cohort and two 5m event records | Read-only from G3; original integrity and SHA preserved |

The code entry point for this stage is `nbot.v5.g3_market_context.classify_event`, with separate independently read-only `nbot.v5.g3_frozen_replay`.

## 2. Exact time and feature sources

- One independent original G2-qualified, frozen top-50 USDT-perpetual cohort (BTC **is counted inside** the 50).
- 96 consecutive, independently archived and SHA256-verified, already-CLOSED Binance five-minute OHLCV bars ending at the selected event_open_ms. No incomplete candle, missing interval, future bar, record after the original commit, or source no longer available at frozen clock is accepted. The data are not true independent completed Binance 1h or 4h candles: those horizons are **past-only 12-bar and 48-bar five-minute return rollups** anchored to the last 5m close.
- Each coin must have its contemporaneous original G2 per-coin public feed observation: source receipt clock for quote and trade, original sampled_at_ms between event close and original decision commit, current market+public feed connected, generation IDs positive, bid/ask noncrossed, spread no more than 1%, quote received within 5 seconds, trade received within 15 seconds of original *sampling clock*. These are LOCAL WSS evidence witnesses, not exchange-signed quote authenticity or executable spreads. Delayed 3-stage REST candle finality cannot retroactively improve an earlier trade/quote sample.
- G3 features are valid FROM original event `committed_ms` only and never earlier. Each output includes version, event, commit timestamp, frozen selected-set digest, per-coin/overall availability, typed reasons and SHA256 content digest, `order_authority=NONE`.

## 3. Frozen quantitative features (hypotheses, NOT evidence of edge)

Features per valid selected coin from its last 96 closed five-minute candles:

| ID | Definition | Availability |
|---|---|---|
| return_5m | Last close / previous five-minute close minus 1 | 2 closed bars |
| return_15m | Last close / close three bars earlier minus 1 | 4 closed bars |
| return_1h | Last close / close twelve five-minute bars earlier minus 1 | 13 closed bars |
| return_4h | Last close / close forty-eight five-minute bars earlier minus 1 | 49 closed bars |
| atr14_fraction | Mean of 14 consecutive true ranges, divided by last close | 15 closed bars, positive finite ATR |
| sma12_fraction / sma48_fraction | SMA12 / SMA48 of already-closed bar closes divided by last close minus 1 | 48 closed bars |
| range12_fraction / range48_fraction | High-low envelope for trailing 12 / 48 closed bars, normalized by last close | All constituent bars required |
| BTC-relative-momentum_1h | Coin one-hour rollup minus BTC one-hour rollup | BTC and coin source both independently qualified |
| altcoin breadth_1h | Number of valid positive altcoin returns minus valid negative returns, divided by number of valid altcoins (BTC excluded) | At least max(8, ceil(80% of selected altcoin count)) clean altcoin sources and valid BTC |
| delayed swing high/low | Pivot higher/lower than two predecessor AND **two successor bars already closed by event time**, with actual original pivot open_ms | Never recognize unconfirmed pivot from the last two bars |

A direction-specific BTC-relative setup is **MATCH** for LONG when (coin_1h − BTC_1h) greater than max(0.001, 0.25*BTC_ATR_fraction); **MATCH** for SHORT when below minus that threshold. Otherwise **NO_MATCH** if both sources valid, **UNAVAILABLE** if either missing/stale. The value is never filled with fabricated zero. This repairs the earlier conceptual unreachable BTC-relative feature without modifying V4.

## 4. Predeclared BTC regime and coin structure taxonomy

BTC regimes (mutually exclusive):

- `UNKNOWN`: BTC source missing, stale, disconnected, invalid timestamp, inadequate/invalid price history or zero ATR; zero confidence and all conditioned coin results withheld
- `SHOCK_UP` / `SHOCK_DOWN`: latest 5m move magnitude >= max(0.75%, 2.0*ATR14 fraction), signed by the actual latest move (prioritized above slow trend)
- `TREND_UP` / `TREND_DOWN`: one-hour and four-hour rollup trends agree, exceed fixed cutoffs (1h: max(0.25%,0.65 ATR), 4h: max(0.50%,1.20 ATR)), and trailing SMA12-versus-SMA48 ordering confirms direction
- `RANGE`: neither one-hour nor four-hour return exceeds its corresponding directional threshold
- `TRANSITION`: contradictory horizons, insufficient trend confirmation or intermediate movement; never invent stable trend

Coin structures (mutually exclusive, with BTC and 80% breadth gates already passed):

- `BREAKOUT_UP` / `BREAKOUT_DOWN`: latest close crosses above/below a historical **confirmed** pivot that was already validated by its two later completed five-minute bars; latest previous close was still on the other side
- `COMPRESSION`: last-12-bar range below max(0.4%, 55% of last-48-bar range)
- `TREND_UP` / `TREND_DOWN`: one-hour and four-hour coin returns agree and exceed above directional cutoffs
- `RANGE`: both horizons below those cutoffs
- `TRANSITION`: all other valid directional conflicts
- `UNKNOWN`: source/BTC/breadth not valid

Confidence scores (0.0–1.0) are **rule-based feature availability/strength indicators, NOT empirical probabilities, forecasts, trade success rates or calibrated model scores**. No classifier outcome authorizes actual execution, selection or training.

## 5. Source-validity / uncertainty acceptance matrix

| Scenario | Mandatory behaviour | Automated evidence |
|---|---|---|
| BTC missing, gapped, zero ATR, stale quote/trade or unavailable WSS epoch | BTC regime UNKNOWN, per-coin conditioned result UNKNOWN, BTC-relative pattern UNAVAILABLE, no zero-filled momentum | Synthetic unit tests |
| Individual coin unavailable but BTC and >=80% market breadth remain qualified | That coin UNKNOWN and others still available; full original top-50 denominator retained | Individual stale/invalid quote/epoch tests |
| Too many altcoin sources missing | Breadth UNKNOWN; all strategy-conditioned coin structure withheld | Minimum cross-section test |
| Quote crossed, >1% spread or trade/quote receipt after sample | Coin UNKNOWN; no fabricated bid/ask eligibility | Quote spread and future/stale clock tests |
| Future/unclosed, noncontiguous, malformed, infinite or incomplete 96-bar history | Coin UNKNOWN, withheld indicator; source replay may HOLD overall for corrupted original SHA/receipt | Synthetic causal and original SHA tamper tests |
| BTC 5m upward or downward shock | SHOCK_UP / SHOCK_DOWN, not ordinary trend | Positive and negative shock fixtures |
| BTC persistent trend, flat/range or conflicting rollups | TREND_UP, TREND_DOWN, RANGE, TRANSITION or UNKNOWN by frozen formula only | Deterministic trend/range fixtures |
| Coin new pivot in last two completed bars | No accepted swing until two future-neighbor bars **have closed** | Delayed-swing fixture |
| Valid coin stronger/weaker than BTC | Long/short BTC-relative pattern MATCH reachable, neutral otherwise NO_MATCH, missing UNAVAILABLE | Positive and missing-BTC tests |
| Valid source captured later than original commit or signature/hash altered | Independent G3 original-source audit **HOLD** | G3 frozen replay tamper/clock tests |
| Any historic G1f record without immutable G2 original selection/quotes | G3 replay **HOLD**, not backfilled from current exchange state | Frozen G2 prerequisite in G3 replay |
| Entire accepted event at frozen clocks | Deterministic feature SHA repeated exactly, 50 coin records, correct selected-set denominator and no order authority | Real source-qualified G2 evidence replay and full test suite |

## 6. Current acceptance and critical limitations

G3 engineering satisfies original V5-03's source-clock, BTC availability, deterministic regime, delayed-pivot and positive/missing fixtures on a **bounded two-window real cohort**. The independently preserved G2 proof has two genuine complete five-minute events at **2026-10-14 05:45:00 and 05:50:00 UTC**, each recording 50/50 valid coins and complete source evidence. Both were replayed from a dedicated separate worktree without network, data writes or running service change. Frozen source coverage at two real points **does NOT prove** robustness across rare shocks/regimes, future generalization, predictive accuracy, liquidity execution, net expectancy, or 24h persistent ingestion. Shock and data-loss cases are synthetic tests for fail-closed correctness, not market-edge validation.

No G3 data should be treated as a matured virtual outcome or economic label; training remains disabled until G4/G5. G3 is purely the BTC/coin *context classifier* that a later rigorously evaluated model or abstaining selector might consult. The temporary G2 witness was stopped cleanly, not deployed as the permanent collector; qualified future data require a separately reviewable/restorable operational rollout.

**Original G3 exit:** causal reproducibility at frozen clocks, BTC stale/absent yields unknown, source-path availability tested and regime labels deterministic. All four criteria have deterministic tests and independently qualified live replay. No later roadmap gate is implicitly satisfied.
