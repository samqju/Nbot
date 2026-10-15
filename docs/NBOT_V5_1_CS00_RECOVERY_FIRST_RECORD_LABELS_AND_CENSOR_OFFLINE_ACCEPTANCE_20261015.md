# NBOT V5.1 — CS-00 Recovery-First, Record-Label and Unrecoverable Research Acceptance (OFFLINE)

**Date:** 15 October 2026 (IST)  
**Branch:** `samqju/Nbot:nbot-v5.1`  
**Exact source SHA independently tested on both VPSs:** `bd0715ad2ca681263cd25c471862cd67cf93cbb7`  
**Status:** **[x] THIS NARROW OFFLINE SOFTWARE CHANGE ACCEPTED; [ ] CS-00 FULL PRESTART COMMISSIONING HOLD; [ ] CS-01 STARTUP NOT AUTHORIZED; [ ] G4–G10 ORIGINAL-SOURCE/SCIENCE/PAPER PARENTS HOLD; [ ] G12 REAL LOCKED.**

## 1. User policy and the deliberate safety boundary

The owner approved the historical-recovery-first, compact V4-style Research recording design and asked that any trade still unrecoverable after genuine recovery be removed from all scored/training use, as though it had never produced a learning outcome. **Implemented safe interpretation:** an unrecoverable Research experiment is **permanently excluded from eligible training, win/loss and model-quality results**; it retains only a small **immutable censored/excluded audit tombstone** identifying the originally frozen experiment and the recovery-failure evidence. It is still counted under censoring in the full prospective denominator. Without this, selective loss of adverse trades could bias win rates and model-selection claims. Existing source HOLD slots do not disappear without a logged, explicit validated CENSOR transition.

No automatically recoverable interrupted position is canceled while recovery remains pending; attempted REST or archive unavailability alone cannot prove permanent failure. An eventual production Research executor must require independently reviewable recovery exhaustion evidence, not just a caller-supplied SHA. Neither this synthetic-only LAB adapter nor its censor operation can unlock real original-source scoring, PAPER or money execution.

## 2. Existing V5.1 records audited — already labeled in code

| Stage | What was actually inspected | Existing labels/provenance and decision |
| --- | --- | --- |
| G2 Observation | `observation.py`, `observation_store.py` | Finalized event/decision clocks, exact manifest, per-symbol route and source epoch, `METADATA_CLOSED` vs `HOLD`, reasons, immutable `bar_hash`, compact replay. **Sufficient basis; no duplicate ledger required.** |
| G3 Exploration | `exploration.py`, `exploration_store.py` | 200 coin-directions, full 24-detector mask, BTC/market/coin regime, pattern version, source reason/grade/hash, maturity, selection groups, inclusion probability and explicit `NO_TRADE`/authority `NONE`. **Sufficient basis.** |
| G4 original deep market | `deep_source.py`, `deep_segments.py`, `source_contract.py` | Deep-20 frozen cohort, kind of raw public feed, source-epoch/sequence and SHA receipts, uncertain epochs HOLD. **Actual continuous original 20/20 verification not yet achieved.** |
| G5 virtual Research | `research_intent.py`, `research_book.py`, `research_journal.py` | Frozen source/economic/source-time and geometry contracts, unique immutable intent ID, durable actions, `ACTIVE`, `SOURCE_HOLD`, `RESTART_HOLD`, `PATH_ONLY`, `COST_PENDING_UNQUALIFIED`, max 40 slots. **New:** `CENSOR` durable explicit evidence-linked `UNRECOVERABLE_EXCLUDED` terminal audit class, with zero score and restart replay. |
| G6 economic/recovery | `recovery_contract.py`, `economic_audit.py` | Distinguishes trade path from quote/execution/funding and net-after-cost; fake original-source grading blocked. **New:** `cs00_history_recovery.py` strictly verifies supplied public aggTrade response pages and computes only retrospective first-touch. |
| G7 Learning | `learning_contract.py`, `learning_science.py` | Unique IDs, market clock, frozen known-at features, 8-source lineage, 24-detector tags, inclusion denominator, source and cost states, anti-future SHA, synthetic vs ORIGINAL/PAPER authority gate. **New:** `UNRECOVERABLE_EXCLUDED` allowed only with **net_r=None**, counted under censored; never an economic/training row. |
| G8+ models and PAPER lab | `training_lab.py`, `paper_contract.py` | Frozen data/policy/model hashes and `LAB_ONLY_NOT_SCIENTIFIC` / `SYNTHETIC_OFFLINE_TEST_ONLY`; separate model book and signed LAB proposal identity; all true owner production releases remain locked. |

**No reason to import a conflicting V4 database, replicate all incoming ticks in SQLite or build a second Learning system.** We preserve compact original evidence required for credible independent source/quote/cost verification.

## 3. Code changes implemented in `nbot-v5.1`

