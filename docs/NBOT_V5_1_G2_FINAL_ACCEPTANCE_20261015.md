# NBOT V5.1 — Entire G2: Read-only 100-Coin Observation Engineering Acceptance

> **CURRENT STATUS POINTER — 15 October 2026:** G2 read-only engineering and initial genuine 100/100 public Binance source checks passed. Later source-only canaries wrote real G2/G3 records into the V5.1 owner backup root. That is not a sustained 100-market production verification; G4 subsequent deep quote staleness caused safe stop. Historical text saying there are no actual records reflects this document's original milestone date, not the latest status. [Latest live-status and next-chat handoff](NBOT_V5_1_NEXT_CHAT_START_HERE_LIVE_G1_G3_PASS_G4_BTC_QUOTE_HOLD_20261015.md). The original numbered acceptance sections below remain historical and are not rewritten to suggest broader evidence.


**Later G3 completion note (15 October 2026):** After this report established its own stage PASS, the separately evidenced G3 causal Exploration gate was also completed. **Current G0/G1/G2/G3 all [x]**, **G4 next [ ]**. [G3 final acceptance](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), commit **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**; source SHA `5d9707fe8521bbe17e96036aef0a5ec44a784a96`, 157/157 tests on both Python3.12.3 VPSs, actual public 100→200 mask and no trades. Old “G2/G3 next” statements below are **historical at original report time**, not current unfinished gates. See [current next-chat handoff](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md). No G1/G2 historical test or release claim changed.

