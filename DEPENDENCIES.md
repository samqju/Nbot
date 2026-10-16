# NBOT V6 — VPS and software dependencies

**Purpose:** Keep the exact deployment prerequisites in GitHub. This is a planning specification for a **new, separate Ubuntu VPS**, not permission to deploy on V5 or enable real orders. The beginner's copy/paste runbook is [VPS_SETUP.md](VPS_SETUP.md).

## Hardware: what we know versus what we estimate

| Intended use | CPU | RAM | Free disk | Evidence / decision |
|---|---:|---:|---:|---|
| One-coin, 3-day FreqAI *diagnostic* | 2 vCPU | **1 GB worked** under a **440 MB process cap** | ~3 GB observed usage on our test VPS | Real BTC LightGBM fit and one-day backtest succeeded; **zero trades** |
| Full M1: 30-day 5m/1h training, 7-day backtest | 2+ vCPU | **Start by testing 2–4 GB** | **30 GB recommended** | **Not yet measured to completion**. Both 30-day single-coin trials were killed at the 440 MB process cap |
| Expanded 25-coin FreqAI research + paper trades | 4+ vCPU preferred | **8 GB recommended starting point** | **50 GB recommended** | Planning estimate, NOT a proven minimum or sufficient guarantee |
| Paper research and a separate approved execution process simultaneously | Benchmark both | Capacity **not established** | Budget for independent models, data and trade DBs | Not commissioned; do not assume 8 GB is automatically sufficient |

Use **64-bit Ubuntu 24.04 LTS** (22.04 supported by install script), **x86_64/amd64** preferred, an SSD, outbound internet, and an ordinary `ubuntu` user with SSH and `sudo` access. ARM requires separately validated Python/image support. No GPU is required for our LightGBM model.

**Important:** A 1-GB VPS is not automatically unsuitable for *all* FreqAI tasks. We proved a *small* real experiment, not the original 30-day configuration. Do not run unbounded training on a 1-GB VPS with active unrelated services. See [the dated test evidence](evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md).

## Required software — recommended Docker route

