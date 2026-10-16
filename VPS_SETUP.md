# NBOT V6 — Easy VPS setup and operation

**For a beginner.** Follow the numbered steps *in order*, copying **one command at a time** into the **Ubuntu terminal** on a **new, dedicated VPS**. You do not need Python programming knowledge. This is our documented deployment procedure **for when V6 passes its release gates**; not an instruction to turn on trading today.

**Current status (2026-10-16):** **M1 partly verified**, not accepted for the intended 30-day/25-coin system; **M4 paper VPS and M7 real-money release are not authorized**. Today it is safe to prepare a research server and run short **historical backtests**. **Do not start a persistent trading process until the appropriate milestone is accepted.**

**Start here:** [Dependencies / specifications](DEPENDENCIES.md) · [Project roadmap](ROADMAP.md) · [M1 evidence](M1_EVIDENCE.md) · [Future live security](LIVE_SAFETY.md)

## A. Before starting — VPS purchase and access

Choose **Ubuntu 24.04 LTS**, **64-bit x86_64**, **2 vCPU**, SSD, **30+ GB free disk** and SSH access as `ubuntu`. For the next full **30-day M1 training test**, start with a dedicated **2-GB RAM VPS**; test **4 GB** only if real memory measurements justify it. **Do not buy 8 GB just to get started.** We have **not measured** memory requirements for 25-coin paper research: test more pairs progressively, keep model training sequential where supported, and increase capacity only when measured RAM/CPU demands it. One-coin 3-day FreqAI training already succeeded on 1 GB, while full 30-day BTC training failed a *protective 440-MB process limit* (not a full 1-GB-capacity test). No RAM figure guarantees the complete deployment.

**Do not install this into either old V5 VPS.** Do not expose Freqtrade's API port (8080) to the internet. Allow inbound SSH (22) only; restrict it to your own IP if available.

**Windows/PuTTY:** Open PuTTY, select your **new** VPS's saved session, and click **Open**. If setting up a new session, enter the VPS's IP, set **Connection → SSH → Auth → Credentials → Private key file** to your own `.ppk` file, and log in with username `ubuntu`. **Never upload the .ppk file or its passphrase to GitHub or ChatGPT.** You will see a terminal like `ubuntu@server:~$`.

All commands below are for this **Ubuntu terminal**, not Windows PowerShell.

## B. Install the small prerequisites

**1.** Update package information:

```bash
sudo apt update
```

**2.** Install basic tools:

```bash
sudo apt install -y git curl python3 ca-certificates acl
```

**3.** Clone **the V6 branch** into its own folder. `main` still contains legacy V5:

```bash
git clone --branch prototype/v6-freqtrade-freqai-20261016 --single-branch https://github.com/samqju/Nbot.git nbot-v6
```

**4.** Enter that folder:

```bash
cd nbot-v6
```

**5.** Install **official Docker Engine and Docker Compose** on this **fresh Ubuntu VPS only**:

```bash
sudo bash scripts/install_docker_ubuntu.sh
```

This script follows Docker's [official Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/) and installs **no NBOT background service**. If Docker was already installed, it does **not** overwrite it. You can [read the short script](scripts/install_docker_ubuntu.sh) before running it. **Do not use this installer on a shared/old V5 machine.**

**6.** Check VPS readiness, Docker and public Binance access:

```bash
bash scripts/check_vps.sh
```

You want **OK** for Docker, Compose, the Binance *spot* and *futures* public APIs, with no failed checks. A RAM **WARN** is not automatically an error; it means you must use a smaller experiment or increase memory. If you get **HTTP 451**, do not proceed on that region's VPS; choose a location where Binance access is legally permitted.

**7.** Pull the image that includes FreqAI and LightGBM:

```bash
sudo docker compose --profile single pull freqtrade
```

**8.** Allow Freqtrade's unprivileged Docker user (UID 1000 in our tested image) to write data **without making the folder public**:

```bash
sudo setfacl -R -m u:1000:rwX user_data
```

```bash
sudo find user_data -type d -exec setfacl -m d:u:1000:rwx {} +
```

**Before future image upgrades**, verify its UID hasn't changed:

