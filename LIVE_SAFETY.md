# NBOT V6 — Owner-gated live mode (code staged, trading LOCKED)

**This is a future release mechanism, NOT permission to send real orders.** M1 has now passed its **technical 25-pair historical training/backtest test**, but that backtest **lost 135.64 simulated USDT**, and M2–M6 quality, safety and forward reliability are not accepted. No Binance API keys, owner Telegram IDs, approval records, model-release certificates or real-money configuration files are committed to Git. **M7 live authorization remains LOCKED**; the code only permits a future separately reviewed owner-armed configuration.

## Install guide and dependencies

For a **future, independent Ubuntu VPS**, start with [VPS_SETUP.md](VPS_SETUP.md) and [DEPENDENCIES.md](DEPENDENCIES.md). Those docs contain short step-by-step installation commands for **historical backtests and, after acceptance, paper-only trading**. They do **not** install Telegram or unlock live money.

The separate `live-locked` profile is deliberately excluded from the beginner's copy/paste starting commands. Before an M7-authorized live release, the owner and reviewer must independently provision a tested live configuration, verify Binance API restrictions, Telegram owner identity, read-only private approvals inside the container, exchange-side stop-market behavior, approved immutable model artifacts, and recovery from lost connectivity. Even then the owner must explicitly authorize the release. **Do not turn on real trading merely because Docker and the setup guide work.**

## Who controls what?

- **Freqtrade + owner-only Telegram (future):** report positions, profits and risk; /status, /count, /profit, /balance, /pause, /start. Restrict Telegram to the owner's *private positive user/chat ID* and exactly one authorized user. Telegram groups are forbidden in live mode.
- **Owner's VPS shell (future, separate):** temporary authorization to accept real entries, using a private approval file that is impossible for Telegram messages to create. The file must be mode 0600, inside the ignored live_private folder, and readable from the live container's read-only mount. Approval lasts at most 24 hours.
- **Freqtrade exchange logic:** executes and reconciles orders and on-exchange stop-market orders (once Binance futures compatibility/restarts are independently verified). Max one global trade, 1x leverage, stake at most 1,000 USDT, 2% initial stop. Actual slippage and losses may exceed nominal amounts.
- **FreqAI:** provides model predictions; invalid/stale predictions must be rejected. Its default live retraining uses the newest model automatically; ***this is not a qualified Champion/Challenger release process***. Shared/approved model versioning and rollback must pass M6 before M7 can be accepted.

## How live authorization is designed

A separate, opt-in Docker Compose profile **live-locked** was added. It contains no credentials and does not start automatically. It references an intentionally nonexistent untracked private configuration file at live_private/config.json (the regular repository always has dry_run=true). Both live_private and local account/trade data remain outside Git.

When a future reviewed private live configuration is loaded, the strategy requires all of the following:

1. Explicit dry_run=false and nbot_live_mode=true, independent of any Telegram command.
2. Not paper research; max_open_trades=1; futures isolated, 1x forced, positive fixed stake <=1,000 USDT, no manual forced entries, API server disabled, FreqAI enabled, nonzero model age expiry.
3. Private Binance exchange keys, supplied only through the untracked private file or secure runtime injection, never version control.
4. Private Telegram bot enabled, chat_id equal to one positive owner user ID, authorized_users containing **only that ID**, valid private token.
5. A matching live_private/approval.json file created only by the owner's VPS terminal: permission 0600, not a symlink, owner ID matches Telegram ID, model identifier matches the declared FreqAI identifier, issued/expiry timestamps valid, duration at most 24h.
6. Exchange-side stop-market order type enabled. Recheck approval, stop-market setting and 1,010-USDT quoted-notional ceiling before every real entry (1% tolerance for rounding). If approval expires/is revoked, new entries are refused; **existing trades must still be managed and exited by Freqtrade**.

Under **no circumstances** should anyone copy a live_private config into Git or claim the protected launch is operationally ready before M7. VPS operator/root accounts and the Telegram service provider remain part of the trust boundary; no software can truthfully guarantee that an attacker controlling the server can never override authorization.

## Future release setup (DOCUMENTED, NOT EXECUTED)

- Complete M1 historical import/training/backtesting and M2/M3 independent after-cost quality checks.
- Complete M4 long-running paper operation and M5 exchange universe/position safety.
- Complete M6 approved model version governance; validate whether FreqAI producer/consumer and native model snapshots meet the controlled release requirement. Do not let unreviewed latest-model retraining automatically trade with money.
- Test Binance FUTURES account permissions and API/IP restrictions, one-trade exchange reconciliation, stoploss_on_exchange market behavior, partial fills, outages, liquidation scenarios, funding and stop/restart recovery. Use a dedicated account with withdrawal permission disabled. Use a small staged risk budget independently approved by owner.
- Supply private config and Telegram owner ID through an owner-controlled server login, *after* all gates. Owner-only Telegram commands are operational controls, never a dry_run-to-live toggle.
- **Future owner terminal script only**: scripts/owner_live_approval.py --arm --owner-telegram-id ID --model-identifier APPROVED_ID --hours 8. The script requires typing the entire real-risk acceptance phrase interactively. File is temporary and ignored by Git. --revoke removes the approval immediately for new entries; it does not close a real position. --status reports expiry.
- Even if armed, do not start the live profile unless M7 is expressly signed off. The code deliberately provides no Telegram /enable_live command and no implicit auto-arm after restart.

**Operational nuance:** Freqtrade Telegram /pause stops new entries while preserving management of open positions. Telegram /stop stops the trader and may leave position management needing a separately verified exit plan. Pause is NOT persistent across restarts, therefore this strategy rechecks arm on *every* live entry.

## Evidence

Current scope: offline code/CI tests of fail-closed owner gate and official Freqtrade strategy discovery, **NOT** a launched Binance live order. The actual Telegram-to-Freqtrade integration, VPS file permissions, model promotions, live stop orders and future M7 operations must be independently tested before activation.

Official references:
- https://www.freqtrade.io/en/stable/telegram-usage/
- https://www.freqtrade.io/en/stable/configuration/
- https://www.freqtrade.io/en/stable/stoploss/
- https://www.freqtrade.io/en/stable/freqai-running/
