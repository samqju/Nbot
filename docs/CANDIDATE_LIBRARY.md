# The 24-candidate paper learner

See also [the shadow simulation guide](SHADOW_TRADING.md): up to ten additional, separate simulated positions; the main account still permits only one position.

For the planned 4 CPU / 8-12 GB Learning VPS, use the **standard** resource
profile. The bot now checks 24 named trade candidates in learned mainnet-paper
mode. A candidate is a rule describing an opportunity, not a promise of profit.

## In simple English

1. Collect completed market candles and train the existing price model.
2. Check which of the 24 rules match each coin and direction.
3. Score the opportunity with the existing model. Adjust its ranking using
   completed paper trades previously assigned to that particular rule.
4. Recommend just one opportunity. Trading still permits at most one open position
   and applies the existing risk, entry, stop and exit rules.
5. Save the chosen rule, all overlapping matches for that coin/direction,
   candle-history digest, library digest, model and original prediction.
6. When that paper trade closes, teach only the chosen rule from its result.
   Ten matching rules do not turn one winning trade into ten wins.

There is one shared base prediction model plus separate rule/context feedback
weights. These are NOT 24 separately trained neural networks. No language-model
API, extra package, GPU or new exchange request is needed by the candidate layer.

The existing five-label research model is preserved. The expanded selection and
actual-paper-result feedback apply ONLY to learned mainnet-paper. Testnet and
real-money selection do not automatically inherit an unvalidated experiment.

## Candidate catalogue

Both LONG and SHORT directions are supported. A SHORT rule uses the corresponding
opposite direction. These exact intraday settings are experimental.

| Candidate | Family | Evidence | Rule |
|---|---|---|---|
| TREND_CONTINUATION_V1 | MOMENTUM | FAMILY_RESEARCH | Existing aligned 4h/15m trend proxy. |
| TREND_PULLBACK_V1 | PULLBACK | EXPERIMENTAL | Existing 15m pullback against a 4h trend. |
| STRETCHED_REVERSAL_V1 | REVERSAL | EXPERIMENTAL | Existing recovery after an ATR-normalised opposing move. |
| VOLATILITY_EXPANSION_V1 | BREAKOUT | EXPERIMENTAL | Existing large-range candle moving in the trade direction. |
| RELATIVE_STRENGTH_V1 | RELATIVE_MOMENTUM | FAMILY_RESEARCH | Existing side-aligned cross-sectional strength. |
| DONCHIAN_BREAKOUT_V1 | BREAKOUT | FAMILY_RESEARCH | Close crosses the previous 20-bar high/low. |
| BREAKOUT_RETEST_V1 | BREAKOUT | EXPERIMENTAL | Previous candle broke a 20-bar level; current wick retests within 0.25 ATR and closes beyond it. |
| FAILED_BREAKOUT_V1 | REVERSAL | EXPERIMENTAL | Wick sweeps the opposite 20-bar extreme but the close returns inside. |
| RANGE_EDGE_REJECTION_V1 | MEAN_REVERSION | EXPERIMENTAL | Quiet trend; reject outer 10% of a 20-bar range back through its outer 20%. |
| BOLLINGER_REENTRY_V1 | MEAN_REVERSION | EXPERIMENTAL | Close returns inside the prior 20-close mean +/- 2 population standard deviations. |
| RSI_RECLAIM_V1 | MEAN_REVERSION | EXPERIMENTAL | Simple 14-change RSI crosses back above 30/below 70. |
| EMA_CROSS_V1 | MOMENTUM | FAMILY_RESEARCH | 8 EMA crosses 21 EMA on completed closes. |
| EMA_PULLBACK_V1 | PULLBACK | EXPERIMENTAL | 8/21 EMA trend; candle touches the 8 EMA and closes back in trend direction. |
| MACD_CROSS_V1 | MOMENTUM | EXPERIMENTAL | 12/26 EMA MACD crosses its 9 EMA signal. |
| SQUEEZE_BREAKOUT_V1 | BREAKOUT | EXPERIMENTAL | Previous 10-close deviation below half its prior 30-close deviation, followed by a 10-bar breakout. |
| VOLUME_BREAKOUT_V1 | BREAKOUT | EXPERIMENTAL | 20-bar breakout with base volume above twice the prior 20-bar median. |
| VWAP_RECLAIM_V1 | MEAN_REVERSION | EXPERIMENTAL | Close crosses a fixed prior 20-bar volume-weighted typical price. |
| INSIDE_BAR_BREAKOUT_V1 | BREAKOUT | EXPERIMENTAL | Previous candle lies strictly inside its mother candle; close breaks the mother's range. |
| OUTSIDE_BAR_REVERSAL_V1 | REVERSAL | EXPERIMENTAL | Current candle expands both extremes, then closes beyond the previous close in the opposite candle direction. |
| ENGULFING_REVERSAL_V1 | REVERSAL | EXPERIMENTAL | Opposing previous body is strictly engulfed in the trade direction. |
| PIN_BAR_REJECTION_V1 | REVERSAL | EXPERIMENTAL | Rejection wick >=60% of range, body <=30%, close in directional outer 25%. |
| MULTITIMEFRAME_TREND_V1 | MOMENTUM | EXPERIMENTAL | 8/21 five-minute EMA and 3/6 fully closed UTC-aligned 15-minute averages agree. |
| CONFIRMED_SWING_CONTINUATION_V1 | STRUCTURE | EXPERIMENTAL | Two confirmed two-left/two-right swing lows rise (highs fall); price breaks the previous candle in trend direction. |
| BTC_RELATIVE_MOMENTUM_V1 | RELATIVE_MOMENTUM | EXPERIMENTAL | Coin's 1h return beats side-aligned BTC by >0.5 ATR, with agreeing 15m move. |