```bash
sudo docker compose --profile single run --rm --entrypoint id freqtrade -u
```

If it is not **1000**, stop and update access permissions for the correct UID before running the bot. **Never use `chmod 777`** on the project folder. Keep `live_private/` private; never apply these broad data-folder permissions to it.

**9.** Confirm Docker and the image start correctly, without sending orders:

```bash
sudo docker compose --profile single config --quiet
```

```bash
sudo docker compose --profile single run --rm freqtrade --version
```

```bash
sudo docker compose --profile single run --rm freqtrade list-strategies --config /freqtrade/user_data/config.json
```

Look for **NbotV6** with **OK**. **Stop here if you see an error**; do not try to solve it by switching off dry-run or adding Binance keys.

## C. Historical training and backtesting (M1) — no real money

**10.** First download BTC futures candle history and standard futures mark/funding data. The command does not place orders:

```bash
sudo docker compose --profile single run --rm freqtrade download-data --config /freqtrade/user_data/config.json --trading-mode futures --pairs BTC/USDT:USDT --timeframes 5m 1h --days 60
```

**11.** Inspect which candle ranges were actually saved:

```bash
sudo docker compose --profile single run --rm freqtrade list-data --config /freqtrade/user_data/config.json --trading-mode futures --show-timerange
```

**12.** For a very small **technical smoke test only**, choose an old, fully completed one-day window automatically:

```bash
START=$(date -u -d '4 days ago' +%Y%m%d)
```

```bash
END=$(date -u -d '3 days ago' +%Y%m%d)
```

**13.** Run the deliberately reduced BTC 3-day training configuration. The test may finish with **zero trades**, which does **not** mean profitability:

```bash
sudo docker compose --profile single run --rm freqtrade backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m1-lowmem.json --strategy NbotV6 --freqaimodel LightGBMRegressor --timerange "$START-$END"
```

For a **complete M1 qualification attempt**, only on a server with sufficient spare memory, download a longer history and backtest 7 completed days with the **normal 30-day configuration**:

```bash
sudo docker compose --profile single run --rm freqtrade download-data --config /freqtrade/user_data/config.json --trading-mode futures --pairs BTC/USDT:USDT ETH/USDT:USDT --timeframes 5m 1h --days 75
```

```bash
START=$(date -u -d '10 days ago' +%Y%m%d)
```

```bash
END=$(date -u -d '3 days ago' +%Y%m%d)
```

```bash
sudo docker compose --profile single run --rm freqtrade backtesting --config /freqtrade/user_data/config.json --strategy NbotV6 --freqaimodel LightGBMRegressor --pairs BTC/USDT:USDT ETH/USDT:USDT --timerange "$START-$END" --export trades
```

**This is a test procedure, not a guarantee of passing:** inspect the full training logs, invalid/stale predictions, return metrics and simulated trades. Backtesting needs completed historical data *before* the selected dates. Report **zero trades or negative returns honestly**. Do not mark M1 accepted until evidence and resource requirements in [ROADMAP.md](ROADMAP.md) are met. Start with 2 pairs, not 25, then expand only if training and data quality pass.

**Optional:** Check 25 active futures contracts and recent candle samples using public Binance data (does not start FreqAI):

```bash
python3 scripts/m1_market_preflight.py --execute
```

## D. Future paper trading (M4) — ONLY after M1–M3 approval

**Paper mode does not need Binance API keys or a Telegram bot.** The research service allows **up to 20 simultaneous simulated trades across the configured 25 coins**; this is a maximum, not a requirement or guaranteed activity. It uses a separate paper-trade ledger and FreqAI identifier. Both its exchange keys and Telegram controls remain empty/disabled by default.

First validate the research configuration:

```bash
sudo docker compose --profile research run --rm paper-research list-strategies --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.paper-research.json
```

When **M4 forward-paper commissioning is separately approved**, start the paper-only process:

```bash
sudo docker compose --profile research up -d paper-research
```

See status:

```bash
sudo docker compose --profile research ps
```

See recent output:

```bash
sudo docker compose --profile research logs --tail=60 paper-research
```

Follow live logs (press **Ctrl+C** to leave the *log viewer*, not stop the bot):

