# NBOT V7 — Offline-only nine-month research baseline

**Branch:** `V7`  
**Research status:** Code under development, **not production ready**. There is no exchange account adapter, paper process, live order engine or VPS deployment in this branch.

## Purpose

Research a **point-in-time USDT-perpetual whole-market strategy-aware universe**, independent long/short candidate outcomes, BTC-regime features, 5-minute OHLC-conservative outcomes with MFE/MAE, and three **versioned** LightGBM learning brains, with matched-date momentum, liquidity and deterministic-random heuristic diagnostic baselines:

- **Brain A:** trained from matured outcomes of months 1–3; frozen examination on months 4–6.
- **Brain B1:** same architecture, retrained using matured outcomes from months 1–6.
- **Brain B2:** contextual regime-specific challenger trained on months 1–6, with general model fallback.
- All **A/B1/B2** are evaluated on months 7–9 with independent one-slot portfolio replay. The experiment reports whether after-cost performance changes; it does not assert automatic improvement.

**No historical range, model, exit, fee or risk settings may be adjusted using months 7–9 and still call the same months an untouched holdout.** Previously inspected 2026 July–September are development data only.

## Current imported legacy source

Only required research-only modules have been selectively copied without edits:
- V3 `nbot/observation/{decision_ledger,chronological_replay,counterfactual,research_replay}.py`
- V5 `nbot/observation/{v5_accounting,v5_paired_exits}.py`
- V5.1 `nbot_v5_1/{core,research_intent,learning_contract,learning_science}.py`.
- V6 historical source inventory `scripts/m2r_binance_historical_universe_inventory.py` and purge module are retained from branch base.

V4 `lambdarank` chronological group-training *logic* is adapted (not blindly copied with transitive dependencies) into `nbot_v7/brain.py`. See `V7_G0_LEGACY_AUDIT_2026-10-20.md` for original blob provenance.

## Accepted offline input

Directory containing historical Binance USD-M `SYMBOL-5m-YYYY-MM.zip` or `.csv` files, one file per symbol/month, 12-column Binance-style candles. Only data files whose nine-month calendar range matches `--start-month` are considered. Newer microsecond open times are converted to milliseconds. Any actual gaps cause local candidate rejection, not fabricated price bars.

A **separately verified historical registry CSV** is mandatory with header:

```csv
symbol,from_ms,to_ms,evidence_sha256,source_grade
BTCUSDT,1767225600000,1798761600000,<64-hex-source-evidence-digest>,SOURCE_ATTESTED
```

**Important:** Entering `SOURCE_ATTESTED` does not cryptographically prove an exchange listing existed; independent archive/lifecycle source attestation is still a G1 blocker. Never create invented listings just to pass the parser.

## Offline usage (after full code/test verification)

```bash
python3 -m pip install -r requirements-v7.txt
python3 -m unittest discover -s tests_v7 -v
python3 -m nbot_v7 build --archive /offline/binance_monthly --registry /offline/historical_contract_registry.csv --db /offline/v7.sqlite --start-month 2026-01
python3 -m nbot_v7 experiment --db /offline/v7.sqlite --out /offline/v7_experiment_001 --start-month 2026-01
```

**The sample 2026-01 period has historical July–September contamination from earlier V6 work and is NOT a blind promotion test.** The nine months above are an example only, not proof of having downloaded them.

This version **does not fetch/download archives**. Doing so will be a separate controlled G1/G2 task after deciding historical listing eligibility, data volume, and available storage.

## Diagnostic benchmark limits

Simple momentum, liquidity and deterministic-random comparison policies use the same dates, path-proxy costs, 20-symbol capacity and one-slot account, but do **not** enforce matched entry frequency. Time-block 95% bootstrap intervals compare A/B1/B2 on daily capital PnL; correlated markets and reused historical windows mean they are **diagnostics**, never automatic promotion proof. Baseline and brain trades are exported separately.

## Economic limitations — never waive

- The default exit lab uses **2% underlying adverse stop, 3% favorable target, 60m max hold**, 0.05% fee per side, 1bp slippage each way and stop-first if same 5m bar. This is a **frozen comparative engineering proxy**, **not the previously disproven 1% trailing rule** and **NOT a recommended live policy**.
- Bar first-touch and simulated MFE/MAE are path estimates, not executable tick/depth fills. No verified funding by contract is integrated in this prototype; it is a significant **NO-GO** for any economic acceptance. The 25bp additional stress is a scenario, not actual funding measurement.
- Dynamic universe selection requires contemporaneous watch rows, and model scores must come only from earlier matured labels; zero eligible coins or zero trades is acceptable.
- Cross-sectional selection must beat the old V6 and simple selectors on truly unseen history **after costs with one-slot constraints** before paper permission. This engineering pipeline alone **does not yet implement all final-native comparisons, independent statistical confidence gates, or verified funding and depth**.
- Do not use the V7 branch on the VPS with exchange keys; do not start paper/live trading based on this code.

## Update policy

Record each change, test, negative result or go/no-go in the **same-branch** `V7_CHAT_HANDOVER.md` before claiming the step completed.
