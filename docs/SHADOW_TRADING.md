# One main position plus ten shadow simulations

Shadow simulation exists alongside learned `live-paper` and learned
`live-trade`; `testnet-trade` has no shadow engine. For current commands for
all three modes, see [ALL_MODES_COMMANDS.md](ALL_MODES_COMMANDS.md).

The main account still allows **one position**. Alongside it, Learning can reserve
up to **10 shadow slots**. A slot is either waiting for its entry candle or holding
a simulated position. There is at most one shadow slot per named candidate.

| Selected main mode | Main account | Shadow accounts |
|---|---|---|
| Learned mainnet-paper | One simulated position | Up to 10 simulated positions |
| Learned mainnet-trading | One real-money position | Up to 10 simulated positions |
| Testnet / mechanical control | Existing behavior | No shadow engine |

Shadows run on the Learning VPS. They cannot place Binance orders, use private
exchange credentials, change the real balance or authorize mainnet trading.
There are no additional exchange requests: they reuse collected LIVE candles.
If no qualifying signals exist, slots stay empty.

## How candidates get slots

The existing base model scores coins and directions. A shadow opportunity needs
a positive score, fresh data, an acceptable spread and a match from the
[24-candidate library](CANDIDATE_LIBRARY.md). MODEL_ONLY is not a shadow candidate.

For each candidate, choose its highest-scored coin/direction. Available slots go
first to candidates with fewer scored completed shadow trades in the current
mode/release. An event-specific deterministic tie breaker avoids permanently
favouring alphabetical names. It is not a guarantee of equal sample counts.

The main recommendation's selected candidate is excluded. A previously served
main recommendation's candidate remains reserved until an outcome or veto is
recorded. This is conservative: a served suggestion is not proof of an entry, so
a missing acknowledgement can reduce shadow activity. More than 1,000 unresolved
main suggestions blocks new shadow allocation with a visible error.

If a candidate already in a shadow slot becomes reserved for the main account,
its shadow is cancelled as MAIN_CANDIDATE_RESERVED. Its unfinished profit/loss is
not counted as a completed result. Reservations are checked on new allocation
events, not through a real-time view of the Trading account.

The 10-slot cap is shared by both mainnet control services and retained positions
from older releases in the SAME Learning database. Do not run separate copies of
the Learning database to multiply the cap. Run only your selected main trading
mode as described in the three-mode guide.

## Entry, stop and cost assumptions

This is a forward candle simulator, not the main paper exchange's tick simulator.

1. Save the decision before any entry price is known.
2. Reserve a pending slot. Entry uses the opening price of the first full
   five-minute interval beginning AFTER the decision time.
3. Apply decision-time half-spread and fixed adverse slippage to that price.
   Reject entry if its adjusted price has drifted too far from the original
   reference (default 0.25%). The actual entry is recorded only after its complete
   candle becomes available.
4. Size at the configured virtual notional and place an initial stop for the
   configured virtual risk.
5. For each later completed candle, check the stop that was active at its start
   FIRST. If both a favorable extreme and that stop occur, the old stop wins.
6. If not stopped, raise the stop using the integer-R staircase:
   +1R peak moves it to entry; +2R locks +1R; +3R locks +2R.
   The new stop applies to the NEXT candle, never retroactively inside the candle.
7. A gap beyond a stop fills at the worse opening price, then adds adverse
   spread/slippage. Entry and exit taker fees reduce simulated profit.

Stops never loosen. The report counts bars where a newly raised stop would also
have been crossed inside the same candle; their exact price order is unknown.
This next-bar approach avoids inventing a favorable intrabar sequence, but it is
not identical to tick-by-tick execution and is not always a worst-case outcome.

Funding, depth, exchange lot-size/minimum-order restrictions, real latency and
changing intrabar spreads are not modelled. Do not treat shadow USD profit as an
exchange-executable promise or directly comparable to differently sized real trades.

A missing candle invalidates that shadow trade as DATA_GAP_UNSCORABLE. It is not
assumed to have survived the gap. Invalid candle/state data produces a visible
shadow error. Stored complete bars can be processed after restart in batches of
at most 96 per position; no historical decisions are invented to fill missed slots.
If a crash occurs after the main decision freezes but before shadow allocation,
that event can have no shadow entries. It is not replayed using hindsight.

## Separate daily accounts

Each candidate/mode/release has its own simulated account, starting at USD 10,000
by default. Entry requires enough simulated balance for its fixed notional.
Closed results update balance and daily realized profit. Other candidates do not
share these balances.

The daily floor follows the existing main-account formula:

