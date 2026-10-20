# NBOT V7 — Four Open-Source Learning Approaches: Actual Three-Coin Trials

**Date:** 2026-10-20 (Asia/Kolkata)  
**Authority:** Owner asked to try Qlib, FreqAI, FinRL and River to improve adaptive Trading Brain.  
**Verdict:** **ONE PROMISING DEFENSIVE EFFECT, NO PROFITABLE LEARNING DEMONSTRATION. LEARN-3C REMAINS HOLD.**  
**Work performed:** source-reviewed upstream official docs; created V7 research-only comparison runner and 2 causal tests; ran real BTC/ETH/SOL April→May–June frozen-A comparative replay, installed **only River** as a package in a separate nonproduction VPS research directory, ran ADWIN drift diagnostics, and reran 41/41 V7 Linux tests. No private Binance access, new data acquisition, retraining of production brain, model promotion, paper/live order or changes to protected executor.

## 1. Exactly what was tried, and what was NOT tried

| Open-source project | Relevant idea tried on original source data | Actual upstream library installed/imported? | Outcome / limitation |
|---|---|---|---|
| [FreqAI](https://docs.freqtrade.io/en/stable/freqai/) | Immutable A learned Jan–Mar; use source-matured April labels to fit a light prediction-bias correction; compare to frozen A on May–June | **NO** — existing V7 LightGBM reused; this is a **FreqAI-inspired calibration overlay**, not FreqAI inference or its live continual learning | Marginal improvement but still negative; shifted forecast allows more trades; incorrect population vs selected calibration remains |
| [Microsoft Qlib](https://github.com/microsoft/qlib), [workflow](https://github.com/microsoft/qlib/blob/main/docs/component/workflow.rst) | Frozen **train/calibrate/evaluate** date split, independent one-slot accounts, unchanged ranker/watch heads, evidence hashes | **NO** — **Qlib-inspired workflow only**; Qlib default equities dataset and broad dependency stack are not automatically compatible with Binance futures | Comparative discipline works, not an alpha claim |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL), [FinRL-Meta](https://github.com/AI4Finance-Foundation/FinRL-Meta) | Try a limited **one-step contextual enter vs NO TRADE reward gate** learned from matured April conditional candidate outcomes, test with identical V7 one-slot replay May–June | **NO** — **NOT** real FinRL DRL/PPO or recurrent RL policy; source candidate-label rewards overlap and are NOT actual portfolio exploration | Abstains from every trade: protects research sleeve but supplies no ability to select winning entries |
| [River ADWIN](https://riverml.xyz/latest/api/drift/ADWIN/) | Actual ADWIN detector on frozen A's **matured outcome forecast errors**, sorted by resolved exit time; detection never triggers trading/model replacement | **YES — river 0.22.0** installed separately with `pip --target ... --no-deps` in VPS `/opt/nbot-v7-20261020/research-packages/river/`; production venv/requirements unchanged | **255** resolved A trades Apr–Jun, **0** ADWIN alerts at fixed delta=.002; small correlated sample means zero alerts ≠ model is stable or predictions good |

The study **did not install/run FreqAI, Qlib or full FinRL frameworks**. It evaluated a small, V7-compatible version of one concept from each. Claiming otherwise would be misleading. This is appropriate for the first 3-coin feasibility gate: full packages would introduce large dependencies, extra simulator assumptions and greater overfitting surface without evidence the forecast objective works.

## 2. Causal preregistration implemented in test script

**Frozen model A:** Original `A_3MONTH_FROZEN` Jan–Mar joblib models reloaded ONLY after verifying SHA256 against their saved V7 manifest and schema; no new LightGBM fitting and no changes to underlying traded universe/entry families/stop/fill rules. Frozen A cutoff **2026-04-01 00:00:00 UTC**.

**Calibration / action reward training:** April 1–30 2026, completed opportunities with `label_available_ms < 2026-05-01 00:00 UTC`. Deterministic full same-decision groups sampled at one timestamp per **hour**; **5,606** matured candidate examples, across `down`, `range`, `up`. Predictor receives **only explicitly whitelisted entry-time fields**. No future May–June outcomes enter any challenger decisions.

**Out-of-calibration test:** May 1–June 30 2026 (separate one-slot replay, identical frozen A forecasts/rank ordering and fixed 2% stop / 3% target / 60-minute max 5m-proxy exit/cost accounting, $10k sleeve, $1k one-trade notional). A fresh wallet begins May 1 for each strategy; do not compare this 2-month number to the old Apr–June 3-month baseline. Prediction score > 0 remains the original trade eligibility, except for the described *offline experimental overlays*.

**Development caveat:** All Jan–Sep 2026 periods are already inspected in V7/V6 research. The May–June split is causally held out **from this specific April fit**, but **NOT** a pristine untouched outside-2026 evaluation and no future live performance proof.

## 3. Actual May–June comparison

| Experimental decision policy | Completed trades | Net simulated USDT | 10,000-USDT sleeve return | What happened |
|---|---:|---:|---:|---|
| Frozen A original | **196** | **−423.3050** | **−4.2331%** | Base model still loses after cost |
| FreqAI-*inspired* April mean-residual correction | **212** | **−382.1335** | **−3.8213%** | Improvement vs base but 16 more trades; still negative |
| April correction **plus fixed 25bp extra predicted-net buffer** | **69** | **−26.4029** | **−0.2640%** | **93.8% lower *absolute loss*** vs frozen A, mainly by abstaining; still negative |
| FinRL-*inspired* context action Q vs NO TRADE | **0** | **0** | **0.0%** | Learned hold across available April contexts: capital protection but no entry selection skill |
| NO TRADE | 0 | 0 | 0.0% | Still beats all trading policies in this period |

**Important precision:**
- The bias correction trained on 5,606 April **all-candidate** samples was **−0.0001249266** = **−1.2493 bp**. Subtracting this *negative* bias **raises** expected-net scores and increased entries, whereas previously reported positive ~28–33bp *selected-trade* optimism had the opposite direction. This is a concrete **selection-conditioned calibration mismatch**: a general all-candidate residual mean is not the remedy for selected top-ranked overconfidence.
- The conservative buffer policy `adjusted prediction = raw prediction − April bias − .0025`. As bias was negative, this is approximately a **+23.75bp extra raw forecast hurdle**, not exactly +25bp relative to raw score. The +25bp figure refers to the buffer applied **on top of the April correction**.
- The FinRL-inspired context Q gate permitted entry in an April regime only if the average net of positive-forecast candidate labels was positive **with >=50 cases**; April positive-prediction coverage had `down:22`, `range:62`, `up:18`. The `range` conditional sample had mean −0.0010772 (~−10.77bp), and unsupported others failed closed. Therefore zero trades is **largely a designed conservative eligibility result**, not demonstrable advanced RL learning.
- Qlib-style chronology plus identical one-slot portfolio replay made a valid **development-only methodological comparison**; Qlib itself did not run. The stronger buffer avoided losses but DID NOT generate positive net returns after the base trading costs, much less stressed profits.
- The original July–September A/B1/B negative baseline is unchanged, and May–June development findings were **not** used to tune July–September; repeating the nine-month data to promote the buffer would be false proof.

## 4. Why River did not solve anything

River v0.22.0 ADWIN actually ran in a separate research-only target directory, no production environment package changes. Feed: frozen A's April–June **255 closed selected trades**, sorted by resolved exit time, with error `predicted_net − realized_net` in basis points. Fixed `delta=0.002`, **zero detected drifts**.

This does NOT mean errors are small: the separate July–Sep autopsy showed 28–33bp overconfidence on selected trades. Drift detection checks changes in the distribution; a persistently overoptimistic model can be stably wrong. Drift is useful for triggering shadow challenger research later, NOT for fixing bad expected returns or deciding to trade.

## 5. Scientific conclusion — no new economic improvement proven

1. Most useful evidence: the fixed abstention margin rejected 127 of 196 base selected-trade opportunities **in the resulting independent wallet simulation** and reduced total loss, but still lost `−26.40`; trade differences need matched replay, not simplistic subtraction because occupancy differs.
2. All-candidate mean error calibration alone cannot address portfolio-selection-conditioned optimism. Test **selection-aware / nested chronological calibrators** and explicit expected net vs NO TRADE utility on independent development folds; do not fit directly to the observed May–June winning thresholds.
3. Adaptive regime decision policy is untrustworthy until its training reward matches one-slot capital/stop/cost semantics. A FinRL-style policy with 0 trade does not validate RL; do not install FinRL/PPO simply because it exists.
4. Actual River drift detector provided zero alerts. Retain optional research dependency separately; no automatic promotion/brain switching is authorized.
5. Before any new package installation, use retained [three-coin autopsy](V7_THREE_COIN_LEARNING_AUTOPSY.md) to design a **selection-aware calibration and blocked walk-forward** experiment, then verify on future observations the team has not inspected. Insufficient evidence => `LEARN-3C HOLD` and full-market expansion paused.

## 6. Reproduction and evidence hashes

**Committed research code:** [scripts/v7_three_coin_challenger_methods.py](scripts/v7_three_coin_challenger_methods.py), commit `4e43aede5803f1e3ab930c71acbebac69b0a5afd`. Causal [tests_v7/test_learning_challenger_methods.py](tests_v7/test_learning_challenger_methods.py), commit `6e144af9b2695bd64e703ef94cdd1c7abaacbf19`.

**Frozen A source/run:** `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed`  
**Label database:** `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/labeled.sqlite`  
**Preliminary without River:** `.../learning-methods-april-cal-may-june-v1.json` (preserved).  
**Final including real River:** `.../learning-methods-river-v2.json`; SHA256 **`a8ac6768062d621c780a09a59f4b060ad5e35f755468998042cc600c755f65e4`**.  
**Tests:** full V7 **41/41 PASS** on Linux, SHA256 `9a38c0b948214ba3812ad7f0700f6e6d5d19db9ca3a92ee3a5c974140fe43a30`; VPS path `/opt/nbot-v7-20261020/runs/learning-methods-apr-jun-tests.txt`.

```sh
cd /opt/nbot-v7-20261020/code
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/opt/nbot-v7-20261020/venv/bin/python -m scripts.v7_three_coin_challenger_methods \
  --db /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/labeled.sqlite \
  --frozen-run /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed \
  --river-dir /opt/nbot-v7-20261020/research-packages/river \
  --out /opt/nbot-v7-20261020/runs/NEW-learning-trial.json
```

The output path MUST be new; prior artifacts are never overwritten. See Python script's header and source for additional limit details. No bulk full-market download, executor modification, private credentials, paper/live order or trusted model replacement in this stage.
