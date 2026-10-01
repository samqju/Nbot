# Seven safety fixes

Historical change and verification record: the dated counts and deployment
statements below describe the safety-fix checkpoint, not today's GitHub or VPS
state. The later learner release is `9fff54c`; its verification and upgrade
limits are in the [small-VPS guide](SMALL_VPS_LEARNER.md). Use the
[beginner guide](TWO_VPS_BEGINNER_GUIDE.md) for current deployment. Preserve the
original test results; do not treat them as fresh-server acceptance.

This work keeps the one-position design and existing execution-authority gates.
It does not assess profitability or enable real-money trading.

## What changed

1. **Uncertain orders:** the exact order identity remains journaled. A timed-out
   request followed by “not found” is not treated as permission to place another
   trade. Only proven terminal states permit automatic resolution.
2. **Partial fills and closes:** partial exposure is protected before cancelling
   the unfilled remainder. Close accounting requires the full expected quantity
   and actual order-linked trade records. Profit in the same time bucket is no
   longer accepted as evidence. Fill pagination checks identity and progress.
3. **Restart:** state transitions share a lock, startup reloads state after
   acquiring runtime ownership, and recovery refreshes exchange position truth.
   Historical fills are recovered even when the exchange has already closed the
   position. Completed outcomes remain durable until acknowledged; retries reuse
   the same saved delivery envelope.
4. **Binance pauses:** request admission and exchange cooldown deadlines are
   recorded in SQLite. Restarting the process does not reset the pause. Corrupt
   or unavailable budget storage blocks requests. The default file is
   `data/common/binance_budget.sqlite` under the source root. Keep this file
   across deployments, or set `NBOT_BINANCE_BUDGET_PATH` to a stable shared path.
   Processes on different machines still need independent rate-limit headroom.
5. **Learning:** predictions use only labels whose entire 48-bar future horizon
   has elapsed. Centered running statistics avoid raw-moment cancellation.
   Interrupted builds resume scoring already committed examples. New challenger
   evaluations start after model availability and use examples with disjoint
   future horizons. Model artifacts include runtime and source information.
6. **Saved learning:** a copy-only upgrade tool replays verified archived training
   examples. It retains immutable evidence and archives old model/governance
   artifacts and promotion results instead of treating old conclusions as newly
   validated. The continuous evaluator uses a new artifact namespace.
7. **Tests:** regressions cover concurrent state writes, interrupted learning,
   delayed labels, persisted cooldowns, partial fills, missing order responses,
   restart/close recovery, paginated fills, upgrade preservation, and lost ACKs.

## Upgrade existing permanent research memory

Stop research writers for the upgrade. Preserve the existing deployment and
database. Create a NEW output path; the tool refuses to overwrite an existing
file or modify the source in place:

```sh
python3 -m nbot.observation.migrate_causal \
  --source /absolute/path/research_memory.db \
  --output /absolute/path/research_memory.causal.db
```

Review the replay counts and source digest before choosing the upgraded copy
for deployment. Old disposable research workspaces must be recreated by the
epoch worker, using the upgraded permanent memory as the seed. Do not relabel
old selection tables as the new version. This command expects the permanent
`research_memory_events` archive schema; a pre-archive/raw-only database requires
a separate import and is rejected rather than guessed. Execution position,
history, outbox, receipts, and order identifiers are not part of this migration.

Evaluation now takes longer to gather enough genuinely future examples. This
does not add more positions or grant a model trading authority.

## Linux verification

Use a separate source copy with no credentials, arm files, or production data.
Mark the command entry points executable. The status-command tests expect an
`.nbot-role` containing `OBSERVATION` in that isolated copy.

```sh
python3 -m compileall -q nbot tests
nice -n 15 python3 -m unittest discover -s tests -q
```

The Linux suite uses simulated exchanges; it does not establish authenticated
Binance testnet acceptance or profitability. Do not use the test directory as
a replacement for the running deployment.

## Verified result — 29 September 2026

All **1,026 tests passed** on the user's Linux VPS with Python 3.12.3, in a
separate source-only test directory. Runtime: 265.111 seconds. Compilation and
direct launch of the admin help command also passed. The report is saved at
`logs/audit/linux-verified.txt`. A separate Windows run of the portable safety,
migration, and challenger checks passed 29 tests.

The installed VPS bot, its configuration, credentials, and saved trading data
were not replaced. No authenticated Binance trading test or production data
migration was performed. Deployment is a separate step.
