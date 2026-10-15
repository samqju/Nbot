# NBOT V5.1 — Entire G3 Causal Exploration Final Acceptance

**Date:** 15 October 2026 IST  
**Repository/branch:** [samqju/Nbot](https://github.com/samqju/Nbot), **`nbot-v5.1` only**  
**Full G3 tested source revision:** `5d9707fe8521bbe17e96036aef0a5ec44a784a96`. Later documentation-only updates do not alter this tested code.  
**Engineering verdict:** **G3-01 [x], G3-02 [x], G3-03 [x], G3-04 [x], G3-05 [x], G3-06 [x], PARENT G3 [x] — PASS for offline/read-only causal Exploration**. No execution or source economics release.  
**Original authority:** Vision V1.9, Engineering Roadmap §4 G3 and §3 D3, approved G2 100-symbol observation code.

## 1. Gate acceptance: every G3 subphase and microtask

- [x] **G3-01-A — Audit exact historical V4 source and register:** Pinned 24 original IDs and V1 descriptions at old immutable commit `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`, [`nbot/observation/candidate_setups.py`](https://github.com/samqju/Nbot/blob/b1a3c4a8d2a82c994669df7adb0d345e0415ffbf/nbot/observation/candidate_setups.py) blob `80eafb9da096633154a7d7095137414998eb37ee`. Independently parsed the old registry AST **without importing V4 runtime**: exactly **5 context + 19 technical**; historical catalog SHA256 **`17cf229ef8beb30e1bc54bc22a0025e2ffed65e3088b915cec17e51e032dad4b`**, checked against new code and test H01.
- [x] **G3-01-B — Selective source reuse:** Newly written `nbot_v5_1/detector_rules.py` selectively incorporates original pure registry, `ema`, `rsi`, `history_digest`, `technical_conditions` and five-context `describe` from original V4 [`context_learning.py`](https://github.com/samqju/Nbot/blob/b1a3c4a8d2a82c994669df7adb0d345e0415ffbf/nbot/observation/context_learning.py), blob `34b6b83bd115e44361eba2a7937f7872774c3c3d`. Excluded original SQL `load_histories`, training, model ranking, old paper adapter and trade execution. Original detector IDs retain the old `_V1` semantic identity and the **NEW wrapper** has its own `NBOT_V5_1_G3_ADAPTER_V1:<catalog SHA>` version.
- [x] **G3-01-C — Audit historic V5 adapter/context, do not import:** Reviewed [`nbot/v5/pattern_adapter.py`](https://github.com/samqju/Nbot/blob/1e7c090d05dc118b290c764d58c2944f56ad4b3b/nbot/v5/pattern_adapter.py), blob `0048eabcdf9008fe0499b3c1b233a6469358f4d2`, and [`nbot/v5/g3_market_context.py`](https://github.com/samqju/Nbot/blob/1e7c090d05dc118b290c764d58c2944f56ad4b3b/nbot/v5/g3_market_context.py), blob `d426ef75e143d9745006de16f16cdf219a599cab`. Both contain **obsolete 50-symbol**/legacy import contracts; V5.1 reimplemented source/denominator/market BTC features from reviewed causal principles instead of transplanting those modules.
- [x] **G3-01-D — Original detector positive and negative fixtures:** H01–H07 passed. The pinned original V4 fixture examples exercise **each of the 19 technical detectors** positively in BOTH LONG/SHORT directions and **all five context rules** positively. Missing BTC relative momentum, flat-market, bad histories, unconfirmed swing and wrong trade direction are negative cases. Existing G1/G2 regression retained.
- [x] **G3-02-A — Causal closed-as-of data interface:** Added read-only `ObservationBook.history_asof` export from G2. Requires 96-contiguous completed five-minute bars, matching event, no gap or future receipt, consistent route/epoch; returns no usable history when unsafe. Never imports old runtime or uses an unfinished/future candle.
- [x] **G3-02-B — BTC/market/coin context:** New `exploration.py` computes from available closed bars only: BTC UP/DOWN/FLAT/UNAVAILABLE, broad up/down/mixed/UNAVAILABLE (requires contemporaneous 80%+ coverage and at least ten markets), coin up/down/range, range break/failed-break/move and FORMING/CONFIRMED/FAILED/UNCONFIRMED maturity. Missing BTC remains explicit **UNAVAILABLE**, never an invented zero BTC return.
- [x] **G3-02-C — Complete grade/context disclosures:** Each row preserves original universe tag(s) (turnover/gainer/loser/BTC/fallback), source route/epoch, G2 candle metadata hash, history count, decision-as-of, source reason, and **CLOSED_PUBLIC_CANDLE_METADATA_NOT_ORIGINAL** grade; liquidity explicitly **UNIVERSE_LIQUIDITY_METADATA_ONLY**, costs explicitly **QUOTE_SLIPPAGE_FEE_FUNDING_UNVERIFIED**. No false economic profitability/fill/quote qualification.
- [x] **G3-02-D — Stale universe and source HOLD:** Older-than-90min membership, missing/gapped/epoch-mismatched source and weak contemporaneous cross-section are rejected or marked unavailable with explicit reasons; no use of previously closed bars at a later event after loss of continuity. E07–E09/E14/E18 passed.
- [x] **G3-03-A — Full 100×2 = 200 denominator:** Exactly **one immutable LONG and one SHORT row** for every G2 manifest symbol (up to 100), including explicit no-pattern, not-evaluated and source-missing rows. Every row carries exactly **24 named detector states**, with frozen version/hash and unique event/coin/side identity.
- [x] **G3-03-B — Five distinct per-detector states:** `MATCH`, `NO_MATCH`, `UNAVAILABLE`, `NOT_EVALUATED_CAPACITY`, `NOT_EVALUATED_SOURCE`; unevaluated symbols must not disappear from the statistical denominator and missing BTC-relative features are never mislabeled NO_MATCH. E02–E08 passed.
- [x] **G3-03-C — Actual vacancy-driven evaluation:** Default reported research vacancy **zero**, so all source-ready directions are **NOT_EVALUATED_CAPACITY** and no heavy 24-rule evaluation occurs. A strictly validated positive **reported** vacancy can trigger read-only candidate evaluation, but creates NO research slot, order, or position. The optional deterministic SHA-rotated scoring cap reports observed, source-skipped and capacity-skipped count plus prospective design inclusion **K/N** for all source-ready candidates; no hindsight-priority based on pattern count. E03–E06/E11/E12/E17 passed.
- [x] **G3-03-D — No forced trades/no edge assumption:** Every G3 observation has immutable `authority=NONE` and `disposition=NO_TRADE`; matching one or several detectors only creates hypotheses. Synthetic breakout positive fixture E10 verified MATCH without order, net-return field or execution functions.
- [x] **G3-04-A — Durable bounded Exploration receipts:** New `exploration_store.py`: exact 200-direction record, nested 24-state masks, full category/source/cost/propensity fields compressed to owner-private gzip files, hash integrity, data+directory `fsync`, idempotent identical retries, maximum 64 MiB default, owner-private directory/file, no silent deletion/migration/rotation or overwritten same-event version. Replay verifies status/denominator/masks/no-order authority.
- [x] **G3-04-B — Replay attack/error tests:** P01–P12 pass: private record persistence, duplicate same-event conflict, torn gzip/corrupt hash, fake LIVE authority, forged original source or after-cost status even after receipt rehash, fake evaluated detector from a capacity mask, unsafe file/folder permissions, quota exhaustion, failed directory fsync followed by safe retry and absent-directory behavior. **Not an independently immutable WORM/off-host archive.**
- [x] **G3-05-A — Entire regression at target Python:** **157/157 passing tests on EACH VPS running Python 3.12.3**, same immutable GitHub code SHA `5d9707fe...`, 0 failures/errors. These include prior 67 G1, prior 53 G2 and new **37 G3** tests (H7 historical + E18 adapter/context + P12 receipt/fault).
- [x] **G3-05-B — Actual 100×2×24 small VPS stress:** Each VPS separately ran 100 markets × two directions × 24 detectors × **12 closed events**, i.e. **2,400 complete direction records**. The synthetic schedule included full/no-vacancy, limited-score and real source-gap placeholders. Counts **1,240 evaluated + 1,020 capacity-skipped + 140 source-skipped = 2,400**; all 12 compressed receipts replay. Actual p99/RSS/CPU/disk results in §3 below, all under caps.
- [x] **G3-05-C — Regressions found and fixed:** First G3 suite found non-JSON tuple batch identity and a backdated-cohort test; the G1 canonical hash correctly rejected the tuple and G2 future-universe guard rejected the backdating. Fixed code/test and reran **142/142**. Further persistence fixture initially tested unsafe permissions instead of quota; corrected. Added richer category/propensity/source-grade audit and adversarial rehash tests; final **157/157** on BOTH hosts. No unsolved test error is relabeled as PASS.
- [x] **G3-06-A — Actual one-shot read-only source-to-G3 integration:** Observation-VPS, exact G3 code SHA `5d9707fe...`, opt-in **public HTTPS GET only** from Binance USD-M. **100 qualifying symbols including BTC**, each with 96 verified closed five-minute bars, **100 G2 METADATA_CLOSED / 0 source HOLD**, **103 byte-exact public receipts compressed and replayed** (792,398 bytes), public request weight **246**. G3 then produced **200 direction records, 24 detector slots per row, zero source skips and 200 capacity skips**, preserving NO_TRADE/NONE. Because G5 has not qualified any real research vacancy, **zero live detector evaluations** were appropriately attempted; all 200 capacity masks and the 17,825-byte compressed G3 receipt were replayed and temporarily removed.
- [x] **G3-06-B — No installation/services or funds:** Tests and one-shot public probe used automatically cleaned temporary GitHub checkouts; **no permanent NBOT installation, old V4 runtime, background Observation service, paper account, actual Binance account endpoint or trading order** was started/accessed. G3 source-grade caution is inherited from G2 (public REST candle data).
- [x] **G3-06-C / PARENT G3 FINAL PASS:** All above source, structural, mask, sampling, replay, local-VPS performance and actual 100×2 public-asof evidence meet the authoritative read-only G3 engineering gate. **No G4+ stage or paper/real release implied.**

## 2. Pinned source files and code hashes at the accepted revision

Code HEAD used for final G3 BOTH-VPS tests, benchmark and public check: **`5d9707fe8521bbe17e96036aef0a5ec44a784a96`**.

| Path on `nbot-v5.1` | Function | Verified Git blob SHA-1 |
| --- | --- | --- |
| `nbot_v5_1/detector_rules.py` | Selected pure original 24 detector/5 context formulas | `d0d981b3555036e5392787c5e90de61c523183e1` |
| `nbot_v5_1/exploration.py` | Causal market/BTC/coin context, 200-direction immutable mask/sampling | `6f8d0227414e82aff0c56c6ef5d32bfa81fc481e` |
| `nbot_v5_1/exploration_store.py` | Bounded compressed 200-row secure replayed evidence | `6591eb608f0f8acfeb1c96f96667adf3b5fd2498` |
| `nbot_v5_1/observation.py` | G2 independent safe-as-of read-only 96 closed-candle export | `3d5b3455e6c1613ccba42e91d33da08c150ab000` |
| `tests/test_v5_1_g3_historical.py` | Seven historical old-V4 pinned catalog/golden detector tests | `94d65da6bf4b67b0beb1ece59882d27ade5f3552` |
| `tests/test_v5_1_g3.py` | 18 BTC/cohort/clock, complete-denominator, 24-state/NO_TRADE tests | `f4f827d74ce2d6794efa7e7787b065f782fad7de` |
| `tests/test_v5_1_g3_store.py` | 12 gzip/authority/cost/propensity/permission/quota/restart negative tests | `8502a0e17fe3b38d7401a1462f1bcce87c71b796` |
| `benchmarks/g3_exploration_benchmark.py` | 100 × 2 × 24, 12-event CPU/RSS/disk/p99 and 2,400 denominator | `3dc12a84e8df82d897fd877379106bc45cae5ac0` |
| `scripts/g3_readonly_probe.py` | One-shot public source 200-capacity-mask, temporary receipt replay | `21c43f456a49fda44ab6c7a3eed03cdb04bd923d` |
| `scripts/g2_readonly_probe.py` | Optional G3 callback after original G2 strict real-public 100-symbol as-of test | `eb5a25defcc45696884b5c4fc36c9427f3fe1574` |

All ten source/test/benchmark/probe GitHub files were separately read back and pinned to the final accepted source revision. No legacy `nbot.observation` package import exists in the new G3 modules.

## 3. Exact two-VPS 157-test and measured performance results

Each host cloned the **same `5d9707fe8521bbe17e96036aef0a5ec44a784a96`** branch commit into a Python private `TemporaryDirectory`; no permanent checkout or service.

**Commands:**
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 -B benchmarks/g3_exploration_benchmark.py
```

| Check | Observation-VPS `base` | Execution-VPS `nbot-execution` |
| --- | ---: | ---: |
| Python | **3.12.3** | **3.12.3** |
| Entire test suite | **157/157 PASS (11.928s)** | **157/157 PASS (12.310s)** |
| Test exit code | 0 | 0 |
| G3 benchmark result | **PASS; exit 0** | **PASS; exit 0** |
| Event records / detector cells | **2,400 / 57,600** | **2,400 / 57,600** |
| Evaluated / capacity skipped / source skipped | **1,240 / 1,020 / 140** | **1,240 / 1,020 / 140** |
| p50 event latency | 290.890 ms | 275.823 ms |
| p95 event latency | **571.799 ms** | **549.342 ms** |
| p99 event latency | **571.799 ms** | **549.342 ms** |
| Worst event latency | 598.022 ms | 591.716 ms |
| Peak test process RSS | **42,884 KiB** | **43,164 KiB** |
| Process CPU | **5.304 s** | **5.196 s** |
| Wall | 5.399 s | 5.272 s |
| 12 compressed G3 receipts total | **198,781 bytes** | **198,781 bytes** |
| Declared hard p99 ceiling | 1,500 ms | 1,500 ms |
| Declared RSS ceiling | 256,000 KiB | 256,000 KiB |
| Declared disk ceiling | 33,554,432 bytes | 33,554,432 bytes |
| Temporary checkouts | Auto-cleaned | Auto-cleaned |

**Caution:** This benchmark is *synthetic deterministic offline* 100×2×24. Its measured CPU/p95/p99 excludes live REST/WSS network latency, always-on service memory, original high-frequency 20 deep source archival, models, cost calculation and order management. Future deep-stream operational endurance/recovery must be qualified separately.

## 4. Genuine one-time public as-of G3 observation

Observation-VPS, exact tested source SHA `5d9707fe...`, explicit `--public-network` only, no secret or account access; G2 public REST source + strict as-of G3 evaluation in the same temporary process.

- G2 response sizes: **927** exchange symbol rows, **793** ticker rows, **795** book-ticker rows.
- Cohort: **100 eligible USD-M symbols**, including BTC; 100 verified histories ×96 closed five-minute bars, no missing history.
- Selected source age **30,439ms** and proper triple-source timestamp/sha matching; G2 event open **1792048800000**; 100 source-ready METADATA_CLOSED, **zero HOLD**.
- Raw public GET evidence: **103 responses, 792,398 bytes compressed**, all source receipts replayed, then deleted with explicit temporary test archive; public budget **246** weight, no accounts/orders.
- G3 response: **200 rows** (100 × LONG/SHORT); each has **24 states**, original V4 catalog version and new V5.1 adapter version; **0 NOT_EVALUATED_SOURCE, 200 NOT_EVALUATED_CAPACITY, 0 detector evaluations**, because G5 has proven **zero independent vacant research positions**.
- G3 receipt compressed to **17,825 bytes**, fsynced, hashed and replayed correctly then removed as a **test**. Every row has NO_TRADE and NONE authority. G3 manifest SHA `9980508dcecbe6915de813c196ea6f4403032217fa0e6225df264122320d6947`, G3 event receipt ID `6f1029e1d4eee3296593ab2712806e610dd86b5e1acdf9005ec2e908b2473ee2`.
- This source grade is **public REST closed-candle metadata**, not independent original trade/quote/funding/fee/slippage path custody, not a prospective original virtual trade trial and not a winning strategy.

## 5. Explicit restrictions and next gate

G3 produces **descriptive hypotheses only**. Multiple pattern matches are overlapping tags on the same movement, not separate independent profitable examples. **NO_TRADE is not NO_MATCH; source missingness and capacity skipped are not negative profitability labels.** No virtual Research trades are started; no paper/live execution or credential capabilities were added.

G3 accepts the **read-only offline engineering** Exploration/observability stage, **not** a deployed continuous service, a scientific after-cost label, physical power-cut/off-host replay qualification, true original first-touch path, or approval to use an old V4 model artifact. The owner's backup waiver for obsolete VPS data never permits deletion of newly generated V5.1 scientific source evidence.

**NEXT: G4** — Select and freeze up to 20 deep research symbols (including BTC) with a fair decision-time shortlisting policy and genuine original trades/quotes/mark/funding source warm-up and compressed bounded retention; measure true 20-source rates, interruption gaps, original-source authenticity, disk quotas and recovery. **G4 [ ]**, as are G5–G12, and every paper/testnet/real trading approval. No service start before explicit later offline full-pipeline acceptance.

## 6. New-chat continuity

Read this report first, then [Owner Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_OWNER_ROADMAP_V1_0.md), [Engineering Roadmap](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md) and Vision V1.9. GitHub branch `nbot-v5.1`; pin code SHA `5d9707fe8521bbe17e96036aef0a5ec44a784a96`. G0, G1, G2 and **G3 all PASS their separate engineering scopes**; G4 next. Review R01–R03 and R10 source register notes; never equate 24 matches to profitable strategies, 100 REST histories to original research streams, or future cost evidence to a current observation. Every small completed G4 task must receive a permanent tick, exact file/code/test evidence and owner-readable summary in BOTH roadmaps.

**Final decision: G3 PARENT [x] COMPLETE**, offline/read-only causal Exploration, **157/157 two-VPS tests** and both measured 200-direction p99/RSS/disk PASS, actual public 100→200 source/capacity audit PASS. **No trading release whatsoever.**