```bash
sudo docker compose --profile research logs -f --tail=60 paper-research
```

After checking for open simulated trades, stop paper research **only when safe**:

```bash
sudo docker compose --profile research stop paper-research
```

You can run the optional **single-position dry-run** service *instead* when M4 permits it:

```bash
sudo docker compose --profile single up -d freqtrade
```

```bash
sudo docker compose --profile single logs --tail=60 freqtrade
```

```bash
sudo docker compose --profile single stop freqtrade
```

**Do not start both services on a small VPS without a resource-capacity review.** Both configurations are dry-run only; the single-position mode is **not live trading**. The project's `restart: "no"` means it **will not automatically restart after a reboot**—this is a deliberate safety setting, not a missing setup step. Restart policy and monitoring must pass M4 acceptance before an unattended installation.

## E. Maintenance, logs, backups and updates

From the `nbot-v6` folder:

| What you want | Short command |
|---|---|
| See VPS memory | `free -h` |
| See free disk | `df -h .` |
| Check public API and dependencies | `bash scripts/check_vps.sh` |
| Check running V6 containers | `sudo docker compose --profile research ps` |
| Inspect paper logs | `sudo docker compose --profile research logs --tail=60 paper-research` |
| See current Git version | `git rev-parse --short HEAD` |

**Backup rule:** Always keep copies of `user_data/data/`, `user_data/models/`, `user_data/backtest_results/` and simulated SQLite trade ledgers (including SQLite WAL/SHM companion files). Stop paper trading *only after it is safe* before making a file-level database backup, or use SQLite's supported online-backup procedure. Keep backups **outside GitHub**, encrypted and access-controlled. A model directory must never be trusted from an unknown source.

**Before updating:** Save and review the exact approved Git commit, model identifier and Docker image digest. Stop the *paper-only* service at a safe point; then update the V6 code:

```bash
git pull --ff-only
```

Do **not** automatically `docker pull` a new mutable tag or switch strategy/model code in a live process. After updating, redo the preflight, Freqtrade schema checks and paper acceptance checks before restarting. Never delete trade databases or models to resolve an error unless a backup and recovery procedure have been approved.

## F. Real-money trading and Telegram — NOT part of initial VPS setup

**STOP: real-money mode is LOCKED at M7.** The `live-locked` Compose profile is *code-staged only*. It intentionally requires an **untracked private live config, Binance keys, owner-only Telegram identity, a short-lived owner-created VPS approval and a reviewed model-release procedure**. A Git clone cannot provide these, and Telegram **cannot** arm live mode by itself.

**Do not put Binance API keys, .ppk files, Telegram tokens or approval files in GitHub, `config.json`, CI variables or chat messages.** Do not expose a web port for the Freqtrade API. When the project eventually passes all milestones, a separately reviewed owner will follow [LIVE_SAFETY.md](LIVE_SAFETY.md), including dedicated exchange-key permissions and position/stop-loss recovery tests. No real-money start command is provided in this beginner guide until M7 is accepted.

## G. If something goes wrong

| What you see | Meaning | Fix |
|---|---|---|
| `docker: command not found` | Docker not installed | Run step B5 on **fresh Ubuntu** |
| `permission denied` when writing `user_data` | Docker ftuser cannot save files | Verify its UID and repeat B8 ACL steps |
| `HTTP 451` from Binance | Binance disallows API from this network/location | Stop; use a VPS location where access is permitted |
| `killed`, exit code `137` | Often process was terminated due to memory cap / OOM | Stop increasing pairs; test a larger isolated VPS |
| `no trades made` | No trade entries occurred in the tested period | Technical backtest may have passed, but no economic quality is established |
| `NbotV6 NOT_FOUND` | Wrong branch, bad volume or failed strategy import | Check `git branch --show-current`, `docker compose ... config`, and strategy test logs |
| `Error loading model` | Missing history/model or stale features | Check historical ranges; retrain with a separate FreqAI identifier after review |
| VPS restarted, no process running | `restart: no` is deliberate | Restart **only an approved dry-run service** after reviewing any open paper positions |

**No VPS can be considered ready merely because the commands run.** M1–M6 still require independent testing, and any future real-money operation always needs separate owner authorization.
