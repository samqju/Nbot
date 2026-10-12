# Enforced V4 paper Champion promotion

Reaching the contest's frozen scored-trade checkpoint makes it review-ready; it does not make a
model Champion. `v4_paper_admin.py promote` rechecks all gates at the moment of
promotion. There is no override flag and no automatic promotion.

These are conservative engineering defaults for paper experiments, not a
calibrated statistical significance test or proof of real-money profitability.
They are versioned in `nbot/observation/v4_promotion.py` as
`NBOT_V4_PAPER_PROMOTION_V1` for 100-trade exams and `NBOT_V4_PAPER_PROMOTION_V2`
for new 50-trade head-to-head contests. Changing them requires a reviewed code change;
environment variables cannot lower them.

## Required evidence and performance

| Requirement | Enforced threshold |
|---|---|
| Completed scored trades | Baseline exams: 100. New head-to-head contests: 50 per model. Existing contests retain their original checkpoint. |
| Open positions at review | None |
| After-cost average | Challenger at least +0.10 R per trade |
| Positive outcomes | Challenger at least 50% |
| Maximum realized drawdown | Challenger at most 10 R |
| Worst individual outcome | Challenger no worse than -3 R |
| Actual forward trading span | At least 72 hours, measured first entry to last exit |
| Time coverage | Entries on at least 3 UTC days and in at least 6 four-hour UTC blocks |
| Block consistency | At least half of occupied blocks have positive total net R |
| Lucky-block stress | Average remains positive after removing the most profitable block |
| Chronological consistency | Both halves of the entry-ordered exam have positive average net R |
| LONG and SHORT support | At least 20 scored trades each; each side has positive average net R |
| Volatility coverage | At least 2 LOW/NORMAL/HIGH regimes have at least 10 trades each; every regime with that support has positive average net R |
| Continuity | Unscorable / (scored + unscorable) at most 20% |

Volatility regimes use the immutable entry feature `volatility_percentile`:
LOW <= 0.25, HIGH >= 0.75, NORMAL otherwise. This is a limited regime proxy,
not proof of coverage of all bull/bear/trend conditions.

Every scored trade must match its immutable decision and `AGGTRADE_RESOLVED`
outcome in `paper_ledger.db`, including net R, exit time/reason, source digest,
frozen model identity, decision feature digest, contract and `order_authority=NONE`.
Missing/nonfinite evidence, overlapping positions, outcomes outside the contest,
changed artifacts, stale generation state, unexpected roles, and mismatched
cached counters block promotion. Historical research results and older paper
contests cannot replace fresh exam evidence.

## Replacing an existing Champion

In addition to all absolute Challenger requirements:

- Both models must reach the checkpoint frozen for the current fresh contest (50 for new head-to-head contests).
- Challenger average net R must exceed Champion average by at least 0.10 R.
- Challenger drawdown and worst outcome must be no worse than Champion's.
- Both models must have entries in at least six common four-hour blocks.
- Total Challenger advantage must remain positive after excluding its best
  advantage block. Block comparison uses total net R on a shared UTC grid;
  a block with no trades for a model contributes zero.

A model cannot become Champion just by losing less money than another loser,
tying the incumbent, or winning in one lucky period.

## First Champion and unsuccessful exams

When no Champion exists, the next research-qualified model runs a solo
`BASELINE_EXAM`. Gen-2 does not need Gen-3 as an opponent. Only Gen-1 has the
special research `BASELINE_READY` exemption; later generations still need
`CHALLENGER_READY`. Every generation must pass the same paper promotion gates.

An exam stops opening positions at its frozen checkpoint. If its evidence is
too short, one-sided, narrow, or unprofitable, waiting after the exam cannot
manufacture eligibility. It remains review-required and cannot promote. The
operator can reject it, allowing the next qualified generation to take its turn.
This change does not reopen, erase, or alter the active Gen-1 exam or its artifact.

## Operator commands and durable review

```bash
cd /home/ubuntu/Nbot
.venv/bin/python deploy/observation/v4_paper_admin.py status
.venv/bin/python deploy/observation/v4_paper_admin.py promote
.venv/bin/python deploy/observation/v4_paper_admin.py reject
```

`status` includes `promotion_review.eligible`, versioned policy, metrics, and
explicit `failed_checks`. A blocked `promote` prints its reasons and exits 1
without changing contest/model state. A prior successful status report never
authorizes promotion after the model, state, or evidence changes.

Successful review stores its proof and the Champion/Challenger state change in
one generation-database transaction. A durable `paper_review_outbox` then closes
the contest idempotently. The runtime recovers unfinished closure before queue
assignment; training cannot fill the Challenger slot while a review is pending.
This avoids relying on atomic multi-database commits under SQLite WAL.

The audit table is an additive schema change, preserving existing models,
history, databases, and pending paths. Restarting the paper service can still
invalidate an open path under its existing continuity contract: deployment
must account for that separately. Do not deploy during the active exam merely
because this patch is ready.

## Telegram approval and Execution recommendations

On the existing Execution bot, `/champion` shows the active contest, completed
trades, failed gates and exact approval/rejection commands. The live-paper menu
registers all ten commands: `/help`, `/status`, `/position`, `/recent`, `/pnl`,
`/learning`, `/enable`, `/disable`, `/champion`, `/wss`. `/help` uses that same
list. Other Execution modes keep the eight base commands.

`/learning` also shows exam
progress. The authorized operator receives a channel notification when the
contest reaches review. Approval is never automatic.

For example, `/champion approve 1 1` approves Gen-1 in contest 1 only if every
gate still passes. `/champion reject 1 1` rejects that same exam and frees the
queue. Copy the command from the current report; old contest/generation
identities are refused under the database locks. The existing Telegram listener
accepts only the configured command chat and operator user ID. The review API
also requires the existing control bearer token and a live-paper target.
Notification delivery is retried until successful and then deduplicated durably.

Run the standalone live-paper control with `--selection v4`. It serves only the
frozen model recorded by a successful gated paper promotion, checking artifact
hashes against the stored review proof. No Champion means
`V4_WAIT_FOR_APPROVED_PAPER_CHAMPION`, with no older-model fallback. The
highest finite-scored opportunity (including a negative raw ranking score)
may produce one frozen proposal per completed live event, matching the paper
contest's top-ranked-candidate selection. LightGBM LambdaRank scores are
relative ranks, **not** after-cost profit forecasts: the proposal's
`expected_after_cost_net_r` is null unless a separately validated
calibration is implemented. Profitability remains assessed from real forward
paper outcomes under the promotion gates. Quotes and proposals retain the
existing 30-second freshness limit. Model replacement waits for the next event. Execution still
owns spread, risk, daily limits, entry permission, and position management.
V4 uses the existing LIVE/PAPER learned authority envelope with explicit V4
generation, model digest, and approved contest attribution. It is forbidden in
the live-trade profile. Promotion never enables entries or real-money trading.

WSS reconnect logs now include stream kind, connection duration, received
messages, time since the last message, queue depth, dropped messages, close
code, exception type, and retry delay. These identify transport, freshness, and
backpressure symptoms; they do not claim a reconnect root cause or change retry
behavior. A running process receives the diagnostics after a safe restart.
Use `/wss` on the Execution bot, or
`.venv/bin/python deploy/observation/wss_diagnosis.py` on Observation, for a
bounded read-only summary of existing journals. This works immediately without
restarting research or Gen-1. Old runtime messages are explicitly unlabelled;
new per-connection fields appear only after those processes safely load the
new transport code.
Do not restart research or the contest while doing so would discard active
paths. Code installed on disk and the version loaded by each service must be
reported separately during a staged deployment.