1. `nbot_v5_1/cs00_history_recovery.py` (**NEW**). Pure offline request planner for `/fapi/v1/aggTrades`, bounded `fromId` pagination and public 48-hour lookback guard. Strict time/symbol/aggregate-ID/duplicate/nonfinite/reordered page checks. Historical source remains **retrospective trade-path only**, never a live decision witness or market quote/funding/fill. Excluded data cannot pass the new eligibility mask. Old/out-of-REST-range gaps remain `ARCHIVE_PENDING`, not silently counted or discarded.
2. Large frozen-plan gaps of up to 500,000 aggregate IDs process only the current maximum 1,000-row page and a tiny first-touch/source digest summary; do **not** keep all price movements in RAM. With no frozen price plan, a request over 10,000 IDs is rejected rather than consuming unbounded memory. Exact first-touch stop-vs-target geometry cannot be rewritten retrospectively.
3. `nbot_v5_1/research_book.py` changed from refusing journal `CENSOR` replay to accepting **strictly held** `SOURCE_HOLD/RESTART_HOLD` synthetic research with explicit typed unrecoverable reason and recovery-proof SHA. It never produces a terminal economic result. Journal SHA replay preserves excluded records, IDs cannot be reopened retroactively; previously observed source-gap HOLD remains. `status()` exposes `unrecoverable_excluded`.
4. `nbot_v5_1/learning_contract.py` permits only **non-scored** `UNRECOVERABLE_EXCLUDED` rows alongside existing `CENSORED`, `SOURCE_HOLD` and `COST_PENDING`; `net_r` for excluded rows is rejected.
5. `nbot_v5_1/learning_science.py` reports excluded rows in **censored** and total, not synthetic-modelled/training profit.
6. `tests/test_v5_1_cs00_history_recovery.py` (**NEW**) has **27** targeted cases covering frozen first touch (STOP before TARGET and vice versa), no quote/mark/cost grade, REST recency/pagination, duplicate/out-of-window/corrupt/order faults, archive pending, aggregation discontinuity review, large-stream no-cached-ticks, excluded G7 label, censored count, durable G5 CENSOR after source HOLD, tamper/replay, duplicate censor and restart no score.

## 4. Independently verified test results

Both VPS tests used Ubuntu Python 3.12.3, an **isolated temporary shallow GitHub clone**, pinned same actual code SHA `bd0715ad2ca681263cd25c471862cd67cf93cbb7`, and:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1*.py' -q
```

| Target | Previously accepted CS-00 baseline | New CS-00 cases | All tests | Actual result | Cleanup |
| --- | ---: | ---: | ---: | --- | --- |
| Observation-VPS (`base`) | 464 | 27 | **491/491** | PASS, 52.882 seconds, exit 0 | `FINAL_TEST_TREE_REMOVED` |
| Execution-VPS (`nbot-execution`) | 464 | 27 | **491/491** | PASS, 54.938 seconds, exit 0 | `FINAL_TEST_TREE_REMOVED` |

Targeted new-file-only suite **27/27 PASS** on Observation VPS, exit 0, ~0.230s. Earlier intermediate 488/488 on both VPSs was superseded by the final pin above. No Binance REST/WSS service was contacted, no permanent collector installed or enabled, no virtual ORIGINAL-qualified results, no PAPER/testnet/real orders, no Champion promotion. Synthetic evidence alone does not close G4–G10.

## 5. Honest limitations and next CS-00 items

- **[x]** CS-00-R1 owner-approved recordkeeping and label/exclusion policy, G2–G10 existing record-label audit.
- **[x]** CS-00-R2-A **pure offline** public USD-M REST query plan/strict single/multi-page response verifier; **[ ]** actual automatic network retry/rate-budget integration into a **separately reviewed public-only** B4 live collector. There is NO hidden HTTP client or automatic runtime fetch in this commit.
- **[x]** CS-00-R3-A offline simulated continuous aggregate-ID/underlying-ID checks; **[ ]** official Binance historical ZIP/CSV + `.CHECKSUM` verification and future delayed-file availability proof; **[ ]** actual G4 former 47 trade-ID discontinuity semantics review and genuine 20/20 source demonstration.
- **[x]** CS-00-R4-A retrospective traded-price STOP/TARGET first-touch verified for synthetic pages with immutable frozen geometry and no price-only-to-economic promotion; **[ ]** original quote/mark/cost custody and verified original economic qualification.
- **[x]** CS-00-R6-A 27 new fault/record/exclusion lab tests; **[ ]** long-run 20-market REST budget/backoff, real outages, multi-session RAM/disk/CPU, and comprehensive actual service/laptop restore.
- **[ ]** CS-00-R7 real minimum-sufficient evidence/backup destination and independent off-host restore test; a laptop could be chosen, but no laptop data-transfer/service is claimed in this code acceptance.
- **[ ]** CS-00-B4 public-only durable source runner/supervisor, CS-00-C4/C5 storage/backup review, CS-00-D3/D4 live watchdog/emergency/rollback acceptance, CS-00-E2 final commissioning signoff. **Parent CS-00 remains [ ] HOLD.**
- **[ ]** CS-01 separately owner-approved public Observation start and all G4–G10 genuine original-source/scientific/PAPER parents remain pending; **G12 separately locked.**

**Critical disclosure:** The new first-touch verifier reconstructs LAST-TRADE-price path only. It cannot infer exact contemporaneous bid/ask, mark-price trigger, slippage, settled funding, or whether the Observation VPS received an event at the original decision time. A mere 64-hex recovery-proof hash is a reference, not independent authenticated proof that all recovery avenues were exhausted; future live deployment must require validated recovery receipts and an independent exclusion policy to avoid selective loss bias.

**Owner-facing final decision:** Retain V4-style small labeled records; automate public history repair in future CS-00-B4; preserve only necessary original witnesses and small backups. **Do not erase unrecoverable experiments from audit denominators, do not let them influence training/PAPER/economic claims, and do not free SOURCE_HOLD slots without verified reviewed censor.** No services started.
