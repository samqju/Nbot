# NBOT V5 G1f isolated observation-only operator gate

## Authority and isolation

This workflow is **public-market observation only**. It has no Binance keys, order route, paper portfolio, champion promotion, execution tunnel, model training or application privilege to any legacy V4 database. It runs Python from \`/home/ubuntu/nbot_v5_sandbox\` and writes **only** to the owner-controlled \`/home/ubuntu/nbot_v5_data/g1f_observe.sqlite\` SQLite journal and its WAL/SHM sidecars.

V4 Observation targets, timers and services must stay inactive. The Execution VPS and its two pre-existing live-paper services must remain untouched until a separately approved transition.

## Required preflight (stop on any failure)

1. Confirm Observation VPS hostname \`base\`, logged-in \`ubuntu\`, expected clean V5 branch and pinned code commit.
2. Confirm all seven legacy Observation units inactive:
   \`nbot-observation-live.service\`, \`nbot-observation-live-paper-control.service\`, \`nbot-v4-research.service\`, \`nbot-v4-paper-contest.service\`, \`nbot-v4-training.timer\`, \`nbot-research-epoch.timer\`, \`nbot-observer.target\`.
3. The isolated writable DB directory \`/home/ubuntu/nbot_v5_data\` must already exist, belong to ubuntu, and not be a symlink. Never reset or delete old database/backups.
4. Run all GitHub/VPS G1f safety tests. Conduct a bounded one-shot 50-coin WSS+REST smoke before activating any durable service.
5. Check memory and disk. Do not start a second concurrent collector against the same SQLite file.
6. Confirm unit file is byte-for-byte identical to the file reviewed and tested in \`deploy/v5/nbot-v5-observation-only.service\`.

## Controlled service

Unit file: \`deploy/v5/nbot-v5-observation-only.service\`.

Service name: \`nbot-v5-observation-only.service\`. Runs under non-root user \`ubuntu\`, uses only public Binance USD-M REST and public WSS, with \`MemoryMax=200M\`, \`CPUQuota=75%\`, restricted writable paths, \`NoNewPrivileges\`, and **Restart=no** (fail-closed). It uses the isolated V5 Python virtual environment with pinned \`websockets==17.2\`.

If authorized after full preflight, install the reviewed unit, \`daemon-reload\`, and start **only this unit**. Do not restart/enable/unmask or change any legacy V4/Execution unit. For emergency rollback:

\`\`\`sh
sudo systemctl stop nbot-v5-observation-only.service
sudo systemctl disable nbot-v5-observation-only.service
\`\`\`

Do not delete the V5 SQLite journal, WAL/SHM or evidence after stopping; that destroys restart/audit provenance. Check journal via \`journalctl -u nbot-v5-observation-only.service --no-pager\` and \`systemctl status\`. Only run read-only SQLite inspection after the service has closed the database cleanly. Keep full event and incident evidence for owner review.

## Research fail-closed constraints

- Persist exactly one time-stamped coin universe snapshot per active database. If eligible symbols change on restart, HOLD; require separately reviewed cohort rotation before a new database/window. Today's coin ranking never becomes historical eligibility.
- Select at most 50 currently TRADING USDT perpetual coins plus BTC context. Each coin holds at most the last 96 complete five-minute candles and one latest depth-500ms quote/trade cursor. No raw quote history is accumulated.
- Only Binance WSS \`k.x=true\` can create a WSS_FINAL candle; REST may bootstrap and repair **candles**, never missing trades/quotes.
- Per event, reconcile the same completed 5m candle against three ordered REST snapshots. Do not overwrite original WSS data, automatically clear revised REST/source quarantine, or mark missing evidence as valid.
- Every eligible coin's LONG and SHORT candidate observation slot must remain visible. Disputed, stale, wide-spread, missing quote/trade/BTC context or incomplete source yields \`UNSCORABLE\` and disables pattern evidence.
- On any unsolved BTC conflict or inadequate cross-section, all directional observation states HOLD. No Champion/Challenger, research label maturation, paper/live execution or real order authority exists at this milestone.
- A process/crash restart records offline intervals as unscorable. If more than 96 consecutive 5-minute events are missing, HOLD for review rather than manufacturing past data.
- Bounded WSS reconnects 2/5/12 seconds and a rolling 5-minute frame budget. Any dropped trade-ID sequence or interrupted cohort remains unverified. No default success on network reconnection.
- Reports show \`research_ready=false\`, \`training_labels_created=0\` and \`order_authority=NONE\` regardless of observed patterns.

## Acceptance limit

A short live process start and even one correctly stored 5m event are **not** 24-hour continuity proof, verified outcome-label maturation, cross-regime validation, or authorization to train/trade. A long-duration passive soak and restart/fault-injection evidence remain future gates. Keep production research/trading readiness on HOLD.