- Below +100R daily peak realized profit: allow 95R giveback.
- At or above +100R: allow 3R giveback.
- A result BELOW the floor blocks more entries for that candidate that UTC day.
- Restart preserves the block. The daily counters reset on UTC rollover; the
  cumulative simulated balance does not reset.
- This uses CLOSED results, not floating profit. It is not a guaranteed daily
  minimum profit. These broad defaults are not a recommendation of suitable risk.

There is no forced four-hour exit: a shadow stays open until its stop closes it,
a data gap makes it unscorable, or a main-candidate reservation cancels it.
Ten long-lived positions can therefore fill all slots; the simulator does not
force turnover to manufacture more evidence.

## Enable and configure

Shadows are enabled by default in the learned LIVE controls in this release.
The Learning VPS must actually run the updated code; pushing GitHub alone does
not restart or update either service.

On a fresh Learning VPS, follow the [beginner guide](TWO_VPS_BEGINNER_GUIDE.md),
use the standard profile for 4 CPU / 8-12 GB, and then follow
[mainnet mode setup](TRADING_MODES.md). Both VPSs must use the same Git release.

Before the FIRST start, optional settings go in Learning's private
config/secrets/control-link.env. The installer already loads this file into both
LIVE control services. The [template](../config/examples/control-link.env.example)
includes the defaults. These values affect only shadow simulation:

~~~ini
NBOT_SHADOW_ENABLED=1
NBOT_SHADOW_STARTING_BALANCE_USD=10000
NBOT_SHADOW_RISK_USD=10
NBOT_SHADOW_NOTIONAL_USD=1000
NBOT_SHADOW_SLIPPAGE_PCT=0.02
NBOT_SHADOW_TAKER_FEE_RATE=0.0005
NBOT_SHADOW_MAX_SPREAD_PCT=0.25
NBOT_SHADOW_MAX_REFERENCE_DRIFT_PCT=0.25
NBOT_SHADOW_DAILY_TRIGGER_R=100
NBOT_SHADOW_NORMAL_GIVEBACK_R=95
NBOT_SHADOW_PROFIT_GIVEBACK_R=3
~~~

The fee is a fraction (0.0005 = 0.05% per side); spread/slippage fields are
percentages. Risk must be positive and below notional; notional must not exceed
starting balance. These settings do NOT change the main account's size or fees.

Settings are frozen per Git release and main mode. Changing them after that
experiment starts gives SHADOW_CONFIG_CHANGED_START_NEW_RELEASE_COHORT rather
than silently mixing incompatible results. Choose settings before first start.
Retain them during the experiment; use a reviewed new release for a new cohort.
The enabled switch itself can be changed without changing the frozen settings.

To pause shadows, set NBOT_SHADOW_ENABLED=0 and restart the selected Learning
control service during a maintenance window. The main engine still manages its
own position independently. Shadow states remain stored; while paused they are
not advanced. On re-enable, available bars are processed; missing paths become
unscorable. Do not delete database rows to reset a losing experiment.

For upgrades, use the beginner guide's flat/stopped backup and same-release
update procedure. This feature does not arm mainnet or enable Trading entries.

## Read results

On Learning:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py shadow-report --output logs/shadow-report.md
cat logs/shadow-report.md
~~~

To review an older cohort:

~~~bash
.venv/bin/python nbot_admin.py shadow-report --release-sha YOUR_40_CHARACTER_COMMIT
~~~

The read-only report shows:

- the global pending/open slots, including those from older releases;
- separate results alongside mainnet-paper and mainnet-trading;
- each candidate's scored trade count, after-cost USD result and mean R;
- cancelled/unscorable counts and reasons, plus ambiguous-bar counts;
- per-candidate balance, last recorded UTC day's realized result, floor and halt.

The result table is limited to the latest 10,000 records per mode/release.
Daily account balances cover all persisted results, so they can differ from
that limited table. Active positions are not counted as realized profit.

Main paper results remain in paper-learning-report. Shadow data is stored only
in dedicated shadow_* tables in the LIVE Observation database, never submitted
as an ExecutionOutcome. Eligible shadow records are read separately by paper feedback at reduced weight.

## What these experiments teach us

They collect forward evidence about opportunities the main account could not
take. Valid completed paper shadows now influence the paper ranking layer at
reduced weight. They do not change real-money ranking. Costs, gaps, stop ambiguity
and correlation still limit this evidence; more simulations do not prove improvement.

Ten candidates trading the same rally are correlated, not ten independent proofs.
Compare later periods and adverse conditions; do not select a lucky winner after
the fact. The main account's one-position results remain the realistic account-level
experiment.

