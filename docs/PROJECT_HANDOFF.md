# NBOT project handover

Saved: 11 October 2026. Read this file first when continuing the project in a new chat.

This is a consolidated project record, not a verbatim chat transcript or proof of every historical claim. It preserves the user's requirements, the major development stages, verified recent changes, deployment facts and remaining work. The repository, linked documents, tests and running services are the sources of truth. Recheck live status before making operational decisions.

## What the owner wants

The owner is not a programmer. Explain decisions in simple English, keep work economical, and complete authorized fixes rather than stopping at a plan. The intended product is a small autonomous Binance trading and learning bot, with one main position at a time. It is currently an experiment in mainnet-paper mode. Do not promise profitability.

The owner first requested a broad correctness/architecture audit, with profitability outside that audit's scope. Subsequent work expanded into execution fixes, learning, deployment and documentation. The complete original per-issue audit is not reproduced here; do not treat every initial audit item as proven closed merely because tests passed.

Standing workflow preferences:

- Publish code changes to GitHub first, validate them, then deploy the tested release to both VPSs.
- Keep both roles on matching runtime releases and protocol versions.
- After a successful deployment, delete only temporary branches that are confirmed merged; preserve other work.
- Preserve learning databases, models, trade history and private configuration during updates.
- Do not enable actual mainnet trading merely because paper tests pass.
- Use modest settings for the actual learning server, which has about 1 GB RAM, even though a larger server was previously discussed.

## System and operating modes

Two servers have separate jobs:

1. Observation/learning collects Binance public market data, builds features, records opportunities and simulated outcomes, trains models and supplies recommendations.
2. Execution/trading independently checks permission, fresh prices, spread, entry drift, risk and position state. It places or simulates trades and records outcomes. There is at most one main position.

Supported profiles are `testnet-trade` (actual Testnet orders), `live-paper` (simulated trades using mainnet market data), and `live-trade` (separately authorized bounded mainnet trial). There is no supported Testnet-paper mode. V3 automatic model replacement is paper-only; real-money inference does not automatically inherit the V3 paper learner.

Public research/learning must have no private exchange order authority. The inter-server control API is authenticated, listens on loopback, and is reached through a strict SSH tunnel. Preserve private-write restrictions and the mainnet activation checks.

## Development history and retained decisions

Early work covered execution lifecycle, reconciliation/recovery, duplicate-order protection, stale market-data handling, permissions, Telegram reporting, deployment and beginner documentation. Mainnet trading was later added as an explicit small trial after the owner's own testing, separately from the automatic economic/champion roadmap. Consult current code and mode documents for exact checks rather than relying on historical chat assurances.

The learning design evolved from price-model recommendations to fixed candidate setups and outcome feedback. The candidate library was expanded; current documents describe 24 versioned rules. The bot learns scores/rankings and model parameters from data. It does not invent unrestricted new strategies or rewrite its own code.

Settled main paper-trade outcomes and eligible shadow outcomes can influence paper feedback, rankings and loss pauses. The main position remains one; up to ten additional candidate shadow simulations are separately labelled. Actual execution profit/loss, paper/shadow feedback and detailed research-policy targets must not be silently mixed or described as equivalent.

The Execution menu has eight base commands: `/help`, `/status`, `/position`, `/recent`, `/pnl`, `/learning`, `/enable`, `/disable`. The live-paper menu also registers `/champion` and `/wss` (ten commands total), and `/help` uses the same profile-specific list. Some research/admin capabilities remain CLI-only. The owner previously changed notification destination settings; preserve current private configuration rather than replacing it with templates.

A prior repeated stale/invalid public-market timestamp error caused execution restart messages. Historical fixes were reported in the conversation, but the exact original patch is not reconstructed here. If this recurs, inspect current logs and data freshness rather than assuming the old cause.

An older learning VPS and its data were lost. A replacement was deployed on Oracle with the tiny profile. Do not assume the missing server's history can be recovered from this handover.

## Current detailed V3 paper learner

PR #14 introduced automatic paper learning from detailed accepted and rejected opportunities:

- Freeze decision-time features, costs and stop geometry; do not build training features using future information.
- Broad research scans target 100 symbols, with high-resolution public WebSocket observation of at most 20.
- Admit hypotheses for one hour, then drain their existing paths, up to four hours. Do not reconnect solely to rotate the symbol cohort.
- Interrupted/non-continuous paths are invalidated rather than treated as complete observations.
- Only verified `AGGTRADE_RESOLVED` outcomes meeting the current feature/data contract are eligible. Old records missing required fields are excluded, not invented or erased.
- Examples from the same event share total weight one. Preserve chronology purging and disjoint evaluation windows.
- Current documented requirements include 80 training events, ten independent historical diagnostic events, and twenty later independent evaluation events. Independent event spacing is about four hours five minutes; read configuration for the authoritative values.
- The twenty later events form two windows. Gates include prediction quality, simulated costs, drawdown and one-position capacity.
- Research-policy targets are simulated after-cost R outcomes, not actual execution PnL. Paper results do not establish real-money profitability.
- Collection/training are bounded: maximum rows/events and hypothesis caps; one ML training thread on the small VPS.

PR #15 corrected an important replacement-model blocker. Freeze the exact actual paper incumbent at candidate creation: active V3, otherwise eligible V2 plus the exact Ridge component used by its blend, otherwise Ridge. Freeze artifact keys, digests and scoring gates. Both future windows must beat that exact incumbent, including at least 0.1 R net improvement per window. If the incumbent changes, reject the old evaluation and require a new comparison. Legacy candidates without this proof cannot activate. Check again before activation/crash recovery. Regression tests cover beating Ridge but losing to V2, a changing V2/Ridge incumbent, missing proof, ties and disabled ML.

Do not weaken this rule: a candidate beating Ridge is insufficient if the model actually being replaced is V2.

PR #16 corrected Telegram `/enable` for paper mode. Previously it rejected permission whenever learning was not READY. Now paper `/enable` allows the bot to wait for a valid recommendation. Freshness, risk, proposal and execution checks still apply before entry. Real-money arming/readiness checks remain. Enabling entries never forces a trade.

PR #17 corrected slow `/learning` reports:

- A report previously took about 24 seconds, exceeding the 15-second client deadline.
- Legacy challenger future-progress reporting now uses bounded, indexed, read-only timestamp lookups without decompressing market payloads. These counts are informational; actual evaluation still verifies selected archives.
- Actual evaluation skips overlapping timestamps before decoding, preserving the same selected event chronology while avoiding wasted CPU and RAM.
- Learning reports have a 30-second cache, copied responses, one builder at a time, no cached failures and a generation timestamp.
- Execution health and trade requests are not served from that informational cache.
- The small-VPS guide explains these changes.

## Verified deployment checkpoint

The latest deployed runtime code at this checkpoint is:

`98e56724ff57475745a272086d694991fff173fe`

It merged PR #17. Tested PR head: `389dc776503d0eaeba32468fd6644bd0e710581c`.

Both VPSs were updated and restarted on 11 October 2026. Cluster startup passed with matching releases/protocol. Paper entries were confirmed enabled, execution alive/ready, no open main position, no entry in flight, no pending outcomes and no recovery-critical state at verification. This is a historical snapshot, not a live-status guarantee.

Services on Observation:

- `nbot-observer.target`
- `nbot-observation-live.service` — public collector
- `nbot-observation-live-paper-control.service` — authenticated recommendations/status
- `nbot-research-epoch.timer` — research scheduler
- `nbot-research-epoch.service` — one-shot job; inactive after successful completion is normal

Services on Execution:

- `nbot-control-tunnel-live-paper.service`
- `nbot-execution-live-paper.service`

Research checks are normally scheduled about fifteen minutes after the preceding job completes. Market collection uses five-minute events. A scheduled check is not a promise of a ready model or trade.

The learning VPS has approximately 954 MB RAM and 2 GB swap. Existing resource overrides retain `NBOT_RESEARCH_MAX_HYPOTHESES=240` and `NBOT_ML_THREADS=1`. About 554 MB RAM was available after the latest restart; automatic restart counters were zero. This does not guarantee headroom under all future workloads. Do not run the full regression suite alongside production learning on this server.