The first five retain the existing classifier's precedence: it emits at most one
of those five labels for a coin/direction. The other 19 can overlap it and each
other. If no named rule matches, the existing base model can still suggest a
MODEL_ONLY opportunity; it is reported separately, not counted as a 25th strategy.

## What the indicators actually use

- Only completed five-minute candles at or before the decision event.
- At least 49 contiguous candles for the 19 new technical rules, up to 96.
  A gap clears the preceding history; insufficient history produces no new
  technical match. Existing base-feature freshness/history checks still apply.
- ATR is the mean of 14 true ranges. RSI uses 14 simple price changes, not Wilder
  smoothing. EMA starts at the first close in this bounded window.
- Bollinger re-entry uses the prior 20 closes and population standard deviation.
  VWAP here means a rolling prior-20-bar, base-volume-weighted typical price,
  not an exchange session VWAP or an order-book execution estimate.
- Fifteen-minute confirmation uses only complete UTC-aligned groups of three
  five-minute candles. Swing pivots require two already-closed candles on each
  side. Neither rule peeks at future candles.
- BTC relative momentum uses the existing side-aligned coin and BTC features.
  Missing BTC return data disables this rule; it is not treated as a zero return.
- Exact formulas live in nbot/observation/candidate_setups.py. Changing definitions
  requires a new library/rule version, not silently reusing past results.

A matching rule does not bypass a negative base score, stale data, missing model,
disabled entries, position limits or any Execution refusal.

## How learning works, and its limits

For each selected candidate, results are grouped by market context and LONG/SHORT.
The learner uses that group when sufficiently supported, otherwise that candidate's
broader same-direction group. It does not borrow an unrelated candidate's wins.
Outcome factors range from 0.25 to 1.5. Downranking needs four time buckets,
three effective buckets and a negative result beyond a caution margin; upweighting
also needs eight buckets. Otherwise the outcome factor stays 1.0. Main paper
outcomes have weight 1 and shadow outcomes together have weight 0.25 per group/time
bucket. Entry-practicality penalties and repeated-loss pauses are separate.

Among overlapping rules with exactly equal scores, a deterministic event-specific
tie breaker spreads attribution. Restarting the same event gives the same choice.
This is not a balanced allocation or a guarantee that every rule will get trades.

Only completed main paper positions and valid completed shadow fills receive their respective profit/loss labels. Unsimulated rules
have unknown execution results. Selection bias remains: these records do not
prove how each candidate would have performed on every opportunity. There is no
parallel baseline account or automatic statistical proof of a winning strategy.