| Dependency | Requirement / source | Who installs it? |
|---|---|---|
| Ubuntu | 22.04 or 24.04 LTS, 64-bit | VPS provider |
| SSH access | `ubuntu`, SSH key; PuTTY .ppk supported on Windows | VPS owner |
| `sudo`, `git`, `curl`, `ca-certificates`, `python3`, `acl` | Ubuntu apt packages | Setup guide |
| Docker Engine | Current vendor-supported release from [Docker's official Ubuntu apt repo](https://docs.docker.com/engine/install/ubuntu/) | `sudo bash scripts/install_docker_ubuntu.sh` on **fresh** VPS |
| Docker Compose | Official **Compose plugin** (use `docker compose`, not legacy `docker-compose`) | Same installer |
| NBOT V6 | The **V6 branch** of `samqju/Nbot`, not V5 `main` | `git clone --branch ...` |
| Freqtrade + FreqAI | `freqtradeorg/freqtrade:stable_freqai` | Pulled by Docker; includes Python, pandas, NumPy, CCXT, FreqAI and LightGBM dependencies |
| FreqAI model | `LightGBMRegressor` | Already configured in V6 Compose |
| Native host Freqtrade, Python ML dependencies | **Not needed** when using Docker | Do **not** install separately for normal deployments |

### Versions and reproducibility

- Successfully tested with **Freqtrade 2026.9**, `LightGBMRegressor`; official image digest observed on **2026-10-16**: `freqtradeorg/freqtrade@sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535`.
- The repository still references the **moving** `stable_freqai` image tag. **Before M4 paper commissioning**, validate the exact image on the target VPS and pin the approved digest in `docker-compose.yml` for repeatable deployment. Do not assume the dated 2026.9 digest will always be the right release.
- The source code's *current* M1 low-memory configurations are experiments and **not default production settings**.
- The 1-GB native experiment used **Python 3.12.3, Freqtrade 2026.9, LightGBM 4.7.0, scikit-learn 1.9.1, datasieve 0.1.9 and XGBoost 3.2.0**. `libgomp.so.1` (Ubuntu `libgomp1`) was also required. These are historical research notes, **not a request to pip-install each one on a Docker VPS**. See [M1_EVIDENCE.md](M1_EVIDENCE.md).

## Networking and security prerequisites

- Public outbound HTTPS access to `https://api.binance.com/api/v3/exchangeInfo` **and** `https://fapi.binance.com/fapi/v1/exchangeInfo`: expect HTTP **200**, not 451. Verify permitted access from the *actual VPS location*; GitHub's US runner received 451.
- Outbound access to GitHub, Docker Hub and normal Ubuntu apt mirrors; DNS and accurate UTC clock (NTP/systemd-timesyncd). Freqtrade's exchange connection also needs access to the relevant Binance futures endpoints/websockets when later authorized.
- Inbound SSH (port 22) restricted to the owner's IP wherever possible. **Do not expose port 8080/API/FreqUI or any bot database to the internet.** The checked-in API and Telegram configs are disabled.
- **No Binance keys or Telegram tokens are required** for data download, historical backtesting or dry-run paper research. The committed config has empty exchange keys, `dry_run=true`, and disabled Telegram/API.
- Freqtrade Docker uses an unprivileged container user (the tested image uses UID **1000**). Bind-mounted `user_data` must be writable by it. The runbook uses **ACLs** instead of world-writable `chmod 777`.
- Keep `user_data/data/`, `user_data/models/`, simulated trade SQLite files, logs, and all `live_private/` credentials **outside Git**. Protect backups and never paste secrets into support tickets or CI logs.

## Required operational artifacts and ownership

| Path | Role | Backup? |
|---|---|---|
| `user_data/config.json` | Version-controlled dry-run baseline, 25 candidates | Git |
| `user_data/config.paper-research.json` | Opt-in 20-slot virtual-trade settings, separate FreqAI model ID and trade DB | Git |
| `user_data/data/` | Downloaded real Binance candle history | Yes / can be reconstructed |
| `user_data/models/` | Locally trained FreqAI artifacts | **Yes; version/validate** |
| `user_data/backtest_results/` | M1–M3 historical result archives | Yes |
| `user_data/*.sqlite*` | Paper trade ledger and runtime persistence | **Yes; stop process before file-level backups** |
| `live_private/` | Future untracked owner/Telegram/Binance secrets and expiring approval | **Do not commit**; separate secret-handling policy |

## Deployment readiness gates

**Not ready today.** Passing `bash scripts/check_vps.sh`, Docker installation or strategy discovery only verifies prerequisites.

1. **M1:** 30-day rolling FreqAI fit + full 5m/1h features + at least one independently held-out 7-day historical backtest accepted. Current status: **PARTIAL** (3-day/1-day technical proof only).
2. **M2–M3:** cost-adjusted no-ML baseline and credible held-out FreqAI evaluation.
3. **M4:** isolated VPS resource assessment, paper-only operation, recovery tests and monitored forward paper evidence.
4. **M5A / M6:** safe eight-hour pair-selector activation and approved shared model governance if enabled; **currently not built**.
5. **M7:** separate owner-approved, audited real-money release. **LOCKED**. The repository's owner-gated code is not an operational live deployment.

For short, exact commands, use **[VPS_SETUP.md](VPS_SETUP.md)**. For strict future owner authorization, use **[LIVE_SAFETY.md](LIVE_SAFETY.md)**.

## Official references

- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose plugin](https://docs.docker.com/compose/install/linux/)
- [Freqtrade Docker quickstart](https://www.freqtrade.io/en/stable/docker_quickstart/)
- [FreqAI image and prerequisites](https://www.freqtrade.io/en/stable/freqai/)
- [FreqAI backtesting and data history](https://www.freqtrade.io/en/stable/freqai-running/)
