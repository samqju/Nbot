# NBOT V6 — Actual global 25×8 research implementation and safe third-stage VPS queue (2026-10-18)

**Owner-authorized OFFLINE research only. Code is committed; new research has NOT started. Paper/live, strategy promotion and V5/main changes remain prohibited.**

## Implemented on the isolated V6 GitHub research branch

- `scripts/m2r_v6_global_dataset.py`: ingest the 25 original historical Binance USDT-M 5m OHLCV files; generate genuinely valid LONG/SHORT signals from the SAME eight frozen native library families on each completed 5m candle; preserve all candidate rows with conservative next-open / adverse-first 12-candle **proxy** outcomes. Chronologically separated LightGBM regression plus classification and calibrated success probability per candidate, including family/pair/side features. 30/60/90/180-day lookbacks; sequential weekly walk-forward decisions for July 15–September 30. Models cannot train on labels that are not yet observed at the historical fit boundary. No claims of true orderbook depth or perfectly filled stop exits from OHLCV.
- `scripts/m2r_v6_global_opportunity_ranker.py`: preexisting strict global 25-coin opportunity ranker; receives comparable calibrated predicted after-base-fee net returns, downside/uncertainty reserve, extra 25bp hypothetical stress and a conservative 5m volume-based liquidity *proxy*, never hindsight outcomes. Select at most one candidate among the competing eight families and both directions or NO TRADE.
- `user_data/strategies/NbotV6GlobalOfflineResearch.py`: new research-only native Freqtrade strategy accepts the winning as-of candle signal as input for **one single 25-market portfolio** with max one open position, 1× leverage, 1000-USDT nominal stake, 2% stop, 5% ROI or 60-minute cap; second variant tests +2%-trigger/+1% trailing against the SAME selected entries. Native engine, not stitched independent strategy PnL, determines actual simulated entries/exits, order sequencing, fees and available funding rules.
- `scripts/m2r_v6_global_batch.py`: finite checkpointed coordinator with 4 LightGBM time-window jobs plus 8 full-engine Freqtrade portfolio A/B jobs, native ZIP consistency and ledger/cost audits, NO TRADE=0 comparison, no automatic promotion, clear per-job progress status. Preserves earlier 2,475 historical fits, 8 native strategies, earlier trailing tests and already queued 120 follow-up exit-policy runs.
- `tests/test_m2r_v6_global_batch_contract.py` and previous `tests/test_m2r_v6_global_opportunity_ranker.py`: synthetic timing/exit, coin and strategy encoding, native archive rejection, no-live, global-rank and NO TRADE tests.
- `scripts/m2r_v6_global_successor_wait.sh` + `deploy/nbot-v6-global-20261018.service`: third-stage permanent fail-closed systemd waiter; waits for both current library and profit-protection services and valid final audited outputs, no other active Docker, clean isolated source, syntax/tests. Stops if predecessor failed or vanished without completion. No arbitrary 24-hour wait cutoff in this **third** handoff.

## VPS actual deployment confirmation

The third-stage `nbot-v6-global-20261018.service` was installed, `systemctl enable --now` succeeded, and `is-enabled=enabled`, `is-active=active` were confirmed **2026-10-18 12:05 UTC**. Its journal reported `WAITING library=running active=1 profit=MISSING active=1`. Both predecessor services remained active; no `global-25x8-20261018/progress.json` was present. This is a WAITING queue, NOT currently running models. The source is in `/root/nbot-v6-m1-20261016/global-next-source`, separate from active `/root/nbot-v6-m1-20261016/source`. The queue fetches and fast-forwards the approved V6 branch **only after both predecessors finish**, then starts finite offline research if checks pass.

## Scope and limitations (do not omit in reporting)

- The native portfolio experiment is fully wired as a research job, but it has **NOT run yet on 25-coin historical data**. Test/CI and static verification are separate from profitable trading evidence.
- Proxy training labels include baseline modeled exchange fees and historical OHLCV stop/ROI paths, **not fully verified realized historical funding, spread, orderbook depth or actual stop-market execution**. Native Freqtrade is the economic reconciliation stage; additional 25bp stress is hypothetical.
- Initial integrated experiment has a fixed entry-target exit policy plus matched same-entry native trailing A/B; it does **not yet train a separate forecast model for every one of the prior five additional profit-protection policies**. Those 120 native results are preserved for owner review, rather than rerun.
- July/August/September are previously inspected; a genuinely untouched later calendar holdout and prospective market microstructure proof remain necessary before any economic approval.
- Historical dynamic 25-of-broad-market selection is separate and remains unproven; the fixed original 25 are the specified comparison universe.
- Core owner objective is **25 × eight strategies × eligible LONG/SHORT**, not one single strategy deployed across coins. Original breakout/pullback remain separately reportable controls and a possible optional ten-family challenger.
- Queue can refuse to start after predecessor error; **do not circumvent the fail-closed gate** or silently claim research progressed.

## How the owner checks status

```bash
systemctl status nbot-v6-global-20261018.service --no-pager
journalctl -u nbot-v6-global-20261018.service -n 12 --no-pager
python3 /root/nbot-v6-m1-20261016/global-next-source/scripts/m2r_v6_global_batch.py --status
```

When running, `global-25x8-20261018/progress.json` contains `jobs_completed / jobs_total` out of 12. If queue is waiting, no new model percentage is earned.