## Operations and backups

The control health output includes shadow_enabled and shadow_error. Unexpected
simulation errors are logged as SHADOW_SIMULATION_FAILED,
SHADOW_CANDIDATES_FAILED or SHADOW_HISTORY_FAILED. The simulation boundary catches
them so they cannot make exchange orders or interrupt main position management.
A shared database/disk failure can still affect Learning as a whole.

Check the selected control service's journal:

~~~bash
sudo journalctl -u nbot-observation-live-paper-control.service -n 100 --no-pager
sudo journalctl -u nbot-observation-live-trade-control.service -n 100 --no-pager
~~~

For real mainnet control, substitute nbot-observation-live-trade-control.service.
Never publish logs containing private values. Keep Learning database backups off
the VPS together with research memory and the separate Trading history.
Monitor disk growth and collection delay; this feature needs no extra collector.

Engineering tests cover long/short stops, costs, gap fills, no hindsight entries,
missing data, restart/deduplication, concurrent global limits, candidate fairness,
main-candidate reservations, independent daily floors, configuration integrity,
separate reports and isolation from order transport.

## Release verification

On 2026-10-03 the full Linux regression suite passed 1,189 tests, including
26 shadow-specific tests. Tests use synthetic data and do not establish market
profitability. Publication does not deploy or restart either VPS.

### Restarts, updates and recommendation timing

A service restart retains saved training data and models. For paper and testnet,
an older model can also survive an operational update when Git proves its
training, feature, data-contract, shared utility, configuration and dependency
sources unchanged. Missing Git history, changed training sources or invalid
artifact contracts block reuse. The original model provenance is retained.
Rejected models, corrupt artifacts and models with future/unmature labels remain
blocked. Real-money trials still require an exact-release model. Both VPSs must
still run the same deployed release.

New market events arrive every five minutes. The recommendation supervisor
refreshes every five seconds by default; the execution worker polls every two
seconds while flat and every 0.5 seconds while managing a position, plus request
time. These faster checks do not retrain or create new market events.
Recommendations expire after their existing short freshness window; between
events, waiting for fresh data is expected. No trade is forced each cycle.

The /learning report now includes recommendation readiness and its waiting
reason, compatible-model availability, shadow positions open/pending, completed
and excluded results, and last opportunity/result timestamps in UTC. Counts across
releases show historical activity; net simulated PnL is reported for the current
release only. Cancelled/unscorable results are not counted as completed scored
trades. Valid shadow outcomes now train the paper ranking layer at reduced weight. The main paper
position and its results remain separate (/position, /recent, /pnl).

### Feedback, loss pauses and entry cancellations (October 2026)

The experimental paper ranking layer now uses two labelled evidence sources:
main paper outcomes and valid completed paper-shadow outcomes. It does not
retrain the base research labels or enable real-money trading. Within each
candidate/direction/context and 4-hour-5-minute block, main outcomes contribute
weight 1 and all parallel shadow outcomes together contribute weight 0.25.
This limits, but does not eliminate, correlation. Old shadow records without
saved market context contribute only to the broad candidate/direction group.
New simulations save their decision-time context; no hindsight context is invented.

Feedback from older releases is reused only when Git history proves that the
fill, risk, attribution, shared configuration and outcome contracts match.
Original release IDs and digests remain intact. Shadow cost/risk configuration
and candidate catalog must also match. Missing history, incompatible contracts,
future receipts, invalid records and unknown candidates are excluded.

After three consecutive losing main paper trades in the same coin and direction
within six hours, that coin/direction is paused until one hour after the latest
loss. A different setup label cannot bypass this pause. A non-losing trade breaks
the streak. The pause is rebuilt from durable verified outcomes after restart,
does not close a position, and cannot create another position. Shadow results
do not trigger this main-account loss pause.

Shadow entries still wait for a forward candle and must pass the original price
drift limit. We did not loosen that limit or fabricate missed fills. New results
record entry delay and drift. Cancelled entries do not train the profit model.
After at least eight distinct entry attempts spanning three time blocks,
repeated drift cancellations can reduce that candidate/direction's preference
by up to 30%, as a separate entry-practicality penalty. Missing-data and
main-candidate-reservation cancellations are excluded from that calculation.

Use /learning to see evidence counts, the latest decision time, choices before
and after feedback, outcome and entry-practicality adjustments, and loss pauses.
The database also retains a per-event paper_feedback_checks record, including
no-trade decisions. Comparing two choices is an audit of behaviour, not proof
that the changed choice will be more profitable. Use /pnl and /recent to judge
the main paper account; shadow balances remain separate.