Recent verification:

- PR #14: 1,314 Linux regression tests passed.
- PR #15: 1,321 Linux regression tests passed.
- PR #16: 1,324 Linux regression tests passed.
- PR #17: 1,330 Linux regression tests passed in 93.494 seconds.
- Learning report after deployment: initially 5.77 seconds locally; after full startup 2.21 seconds through the actual inter-server tunnel. Repeated cached request was under 0.01 seconds.
- Readiness and paper-entry permission are separate. NO TRADE can be correct when model confidence/edge is insufficient.

Private backups were made on each VPS before the deployment. Their locations are in the private local handover, not this public document. These are same-server backups, not off-server disaster recovery.

## Learning progress and unfinished work

At the last detailed check, there were 1,147 eligible detailed outcomes, including 1,130 rejected opportunities and 17 accepted opportunities; 25 training event groups and one independent diagnostic event were ready. No new V3 candidate or active V3 model existed yet. It still needed enough independent evidence. These counts will change; do not repeat them as current without checking.

There were also 107 main paper outcomes and 378 eligible legacy shadow outcomes in the feedback report. Legacy shadows and new tick-policy research are separate populations. One old challenger showed 39/40 later events. Do not confuse that legacy progress with the new V3 learner's twenty later events.

Older models remain stored. Deployment changes can make them incompatible with current inference. A current-release Ridge snapshot can provide the paper fallback after causal availability/fresh-event checks; V2 can be retrained for the current release. A compatible artifact existing now does not mean it was available before an earlier market event. Never bypass those temporal checks to force READY.

Outstanding priorities:

1. Let data collection run; confirm new high-resolution paths mature and invalid paths are labelled honestly.
2. Monitor CPU, available RAM, swap, disk, service restarts and report latency under actual training load.
3. Verify training begins after enough independent event groups, and inspect explicit rejection/wait reasons.
4. Verify a promoted V3 model actually beats the exact frozen paper incumbent in both later windows.
5. Continue paper testing and measure after-cost outcomes; profitable adaptation has not been proven.
6. Plan off-server backups if the owner wants protection against another VPS loss.
7. Re-audit any earlier concern that lacks a specific patch/test; a large passing test count is not proof the whole original audit is closed.

## Read these documents before editing

- [Enforced V4 paper Champion promotion](V4_CHAMPION_PROMOTION.md) — numerical
  promotion gates, immutable proof checks, failed-review behavior, and durable
  recovery. A model completing 100 trades is not automatically eligible.

- [Documentation index](DOCUMENTATION_INDEX.md)
- [Beginner two-VPS deployment guide](TWO_VPS_BEGINNER_GUIDE.md)
- [Three trading modes](TRADING_MODES.md)
- [Commands for all modes](ALL_MODES_COMMANDS.md)
- [Private environment-file setup](ENVIRONMENT_SETUP.md)
- [Detailed accepted/rejected outcome learning](DETAILED_OUTCOME_LEARNING.md)
- [Small learning VPS](SMALL_VPS_LEARNER.md)
- [Candidate library](CANDIDATE_LIBRARY.md)
- [Selective ML fallback](SELECTIVE_ML.md)
- [Paper outcome adaptation](PAPER_AUTO_LEARNING.md)
- [Shadow simulations](SHADOW_TRADING.md)
- [Operations](OPERATIONS.md)

Relevant recent PRs: [#14](https://github.com/samqju/Nbot/pull/14), [#15](https://github.com/samqju/Nbot/pull/15), [#16](https://github.com/samqju/Nbot/pull/16), [#17](https://github.com/samqju/Nbot/pull/17).

## Continuing safely in a new chat

Ask the new assistant to read this file and the documentation index, inspect current GitHub main, then check current service/model state. Public GitHub deliberately contains no VPS IPs, SSH keys, tokens or private configuration. The owner has a separate private local handover for authorized access.

This handover publication is documentation-only. It does not redeploy the servers or change their running release. Future code deployments must use the normal tested-release workflow. Never reset a working tree containing uncommitted changes to make it match this snapshot.
