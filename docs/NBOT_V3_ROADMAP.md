# NBOT V3 — Clean Two-VPS Self-Learning Trading System Roadmap

**2026-10-02 mode update:** [The three-mode guide](TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


## Current implementation addendum - 2026-10-01

This roadmap contains the original 2026-08-18 plan, dated acceptance records,
and future goals. Its final "starting status" is the adoption-time snapshot,
not today's runtime status. V1/V2 references remain in Git history and tags;
they are not current deployment instructions. Original reset/delete instructions
describe the one-time V3 rebuild and must not be repeated during upgrades.

The [documentation index](DOCUMENTATION_INDEX.md) summarizes current behavior.
For a new server use the [beginner guide](TWO_VPS_BEGINNER_GUIDE.md), plus the
[1 CPU / 1 GB guide](SMALL_VPS_LEARNER.md); historical root-directory examples
are illustrative, not a requirement to run as root.

The current learned-Testnet implementation is reviewed at `9fff54c`:

- Testnet defaults to an explicitly experimental LIVE-trained model, with
  mechanical canary selection still explicit. This is separate from Research
  Champion authority and does not count as LIVE economic proof.
- The selector is `CONTEXT_CALIBRATED_RIDGE_V1`, with accumulated Ridge training
  plus recent support for five fixed setup proxies and market conditions.
  It is not an unrestricted strategy inventor.
- `V39_CONTEXT_DISJOINT_20_20_V4` evaluates a frozen model on disjoint future
  events after model availability and label maturity. Historical adjacent-event
  windows and old selector names below describe their original versions only.
  New artifacts use `v39:context-v4:`; old evidence is never relabeled.
- A 96-event epoch continues accumulating evidence while a frozen challenger
  waits for evaluation. The 15-minute timer does not retrain every 15 minutes.
- Tiny mode is opt-in: up to 20 coins, two candle workers, four recovery events
  per pass, and installed-service CPU/RAM limits. Capacity still needs testing
  on the actual server.
- Fresh generations cannot recreate the fixed historical V3.9.4 calibration.
  `UNAVAILABLE_HISTORICAL_CALIBRATION` is not a passed research audit.
- Research targets remain simulated four-hour ATR-based R; execution uses its
  own risk and exit lifecycle. Prediction is a ranking proxy, not actual P&L.
- Research promotion, Paper Champion proof and V3.10 real-capital gates remain
  separate. Code/tests/documentation do not close those evidence requirements.

This addendum describes implemented changes; it does not alter frozen promotion
thresholds, rewrite dated test results, or claim deployment on both VPSs.

## Original roadmap and dated phase history

**Version:** 2026-08-18
**Status:** CANONICAL V3 IMPLEMENTATION CONTRACT
**Supersedes:** NBOT V1 implementation roadmap and NBOT V2 rebuild roadmap for all new implementation work
**Starting policy:** clean runtime, clean databases, clean state, one active `main` branch, phase tags as immutable checkpoints
**Build order:** **Execution first -> Observation second -> Research/Learning -> Communication -> Testnet end-to-end -> LIVE+PAPER -> Long-term Paper Champion -> Micro LIVE+TRADE**

\---

# 0\. PURPOSE AND AUTHORITY OF THIS DOCUMENT

This file is the source-of-truth roadmap for NBOT V3.

Its job is to prevent architectural drift while rebuilding NBOT from a clean runtime using the strongest proven ideas from NBOT V1 and NBOT V2.

When this document conflicts with an older roadmap, this document wins unless a later Git-committed V3 roadmap explicitly replaces it.

No phase is complete merely because code exists. V3 uses four separate completion states:

1. **CODE COMPLETE** — implementation exists and automated tests pass.
2. **DEPLOYED** — the intended code is installed on the intended VPS under the intended profile.
3. **OPERATIONALLY PROVEN** — required physical/network/restart/failure tests pass.
4. **ECONOMICALLY PROVEN** — required unseen LIVE/PAPER evidence passes predeclared economic gates.

A phase may be CODE COMPLETE but not DEPLOYED. It may be DEPLOYED but not OPERATIONALLY PROVEN. A system may be operationally perfect but not economically good enough to trade real money.

Those distinctions must never be collapsed.

\---

# 1\. V3 RESET DECISION

V3 deliberately starts fresh.

We are not preserving old runtime databases, state files, logs, locks, pending outcomes, paper accounts, model runtime state, or Testnet sessions as active V3 state.

We are preserving only engineering references:

* NBOT V1 final source snapshot;
* NBOT V2 final source snapshot;
* NBOT V2 final roadmap;
* Git history/tags required to recover those source versions;
* this V3 roadmap.

## 1.1 Reference source snapshots

### NBOT V1 reference

Snapshot used while designing V3:

* file: `nbot\_oldv1\_source.txt`;
* snapshot generated: `2026-08-16T05:04:01Z`;
* branch in snapshot: `phase-7-learning-validation`;
* commit in snapshot: `1816b2fda6a74484836962dc7f60a675f81b7403`;
* exact tag in snapshot: `phase7-5d2b3-cross-sectional-momentum-signal-runtime-validated`.

V1 is primarily the **execution/safety/operations reference** for V3.

### NBOT V2 reference

Snapshot used while designing V3:

* file: `nbot\_v2.8.5\_latestsource.txt`;
* HEAD: `b20795a03112905deba03326efa0d53a09f7a610`;
* tag: `v2.8.5-execution-parity-final`.

V2 is primarily the **unbiased observation/research/evidence reference**, and its V2.8.5 Execution work is also a safety consolidation reference.

## 1.2 Before deleting/rebuilding VPS runtime

The current V2 source must first be pushed to `main` and tagged as the final pre-V3 source checkpoint.

Suggested tag:

`legacy-v2-final-before-v3`

After that:

* remove obsolete long-lived development branches if desired;
* keep `main` as the active V3 branch;
* clean both VPS runtime directories;
* deploy V3 only from committed/tagged source;
* create all V3 databases and state from zero.

The V3 reset is intentional. Old runtime evidence is not silently imported later.

\---

# 2\. V3 MISSION

Build NBOT as a two-VPS, self-improving crypto-futures trading system that:

1. observes a broad liquid market without a legacy trading rule deciding what evidence is allowed into the dataset;
2. records point-in-time market truth before future outcomes are known;
3. derives deterministic, versioned features from that evidence;
4. evaluates multiple entry ideas on the same independent market events;
5. evaluates multiple exit/profit-capture policies on the same entries;
6. learns which available opportunity has the best expected **after-cost** result;
7. evaluates challengers chronologically on unseen data;
8. promotes research authorities only when evidence passes frozen gates;
9. keeps all observation, research, simulation, training and model work physically separate from capital management;
10. allows exactly one capital-bearing position at a time;
11. lets Execution independently reject any recommendation for safety/risk reasons;
12. protects an open position without requiring Observation to be online;
13. reconciles exchange truth safely after crashes/restarts/ambiguous responses;
14. feeds completed execution outcomes back to Observation durably and idempotently;
15. proves operational correctness on Binance Testnet before LIVE-market paper validation;
16. proves economic usefulness on LIVE market + PAPER execution before any real order authority is enabled;
17. introduces real capital only in a tiny, explicitly armed final stage.

The objective is not to make every trade profitable.

The objective is:

> \*\*Select materially better opportunities than weak alternatives, capture favorable movement efficiently, bound losses, survive failures, improve through evidence, and prove that the advantage survives real operating conditions before real capital is exposed.\*\*

\---

# 3\. NON-NEGOTIABLE V3 PRINCIPLES

1. **Capital safety outranks profit.**
2. **Execution owns capital authority.**
3. **Observation owns intelligence but never order authority.**
4. **Exactly one capital-bearing position maximum.**
5. **Execution receives its own market truth directly from Binance.**
6. **Observation receives its own market truth directly from Binance.**
7. **No market-data relay between VPSs.**
8. **No shared mutable runtime files between VPSs.**
9. **Observation cannot place Binance orders.**
10. **Execution cannot train models or scan hundreds of symbols.**
11. **When a position is open, normal trading operation has no Observation dependency.**
12. **When flat and Observation is unavailable, Execution stays flat.**
13. **A proposal is advisory, never an order command.**
14. **Execution recalculates current price, spread, balance, notional and risk locally.**
15. **A stale/duplicate/malformed/wrong-profile proposal cannot execute.**
16. **Ambiguous order responses are recovered by durable identity, not blind retries.**
17. **A filled position must be protected immediately; inability to prove protection is an emergency.**
18. **New stop protection must be verified before old known protection is removed whenever exchange mechanics permit.**
19. **Exchange truth wins over stale local assumptions, but contradictory exchange evidence fails closed.**
20. **Corrupt execution state never silently resets to FLAT.**
21. **Completed outcomes are persisted before network delivery.**
22. **A pending completed outcome must be ACKed before a new trade request is allowed.**
23. **Duplicate outcomes create one durable Observation record.**
24. **Testnet evidence is operational evidence, never profitability evidence.**
25. **LIVE/PAPER evidence is separate from Testnet evidence.**
26. **Research Champion authority is not automatically Execution authority.**
27. **Training uses chronological past only; no future leakage.**
28. **Model/policy definitions are versioned and immutable once evaluated.**
29. **Economic thresholds are frozen before the evaluation window is judged.**
30. **Testnet remains permanently available as the regression laboratory for future safety-sensitive changes.**
31. **Same Git version should be deployable to both VPSs.**
32. **One-command operation must never weaken the underlying worker independence.**

\---

# 4\. TARGET PHYSICAL ARCHITECTURE

```text
                         BINANCE
                    /                \\
                   /                  \\
                  v                    v

       +---------------------+    +---------------------------+
       | EXECUTION VPS       |    | OBSERVATION VPS           |
       |                     |    |                           |
       | Own market feed     |    | Own market feed           |
       | Proposal validation |    | Broad observation         |
       | Risk / sizing       |    | Canonical evidence        |
       | Entry               |    | Features / signals        |
       | Stop protection     |    | Future paths              |
       | Position management |    | Exit-policy lab           |
       | Reconciliation      |    | Selection learning        |
       | Emergency flatten   |    | Champion/challenger       |
       | Execution state     |    | Training/evaluation       |
       | Outcome outbox      |    | Recommendation snapshot   |
       |                     |    | Outcome receiver           |
       | NO research         |    | NO order credentials      |
       | NO training         |    | NO capital authority      |
       +----------+----------+    +-------------+-------------+
                  |                             ^
                  | TradeRequest                |
                  +---------------------------->|
                  |                             |
                  | PROPOSAL / NO\_TRADE /       |
                  | NOT\_READY                   |
                  |<----------------------------+
                  |                             |
                  | ExecutionOutcome            |
                  +---------------------------->|
                  |                             |
                  | ACK                         |
                  |<----------------------------+
```

## 4.1 Flat mode

When Execution is flat:

```text
reconcile
 -> deliver pending outcomes
 -> confirm entry gate/risk health
 -> request recommendation
 -> receive PROPOSAL / NO\_TRADE / NOT\_READY
 -> validate proposal locally
 -> verify current market/account truth
 -> enter only if every gate passes
```

## 4.2 Position-open mode

When a position is open:

```text
Execution Binance feed
 -> open-symbol price
 -> position truth
 -> MAE/MFE
 -> risk-contract check
 -> exit-policy/trailing decision
 -> stop replacement/verification
 -> close/reconciliation
```

No normal Observation request belongs in this path.

## 4.3 After close

```text
close proven
 -> settle local accounting
 -> build deterministic ExecutionOutcome
 -> persist locally
 -> queue durable outcome
 -> deliver to Observation
 -> valid ACK
 -> remove pending copy
 -> only then become eligible for a new TradeRequest
```

\---

# 5\. ONE REPOSITORY, CLEAN ROLE-BASED STRUCTURE

Canonical V3 repository structure:

```text
/root/Nbot/
│
├── nbot/
│   ├── observation/
│   │   ├── observer.py
│   │   ├── evidence.py
│   │   ├── database.py
│   │   ├── features.py
│   │   ├── signals.py
│   │   ├── outcomes.py
│   │   ├── policies.py
│   │   ├── selection.py
│   │   ├── champion.py
│   │   ├── challengers.py
│   │   ├── training.py
│   │   ├── recommendation.py
│   │   └── health.py
│   │
│   ├── execution/
│   │   ├── execution.py
│   │   ├── entry.py
│   │   ├── position.py
│   │   ├── risk.py
│   │   ├── daily.py
│   │   ├── reconciliation.py
│   │   ├── emergency.py
│   │   ├── state.py
│   │   ├── outcomes.py
│   │   └── health.py
│   │
│   ├── exchange/
│   │   ├── contracts.py
│   │   ├── binance\_public.py
│   │   ├── binance\_testnet.py
│   │   ├── binance\_live.py          # enabled only in final real-capital phase
│   │   └── paper.py
│   │
│   ├── communication/
│   │   ├── contracts.py
│   │   ├── validation.py
│   │   ├── client.py
│   │   ├── server.py
│   │   └── auth.py
│   │
│   ├── config/
│   │   ├── loader.py
│   │   ├── profiles.py
│   │   └── validation.py
│   │
│   └── common/
│       ├── ids.py
│       ├── time.py
│       ├── atomic\_io.py
│       └── logging.py
│
├── run\_observation.py
├── run\_execution.py
├── nbot\_admin.py
├── nbotctl
│
├── config/
│   ├── profiles/
│   │   ├── testnet-trade.env
│   │   ├── live-paper.env
│   │   └── live-trade.env
│   ├── examples/
│   │   ├── observation.env.example
│   │   └── execution.env.example
│   └── secrets/                     # ignored by Git, chmod 0600
│       ├── execution-testnet.env
│       ├── execution-live.env
│       └── control-link.env
│
├── data/
│   ├── observation/
│   │   ├── live/
│   │   │   ├── observer.db
│   │   │   └── backups/
│   │   └── testnet/
│   │       ├── observer.db
│   │       └── backups/
│   │
│   └── execution/
│       ├── testnet/
│       │   ├── execution\_state.json
│       │   ├── execution\_history.jsonl
│       │   └── pending\_outcomes/
│       ├── paper/
│       │   ├── account.json
│       │   ├── execution\_state.json
│       │   ├── execution\_history.jsonl
│       │   └── pending\_outcomes/
│       └── real/
│           ├── execution\_state.json
│           ├── execution\_history.jsonl
│           └── pending\_outcomes/
│
├── runtime/
│   ├── observation/
│   │   ├── live/
│   │   └── testnet/
│   └── execution/
│       ├── testnet/
│       │   ├── execution.lock
│       │   └── TESTNET\_TRADING\_ARMED
│       ├── paper/
│       │   └── execution.lock
│       └── real/
│           ├── execution.lock
│           └── LIVE\_TRADING\_ARMED
│
├── logs/
│   ├── observation/
│   │   ├── live/
│   │   └── testnet/
│   └── execution/
│       ├── testnet/
│       ├── paper/
│       └── real/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── execution\_parity/
│   ├── research/
│   ├── communication/
│   └── testnet\_canary/
│
├── deploy/
│   ├── execution/
│   ├── observation/
│   └── systemd/
│
├── docs/
│   ├── NBOT\_V3\_ROADMAP.md
│   ├── EXECUTION\_SAFETY\_CONTRACT.md
│   ├── EVIDENCE\_LINEAGE\_CONTRACT.md
│   ├── PROTOCOL\_CONTRACT.md
│   └── OPERATIONS.md
│
├── .gitignore
├── requirements.txt
└── README.md
```

## 5.1 Runtime files stay inside NBOT but out of Git

V3 intentionally keeps runtime paths understandable and self-contained under the NBOT directory, similar to the useful V1 operating style.

`.gitignore` must exclude at least:

```text
.env
.env.\*
config/secrets/
data/
runtime/
logs/
models/
\*.db
\*.sqlite
\*.sqlite3
\*.db-wal
\*.db-shm
\_\_pycache\_\_/
.venv/
```

Directory templates may be tracked with `.gitkeep` files if useful, but mutable runtime content is never committed.

\---

# 6\. THREE OPERATING PROFILES

V3 does not expose arbitrary unsafe combinations of environment variables as the normal operator interface.

There are three named capital profiles:

1. `testnet-trade`
2. `live-paper`
3. `live-trade`

The profile is validated before either worker starts.

## 6.1 TESTNET\_TRADE

Purpose: permanent operational regression laboratory.

```text
Profile                  TESTNET\_TRADE
Execution market         Binance Futures Testnet
Execution orders         Binance Testnet orders
Capital                   Testnet fake capital
Execution state           data/execution/testnet/
Execution evidence        TESTNET\_OPERATIONAL\_ONLY
Observation proposal env  TESTNET
Observation test DB       data/observation/testnet/observer.db
LIVE research collector   allowed/expected in parallel once deployed
Real Binance writes       IMPOSSIBLE
```

Testnet outcomes may validate mechanics, timing, failure handling and protocol correctness. They cannot promote a LIVE research model or prove profitability.

## 6.2 LIVE\_PAPER

Purpose: real-market operational and economic validation without real orders.

```text
Profile                  LIVE\_PAPER
Execution market         Binance LIVE public market
Execution adapter        Local PaperExchange
Capital                   Local paper account
Execution state           data/execution/paper/
Observation market        Binance LIVE public market
Observation DB            data/observation/live/observer.db
Evidence lineage          LIVE\_PAPER\_OPERATIONAL
Binance private writes    IMPOSSIBLE BY ADAPTER DESIGN
```

The paper adapter must implement the same Execution exchange contract but must have no code path capable of submitting a Binance order.

## 6.3 LIVE\_TRADE

Purpose: real capital only after all earlier gates pass.

```text
Profile                  LIVE\_TRADE
Execution market         Binance LIVE
Execution adapter        BinanceLiveExchange
Capital                   REAL
Execution state           data/execution/real/
Observation market        Binance LIVE public
Observation DB            data/observation/live/observer.db
Evidence lineage          LIVE\_REAL\_CAPITAL
Order writes              YES
Extra arm gate            REQUIRED
```

`LIVE\_TRADE` cannot start merely because the profile exists.

It additionally requires:

`runtime/execution/real/LIVE\_TRADING\_ARMED`

and explicit operator arming through `nbotctl`.

\---

# 7\. ONE-COMMAND OPERATION: `nbotctl`

The operator-facing goal is:

```bash
./nbotctl cluster start testnet-trade
./nbotctl cluster start live-paper
./nbotctl cluster start live-trade
```

## 7.1 Local role identity

Each VPS has one ignored local role file:

Observation VPS:

```text
/root/Nbot/.nbot-role
OBSERVATION
```

Execution VPS:

```text
/root/Nbot/.nbot-role
EXECUTION
```

The same Git commit therefore behaves differently only because the machine role and chosen profile differ.

## 7.2 Local commands

Required commands:

```text
./nbotctl doctor <profile>
./nbotctl start <profile>
./nbotctl stop
./nbotctl restart <profile>
./nbotctl status
./nbotctl logs
./nbotctl arm testnet-trade
./nbotctl disarm testnet-trade
./nbotctl arm live-trade
./nbotctl disarm live-trade
```

## 7.3 Cluster commands

After local commands are proven:

```text
./nbotctl cluster doctor <profile>
./nbotctl cluster start <profile>
./nbotctl cluster stop
./nbotctl cluster status
```

Cluster orchestration may SSH to the other VPS for deployment/start/health verification, but SSH orchestration must never sit inside the open-position management path.

## 7.4 Same-commit enforcement

Before `cluster start` succeeds:

* Observation Git SHA must be known;
* Execution Git SHA must be known;
* required protocol version must match;
* required profile contract must match;
* same release/tag should be required for normal operation.

A mismatch returns FAIL before enabling new entries.

## 7.5 `testnet-trade` parallel LIVE collection

Once Observation V3 exists, `testnet-trade` cluster mode should support the intended V3 workflow:

```text
Observation VPS
   |- LIVE passive research collector -> data/observation/live/observer.db
   `- TESTNET canary observer         -> data/observation/testnet/observer.db

Execution VPS
   `- TESTNET execution              -> data/execution/testnet/
```

This lets clean LIVE evidence accumulate while Testnet operational work is being exercised.

The two Observation instances must use separate DBs, locks, logs, ports, lineage IDs and service identities.

## 7.6 `doctor` must fail closed

`nbotctl doctor` checks at minimum:

* role file;
* profile syntax;
* Git SHA/tag;
* Python environment/dependencies;
* required directories/permissions;
* clock synchronization;
* endpoint pinning;
* credentials appropriate to role/profile;
* absence of forbidden credentials on Observation;
* state-file readability/integrity;
* single-instance lock availability;
* pending outcomes;
* open-position reconciliation readiness;
* Observation/Execution protocol compatibility when connection is enabled;
* arming state;
* disk space;
* database integrity for Observation;
* no wrong-environment database/state path.

Doctor never creates order authority by itself.

\---

# 8\. WHAT V1 CONTAINED AND WHAT V3 MUST INHERIT

V1 is not copied wholesale. It is used as an execution/safety behavior inventory.

## 8.1 V1 Execution architecture worth preserving

The V1 snapshot contains mature execution-side modules including:

* `engine/entry\_lifecycle.py`;
* `engine/position\_lifecycle.py`;
* `engine/reconciliation.py`;
* `engine/daily\_lifecycle.py`;
* `engine/emergency.py`;
* `engine/market\_state.py`;
* `risk/risk.py`;
* `execution/paper\_exchange.py`;
* `execution/testnet\_exchange.py`;
* `execution/live\_exchange.py`;
* `execution/outcome\_builder.py`;
* `execution/outcome\_outbox.py`;
* `execution/outcome\_publisher.py`;
* `state/state.py`;
* communication contracts and clients/servers;
* deployment/systemd/operator tooling.

V3 must reproduce the useful behavior while removing old coupling.

## 8.2 V1 entry protections to reimplement

V3 Execution must implement and test:

### Pre-entry

* entries-enabled gate;
* exactly-one-position guard;
* entry-in-progress guard;
* valid symbol and side;
* fresh current price/quote;
* spread limit;
* available-balance/margin check;
* leverage set/verified;
* local risk plan;
* max notional;
* quantity/price quantization;
* current profile/environment validity.

### Durable order identity

V1 used explicit client order IDs and ambiguous-entry recovery.

V3 must:

* reserve proposal ID durably before order submission;
* persist entry-inflight state before market-order call;
* derive a deterministic/recoverable client order ID;
* never blindly resubmit a market order after an ambiguous response;
* query/recover the same client identity;
* fail closed when exact entry truth cannot be proven.

### Post-fill verification

V1 had post-fill safety boundaries including:

* actual notional verification;
* actual dollar-risk verification;
* entry slippage verification;
* immediate initial stop placement;
* stop verification against exchange truth;
* emergency flatten when the filled position cannot be proven protected.

V3 treats these as mandatory, not optional optimizations.

## 8.3 V1 position-management protections to reimplement

V3 must preserve or improve:

* open-symbol focused position management;
* current price tracking;
* unrealized PnL;
* MAE;
* MFE;
* initial risk contract;
* trailing-stop progression;
* stop identity persistence;
* stop-update verification;
* no silent loosening of protection;
* risk-contract breach detection;
* emergency response when risk truth becomes unsafe;
* close detection;
* local finalization only from sufficient close evidence;
* execution outcome creation.

V1's integer-R staircase behavior is preserved initially as a **control/execution parity policy**, not as a permanent claim that it is the best exit.

## 8.4 V1 reconciliation behavior to reimplement

V3 startup/restart must reconcile before requesting a new trade.

Required behaviors:

* local flat + exchange flat -> safe flat;
* local open + matching exchange open -> recover position;
* recover/verify protective stop;
* unexpected unmanaged exchange position -> fail closed;
* multiple/hedged positions -> fail closed unless a later explicit architecture supports them;
* exchange closed while local says open -> recover close using authoritative history;
* manual/external close detection;
* orphan protective-stop detection/cleanup;
* side/quantity mismatch detection;
* no fabricated zero exit price or zero PnL just to make state convenient;
* exchange realized PnL is authoritative when proven;
* contradictory accounting remains unresolved/fail-closed rather than guessed.

## 8.5 V1 emergency behavior to reimplement

V1's emergency handler attempted an exit and then verified flatness.

V3 must implement:

* bounded emergency-close retries;
* post-attempt exchange position verification;
* explicit `EMERGENCY\_EXIT\_CONFIRMED\_FLAT` state/event equivalent;
* if emergency flatten cannot prove flatness, preserve local open-risk state and raise a critical condition;
* never erase local position state merely because a close request was sent.

## 8.6 V1 daily risk behavior to reimplement

V1 contained a daily lifecycle and dynamic daily loss/profit-giveback logic.

V2.8.5 later made parity defaults explicit.

V3 must support:

* UTC trading-day rollover;
* daily realized PnL;
* daily peak realized PnL;
* daily trade count;
* daily loss floor;
* daily halt;
* profit-giveback protection;
* halt persists through process restart;
* rollover resets daily accounting deterministically;
* values are configurable but defaults are frozen per release.

The old V2.8.5 parity defaults (including the large 100R/95R/3R values) are reference values only; V3 must not silently change them during architecture work. Any later economic change requires a separate reviewed config decision.

## 8.7 V1 Paper Exchange behavior to reimplement

Useful V1 PaperExchange properties:

* local paper account;
* market-tick driven paper fills/position updates;
* spread/slippage modeling;
* leverage/risk compatibility;
* deterministic order identity where useful;
* ambiguous-entry behavior testability;
* initial/trailing stops;
* emergency exit;
* realized PnL;
* restart recovery;
* same general ExchangePort as Testnet/real execution.

V3 PaperExchange becomes the LIVE\_PAPER capital adapter and must contain no Binance order-write method.

## 8.8 V1 durable outcome boundary to reimplement

V1's later split included:

* deterministic `ExecutionOutcome` construction;
* durable outbox;
* publisher;
* ACK-only deletion;
* idempotent Observation receiver;
* duplicate-safe outcome IDs;
* wrong environment/mode rejection.

V3 keeps this architecture from the beginning.

## 8.9 V1 worker-separation tests to retain as V3 invariants

V1 tests explicitly exercised important boundaries such as:

* Execution prepares/reconciles before any flat request;
* open-position startup does not contact Observation;
* pending outcomes are retried before a new request;
* open-position ticks do not request trades or retry outcomes;
* irrelevant symbols are ignored early;
* Observation failure while flat means no trade;
* stale/wrong-environment proposals are rejected;
* Execution imports no strategy/learning/universe stack;
* duplicate outcomes remain idempotent.

Equivalent V3 tests are required.

## 8.10 V1 learning concepts worth retaining later — but not V1 evidence gating

V1 also contained substantial learning infrastructure:

* model registry;
* challenger evaluation;
* time splits;
* training orchestrator;
* automatic promotion/rollback;
* shadow scoring/testing;
* strategy lab;
* evidence ledger;
* paper canary controls;
* operator learning status.

These are useful **operational concepts** for later V3 continuous learning.

However V3 must NOT restore the old pattern where a legacy trading strategy first filters what the bot is allowed to observe/learn from.

V3 will reimplement useful model-registry/challenger/rollback ideas only on top of the unbiased V2-style canonical evidence pipeline.

\---

# 9\. WHAT V2 CONTAINED AND WHAT V3 MUST INHERIT

V2 is the research-first specification for V3.

## 9.1 V2 unbiased evidence foundation

V2's Observation config and collector were deliberately research-only and collected completed 5-minute LIVE Binance USD-M Futures evidence.

V3 must preserve the principles:

* completed 5-minute decision clock initially;
* broad liquid universe, initially around 200 symbols subject to resource/evidence validation;
* point-in-time universe membership;
* point-in-time quote volume;
* point-in-time spread;
* canonical candles;
* market event identity;
* event provenance;
* source capture metadata;
* explicit collection attempts/errors;
* funding-event history;
* auditability;
* backup/checkpoint support;
* clock-skew checks;
* late-context rejection;
* atomic event insertion.

## 9.2 V2 gap-recovery principle

V2 intentionally refused to fabricate historical point-in-time spread/volume context.

V3 must preserve this rule:

* historical candles may be recovered when objectively available;
* recovered context is marked honestly;
* historical live spread/volume is not invented;
* context-incomplete rows are not silently promoted to fully complete research targets.

## 9.3 V2 canonical database model

V2's evidence DB included tables/concepts for:

### Raw evidence

* metadata;
* market events;
* 5m candles;
* market snapshots;
* event provenance;
* universe membership;
* source captures;
* collection attempts;
* funding events;
* funding sync ranges;
* audit runs.

### Derived research

* feature sets;
* canonical features;
* signal sets;
* signal annotations;
* feature builds.

### Future labels

* future path sets;
* future candle cache;
* future paths;
* future path builds;
* future path attempts.

### Exit research

* exit policy labs;
* exit policy sets;
* exit policy results;
* exit policy builds.

### Entry selection

* entry selection labs;
* entry selector sets;
* entry selection examples;
* entry selection builds;
* entry selection predictions;
* prediction builds.

### Champion evaluation

* research champion sets;
* research champion evaluations;
* research champions.

V3 may rename tables/modules, but it must preserve the lineage separations and deterministic rebuild/audit behavior.

## 9.4 V2 canonical features to carry forward

The initial V2 feature set included:

* returns: 5m, 15m, 30m, 1h, 2h, 4h;
* realized volatility: 1h and 4h;
* ATR14 as fraction of price;
* current bar range fraction;
* 24h quote volume;
* spread percentage;
* funding rate;
* minutes to next funding;
* universe selection rank;
* liquidity percentile;
* 1h return percentile;
* 4h return percentile;
* volatility percentile;
* BTC 5m/1h/4h returns;
* breadth positive 5m/1h;
* median market return 5m/1h;
* UTC hour/minute/day-of-week;
* context delay;
* history completeness flags.

V3 must start with at least equivalent information before adding new features.

Feature definitions must be versioned and deterministic.

## 9.5 V2 research signals to carry forward

V2 started with three deliberately transparent signal families:

1. `CSM\_RANK\_1H\_4H\_V1` — cross-sectional momentum/ranking;
2. `TSMOM\_4H\_VOL\_ADJ\_V1` — time-series momentum normalized by volatility;
3. `INTRADAY\_CONDITIONAL\_MOM\_REV\_V1` — conditional intraday momentum/reversion.

V3 should initially reproduce these as **research annotations**, not hard entry gates.

All eligible market examples must remain available even when a signal is inactive/missing.

## 9.6 V2 future-path layer to carry forward

V2's `FUTURE\_PATH\_4H\_V1` evaluated forward horizons:

* 1 bar / 5m;
* 3 bars / 15m;
* 6 bars / 30m;
* 12 bars / 1h;
* 24 bars / 2h;
* 48 bars / 4h.

It included an ATR14-based research risk unit and R barriers:

* 0.5R;
* 1R;
* 2R;
* 3R.

V3 must retain the principle of storing the **path**, not merely final win/loss.

Metrics should include at least:

* forward returns by horizon;
* favorable excursion;
* adverse excursion;
* barrier hits/timing;
* ambiguous same-bar barrier ordering flags;
* future realized volatility;
* funding costs;
* spread/slippage/fee cost evidence;
* gross and after-cost directional results.

The future-label cache must never be usable by decision-time features.

## 9.7 V2 cost model principle

V2 standardized research around explicit costs:

* taker fees;
* spread;
* entry slippage;
* exit slippage;
* funding when applicable.

V3 must retain an explicit versioned cost contract.

Research should optimize after-cost outcomes, not gross fantasy returns.

Operational LIVE/PAPER later compares assumed research costs with observed operating degradation.

## 9.8 V2 exit-policy laboratory to carry forward

V2 compared one control plus seven challengers:

1. `INTEGER\_R\_STEP\_CONTROL`;
2. `CONTINUOUS\_R\_GIVEBACK\_V1`;
3. `ATR\_VOLATILITY\_TRAIL\_V1`;
4. `CHANDELIER\_TRAIL\_V1`;
5. `STRUCTURE\_TRAIL\_V1`;
6. `RUNNER\_POLICY\_V1`;
7. `STAGNATION\_TIME\_EXIT\_V1`;
8. `EXHAUSTION\_TIGHTENING\_V1`.

V3 must preserve the central experimental rule:

> Entry selection and exit management are separate questions and should be evaluated separately on the same underlying evidence.

Initial risk may not be widened by an exit policy.

The policy decision clock must not retroactively use information that occurred later inside the same candle.

Policy metrics should include:

* gross return/R;
* after-cost return/R;
* MFE/MAE;
* winner capture ratio;
* peak favorable R;
* giveback from peak;
* time to MFE;
* holding time;
* post-exit MFE;
* missed extension;
* stop update count;
* stop trace;
* ambiguity flags.

## 9.9 V2 entry-selection lab to carry forward

V2's selection lab deliberately created an example for every eligible symbol/side result under the target policy without signal gating.

Transparent baselines:

1. deterministic random/hash baseline;
2. liquidity baseline;
3. cross-sectional momentum baseline;
4. time-series momentum baseline;
5. intraday conditional baseline.

Learned selector:

`RIDGE\_EXPECTED\_NET\_R\_V1`

Its objective was:

`EXPECTED\_AFTER\_COST\_NET\_R`

and its training rule used only events strictly before the scored event.

V3 must preserve:

* transparent baselines;
* no hidden candidate filtering;
* all eligible alternatives available to the selector;
* strict forward-chained training;
* model standardization fitted only on training history;
* immutable model/definition digest per evaluated version;
* event-level ranking of available opportunities.

Ridge regression remains the first reproducible learned baseline, not the final intelligence ceiling.

## 9.10 V2 Champion evaluation to carry forward

V2's initial evaluator:

`WALK\_FORWARD\_CHAMPION\_V1`

paired:

* candidate selector: `RIDGE\_EXPECTED\_NET\_R\_V1`;
* exit control: `INTEGER\_R\_STEP\_CONTROL`.

Its initial frozen windows used:

* first 20 genuinely forward-scored events for validation;
* next 20 for untouched final test;
* later events excluded from changing the original final-test promotion decision.

It also used:

* 2,000 bootstrap samples;
* 95% confidence;
* cost stress at 1.0x, 1.5x, 2.0x;
* transparent benchmark chosen using validation only;
* regime robustness checks;
* drawdown/date/symbol stability;
* source digests/integrity checks;
* training leakage detection.

A pass created only a **research-only** authority.

V3 must preserve this philosophy. Exact sample thresholds may later be increased deliberately, but they cannot be relaxed after seeing the result.

## 9.11 V2.8.5 execution improvements to carry forward too

Although V1 is the main execution reference, V2.8.5 added/consolidated important safety behavior that V3 must keep:

* single-process Execution lock;
* durable entry-inflight journal;
* persistent processed-proposal reservation;
* restart recovery without duplicate order;
* missing-stop restoration;
* stop-breach settlement grace before emergency action;
* exchange-side close recovery;
* deterministic outcome identity;
* corrupt state fail-closed behavior;
* Testnet arm gate and persistent session entry limits;
* hard-pinned Testnet hosts;
* ambiguous stop recovery by deterministic client algo ID;
* new stop verified before obsolete protection is pruned;
* exchange realized PnL as authoritative where proven;
* no invented PnL when close evidence is incomplete;
* health counters and position-management latency;
* separate Observation/Execution logging;
* role-specific Telegram/operator notifications that never raise into the worker.

\---

# 10\. WHAT V3 MUST NOT IMPORT FROM V1/V2

V3 is a clean architecture, not a merger.

Do NOT port these as architectural dependencies:

1. V1 `TradingEngine` coupling strategy/learning/execution in one process.
2. V1 strategy-first evidence gating as the canonical learning dataset.
3. V1 learning files written directly by Execution position lifecycle.
4. V1 universe/strategy imports inside Execution.
5. V1 automatic learning/promotion code until it is redesigned on V3 canonical evidence.
6. V2 temporary `StaticProposalClient` as the integrated production communication path.
7. V2 Testnet evidence as research profitability evidence.
8. V2 research-only Champion directly as live order authority.
9. Any legacy DB migration into V3 active databases.
10. Any legacy open-position/order state into V3 execution state.
11. Any shared `.json` runtime file between the two VPSs.
12. Any operator dashboard/control call in the open-position hot path.
13. Any automatic fallback where Execution invents a trade if Observation is unavailable.
14. Any real LIVE order adapter until long-term LIVE/PAPER validation passes.

\---

# 11\. V3 COMMUNICATION CONTRACT

V3 freezes a new protocol namespace rather than pretending V2 wire compatibility is permanent.

Suggested initial protocol:

`NBOT\_V3\_EXECUTION\_V1`

## 11.1 TradeRequest

Required fields should include:

* `protocol\_version`;
* `request\_id`;
* `requested\_at\_ms`;
* `profile`;
* `market\_environment`;
* `execution\_mode`;
* `execution\_state = FLAT`;
* `execution\_instance\_id`;
* optional previous `proposal\_id`;
* optional previous veto/rejection result;
* supported proposal schema version;
* execution release/git identity where useful.

## 11.2 TradeResponse

Statuses:

* `PROPOSAL`;
* `NO\_TRADE`;
* `NOT\_READY`.

No network/HTTP error is interpreted as `PROPOSAL`.

## 11.3 ExecutionProposal

Required fields should include:

* `protocol\_version`;
* `proposal\_id`;
* `generated\_at\_ms`;
* `expires\_at\_ms`;
* `profile`;
* `market\_environment`;
* `evidence\_lineage`;
* `symbol`;
* `side`;
* `market\_event\_id`;
* `data\_generation\_id`;
* `feature\_version`;
* `signal/research versions` where relevant;
* `selector\_version`;
* `entry\_authority`;
* `exit\_policy\_version`;
* selection score/rank;
* expected after-cost result when applicable;
* research reference price/quote metadata for later degradation measurement;
* experiment/champion metadata;
* source digest/version metadata.

Risk quantity from Observation is advisory only. Execution builds actual local size/risk.

## 11.4 Execution veto feedback

Execution may reject a valid recommendation because of local current truth.

Examples:

* stale proposal;
* spread too high;
* price drift too high;
* quote stale;
* insufficient balance;
* leverage failure;
* risk plan invalid;
* daily halt;
* exchange unhealthy;
* already open;
* duplicate proposal;
* wrong profile/environment/authority.

A veto is not a losing trade and must not be recorded as a market loss.

## 11.5 ExecutionOutcome

Required fields should include:

* `protocol\_version`;
* deterministic `outcome\_id`;
* `proposal\_id`;
* `request\_id` where available;
* `profile`;
* `market\_environment`;
* `evidence\_lineage`;
* `symbol`;
* `side`;
* `market\_event\_id`;
* selector/model/champion metadata;
* exit-policy version;
* entry reference price;
* actual fill price;
* exit price;
* quantity;
* realized PnL;
* initial risk USD;
* realized R;
* MAE/MFE USD and R;
* entry/close timestamps;
* holding duration;
* entry order/client IDs;
* final stop identity/history summary;
* exit reason;
* slippage/spread/notional/risk diagnostics;
* close evidence source;
* execution health/latency summary if useful.

## 11.6 OutcomeAcknowledgement

ACK is valid only after Observation durably records the outcome or confirms the same already-recorded `outcome\_id`.

Fields:

* protocol version;
* outcome ID;
* status (`RECORDED` or `ALREADY\_RECORDED`);
* recorded timestamp;
* Observation lineage/store identity.

## 11.7 Pull-only recommendation model

Observation never pushes `BUY NOW` to Execution.

Execution asks only while flat.

This preserves one-position-at-a-time naturally and prevents recommendations from being pushed while capital is already exposed.

\---

# 12\. EXECUTION STATE CONTRACT

Execution runtime state is separate per capital profile.

Minimum durable state:

```text
state\_version
profile
market\_environment
execution\_instance\_id
entries\_enabled
open\_position
entry\_inflight
processed\_proposal\_ids
daily\_risk
last\_completed\_trade
health/recovery metadata
```

Pending outcomes may be separate one-file-per-outcome durable records under `pending\_outcomes/`.

## 12.1 Atomic persistence

Critical execution state writes must use:

```text
write temp
 -> flush
 -> fsync file
 -> atomic rename/replace
 -> fsync directory where required
```

A half-written state file cannot be silently accepted.

## 12.2 Entry journal ordering

Before sending a market entry:

```text
validate proposal
 -> reserve proposal ID
 -> build EntryPlan
 -> persist entry\_inflight + deterministic client ID
 -> only then submit market order
```

## 12.3 Post-fill ordering

After fill:

```text
record fill
 -> calculate actual risk/notional/slippage
 -> establish and verify protective stop
 -> if any fatal post-fill safety breach: verified emergency flatten
 -> only after safe protection: promote to open\_position
```

## 12.4 Close ordering

```text
prove close
 -> calculate/obtain authoritative accounting
 -> create outcome
 -> persist execution history
 -> persist/queue outcome
 -> clear open position atomically
```

The exact transaction boundary must ensure a restart cannot lose both the position record and the completed outcome.

\---

# 13\. OBSERVATION DATABASE AND EVIDENCE LINEAGE CONTRACT

There are separate Observation databases:

```text
data/observation/live/observer.db
data/observation/testnet/observer.db
```

They are never merged.

## 13.1 LIVE database

Purpose:

* canonical research evidence;
* LIVE features/signals;
* LIVE future paths;
* LIVE policy lab;
* LIVE selection/champion evidence;
* LIVE/PAPER execution outcomes in dedicated operational tables;
* later real execution outcomes in clearly labeled tables.

## 13.2 TESTNET database

Purpose:

* Testnet market canary data;
* Testnet proposal registry;
* Testnet execution outcomes;
* operational timing/failure evidence.

Authority label:

`TESTNET\_OPERATIONAL\_ONLY`

It cannot create a LIVE Research Champion.

## 13.3 Point-in-time requirement

A market event can become a canonical research target only when its required decision-time information is proven available at the decision clock.

Late or reconstructed context is marked and excluded according to versioned rules.

## 13.4 Immutable definitions

Every important dataset transformation stores:

* version;
* definition JSON;
* definition hash;
* source digest;
* build timestamp;
* audit status.

Reusing the same version string with changed semantics is an error.

\---

# 14\. V3 CONTINUOUS LEARNING TARGET

V2 established the clean research foundation but V3's long-term mission still includes continuous self-improvement.

V3 therefore reintroduces selected V1 learning-operational concepts on top of V2-style unbiased evidence.

## 14.1 Training must be separate from realtime collection

Observation realtime collection must not synchronously run heavy training.

Use separate processes/services for:

* dataset builds;
* challenger training;
* walk-forward evaluation;
* model registry updates;
* drift reports;
* promotion decisions.

## 14.2 Champion/challenger model

At any time maintain:

* transparent baselines;
* current research champion;
* one or more challengers;
* frozen champion evaluation evidence;
* promotion history;
* rollback history.

## 14.3 Model registry

Inspired by V1's useful model-registry concept, V3 registry entries should include:

* immutable model ID/version;
* training window;
* feature version;
* target version;
* hyperparameters;
* training source digest;
* code/release identity;
* validation metrics;
* final-test metrics;
* calibration metadata if probabilistic;
* regime metrics;
* status (`CHALLENGER`, `RESEARCH\_CHAMPION`, `PAPER\_CHAMPION`, `RETIRED`);
* authority boundary.

## 14.4 Promotion is evidence-driven

No challenger is promoted because it is newer or more complex.

Promotion requires predeclared gates such as:

* positive after-cost expectancy/confidence;
* paired lift over a frozen benchmark/champion;
* acceptable drawdown;
* adequate independent-event count;
* symbol/date/regime robustness;
* cost-stress survival;
* no training leakage;
* clean source digests;
* acceptable operational performance when relevant.

## 14.5 Automatic rollback

V1 had automatic rollback concepts. V3 may reimplement them only after the paper stage is mature.

Rollback trigger examples:

* material expectancy degradation;
* drift threshold breach;
* calibration collapse where applicable;
* regime-specific catastrophic behavior;
* repeated operational rejection caused by model outputs;
* data-integrity failure;
* invalid model artifact/digest.

Rollback changes recommendation authority only. It never changes Execution safety rules or gives a model order authority.

\---

# 15\. PHASE LEDGER — REQUIRED BUILD ORDER

```text
V3.0  Clean repository/runtime foundation + profiles + nbotctl skeleton
  |
  v
V3.1  Execution Worker clean rebuild (V1/V2.8.5 parity)
  |
  v
V3.2  Deploy Execution first + standalone Testnet mechanical canary
  |
  v
V3.3  Observation evidence worker + fresh LIVE collection
  |
  v
V3.4  Observation research stack + learning foundation
  |
  v
V3.5  Recommendation service + V3 protocol/remote client/outcome receiver
  |
  v
V3.6  Dry two-VPS integration with Testnet order writes disarmed
  |
  v
V3.7  TESTNET\_TRADE full end-to-end operational/fault canary
  |
  v
V3.8  LIVE\_PAPER operational/economic canary
  |
  v
V3.9  Continuous challenger learning + Paper Champion long-term validation
  |
  v
V3.10 LIVE\_TRADE adapter/gate + micro real-capital validation
  |
  v
V3.11 Mature V3 operating system
```

\---

# 16\. PHASE V3.0 — CLEAN FOUNDATION AND RESET

## Goal

Create a clean, boring, reproducible V3 base before implementing trading behavior.

## Tasks

### Git

* push current pre-V3 code to `main`;
* tag final V2 checkpoint;
* remove obsolete long-lived branches if desired;
* create V3 skeleton on `main`;
* use small commits;
* tag every completed V3 phase.

### VPS reset

On both VPSs:

* stop/disable old NBOT services;
* remove old V1/V2 runtime databases/state/logs/locks;
* remove old virtualenv/runtime processes;
* clone/install clean `/root/Nbot` or role-appropriate home path;
* create clean virtualenv;
* install pinned requirements;
* create `.nbot-role`;
* create required ignored directories;
* configure time synchronization;
* configure firewall/control-link baseline.

### Repository skeleton

Implement:

* directory structure in Section 5;
* `profiles.py`;
* `nbotctl` command skeleton;
* role detection;
* profile validation;
* logging bootstrap;
* atomic IO helpers;
* common ID/time helpers;
* systemd templates;
* `.gitignore`;
* secret-directory permissions.

### Profile validation

Unit tests must prove impossible/invalid combinations fail, including:

* Observation with order credentials/adapter;
* TESTNET profile with LIVE order host;
* LIVE\_PAPER with order-writing adapter;
* LIVE\_TRADE without arm gate;
* wrong data/state directory for profile;
* unsupported role/profile combination.

## Acceptance gate

* \[ ] clean repo installs on both fresh VPSs;
* \[ ] no old runtime state is loaded;
* \[ ] `nbotctl doctor` works on each role;
* \[ ] role identity works;
* \[ ] all three profiles parse/validate;
* \[ ] no profile can accidentally cross Testnet/LIVE state paths;
* \[ ] Observation startup contract contains no private order credential requirement;
* \[ ] Execution startup can exist without importing research modules;
* \[ ] Git working tree clean after install;
* \[ ] automated foundation tests pass.

Suggested tag:

`v3.0-clean-foundation`

\---

# 17\. PHASE V3.1 — EXECUTION WORKER CLEAN REBUILD

## Goal

Build the capital guardian first, before Observation exists.

Execution is developed against abstract `ProposalClient`, `OutcomeClient`, and `ExchangePort` interfaces.

A synthetic/local proposal source may exist **only as a test/canary tool**, not the future integrated production path.

## V3.1.1 Execution data models

Implement:

* Quote;
* AccountSnapshot;
* ExchangePosition;
* Fill;
* CloseFill;
* ProtectiveStopRef;
* EntryPlan;
* OpenPosition state;
* EntryInflight state;
* DailyRisk state;
* ExecutionHealth.

## V3.1.2 State store

Implement:

* atomic JSON state;
* schema version;
* corrupt-state fail closed;
* entry-inflight journal;
* processed proposal reservation;
* separate profile paths;
* daily-risk persistence;
* completed execution history;
* pending outcome outbox.

## V3.1.3 Risk manager

Initial Execution risk manager must support:

* risk-per-trade USD;
* max notional;
* leverage;
* spread limit;
* quote-age limit;
* reference-price drift limit;
* post-fill notional tolerance;
* post-fill risk tolerance;
* max entry slippage;
* daily risk floor;
* profit giveback;
* one-position limit.

Do not optimize these parameters during architecture rebuild.

## V3.1.4 Entry lifecycle

Port/reimplement V1/V2 behavior:

1. validate proposal contract;
2. validate profile/environment/authority/expiry;
3. reject duplicate proposal;
4. confirm flat locally and on exchange;
5. fetch fresh local quote;
6. check spread;
7. check reference drift;
8. check account/balance;
9. build local EntryPlan;
10. set/verify leverage;
11. persist entry-inflight journal/client ID;
12. submit exactly one market entry request;
13. recover ambiguous response by same identity;
14. record fill;
15. verify actual notional/risk/slippage;
16. place initial protective stop;
17. verify protective stop;
18. if fatal post-fill violation/protection failure -> verified emergency flatten;
19. promote to OPEN only after safe state is proven.

## V3.1.5 Position lifecycle

Implement:

* open-symbol price processing;
* MAE/MFE;
* current unrealized PnL;
* risk-contract monitoring;
* initial control exit policy `INTEGER\_R\_STEP\_CONTROL`;
* trailing stop decisions;
* stop replacement verification;
* stop identity persistence;
* close detection;
* emergency risk response;
* health/latency measurement.

## V3.1.6 Reconciliation

Implement startup and on-demand reconciliation before any new request:

* exchange flat / local flat;
* local open / exchange open matching;
* missing stop recovery;
* stale/incorrect stop recovery;
* local open / exchange flat close recovery;
* unmanaged exchange position fail closed;
* multiple/hedge mode fail closed;
* orphan stop handling;
* entry-inflight recovery;
* exact order/trade/accounting evidence;
* no invented values.

## V3.1.7 Emergency flatten

Implement bounded close attempts with explicit verify-flat loop.

Critical rule:

> A close request is not proof of a close.

## V3.1.8 Paper Exchange

Implement the common ExchangePort with local PAPER mechanics early, even though LIVE\_PAPER is a later phase.

It enables deterministic unit/integration tests without order APIs.

## V3.1.9 Testnet Exchange

Reimplement V2.8.5 safety properties:

* hard-pinned Testnet hosts;
* signed requests;
* deterministic client order ID;
* ambiguous entry recovery;
* current Binance algo-stop service behavior;
* deterministic client algo IDs;
* ambiguous stop recovery;
* verify new stop before pruning obsolete stop;
* authoritative close recovery from Testnet orders/trades/income;
* orphan stop cleanup;
* no invented PnL;
* arm gate;
* persistent session limit;
* single instance.

## V3.1.10 Execution Worker integration

Added during the V3.1 implementation audit after the component lifecycles were complete.
This subphase does not change trading logic; it assembles the proven components into the capital-first `ExecutionWorker`.

Required ordering/invariants:

* one canonical exchange/state/risk identity across Entry, Position and Reconciliation;
* reconciliation before any flat-side proposal opportunity;
* pending outcome delivery/ACK before another proposal request;
* OPEN hot path has no ProposalClient/OutcomeClient dependency;
* irrelevant symbols are ignored early;
* PAPER market tick settlement occurs before position management;
* restart can adopt and continue a durable protected position.

## V3.1.11 Runtime and acceptance closure

Added during the V3.1 implementation audit because the V3.0 runtime/operator skeleton still reported Execution as unimplemented after the component code existed.
This is an operational closure subphase, not a trading-semantics change.

Implement/verify:

* `run_execution.py` is a real capital-first Execution entrypoint;
* V3.1 Testnet runtime starts only after explicit profile, arm and authenticated preflight;
* the V3.1 runtime starts with new entries disabled and no integrated recommendation authority;
* local `nbotctl start/stop/restart/status/logs` execution controls exist;
* PID convenience controls verify process identity before signalling;
* real V3.1 doctor checks replace the old `DEFERRED_UNTIL_V3_1` placeholders;
* existing/corrupt state, history, pending outcomes and single-instance lock are surfaced fail-closed;
* LIVE_PAPER remains non-runnable until its independent LIVE public market path is available in the later LIVE/PAPER phase;
* LIVE_TRADE remains forbidden until V3.10;
* final V3.1 acceptance audit passes before the phase tag is created.

## V3.1 acceptance gate

* \[ ] Execution imports no Observation/research/training modules;
* \[ ] unit tests reproduce all critical V1/V2.8.5 safety invariants;
* \[ ] corrupt state fails closed;
* \[ ] duplicate proposal cannot call market order twice;
* \[ ] ambiguous entry never blindly resubmits;
* \[ ] post-fill risk/notional/slippage breaches lead to protected emergency close;
* \[ ] initial stop failure cannot leave accepted unmanaged exposure;
* \[ ] stop replacement preserves known protection;
* \[ ] reconciliation happens before enabling entries;
* \[ ] open position manages without ProposalClient/OutcomeClient availability;
* \[ ] pending outcome blocks next request until ACK;
* \[ ] health metrics available.

Suggested tag:

`v3.1-execution-core-parity`

\---

# 18\. PHASE V3.2 — DEPLOY EXECUTION FIRST / STANDALONE TESTNET MECHANICAL CANARY

## Goal

Physically deploy Execution V3 on the Execution VPS and prove exchange mechanics before Observation V3 exists.

This is deliberately Execution-first.

## Runtime

```text
Synthetic/manual canary proposal
          |
          v
   V3 Execution Worker
          |
          v
   Binance Testnet
```

The synthetic proposal source must be clearly labeled:

`TESTNET\_MECHANICAL\_ONLY`

It is not research authority.

## Required tests

### Normal

* LONG entry + initial stop + managed close;
* SHORT entry + initial stop + managed close;
* controlled trailing-stop replacement;
* operator force close.

### Entry failure

* network timeout after order may have reached Binance;
* duplicate invocation;
* insufficient balance;
* spread fail;
* price drift fail;
* leverage fail;
* quantization edge;
* post-fill slippage breach;
* post-fill notional breach;
* post-fill risk breach.

### Stop failure

* stop placement timeout;
* ambiguous stop placement;
* duplicate stop identities;
* replacement timeout;
* new stop visible before old stop removal;
* missing stop after restart;
* orphan stop after close.

### Restart/reconciliation

* kill after journal but before order result;
* kill after fill before stop persistence;
* kill after stop placement before local open promotion;
* kill during open position;
* exchange closes while process offline;
* manual close while process offline;
* stop closes while process offline;
* restart with corrupt local state;
* restart with exchange/local mismatch.

### Emergency

* unprotected position -> emergency flatten;
* emergency first attempt fails, bounded retry succeeds;
* emergency cannot prove flat -> critical fail-closed state retained.

## Telemetry

Record:

* order request/fill latency;
* stop placement/verification latency;
* stop replacement latency;
* reconciliation latency;
* open-position management latency;
* emergency attempts/results;
* recovery counts;
* duplicate prevention counts;
* CPU/RAM.

## Acceptance gate

Do not proceed to Observation implementation until:

* \[ ] Testnet LONG lifecycle passed;
* \[ ] Testnet SHORT lifecycle passed where supported;
* \[ ] all capital-safety fault tests passed or have deterministic equivalent tests;
* \[ ] no duplicate entry defect remains;
* \[ ] no unprotected-exposure defect remains;
* \[ ] restart recovery is deterministic;
* \[ ] no invented close/PnL accounting remains;
* \[ ] Execution can remain OPEN and function with no Observation process at all.

Suggested tag:

`v3.2-execution-testnet-mechanical-proven`

\---

# 19\. PHASE V3.3 — OBSERVATION EVIDENCE WORKER

## Goal

Only after Execution is mechanically proven, build/deploy the independent market-evidence worker.

Observation V3 initially has **no recommendation authority**.

## V3.3.1 Generic public market client

Support explicit public profiles:

* LIVE Binance USD-M public;
* Testnet/demo public where needed for operational canary.

The LIVE research profile is canonical.

## V3.3.2 Canonical collection clock

Initial clock remains completed 5-minute candles.

Use server time and settle delay.

Reject excessive clock skew.

## V3.3.3 Universe

Initial target:

* broad USD-M eligible universe;
* target around 200 symbols;
* liquidity threshold;
* spread threshold;
* deterministic selection/rank;
* explicit universe membership per event.

## V3.3.4 Atomic evidence event

A complete event stores point-in-time:

* event ID/open time;
* eligible universe;
* candle(s);
* quote/spread context;
* 24h liquidity context;
* funding/current relevant context;
* capture timing/provenance;
* completeness state.

Partial capture does not pretend to be a complete canonical event.

## V3.3.5 Gap recovery

Implement V2 rule:

* missing historical candles may be recovered;
* point-in-time spread/liquidity is not fabricated;
* recovered/incomplete lineage explicit;
* research readiness excludes invalid context according to frozen rules.

## V3.3.6 Funding history

Persist timestamped funding events/ranges independently so later cost calculation can prove coverage.

## V3.3.7 Database operations

Implement:

* SQLite WAL policy;
* checkpoint;
* backup;
* integrity check;
* deterministic audit;
* event-gap audit;
* late-context audit;
* source-capture timing audit.

## V3.3.8 Deploy LIVE collector

Once V3.3 code passes tests, deploy Observation VPS and start:

```text
LIVE public collector
 -> data/observation/live/observer.db
```

From this moment forward clean V3 LIVE evidence begins accumulating while later phases are developed.

Observation still has:

* no private Binance credentials;
* no recommendation authority;
* no execution outcome API required yet;
* no order path.

## Acceptance gate

* \[ ] clean LIVE DB starts from zero;
* \[ ] completed events are atomic;
* \[ ] late/incomplete context is explicit;
* \[ ] recovery never fabricates context;
* \[ ] funding coverage is auditable;
* \[ ] deterministic audit passes;
* \[ ] database backup/restore tested;
* \[ ] process restart resumes correctly;
* \[ ] CPU/RAM/disk growth measured;
* \[ ] Observation contains no order credentials.

Suggested tag:

`v3.3-observation-evidence-foundation`

\---

# 20\. PHASE V3.4 — RESEARCH, OUTCOMES, EXIT LAB, SELECTION AND LEARNING FOUNDATION

## Goal

Rebuild the V2 research-first intelligence on the clean V3 LIVE evidence DB.

No capital recommendation authority yet.

## V3.4.1 Canonical features

Implement/version at least V2-equivalent features from Section 9.4.

Tests:

* never read future event/candle;
* deterministic rebuild;
* incomplete history remains explicit;
* context-incomplete event is not silently used;
* definition hash mismatch fails.

## V3.4.2 Research signal annotations

Implement initially:

* CSM;
* TSMOM;
* intraday conditional momentum/reversion.

Every research-ready market row receives signal annotations, including inactive/none states.

Signals do not gate raw evidence.

## V3.4.3 Future-path outcomes

Build mature forward labels only after the full required horizon exists.

Implement:

* 5m through 4h horizons;
* MFE/MAE;
* barrier events;
* ambiguity flags;
* future volatility;
* costs/funding;
* deterministic source digest;
* label-only future candle cache isolated from features.

## V3.4.4 Exit-policy lab

Reproduce the V2 control + seven challengers.

Initial output is research-only.

No challenger becomes Execution policy merely because it wins a small sample.

## V3.4.5 Entry-selection lab

Reproduce:

* all eligible symbol/side examples;
* five transparent baselines;
* forward-chained ridge learned selector;
* after-cost net-R objective;
* event-level ranking;
* no signal gating;
* deterministic audit/digests.

## V3.4.6 Research Champion evaluator

Reproduce V2 walk-forward philosophy:

* chronological validation/final test;
* benchmark frozen from validation;
* independent event counting;
* bootstrap confidence;
* cost stress;
* regime/symbol/date robustness;
* training leakage checks;
* immutable evaluation digest.

The first pass creates only:

`RESEARCH\_ONLY\_NO\_EXECUTION`

## V3.4.7 Continuous learning foundation

Add V3-native skeletons for later:

* model registry;
* challenger registry;
* training job state;
* evaluation ledger;
* drift reports;
* rollback records.

Do not enable automatic promotion to execution-facing authority yet.

## Acceptance gate

* \[ ] raw evidence digests unchanged by research builds;
* \[ ] features are point-in-time safe;
* \[ ] future labels cannot leak into features;
* \[ ] policy lab deterministic;
* \[ ] selection training strictly forward chained;
* \[ ] transparent baselines retained;
* \[ ] Research Champion cannot obtain order authority;
* \[ ] all build/audit commands exposed through `nbot\_admin.py`;
* \[ ] heavy research can run without breaking LIVE collection timing.

Suggested tag:

`v3.4-research-learning-foundation`

\---

# 21\. PHASE V3.5 — RECOMMENDATION SNAPSHOT AND COMMUNICATION SERVICES

## Goal

Prepare Observation and Execution to communicate, but do not enable Testnet order writes through the remote path yet.

## V3.5.1 Freeze protocol

Implement `NBOT\_V3\_EXECUTION\_V1` contracts from Section 11.

Tests:

* strict serialization/deserialization;
* unknown/missing field handling;
* wrong protocol;
* wrong profile;
* wrong environment;
* wrong lineage;
* expiry;
* future timestamp;
* invalid symbol/side;
* deterministic IDs;
* duplicate outcome ACK.

## V3.5.2 Recommendation snapshot

Observation continuously maintains a small latest recommendation state derived from a completed decision cycle.

It must contain:

* authority identity;
* market event;
* generated/expiry time;
* chosen symbol/side;
* selector/policy version;
* score/rank/expected metric;
* source lineage/digest.

It is informational until Execution requests it.

## V3.5.3 Testnet operational recommendation authority

Because Testnet is not economic proof, V3.5 may define a clearly marked authority:

`TESTNET\_OPERATIONAL\_CANARY\_V1`

Its only purpose is to exercise the complete machine.

It cannot appear in LIVE/PAPER research champion tables as economic evidence.

## V3.5.4 Observation control service

Required endpoints/operations:

```text
GET  /health
POST /trade-request
POST /execution-outcome
```

Requirements:

* authenticated;
* encrypted/private transport;
* bounded request handling;
* no heavy training in handler;
* idempotent outcome recording;
* explicit profile/lineage validation;
* no secrets in responses.

## V3.5.5 Execution remote client

Implement bounded remote client:

* no fallback local strategy;
* network failure -> stay flat;
* never reused cached stale proposal;
* previous veto feedback supported;
* never invoked from open-position hot path.

## V3.5.6 Durable network outcome publisher

Execution sends pending outcomes and removes them only after valid ACK.

## Acceptance gate

* \[ ] real remote client exists;
* \[ ] real Observation service exists;
* \[ ] Testnet canary authority clearly labeled operational-only;
* \[ ] idempotent outcome receiver persists exactly once;
* \[ ] auth failure returns no proposal;
* \[ ] wrong lineage/profile fails closed;
* \[ ] open-position code has no remote call;
* \[ ] pending outcome ordering enforced.

Suggested tag:

`v3.5-recommendation-protocol-ready`

\---

# 22\. PHASE V3.6 — TWO-VPS DRY INTEGRATION, ORDERS DISARMED

## Goal

Connect the actual Observation VPS and Execution VPS before allowing the integrated path to place Testnet orders.

## Runtime

```text
Execution FLAT
 -> network TradeRequest
Observation
 -> PROPOSAL / NO\_TRADE / NOT\_READY
Execution
 -> validates/logs decision
 -> NO ORDER (integrated order gate disarmed)
```

Synthetic execution outcomes may be used to prove durable receiver/ACK behavior in a dedicated Testnet store.

## Mandatory tests

* authenticated handshake;
* same protocol;
* same profile;
* same Git release;
* clock skew;
* NO\_TRADE;
* NOT\_READY;
* valid proposal;
* expired proposal;
* wrong profile/environment;
* duplicate proposal;
* previous veto feedback;
* Observation process down;
* network route blocked;
* timeout;
* duplicate outcome;
* invalid ACK;
* Observation restart;
* Execution restart while flat;
* pending outcome before next request.

## Acceptance gate

* \[ ] real two-VPS dry handshake passes;
* \[ ] no integrated order write occurs;
* \[ ] protocol/auth failure always stays flat;
* \[ ] duplicate message behavior is safe;
* \[ ] pending outcome survives restart/outage;
* \[ ] same release identity proven;
* \[ ] LIVE and Testnet Observation DBs remain separated;
* \[ ] LIVE passive evidence collection remains healthy if running in parallel.

Suggested tag:

`v3.6-two-vps-dry-integration`

\---

# 23\. PHASE V3.7 — TESTNET\_TRADE END-TO-END OPERATIONAL CANARY

## Goal

Prove the complete architecture with real two-VPS communication and Binance Testnet orders.

This phase answers:

> \*\*Does the whole machine work safely?\*\*

It does not answer:

> \*\*Is the strategy profitable on LIVE markets?\*\*

## Runtime

```text
                         BINANCE TESTNET
                        /               \\
                       v                 v
          Testnet Observation      V3 Execution
                 |                     |
                 |<-- TradeRequest ----|
                 |                     |
                 |---- Proposal ------>|
                 |                     |
                 |               local validation
                 |               Testnet entry
                 |               stop / trailing
                 |               close / recovery
                 |                     |
                 |<-- Outcome ---------|
                 |---- ACK ----------->|

Meanwhile:
LIVE passive Observation may continue collecting canonical research evidence
into data/observation/live/observer.db.
```

## Mandatory failure campaign

### A. Normal LONG

Full request -> proposal -> entry -> stop -> management -> close -> outcome -> ACK.

### B. Normal SHORT

Same lifecycle.

### C. Observation dies while position is OPEN

Execution continues managing independently.

### D. Control network link dies while OPEN

No effect on position management.

### E. Observation remains down after close

Outcome stays pending and Execution stays flat.

### F. Observation returns

Outcome delivered once/ACKed before next request.

### G. Execution dies while OPEN

Restart reconciles exchange first, recovers position/protection, resumes management.

### H. Duplicate proposal

At most one entry.

### I. Duplicate outcome

One Observation record.

### J. Expired proposal

No entry.

### K. Wrong environment/profile/lineage

No entry.

### L. Observation NO\_TRADE

Execution remains flat normally.

### M. Observation NOT\_READY

Execution remains flat normally.

### N. Current spread/price drift veto

No entry; veto recorded, not counted as loss.

### O. Ambiguous entry response

Recover same client ID; no blind resubmit.

### P. Ambiguous stop response

Recover same stop identity; no unprotected retry sequence.

### Q. Stop replacement fault

Known old protection is not removed before new verified protection.

### R. External/manual close

Restart/reconcile using authoritative exchange history/accounting.

### S. Orphan stop

Flatness not considered clean until orphan protection handled.

### T. Post-fill safety breach

Position protected then verified emergency close.

### U. Heavy Observation research load

Execution management latency remains independent.

### V. LIVE passive collector continuity

No Testnet contamination, no lock/DB collision, acceptable timing.

## Telemetry

Record at least:

* request count;
* proposal/no-trade/not-ready count;
* control API RTT;
* proposal age;
* veto counts/reasons;
* entry request/fill latency;
* stop placement/verification latency;
* stop replacement latency;
* position loop latency;
* reconciliation counts/results;
* emergency attempts/results;
* restart recovery counts;
* pending outcome depth/age;
* ACK latency;
* duplicate suppression counts;
* CPU/RAM;
* LIVE collector event-gap/capture timing while parallel.

## Acceptance gate

* \[ ] complete end-to-end LONG passed;
* \[ ] complete end-to-end SHORT passed where possible;
* \[ ] mandatory fault campaign passed or equivalent deterministic test documented;
* \[ ] no duplicate exposure defect;
* \[ ] no unprotected exposure defect;
* \[ ] no lost completed outcome;
* \[ ] no duplicate Observation outcome;
* \[ ] Observation outage cannot affect OPEN management;
* \[ ] Execution restart reconciles before new request;
* \[ ] control-link failure while flat blocks entry;
* \[ ] wrong profile/environment/lineage fails closed;
* \[ ] no unresolved capital/state-integrity defect;
* \[ ] Testnet evidence remains `TESTNET\_OPERATIONAL\_ONLY`;
* \[ ] Testnet canary remains reusable for future regression.

Suggested tag:

`v3.7-testnet-e2e-operational-proven`

## Implementation sequencing exception — 2026-08-21

This records current implementation status without rewriting the V3.7 acceptance gate above.

- V3.7-A Normal LONG: **PASS** through the integrated Observation request/proposal, Binance Testnet entry/protection/OPEN management, Execution-managed protective-stop close, authoritative accounting, durable outcome delivery and exactly-once Observation recording/ACK.
- V3.7-B Normal SHORT: **DEFERRED** by explicit operator sequencing decision.
- V3.7 C–V mandatory operational/fault campaign: **PASS** from the preserved physical and deterministic-equivalent evidence.
- At transition, Testnet Execution is required FLAT, with no entry inflight or pending outcome, DISARMED and stopped.

Because V3.7-B is deferred, the canonical V3.7 gate is **not fully passed** and `v3.7-testnet-e2e-operational-proven` must not be created. The operator explicitly authorizes V3.8 implementation to begin as a sequencing exception. This exception grants no economic authority and no order authority. A later LIVE_PAPER SHORT is different evidence and does not retroactively convert V3.7-B into a Testnet PASS. The deferred Testnet SHORT remains visible regression debt.

## V3.7-B closure — 2026-08-23

The sequencing exception above is retained as historical change-control evidence. It is no longer an active acceptance deferral. V3.7-B was closed by an actual integrated Binance Testnet Normal SHORT, not by LIVE/PAPER substitution or by weakening the acceptance gate.

Physical closure evidence:

- integrated `DOGEUSDT` SHORT proposal `PROP-33b8005daa79db45b237a3c449ec677c3d2d4db6` was reconstructed from point-in-time Observation evidence and served through the TradeRequest/TradeResponse boundary;
- both VPSs ran release `e6b7c75eb8289edb7823a8f771d8443207c2f8f2` for the accepted lifecycle;
- Binance entry `2325102242` filled `11074` DOGE at `0.09031` and the full position was protected by stop `1000000178342683` / `NBV3SL-b44cf9af41f9374817d5d7ce`;
- OPEN management remained active and recovery stayed non-critical;
- the protective `STOP_MARKET` triggered autonomously and child order `2325127093` closed the complete SHORT at `0.09121`;
- authoritative Binance realized PnL was `-9.9666` USD (`-0.99666R`) with `exit_reason=PROTECTIVE_STOP_TRIGGERED`;
- Execution produced deterministic outcome `OUT-9b671e52f3e35e5ca9138358a96df3ae`;
- Observation stored exactly one matching outcome, linked it to the served proposal, and Execution removed its pending copy after the matching ACK;
- final state was exchange/local FLAT, `entry_inflight=null`, pending outcomes zero, recovery non-critical, Testnet DISARMED, and new entries disabled;
- the troubleshooting DOGE SHORT, intervening DOGE LONG, and accepted DOGE SHORT had distinct proposal IDs and distinct entry client identities with no residual state contamination.

Together with the already accepted V3.7-A Normal LONG and V3.7 C–V operational/fault campaign, the canonical V3.7 operational acceptance gate is now **PASSED**.

The tag `v3.7-testnet-e2e-operational-proven` may be created only after this closure release passes automated validation, is committed/pushed to `main`, and the same release SHA is physically deployed and verified on both VPSs.

\---

# 24\. PHASE V3.8 — LIVE\_PAPER OPERATIONAL AND ECONOMIC CANARY

## Goal

Switch from Testnet market/order mechanics to:

* **LIVE Binance market truth**;
* **local PAPER capital**;
* **zero Binance order writes**.

This phase asks:

> Does the research advantage survive real-time market conditions, proposal latency, current spread, price deterioration, Execution vetoes and the actual position-management path?

## Preconditions

* V3.7 operational gate passed;
* Testnet state has no open/inflight position;
* pending Testnet outcomes ACKed;
* PAPER state starts clean;
* LIVE Observation DB is healthy;
* research pipeline auditable;
* a valid research-facing authority exists or phase runs in explicitly non-promotional dry mode until it does;
* PaperExchange order writes are structurally impossible.

Implementation note (2026-08-21): the first precondition remains the canonical rule, but the explicit V3.7 sequencing exception above permits V3.8 implementation to start with V3.7-B still recorded as deferred. This does not mark V3.7 complete or authorize its canonical acceptance tag.

### V3.8.1R research scalability recovery

Physical V3.8.1 catch-up on 2026-08-22 exposed an implementation-scale defect rather than an economic-gate defect: reproducible derived research rows consumed the overwhelming majority of the LIVE SQLite database, expanding-window Ridge repeatedly reread/refit historical rows, and Champion integrity evaluation could rescan unrelated historical research for hours.

The recovery boundary therefore permits implementation/storage optimization while preserving every frozen V3.4 research meaning:

* canonical raw LIVE evidence remains durable and must not be deleted or relabeled;
* `RIDGE_EXPECTED_NET_R_V1` keeps the same features, alpha, forward-only chronology and ranking objective;
* the first 20 genuinely forward-scored events remain validation and the next 20 remain untouched final test;
* Research Champion thresholds/authority are unchanged;
* cumulative sufficient statistics may replace repeated full-history Ridge materialization only after the frozen first 20 validation + next 20 final-test events preserve exact scores/ranks, all later events preserve exact rank/symbol/side ordering and chronology metadata, and post-test within-event score differences remain equivalent; a common post-test additive intercept offset caused solely by floating-point centering is diagnostic and cannot alter the original frozen Champion decision;
* routine Champion integrity checks should be scoped to the frozen evaluation window instead of rescanning unrelated later history;
* an explicit maintenance operation may discard reproducible derived research state only after a reference snapshot is verified and a deterministic raw-evidence manifest proves the canonical raw tables are unchanged before and after reset/VACUUM;
* the recovery grants no recommendation, paper, Testnet, or real-order authority by itself.

This recovery is complete only when the optimized implementation passes automated regression, reference-equivalence verification, raw-evidence preservation proof, and a bounded clean rebuild sufficient for the original frozen Champion gate.

### V3.8.2 compact research ledger and derived-data lifecycle

V3.8.1R proved that canonical raw LIVE truth is small while reproducible relational research detail can be hundreds of megabytes for only dozens of events.  V3.8.2 therefore makes derived storage lifecycle-bounded instead of allowing historical intermediates to accumulate forever.

The storage contract is:

* canonical raw LIVE evidence remains durable;
* every completed selection event is sealed first into `COMPACT_RESEARCH_LEDGER_V1`;
* the compact archive permanently retains the decision-time training vector/after-cost target plus immutable source/build/model/policy/selector digests and event summaries needed for future audit or challenger training;
* sealing is digest-verified before any detailed row can be removed;
* the earliest 60 selection events remain detailed as the original 20-event Ridge training foundation plus 20 validation + 20 untouched final-test evidence;
* the newest 64 selection events remain detailed as the active debugging/research window;
* only sealed events outside both protected windows may be compacted;
* compaction removes reproducible event-level features/signals/future paths/policy results/selection examples/predictions in dependency-safe order while retaining definition tables, cumulative Ridge state, compact archives, Champion evaluation records and all canonical raw evidence;
* compacted raw events must not be silently rebuilt merely because their detailed feature rows were intentionally removed;
* freed SQLite pages are reusable working capacity; file truncation/VACUUM is a separate explicit maintenance action and is never required in the realtime collector hot path;
* retention/audit failure blocks further compaction;
* a 1 GiB live-page hard ceiling applies to the V3.8 research database until later evidence deliberately changes it;
* this lifecycle grants no Research Champion, paper-canary, Testnet or real-order authority.

Normal catch-up therefore becomes: build a bounded batch -> seal completed selection events -> verify compact archive -> compact eligible historical detail -> audit -> continue.

### V3.8.3 bounded research catch-up controller

After V3.8.2 physically proves the lifecycle on LIVE evidence, V3.8.3 may automate only that already-proven sequence.  It is an operational scalability controller, not a model/policy change.

The controller contract is:

* `BOUNDED_RESEARCH_CATCHUP_V1` runs on the Observation VPS only and has `RESEARCH_ONLY_NO_EXECUTION` authority;
* one catch-up batch may create at most 8 new selection events because 8 is the physically accepted V3.8.2 steady-state batch;
* each invocation has an explicit bounded cycle count and may never become an unbounded background `catch up everything` loop;
* the separate LIVE raw collector must still own its runtime lock and have a fresh recent capture before catch-up may start or continue;
* a second catch-up controller is blocked by its own process lock;
* before the first build, and after every sealed/compacted batch, SQLite integrity, retention integrity, full research integrity, cumulative Ridge state and the frozen Champion/evaluation fingerprint must remain healthy;
* the operating live-page ceiling is 900 MiB, deliberately below the V3.8.2 1 GiB emergency hard ceiling;
* a new 8-event build may start only with at least 64 MiB of live-page headroom below that 900 MiB operating ceiling; this reserve is based on the physically observed V3.8.2 batch growth and prevents retention from being used as an excuse to build through the ceiling;
* the controller builds only the existing frozen feature/signal/outcome/policy/selection definitions;
* the actual new-selection delta is measured from pending unsealed detailed events, never inferred from total ledger rows because compacted ledger events intentionally have no detailed selection-build row;
* after a successful build the controller seals exactly the new selection events and requests compaction of no more than that same count;
* after the 60+64 protected windows are populated, detailed selection history must stay at or below 124 events while the permanent compact ledger may continue growing;
* if a prior controller/process stops after building but before sealing, a later invocation may recover only a pending unsealed set no larger than the proven batch, then must re-run all safety gates before new work;
* zero newly mature selection events is a normal `WAIT_FOR_MATURE_EVIDENCE` stop, not a reason to widen the batch or weaken maturity rules;
* build failure, collector failure/staleness, SQLite/FK failure, retention failure, research-audit failure, Ridge-state mismatch, Champion/evaluation mutation, unbounded detailed working set or storage-ceiling breach fails closed immediately;
* the controller never calls Champion evaluation, never changes a Research Champion decision, never creates recommendation authority, and never starts Paper/Testnet/real execution.

This controller is complete only after automated regression plus a physical LIVE run demonstrates that multiple bounded cycles advance permanent ledger history while the detailed working set remains bounded and the LIVE raw collector continues independently.

### V3.8.4 epoch research / disposable derived-workspace correction

Physical V3.8.3 acceptance on 2026-08-22 proved the compact lifecycle but also proved that its steady-state operating model is unsuitable for continuous autonomous learning: processing only 24 mature events consumed sustained near-full CPU for tens of minutes because detailed research was materialized in the long-lived collector database and full historical research integrity was repeatedly rescanned around tiny batches.  The defect is architectural, not an economic-gate result.

V3.8.4 therefore deliberately supersedes the V3.8.1R/V3.8.2 assumption that all canonical raw evidence and reproducible derived research must remain together in one indefinitely growing SQLite file.  The new storage/processing contract is:

* realtime Observation continues to collect honest broad LIVE point-in-time evidence every five minutes; collection remains the highest-priority Observation workload;
* heavy research is decoupled from the collector and runs in **96-event epochs** (approximately eight hours of research-ready 5-minute events);
* an epoch is eligible only after the full 48-bar / four-hour future-label horizon for its final target event is available;
* each epoch receives a 48-bar historical context window and 48-bar future context window, so the raw dependency supplied to research is bounded and explicit;
* research runs in a **disposable SQLite workspace** containing only the epoch and its bounded raw context; expanded feature/signal/future-path/policy/selection rows are never permanent collector state;
* because the epoch workspace is disposable and has no authority until compact memory import succeeds, it uses ephemeral SQLite durability (`journal_mode=MEMORY`, `synchronous=OFF`, memory temp storage/cache) rather than paying durable WAL/FULL fsync costs for scratch rows; canonical raw evidence and permanent research memory remain durable;
* event research must bulk-load future candles/funding across the event symbol set instead of issuing per-symbol SQLite path queries; canonical raw candles retain precedence over any historical fallback cache and the economic/research definitions are unchanged;
* after successful selection, each target event is sealed once into permanent compact research memory using the already-proven compressed training vector/after-cost target and immutable lineage digests;
* permanent research memory also retains cumulative Ridge sufficient statistics and durable model/challenger/evaluation/drift/promotion/rollback artifacts as those later phases populate them;
* successful epoch workspaces are deleted after compact memory is durably committed; failed workspaces may be retained temporarily for forensic diagnosis but have no training authority;
* normal research never replays already-qualified raw events under the same immutable research definition; an explicit new feature/research generation starts prospectively unless a separately approved offline historical backfill is justified;
* normal selection scoring processes only newly built epoch events.  Historical transparent-baseline predictions are immutable and must not be rescored merely because new evidence arrived;
* the cumulative Ridge learner begins each epoch from its persisted sufficient statistics/history summary and advances only through the new chronological epoch; it must not reread historical raw candles or rebuild historical baseline predictions;
* full-history research audits are removed from the per-epoch hot path.  Promotion-time, release-time or deliberate maintenance audits may still perform expensive deep verification;
* raw collector retention becomes **dependency-watermark based**, not indefinite: old raw events may be deleted only after compact research memory proves qualification and after they are older than the 48-bar history dependency needed by the next unresolved epoch; if research falls behind, raw storage grows rather than deleting unprocessed evidence;
* collector raw pages may be reused by SQLite without realtime `VACUUM`; physical truncation remains an explicit maintenance operation;
* V3.8.4 starts a deliberately clean research generation: the accepted pre-V3.8.4 mixed raw+derived database is discarded after the collector is stopped and its final event boundary is recorded; no old raw, derived, Ridge, Champion or compact-ledger row is migrated into the new generation;
* the old `BOUNDED_RESEARCH_CATCHUP_V1` controller becomes a legacy recovery/diagnostic implementation and is not the continuous-learning runtime after V3.8.4 cutover;
* V3.8.4 changes storage scheduling and computational reuse only.  Feature definitions, outcome horizons, exit policies, `RIDGE_EXPECTED_NET_R_V1`, frozen Champion thresholds, research authority and Execution authority remain unchanged.

Performance is now a first-class operational gate.  A 96-event epoch must complete in at most two hours on the Observation VPS before automatic scheduling is enabled; the target is at most one hour.  The stage report must expose workspace-copy, feature, signal, outcome, policy, selection, seal and memory-import timings so further optimization is evidence-driven.  The LIVE collector must stay fresh independently throughout.

V3.8.4 is complete only after: (1) the legacy mixed database is deliberately discarded at a controlled generation boundary and empty compact memory is initialized; (2) a fresh raw-only generation accumulates its own 48-event historical context before the first target epoch; (3) at least one physical 96-event epoch is processed exactly once; (4) its disposable derived workspace is removed after commit; (5) permanent memory increases by exactly the epoch event count and cumulative Ridge state advances consistently; (6) rerunning the epoch is idempotent/skip-only; (7) raw pruning advances only behind the qualified dependency watermark; and (8) the epoch runtime satisfies the two-hour hard gate while the collector remains healthy.

#### V3.8.4 physical acceptance — 2026-08-23

The first production-sized epoch `EPOCH-1787436600000-1787465700000` passed all physical gates on the Observation VPS: 96/96 targets, 399.398 seconds elapsed, 187916 KiB peak RSS, zero swap, exactly 96 compact memory imports, Ridge advanced to 96 events / 37770 rows, scratch workspace deleted, exact-once re-invocation skipped, dependency-watermark raw pruning deleted only the bounded 96-event eligible prefix, SQLite quick/FK checks remained clean, and the LIVE collector remained healthy. Authority remained `RESEARCH_ONLY_NO_EXECUTION`.

### V3.8.5 Observation operations hardening

After V3.8.4 physical acceptance, make the proven research lifecycle self-operating without creating idle heavyweight daemons:

* `nbot-observation-live.service` continuously owns the canonical LIVE collector and explicitly runs `run_observation.py --profile live-paper`;
* `nbot-research-epoch.timer` is persistent across reboot and periodically invokes a low-priority `nbot-research-epoch.service` oneshot;
* the oneshot runs one bounded `research-epoch-run --prune-raw`; immature windows exit cheaply, while a mature 96-event epoch processes exactly once;
* epoch execution and manual raw pruning share a process lock so scheduler/manual overlap cannot race the same research workspace or retention boundary;
* `nbot-observer.target` is the boot-enabled base Observation role and starts only the LIVE collector plus epoch timer;
* LIVE_PAPER control is a separate optional continuous service enabled only when integrated paper execution is deliberately active;
* Testnet Observation control remains disabled except during deliberate regression;
* SQLite itself has no daemon service: raw-to-disposable-workspace-to-compact-memory atomicity remains an application transaction/workflow responsibility.

Collection retains priority over research through normal collector scheduling and low research CPU/I/O priority. Research service failure must not stop or bind the LIVE collector.

### V3.8.6 Operator and observability parity

Before the persistent LIVE_PAPER Execution canary starts, restore the useful V1/V2.8.5 operator visibility without restoring legacy runtime coupling:

* Execution writes rotating profile-scoped operations and trade-audit logs while systemd journal remains the service/startup forensic source;
* Observation writes separate rotating collector, control and research logs;
* Telegram is optional, best-effort and may never raise into capital management, collection, research, reconciliation or stop handling;
* Execution owns the single Telegram command-listener credential namespace; Observation does not consume `getUpdates` and may use separate optional credentials only for best-effort outbound notifications;
* Telegram commands queued while a worker was offline are discarded before the listener starts, so stale `/enable` cannot affect a restarted worker;
* Execution owns one editable trade panel.  It is created only after durable OPEN+verified protection exists, updated only for meaningful durable transitions (for example a verified stop improvement), edited closed from authoritative completed-execution history, and may show pending/recorded outcome ACK state;
* trade-panel metadata is durable but kept outside safety-critical execution state.  Missing/corrupt panel metadata may recreate a panel but can never block or alter capital truth;
* The current Execution Telegram menu has eight commands: /help, /status, /position, /recent, /pnl, /learning, /enable, /disable. Detailed research views remain server-side diagnostics. Status and learning are read-only; disable pauses new entries only, and enable remains subject to every safety gate. See OPERATIONS.md for separate notification and command chats.
* Observation exposes read-only status documents through the authenticated control API but owns no Telegram command listener or command menu; Observation order authority remains `NONE`;
* the 15-minute immature research-epoch wait state is not a Telegram alert.  Completed or unhealthy epochs may notify, avoiding heartbeat/WAIT spam;
* `nbotctl` exposes local position, health, recent-trade, PnL, entry-block and component-log inspection without adding a remote call to the OPEN-position hot path;
* emergency flatten remains a local capital command, not a Telegram command.

The V1 implementation is an operations reference only.  V3 keeps the useful operator semantics but does not restore V1 Strategy/learning coupling or shared mutable state.

### V3.8.7 LIVE/PAPER operational canary authority

Before a Research Champion exists, V3 may run a deliberately narrow **operational-only** LIVE/PAPER canary to prove the real-time proposal, independent Execution quote, local PaperExchange, trade-panel, restart/outage and outcome-delivery mechanics. This authority is:

`LIVE_PAPER_OPERATIONAL_CANARY_V1`

It is **not** a Research Champion, Paper Champion, economic authority, or LIVE order authority. Every proposal carries `research_evidence=false`, `economic_claim=false`, `research_champion=null`, and `expected_after_cost_net_r=null`. Therefore this subphase can close operational defects but can never satisfy the V3.8 economic acceptance gate.

The canary contract is intentionally narrow:

* proposal source is the freshest complete canonical LIVE point-in-time event only; stale/incomplete/reconstructed context remains NOT_READY;
* the top point-in-time universe-ranked symbol is used only as a deterministic operational target and direction is a deterministic hash, not a profitability claim;
* proposal TTL remains 30 seconds;
* Observation health must be authenticated, same-release, `READY`, order authority `NONE`, and expose exactly `LIVE_PAPER_OPERATIONAL_CANARY_V1`;
* Execution startup/restart always disables new entries; a human must send a fresh `/enable`;
* the first eligible FLAT proposal attempt consumes that `/enable` permission whether it opens, is vetoed, expires, or returns no trade; therefore approval cannot linger into a later market event;
* Execution still owns all current LIVE quote, spread, price-drift, risk, one-position, daily-risk, reconciliation and protection vetoes;
* PaperExchange remains the only capital adapter and Binance private writes remain structurally unavailable;
* Execution durably receipts the wire proposal before returning it and captures its own bid/ask/mid/spread immediately before entry evaluation; missing/corrupt operational context fails the proposal/outcome audit path closed;
* the eventual outcome carries proposal receive latency, Execution quote/spread, reference-to-Execution and reference-to-fill deterioration, paper R, and outcome-delivery timing in `experiment_context.execution_operational`;
* `nbot_admin.py live-paper-canary-report` is read-only and clearly reports `economic_claim=false` plus the reason economic comparison remains deferred.

A successful operational canary proves mechanics only. A later validated research authority must supply expected after-cost economics before V3.8 can be called ECONOMICALLY PROVEN or before V3.9 Paper Champion work begins.

## Runtime

```text
LIVE Binance market
     |                 \\
     v                  v
Observation          Execution own LIVE public feed
     |                  |
proposal                |
     +----------------->|
                        |
                 local current checks
                        |
                 PaperExchange entry
                        |
                 local paper stop/risk
                        |
                 paper close
                        |
outcome <---------------+
```

## Required comparisons

For every proposal/trade retain:

* research decision time;
* proposal generation time;
* Execution receive time;
* research reference price;
* Execution bid/ask/current midpoint;
* entry price deterioration;
* spread at Execution;
* veto reason if rejected;
* expected after-cost R;
* actual paper after-cost R;
* research exit-policy reference;
* actual operational exit result;
* MAE/MFE;
* winner capture;
* missed extension;
* holding time;
* proposal latency;
* outcome delivery latency.

## PAPER execution realism

PaperExchange should use Execution's actual LIVE quote stream and frozen, explicit assumptions for:

* entry slippage;
* exit slippage;
* fees;
* funding when applicable;
* stop fills/gaps;
* quantization/notional constraints.

Assumptions must be conservative enough to avoid flattering the strategy.

## Acceptance gate

Before long-term paper validation:

* \[ ] LIVE research authority valid and traceable;
* \[ ] no Testnet lineage in LIVE/PAPER records;
* \[ ] Execution independently uses LIVE market truth;
* \[ ] Binance private order writes unavailable;
* \[ ] one paper position maximum;
* \[ ] operational latency/degradation measured;
* \[ ] vetoes recorded correctly;
* \[ ] paper state survives restart;
* \[ ] open paper position survives Observation outage;
* \[ ] outcomes durable/idempotent;
* \[ ] research-vs-operational degradation quantified;
* \[ ] predeclared operational/economic tolerances met;
* \[ ] no unresolved defect invalidates evidence.

Suggested tag:

`v3.8-live-paper-operational-canary`

\---

# 25\. PHASE V3.9 — CONTINUOUS LEARNING AND LONG-TERM PAPER CHAMPION

## Goal

Prove that the complete system improves and remains useful over enough independent LIVE market conditions that a short lucky streak cannot justify real capital.

## V3.9.1 Expand challenger framework

After the ridge baseline is stable, challengers may include:

* alternative regularized linear models;
* ranking models;
* tree-based models;
* regime-aware selectors;
* calibrated classifiers when probability is a real objective;
* ensemble selectors;
* alternative feature sets;
* alternative exit-policy/champion combinations.

Every new family must first beat transparent baselines and the current champion under frozen evaluation rules.

## V3.9.2 Model registry and artifacts

Persist versioned model artifacts outside Execution.

Observation owns:

* artifact files;
* metadata;
* training/evaluation reports;
* registry;
* champion pointer;
* challenger state;
* rollback state.

Execution never loads arbitrary training artifacts merely because they exist. It receives only a versioned approved recommendation through the protocol.

## V3.9.3 Champion/challenger reevaluation

Use rolling chronological windows without rewriting historical final-test decisions.

Track:

* after-cost expectancy;
* confidence intervals;
* paired lift;
* drawdown;
* profit factor where useful;
* calibration/Brier score when applicable;
* winner capture;
* selection regret;
* symbol/date/regime concentration;
* drift/PSI or equivalent;
* cost stress;
* live operational degradation.

## V3.9.4 Market regimes

Evidence should eventually cover, as available:

* bullish trend;
* bearish trend;
* sideways/chop;
* low volatility;
* high volatility;
* sudden volatility shocks;
* risk-on/risk-off breadth;
* high/low funding environments;
* different liquidity conditions.

## V3.9.5 Operational regimes

Continue fault testing during paper validation:

* Observation restart;
* Execution restart;
* network interruption;
* public-feed reconnect;
* large DB growth;
* heavy training CPU;
* disk pressure alert;
* model promotion;
* model rollback;
* operator/Telegram failure.

## V3.9.6 Paper Champion

Only an authority that passes both research and sustained LIVE/PAPER evidence may be named:

`PAPER\_CHAMPION`

A Research Champion is not automatically a Paper Champion.

## Acceptance gate

The exact minimum sample/time/economic thresholds must be frozen before judging the gate.

At minimum require:

* \[ ] enough independent market events/trades;
* \[ ] positive after-cost expectancy with acceptable confidence;
* \[ ] controlled drawdown;
* \[ ] no single symbol/date/regime explains the result;
* \[ ] operational degradation remains within tolerance;
* \[ ] selection quality beats frozen weak baselines;
* \[ ] exit policy captures acceptable share of winners;
* \[ ] drift monitored;
* \[ ] no safety defect;
* \[ ] Testnet regression still passes on current release;
* \[ ] automatic rollback/authority controls proven if enabled.

Suggested tag:

`v3.9-paper-champion-proven`

\---

# 26\. PHASE V3.10 — LIVE\_TRADE ADAPTER AND MICRO REAL CAPITAL

## Goal

Introduce the first real-order authority only after V3.9 passes.

Important source-history fact:

Neither V1 nor V2 should be treated as proof that unrestricted LIVE real-order execution was already production-proven. V3 therefore treats the LIVE write adapter as a new final-stage capability derived from the already-proven Testnet exchange contract.

## V3.10.1 Build BinanceLiveExchange from the proven contract

Requirements:

* hard-pinned LIVE futures hosts;
* LIVE credentials only on Execution VPS;
* restricted API permissions;
* IP restriction where practical;
* no withdrawal permission;
* same durable client ID/recovery principles as Testnet;
* same protective-stop identity/recovery principles;
* authoritative LIVE close/accounting recovery;
* exchange mode checks (one-way/hedge assumptions);
* small maximum notional/risk hard caps.

## V3.10.2 Explicit arm gate

Required sequence:

```text
./nbotctl arm live-trade
 -> display REAL MONEY warning/profile/limits
 -> explicit operator confirmation
 -> create LIVE\_TRADING\_ARMED with release/profile identity
```

Arm file should become invalid when relevant release/profile/credential identity changes.

## V3.10.3 Pre-real regression

Before every initial real release:

* full automated suite;
* Testnet operational regression on the same Git release;
* LIVE\_PAPER regression on same release;
* reconcile/kill-switch test;
* emergency flatten test in non-real environment;
* pending outcome test;
* live adapter read-only preflight;
* operator review of risk caps.

## V3.10.4 Micro capital rules

* exactly one real position;
* tiny fixed risk;
* tiny max notional;
* no automatic increase in risk based on early wins;
* daily loss halt;
* hard kill switch;
* human supervision;
* every real outcome fed back to Observation with explicit REAL lineage;
* Observation still has no order credentials.

## V3.10.5 Real validation

Compare real fills/costs/latency with paper assumptions.

If real execution materially underperforms assumptions, return to LIVE\_PAPER and fix the model/assumptions; do not simply raise risk.

## Acceptance gate

Real capital may continue only while:

* \[ ] no execution safety defect;
* \[ ] reconciliation reliable;
* \[ ] real slippage/costs understood;
* \[ ] realized behavior within risk contract;
* \[ ] Paper Champion evidence still valid;
* \[ ] model/operational drift acceptable;
* \[ ] emergency controls proven;
* \[ ] capital limits remain micro until a later explicit roadmap revision.

Suggested tag:

`v3.10-micro-real-capital`

\---

# 27\. PHASE V3.11 — MATURE V3 BOT

V3 may be called mature only when all of these statements are true:

## Execution

* exactly one position maximum;
* independent Binance market truth;
* deterministic entry identity;
* ambiguous-order recovery;
* immediate verified protection;
* verified stop replacement;
* MAE/MFE and risk-contract monitoring;
* daily risk protection;
* reconciliation/restart recovery;
* emergency flatten;
* durable state/outcomes;
* no research/training dependency.

## Observation

* broad unbiased market collection;
* point-in-time evidence lineage;
* deterministic features;
* future-path labels without leakage;
* after-cost outcome research;
* multiple entry and exit competitors;
* chronological champion/challenger evaluation;
* continuous research/training isolated from collection;
* outcome feedback;
* no order authority.

## Communication

* authenticated/versioned;
* pull-only proposal path;
* stale/duplicate/wrong-profile rejection;
* durable idempotent outcomes;
* network failure blocks new entries, not open-position management.

## Operations

* `nbotctl` profiles reliable;
* same release across VPSs;
* Testnet canary reusable;
* LIVE/PAPER supported;
* LIVE/TRADE explicitly armed only after evidence gate;
* logs/health/Telegram role-separated;
* backup/audit/recovery documented.

\---

# 28\. EXECUTION ACCEPTANCE TEST MASTER LIST

The following tests are permanent regression requirements for safety-sensitive Execution changes.

## State / identity

* single Execution process lock;
* corrupt state fails closed;
* profile mismatch state rejected;
* processed proposal duplicate rejected;
* entry journal persisted before order;
* deterministic client ID;
* state survives restart.

## Entry

* valid long/short plan;
* stale quote rejected;
* wide spread rejected;
* reference drift rejected;
* insufficient balance rejected;
* invalid leverage rejected;
* duplicate proposal rejected;
* ambiguous order recovered;
* known unfilled entry cleared only with proof;
* ambiguous inflight remains fail closed.

## Post-fill

* notional tolerance;
* risk tolerance;
* slippage tolerance;
* initial stop placed;
* initial stop verified;
* failure leads to emergency flatten;
* emergency failure preserves open-risk state.

## Position

* MAE/MFE;
* integer-R control steps;
* no stop loosening;
* new stop verified before old removed;
* missing stop recovery;
* stop-breach settlement grace;
* risk-contract breach emergency;
* Observation unavailable while open;
* irrelevant symbols ignored early;
* latency tracked.

## Reconciliation

* flat/flat;
* open/open match;
* missing stop;
* wrong stop;
* local open/exchange flat;
* unexpected exchange open;
* multiple positions;
* hedge-mode mismatch;
* external close;
* manual close;
* stop close;
* orphan stop;
* close accounting source conflict;
* no fabricated PnL.

## Daily risk

* UTC rollover;
* realized update;
* peak update;
* daily floor;
* giveback halt;
* restart persistence.

## Outcomes

* deterministic ID;
* durable queue;
* retry on network fail;
* remove after valid ACK only;
* bad ACK retains pending;
* duplicate receiver idempotent;
* pending blocks next request.

\---

# 29\. OBSERVATION/RESEARCH ACCEPTANCE TEST MASTER LIST

## Raw evidence

* completed-candle clock;
* point-in-time context;
* partial capture atomic rejection;
* late context rejection;
* clock skew rejection;
* deterministic universe;
* gap detection;
* recovery marking;
* funding coverage;
* backup integrity;
* trailing downtime detection.

## Features

* no future reads;
* deterministic rebuild;
* definition hash frozen;
* incomplete history explicit;
* context-incomplete target handling;
* source digest integrity.

## Outcomes

* mature windows only;
* future label cache isolated;
* cost/funding coverage required;
* ambiguity explicit;
* deterministic rebuild;
* source mutation detected.

## Policies

* control + challengers registered;
* initial risk never widened;
* completed-bar decision timing;
* gap stop fill conservative;
* deterministic results;
* metrics complete;
* source mutation detected.

## Selection

* every eligible symbol/side example retained;
* baselines score every example;
* learned selector training strictly prior events;
* complete rank per event;
* no target leakage;
* deterministic rebuild;
* policy/feature source mutation detected.

## Champion

* validation/final windows frozen;
* benchmark chosen from validation only;
* post-test data cannot rewrite frozen decision;
* bootstrap/cost stress reproducible;
* leakage detected;
* failed candidate cannot create champion;
* passing candidate gets research-only authority;
* source/evaluation digest tampering detected.

\---

# 30\. TWO-VPS FAILURE TEST MASTER LIST

Permanent operational tests:

1. Power off Observation while Execution OPEN.
2. Block control-link network while OPEN.
3. Keep Observation down after close.
4. Restore Observation and deliver pending outcome exactly once.
5. Kill Execution while OPEN and restart.
6. Kill Execution during entry-inflight and restart.
7. Run heavy Observation database/research load while OPEN.
8. Send same proposal twice.
9. Send same outcome twice.
10. Send expired proposal.
11. Send wrong profile/environment proposal.
12. Send wrong lineage outcome.
13. Observation returns NO\_TRADE.
14. Observation returns NOT\_READY.
15. Auth token/certificate invalid.
16. Clock skew beyond allowed tolerance.
17. Observation DB unavailable/corrupt -> no proposal readiness.
18. Execution state corrupt -> no new entries.
19. Binance public feed issue on Observation -> recommendation NOT\_READY.
20. Binance Execution market truth stale -> no entry.
21. Testnet and LIVE Observation services run concurrently with no mutable collision.
22. Telegram/operator notification failure does not affect workers.

\---

# 31\. LOGGING, HEALTH AND TRACEABILITY

Every executed/paper/Testnet selected trade must be traceable from idea to outcome.

Retain at minimum:

* Git release SHA/tag;
* profile;
* role;
* protocol version;
* request ID;
* proposal ID;
* outcome ID;
* market environment;
* evidence lineage;
* market event ID;
* feature version;
* signal versions;
* selector/model/champion version;
* entry authority;
* exit policy;
* proposal generated/expiry timestamps;
* Execution receive timestamp;
* Observation reference price;
* Execution bid/ask/current quote;
* veto reason or acceptance;
* risk/notional/leverage;
* entry order/client ID;
* stop identities;
* entry fill;
* exit fill/reason;
* realized PnL/R;
* MAE/MFE;
* slippage/cost metrics;
* management latency;
* outcome delivery attempts/ACK.

We must be able to answer later:

* Why did Observation prefer this trade?
* What alternatives existed?
* Which model/policy/version made the decision?
* What evidence lineage produced it?
* Did Execution veto or enter it?
* What did Execution know at entry time?
* What exact safety gates passed?
* What happened during the position?
* Was close evidence authoritative?
* Was the outcome recorded exactly once?

\---

# 32\. OPERATOR AND TELEGRAM RESPONSIBILITIES

## Execution notifications

Focus on capital/safety:

* worker status;
* profile;
* entries enabled/disabled;
* open position;
* entry accepted/rejected;
* stop/protection status;
* emergency event;
* reconciliation issue;
* completed trade;
* daily halt;
* health latency warning;
* live-trade arm/disarm.

## Observation notifications

Focus on intelligence/data:

* collector health;
* event gaps;
* database/audit status;
* universe size;
* recommendation readiness;
* current research authority;
* training/challenger status;
* champion promotion/rejection;
* drift/rollback;
* outcome receiver health.

No Telegram failure may raise into the capital or observation worker main loops.

\---

# 33\. RESOURCE AND PERFORMANCE RULES

## Execution VPS

Execution must remain deliberately small and boring.

Measure:

* CPU;
* RAM;
* loop latency;
* quote freshness;
* stop update latency;
* REST/user-stream health;
* disk persistence latency.

No training or broad-market scan is allowed.

## Observation VPS

Observation may use more CPU/RAM, but realtime collection has priority over training.

Training/research processes should have bounded concurrency/resource priority.

When LIVE and Testnet observation run together during TESTNET\_TRADE:

* separate process identities;
* separate DBs;
* separate locks/logs/ports;
* monitor LIVE capture delay/gaps;
* throttle nonessential Testnet/research workload if canonical LIVE capture degrades.

\---

# 34\. GIT AND RELEASE POLICY

## Main branch

`main` is the canonical integrated V3 source.

Avoid long-lived divergent branches.

Short-lived local/feature branches may be used if they are merged promptly, but phase completion always means the exact passing source is on `main` and tagged.

## Required phase tags

Suggested:

```text
v3.0-clean-foundation
v3.1-execution-core-parity
v3.2-execution-testnet-mechanical-proven
v3.3-observation-evidence-foundation
v3.4-research-learning-foundation
v3.5-recommendation-protocol-ready
v3.6-two-vps-dry-integration
v3.7-testnet-e2e-operational-proven
v3.8-live-paper-operational-canary
v3.9-paper-champion-proven
v3.10-micro-real-capital
```

## Release rule

Never deploy an uncommitted dirty working tree as the intended canonical runtime.

`nbotctl status` should print release SHA/tag on both workers.

\---

# 35\. DEPLOYMENT ORDER FOR EVERY PHASE

For implementation phases:

1. change code locally/repo;
2. run targeted tests;
3. run full automated suite;
4. inspect diff;
5. commit;
6. push `main`;
7. deploy same commit to relevant VPS;
8. run `nbotctl doctor`;
9. run phase-specific physical validation;
10. preserve evidence/report;
11. tag only after acceptance gate.

A tag means the gate passed, not merely that development stopped.

\---

# 36\. ANTI-DRIFT CHANGE CONTROL

Any proposed change must be classified before implementation.

## Architecture change

Examples:

* worker responsibility;
* state ownership;
* protocol;
* environment/profile model.

Requires roadmap update before code.

## Execution safety change

Examples:

* risk;
* leverage;
* slippage tolerance;
* stop behavior;
* emergency behavior;
* daily halt.

Requires:

* explicit config/version change;
* execution parity tests;
* Testnet regression before LIVE/PAPER or LIVE/TRADE.

## Research change

Examples:

* feature definition;
* target;
* model;
* exit policy;
* evaluation gate.

Requires new immutable version and chronological evaluation. Never mutate an evaluated definition under the same version string.

## Operational change

Examples:

* systemd;
* logging;
* Telegram;
* backup;
* `nbotctl`.

Must not change trading/research semantics silently.

\---

# 37\. DEFINITION OF DONE FOR THE TWO-WORKER ARCHITECTURE

The architecture is considered proven only when both statements are physically true:

> \*\*I can power off the Observation VPS while Execution has an open position, and Execution continues receiving its own market data, manages protection/risk/trailing correctly, closes/reconciles safely, stores the outcome, and refuses to start another trade until Observation is available and the outcome is ACKed.\*\*

and:

> \*\*I can power off the Execution VPS and Observation continues collecting the market, building research evidence, evaluating virtual alternatives/challengers, and training without needing Execution to be alive.\*\*

\---

# 38\. DEFINITION OF DONE FOR THE SELF-LEARNING SYSTEM

V3 is genuinely self-improving only when:

1. new LIVE market events enter an unbiased canonical dataset;
2. future outcomes mature without look-ahead leakage;
3. entry/exit alternatives are evaluated on comparable evidence;
4. challengers train only on chronological past;
5. unseen validation/test evidence determines promotion;
6. promotions/rollbacks are recorded and reversible;
7. the research authority can change without modifying Execution safety code;
8. LIVE/PAPER evidence confirms that research improvement survives operation;
9. Execution outcomes feed back durably;
10. the system can explain which authority produced each recommendation.

Merely retraining a model is not self-learning if the model cannot prove improvement.

\---

# 39\. SIMPLE MENTAL MODEL

Think of V3 as three layers.

## Layer 1 — Truth

```text
Market
 -> canonical evidence
 -> future path
 -> costs
```

## Layer 2 — Intelligence

```text
features
 -> signals
 -> entry competitors
 -> exit competitors
 -> challengers
 -> walk-forward evidence
 -> approved recommendation authority
```

## Layer 3 — Capital

```text
Execution asks while flat
 -> receives advisory proposal
 -> checks current truth/risk locally
 -> enters safely or vetoes
 -> protects/manages one position
 -> returns durable outcome
```

Truth is not controlled by the strategy.

Intelligence cannot control orders.

Capital management does not train models.

\---

# 40\. FINAL IMPLEMENTATION PRIORITY ORDER

If there is ever doubt about what to do next, use this order:

1. Freeze/tag pre-V3 source references.
2. Clean/rebuild both VPS runtimes.
3. Build V3 repo/profile/`nbotctl` foundation.
4. Build Execution state/risk/exchange contracts.
5. Reimplement V1/V2.8.5 Execution safety parity.
6. Deploy Execution first.
7. Prove standalone Binance Testnet mechanical execution and recovery.
8. Build Observation point-in-time evidence collector.
9. Deploy fresh LIVE Observation and begin accumulating data.
10. Build V2-style features/signals/outcomes.
11. Build exit-policy lab.
12. Build entry-selection lab.
13. Build Research Champion/challenger foundation.
14. Freeze V3 protocol/recommendation contract.
15. Build Observation control service and Execution remote client.
16. Run two-VPS dry handshake with orders disarmed.
17. Run full TESTNET\_TRADE end-to-end canary and fault campaign.
18. Keep Testnet capability permanently available for regression.
19. Switch to LIVE\_PAPER only after Testnet operational gate passes.
20. Measure research-vs-operational degradation.
21. Run long-term LIVE/PAPER Champion validation.
22. Add continuous challenger training/promotion/rollback only with evidence gates.
23. Build/enable LIVE order adapter only after Paper Champion.
24. Rerun Testnet + LIVE/PAPER regressions on same release.
25. Enable tiny explicitly armed LIVE\_TRADE risk.
26. Increase capability/risk only under a later explicit roadmap revision.

\---

# 41\. FINAL V3 SUCCESS STATEMENT

NBOT V3 succeeds when the following is true:

> \*\*Observation independently watches the broad market, stores honest point-in-time evidence, evaluates what happened afterward, compares entry and exit alternatives, trains/evaluates challengers chronologically, and maintains only evidence-backed recommendation authority. Execution independently owns one position, current market truth, risk, orders, stops, reconciliation and emergency safety. The two communicate only at the capital boundary. Testnet continuously proves the machine; LIVE+PAPER proves the edge; only long proven evidence permits tiny real capital.\*\*

That is the architecture V3 must implement. Anything that weakens these boundaries is architectural drift and requires an explicit roadmap change before implementation.

\---

# 42\. CURRENT V3 STARTING STATUS

At the moment this roadmap is adopted:

```text
V1 snapshot                     AVAILABLE AS REFERENCE
V2.8.5 snapshot                 AVAILABLE AS REFERENCE
V2 roadmap                      AVAILABLE AS REFERENCE
V3 runtime databases            INTENTIONALLY NONE / TO START FRESH
V3 Execution                    NOT YET BUILT
V3 Observation                  NOT YET BUILT
V3 communication                NOT YET BUILT
V3 Testnet end-to-end           NOT YET RUN
V3 LIVE+PAPER                   NOT YET RUN
V3 Paper Champion               NOT YET PROVEN
V3 real capital                 FORBIDDEN

NEXT PHASE: V3.0 CLEAN FOUNDATION
THEN:       V3.1 EXECUTION CORE
THEN:       V3.2 DEPLOY EXECUTION FIRST
```

**END OF NBOT V3 ROADMAP**