**Date:** 15 October 2026 IST  
**Branch:** `nbot-v5.1` only; historical GitHub branches and default branch untouched.  
**Evidence-backed result:** **G2-01 through G2-06 / parent engineering G2 PASS** for **read-only lightweight closed-five-minute Observation**. **Not** a production streaming-service release, an independently authenticated trade/quote custody grade, a profitable model, or an order/trading permission.  
**Reference:** Authoritative Engineering Roadmap §4 G2 and §3 D0–D2, and Vision V1.9 §8G–§8H (owner's approved **100 broad / 20 deep / 40 virtual** design).  
**Exact source revision tested on BOTH VPSs and for public/binance and benchmark:** `4ba07385bb06ad8cde2460d83953448386f1a751`.

## 1. G2 scope mapping and independent completion ticks

The owner requested completion of ALL G2 under roadmap audit continuity, without skipping microtasks.

- [x] **G2-01-A — Public USD-M market eligibility:** Require TRADING, PERPETUAL, USDT quote AND USDT margin (USDⓈ-M) plus qualified liquidity, bid/ask spread, minimum 96 completed-bar history, healthy source markers. Every rejection is coded and auditable. Invalid NaN/Infinity and malformed market fields reject, not coerce.
- [x] **G2-01-B — 100-coin deterministic category selection:** Up to 50 turnover-ranked, 25 gainer-ranked, 25 loser-ranked, deduplicate overlapping symbols, preserve all original group tags, force qualified BTC into the selected set and deterministically fill remaining places by already-qualified turnover. Exactly 100 when enough qualify, otherwise honest smaller cohort; never manufacture BTC if invalid.
- [x] **G2-01-C — Point-in-time source manifests:** Store explicit selection/as-of clock, current eligible/rejected denominator, group tags, normalized source hash and strictly checked triple raw public-source SHA256/independent receipt times (exchangeInfo/24h ticker/bookTicker) with maximum 15-second inter-source skew and 60-second staleness limit. A spoofed decoded body vs recorded raw bytes, wrong endpoint or future time is HOLD.
- [x] **G2-02-A — Five-minute finality:** Strict 300,000-ms aligned immutable OHLCV with close-time = open+299999, `received_at_ms >= close+1`, full finite positive price/volume validation. A REST response's still-forming latest kline cannot enter a closed candle record.
- [x] **G2-02-B — Bounded 100-symbol histories and historical bootstrap:** Per-symbol rolling 96 finalized bars (max 9,600 entries total), strict 96-bar continuous bootstrap with as-of clock, explicit source/route/epoch checks, no stale/future features, rejected duplicates/conflicts and source discontinuity.
- [x] **G2-02-C — Source reconnect and HOLD:** New connection/epoch never fabricates continuity. Gap, missing candle, stale candle, malformed candle, future receipt, wrong epoch or route and insufficient bootstrap remain **HOLD** until qualified 96-bar history is explicitly re-established.
- [x] **G2-02-D — Full observation denominator/BTC/breadth:** Each observation event produces exactly one record per current manifest symbol, up to 100; each records known-at clock, source state, history count, route, epoch, candle metadata hash and precise missing/HOLD reason; BTC safety/breadth and aggregate healthy/HOLD count calculated. All prices remain **METADATA_CLOSED only**, not independently proven original trade/quote evidence or economics.
- [x] **G2-03-A — Compact persisted manifest and event snapshots:** A private owner-only append-only-intent directory with versioned JSON receipts, deterministic SHA256, first-file fsync and directory fsync, immutable event IDs, duplicate verification and strict schema/replay validation. Disk-bound quota; no silent record rotation/pruning or credential contents.
- [x] **G2-03-B — Exact public source byte custody interface:** `PublicResponse.raw_bytes` retained at the public boundary. The separate compressed `PublicSourceArchive` fsyncs byte-exact public exchangeInfo/ticker/book/klines GET responses, receipt time, source URI and raw hash; replay verifies gzip, raw SHA, owner permissions and file naming. Fail closed on corrupted/unknown/incomplete files, symlinks, mismatches and full disk. This is **public REST capture** only, **NOT** independently authenticated original tick/quote/funding custody or WORM/off-host evidence.
- [x] **G2-04-A — Explicit public network safety:** GET-only hard-whitelisted Binance USDⓈ-M `/fapi/v1/exchangeInfo`, `/ticker/24hr`, `/ticker/bookTicker`, `/klines` (5m; bounded symbol/limit); HTTPS, bounded body and request timeout, no redirects, no API keys or signed/account/order endpoints, fail-closed public request weight budget. **Network disabled by default**, one-shot test explicitly requests `--public-network`.
- [x] **G2-04-B — Actual public one-shot 100-cohort verification:** On Observation-VPS, one-time authenticated-TLS public HTTPS GETs with **zero secrets or order actions**. 100 qualified names, BTC present, **each has at least 96 contiguous closed five-minute bars**; same as-of snapshot yields **100 METADATA_CLOSED, zero HOLD**, public source age 32.657 seconds; 3 market-wide source SHA witnesses plus 100 kline responses, weight **246**. Temporary archive replayed all **103 receipts**, totaling **792,894 compressed bytes**, then test archive and Git checkout automatically cleaned.
- [x] **G2-05-A — Exhaustive deterministic regression and negative tests:** G1 67 existing tests plus 33 G2 universe/bar/store/client tests, 10 byte-exact source archive tests and 10 raw-source time/authentication-hardening tests = **120/120 PASS, no errors/failures** under **Python 3.12.3 on Observation-VPS AND independently Execution-VPS**, using exact same GitHub SHA `4ba073...`.
- [x] **G2-05-B — 100-symbol capacity / 100% denominator:** Both VPSs separately benchmarked 100 symbols × 96 closed candles × **120 five-minute events** with ten injected disconnected symbols from event 40 onward; per-event 100 records preserved and 10 honest HOLD states, no missing duplicates, capped 9,600-bar memory. **p95/p99 latency, RSS, CPU, disk** measured; all declared limits pass. Synthetic mock 103 public calls incurred **246 simulated request-weight units**, below 600-unit budget, no real HTTP during benchmark.
- [x] **G2-05-C — Independent source/code diff and error audit:** G2 changed only new V5.1 read-only code, offline tests, one-shot probe, synthetic benchmark and current V5.1 documentation; no old V4/V5 runtime copy, Binance private action, VPS service deployment or execution unlock. The first 100-test run discovered a PosixPath type handling issue and two faulty fixture expectations; fixed and rerun PASS. Later raw/decoded source mismatch and nonpublic-path access adversarial tests exposed real guard defects, fixed and full 120-test suite PASS.
- [x] **G2-06 — Parent gate acceptance:** G2-01..05 have distinct actual code/test/source/capacity evidence and the limited source-grade claim is explicit. **G2 engineering PASS** under the authoritative read-only lightweight Observation acceptance; **G3–G12 remain [ ]**, no future stage or trading release inherited.

## 2. New and modified code, audit provenance

Code base before G2: branch HEAD `67c90784b3ebe2475672af39a3c429c4b2fdd479` (entire G1 complete). G2 source HEAD tested: **`4ba07385bb06ad8cde2460d83953448386f1a751`**.

| GitHub file | Function | Git blob SHA-1 at G2 test HEAD |
| --- | --- | --- |
| `nbot_v5_1/universe.py` | Qualified deterministic USD-M 100-coin cohort, point-in-time selection/source hashes/reasons | `01f71151708c48e1f2eaa5983f5bb45195c5bd13` |
| `nbot_v5_1/observation.py` | Immutable finalized OHLCV, 96-candle per-symbol ring, route/epoch/gap HOLD, 100-row event | `3c0ae57a63af33b6520e76e9afa32167bacfa4f4` |
| `nbot_v5_1/observation_store.py` | Owner-private bounded fsynced manifest/snapshot receipts | `bcd628f9cd19b7bb3b626948aaaf3973cc1972cb` |
| `nbot_v5_1/public_market.py` | Explicit opt-in, budgeted HTTPS public GET-only adapter, source/raw-as-of verification | `4dbdececa170a582051c0e4ae191323e10e63994` |
| `nbot_v5_1/source_archive.py` | Byte-exact gzip public REST receipt source custody with replay/quotas | `b648086a79430687966d5718d7ab19e8da4918e1` |
| `scripts/g2_readonly_probe.py` | One-shot user-authorized public smoke + temporary source replay; no service | `d520e283ec412fbc50b6b905b838ae0c9787c4a9` |
| `benchmarks/g2_observation_benchmark.py` | Synthetic 100×96 closed-candle 120-event p95/p99/RSS/CPU/disk benchmark | `14715b1d2b52cd4eff3fa180a2b1fd177ae4f5ed` |
| `tests/test_v5_1_g2.py` | U01–U10/O01–O12/S01–S07/P01–P04 (33 cases) | `3208462a9eaa6dde1736137bcc77a805e8f4a3b3` |
| `tests/test_v5_1_g2_archive.py` | A01–A10 (10 byte-exact source custody cases) | `62011a9a5c0110545397d93ab04742fc13fb9c41` |
| `tests/test_v5_1_g2_receipts.py` | R01–R10 (10 independent-source hardening cases) | `b8a81f61043cc62e27dce5e39013b341cbfdefb0` |

All G2 GitHub paths were read back and verified after implementation, and the actual VPS test/bench/probe commands cloned `nbot-v5.1` from GitHub at the same `4ba073...` code SHA. No app files changed afterwards; only this report and roadmaps will follow.

## 3. Actual test evidence on both target hosts

**Command:** `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py' -q`, invoked in separate shallow GitHub clones within Python `TemporaryDirectory` over preexisting authorized SSH/PuTTY profiles. Both use Python **3.12.3**, Linux; no service or permanent NBOT deployment.

| Host | Source revision | Result | Exit |
| --- | --- | --- | --- |
| Observation-VPS `base` | `4ba07385...` | `Ran 120 tests in 3.308s; OK` | **0** |
| Execution-VPS `nbot-execution` | `4ba07385...` | `Ran 120 tests in 3.377s; OK` | **0** |

The previous 67 G1 test cases remained passing; no paper/REAL permission changed.

## 4. Actual 100-symbol capacity results

**Command:** `PYTHONDONTWRITEBYTECODE=1 python3 -B benchmarks/g2_observation_benchmark.py` run separately on BOTH VPSs, exact GitHub revision `4ba07385...` with a temporary private filesystem. **100 selected symbol records, 96 closed bars each, 120 five-minute events, 10 injected source disconnections**; verified 100-row denominator and per-gap HOLD on each event; replayed **121** compact records (manifest plus 120 events). No live API requests in this measurement.

| Measured quantity | Observation-VPS | Execution-VPS | Gate limit |
| --- | ---: | ---: | ---: |
| Event p50 latency | 10.831 ms | 9.756 ms | Informational |
| Event p95 latency | **50.500 ms** | **51.823 ms** | Informational |
| Event p99 latency | **51.867 ms** | **60.326 ms** | **1,000 ms** |
| Worst event latency | 63.083 ms | 71.353 ms | Informational |
| Peak process RSS | **37,964 KiB** | **37,868 KiB** | 245,760 KiB |
| Process CPU, complete run | 2.2465 s | 2.1026 s | Informational |
| End-to-end benchmark wall | 2.7698 s | 2.7743 s | Informational |
| Persisted compact receipts | **2,713,184 bytes** | **2,713,184 bytes** | 33,554,432 bytes |
| Synthetic public request weight | 246 | 246 | 600 |
| Result | **PASS** | **PASS** | All hard limits passed |

**Limits of this result:** p95/p99 refer to local event + compact persistence processing under synthetic deterministic data. They do **not** include real HTTPS latency, actual Binance WSS disconnections, live rate bans, original trade/quote archive handling, model inference or active paper/real positions. VPS CPU/RSS cover this temporary isolated run, not an installed always-on production service. Finite receipt quotas **fail closed**, not silently delete important evidence.

## 5. Real public USD-M source verification — one-time, explicit read-only permission

**Observation-VPS, 15 Oct 2026 06:49:52 UTC**, exact tested G2 source SHA `4ba07385...`, command `python3 -B scripts/g2_readonly_probe.py --public-network --max-history-requests 130`, executed once inside a temporary GitHub clone and source replay directory. Public TLS GET only; no account IDs/keys, private endpoints, trade submission or paid market service.

- ExchangeInfo response: **927** symbol rows; 24-hour ticker: **793**; bookTicker: **795**.
- Qualified/deduplicated V5.1 universe: **100 of 100**, including mandatory **BTCUSDT**; each of the 100 passed public bid/ask, history/market, contract and source checks.
- All 100 had at least **96 continuous finished five-minute candles** with reception no earlier than bar finality; common latest five-minute event `1792046400000` ms, as-of decision `1792046992423` ms. **100 METADATA_CLOSED, 0 HOLD**, 100 denominators, no future candle admitted.
- Source snapshot age **32,657ms** (strict ≤60,000ms), independent exchange/24h/book source times coherent; all source HTTP bytes validated as matching decoded payloads; all original public-byte responses retained in a temporary private audit archive, **103 receipts replayed without errors**, gzip **792,894 bytes**. Temporary archive and test Git clone cleaned on completion.
- Actual public request-weight budget used **246**, below configured 450-unit one-shot limit. Request bounded, no persistent market subscription.
- Public response witness hashes (SHA-256): exchange `80aa9cb036c78e2e825e21b5e9a8f40cc14c836635cea498e728d909299d3eb3`, 24-hour ticker `1c2db18b2f269f89bbc50c4955da97452beae4f82dc783ca023e9161b4341c6b`, book `00951a2fc3d39dcfd8a0cada3a296e111b77ad6493cc3b9d7f4d810ccf507e2d`; combined public archive receipt root `717c9e09b1825ed6798f7629fab71e3d3d8663375aa66fafa044bd731620bf69`.
- Manifest identity `f44d14b0f50dbe50e86e9152e65639563d477bfbcd766f47f872b1b400ab682c`; snapshot identity `54c6d59101dd3dca7cc29f4add046c41bad5a70b5f754db27a86e34ed53fadc9`. Independent public receipts were checked against exact source time and typed known-at manifest.
- Source grade is explicitly **`PUBLIC_REST_METADATA_NOT_ORIGINAL`**, **NOT** `ORIGINAL_VERIFIED` nor `AFTER_COST_QUALIFIED`. Public OHLCV identity and HTTPS are NOT independent market trade/quote/funding custody, and these receipts do NOT qualify a profitable virtual outcome.

The one-time original bytes were held for **test replay only** in an automatically deleted temporary directory; **the production original-source retention pipeline has NOT been deployed**. Reproducible code exists to persist new source receipts with explicit quotas under a separately approved operational phase. Do not claim persistent on-host running source collection from this smoke test.

## 6. Safety, recovery and exact next gate

**G2 PASS** is limited to a read-only **engineering acceptance** with offline failure, scale and real one-shot public-data verification, NOT an always-on Binance subscriber or a market-science/revenue claim. All current G1 RunConfig nontrading defaults and guardian veto remain intact. No Binance API key, account access, WebSocket user stream, position, paper or real trading mode exists here.

Important future gates are not waived:
- **G3** must independently audit all 24 legacy V4 detector definitions, known-at structural features, 200-direction denominator and capacity/skipped-source labels. A 100-symbol G2 candle snapshot does NOT imply 24 detectors or successful strategies.
- **G4** must build and demonstrate the continuous original deep-20 trade/quote/funding evidence custody, bounded archival retention and crash/restore path with qualified original proof — not inferred from broad REST candles.
- **G5–G6** require rolling 40 virtual intents, source-first-touch stops and genuine after-cost economic outcomes. **G7+** paper gates and any real-money approval remain separately LOCKED.
- Production scheduling, durable off-host scientific backup, long-duration uptime/restarts, physical VPS power-loss integrity and market-provider rate bans remain future **operational acceptance** items and cannot be claimed as validated from a synthetic 120-event benchmark.

**Legacy data waiver:** Owner's previous no-backup decision applied solely to obsolete installations. New V5.1 market evidence must never be silently deleted as a workaround for quotas or missing restoration. Broad-source archive and snapshot stores currently **HOLD** on full quota, damaged data and unsafe filesystem conditions; no lossy auto-rotation is enabled.

## 7. Future-chat handoff

When a chat limit is reached, start by reading this report, then the Owner and Engineering Roadmaps at branch `nbot-v5.1` and the authoritative Vision V1.9. Continue with **G3-01** (actual reviewed detector list/provenance), one small evidence-backed milestone at a time. Avoid default-branch changes, old code wholesale copies, missing-history extrapolation, fabricated economics and ALL paper/REAL unlocks. Keep every microtick backed by exact GitHub commit and executed test/source evidence.

**G2 completion decision:** **G2-01–06 [x] and G2 parent [x]**, evidence above. **G3+ [ ]**. No trading access granted.