More rules divide the available evidence. With one open position, 30 days may
leave many candidates untested or inconclusive. Trying many rules also increases
the chance of finding an apparent winner by luck. Do not choose a profitable
row after the fact and call that proof. Keep the release fixed, review later
forward results, costs, drawdowns and different market periods.

Paper fees are included; funding and realistic fill/liquidity effects remain
limitations. No candidate is guaranteed profitable or automatically approved
for real-money trading.

## Published research versus experimental rules

Research motivates some broad families. It does not validate this bot, its
five-minute thresholds, particular coins, fees or future returns.

- [Liu and Tsyvinski: Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877):
  cryptocurrency return characteristics, including time-series momentum.
- [Liu, Tsyvinski and Wu: Common Risk Factors in Cryptocurrency](https://www.nber.org/papers/w25882):
  cryptocurrency cross-sectional factors, including momentum.
- [Corbet and colleagues: The effectiveness of technical trading rules in cryptocurrency markets](https://www.sciencedirect.com/science/article/pii/S1544612319300315):
  moving-average and trading-range rule families in Bitcoin.
- [Lo, Mamaysky and Wang: Foundations of Technical Analysis](https://www.nber.org/papers/w7613):
  systematic pattern-recognition methodology, not proof for these crypto rules.

FAMILY_RESEARCH in the catalogue means related published research, not approval
of our exact rule. EXPERIMENTAL means a testable hypothesis. Names such as
engulfing or pin bar should not be mistaken for established profitability.

## Set up the larger Learning VPS

Follow the [two-VPS beginner guide](TWO_VPS_BEGINNER_GUIDE.md) to create Ubuntu,
install Python and this repository, create private configuration, connect the
two servers and verify SSH fingerprints. Use the same Git commit on BOTH servers;
an older Trading release will fail the release handshake.

When installing Learning services, choose standard instead of tiny:

~~~bash
cd "$HOME/Nbot"
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user ubuntu \
  --resource-profile standard
~~~

Then follow the [three-mode guide](TRADING_MODES.md) to configure learned paper
control and the [30-day experiment guide](PAPER_AUTO_LEARNING.md) to start and
inspect mainnet-paper. The command above installs service definitions; it does
not enable entries or start a new experiment by itself.

Standard defaults collect up to 200 symbols with bounded fetch concurrency.
Binance request limits still apply. Start with one collector and one research
timer, not duplicate workers. Monitor disk space, collection delay and completed
research epochs; 4 CPUs do not mean every Python task uses four CPUs.

For an EXISTING tiny installation, first use the beginner guide's stopped
upgrade/backup procedure. Re-rendering with standard replaces the installer-added
tiny limits in base units. Custom systemd drop-ins or environment files can still
override them: inspect with systemctl cat before restarting. Keep the learned
paper selection override. Never delete private configuration to change profile.

## Read the results

On Learning:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py paper-learning-report --output logs/paper-learning-report.md
cat logs/paper-learning-report.md
~~~

The candidate table lists all 24 plus MODEL_ONLY, with completed trade counts and
paper profit/loss. Zero trades means no evidence, not a losing strategy. The
weight table gives context-specific support; its context and ALL rows overlap,
so do not add their trade counts together.

The report records completed trades, not a count of every detected signal.
Overlapping matches for the selected opportunity are kept in the durable proposal.
Unselected opportunities do not become main-account wins/losses. The separate
[shadow simulator](SHADOW_TRADING.md) can track up to ten additional opportunities
without adding those outcomes to main-account feedback.

Candidate evidence, snapshots and decisions survive ordinary restarts. Upgrading
the Git release starts a new experiment cohort; old records remain stored.
Back up the Learning databases and Trading history outside the VPS. GitHub stores
the code and documentation, not your private learning memory.

## Engineering checks

Synthetic fixtures cover all 24 rule identities, LONG/SHORT technical matches,
flat markets, missing history, invalid candles, causal history bounds, unconfirmed
swings, deterministic tie attribution, one frozen proposal and selected-rule-only
feedback. These verify program behavior, not market profitability.

On 2026-10-03, the expanded full regression run passed 1,162 tests. A subsequent
missing-BTC-data guard and metadata validation were verified with 56 focused
candidate, feedback and recommendation tests. These checks use synthetic data.
