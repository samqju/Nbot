# NBOT V5 — Genuine Binance G4 Source Acquisition Pilot and Mandatory Quality HOLD

**Date:** 2026-10-14; **source host:** actual Observation VPS `ubuntu@base`, reached through connected Sameer-Laptop/PuTTY Observation-VPS. **Scope:** read-only public HTTPS market-source pilot + separate offline verifier; not a service deployment, live database write, full G4 forward outcome, trading ledger, accepted G1 24h or operational G4 scientific PASS.

## 1. Preservation and security

All pilot source artifacts are retained under the **existing** restricted historical backup hierarchy:
`/home/ubuntu/nbot-backups/g4-source-pilot-20261014/` (private `umask 077` files, no production data directory change). This is not another V5 release/worktree/service. Original raw response bytes, captured HTTPS response headers, clock files, SHA digests, raw Binance ZIP and its companion CHECKSUM are all preserved. `nbot-v5-g1g2g3-observation.service`, its code SHA, live SQLite, WAL, health timer and all F0/G1f/G2/G3 databases remain unchanged.

## 2. First genuine source: official QNTUSDT 2026-10-12 daily aggTrades

Selected frozen-50 market: **QNTUSDT**. Official source, independently HTTPS certificate-verified:
- ZIP URL `https://data.binance.vision/data/futures/um/daily/aggTrades/QNTUSDT/QNTUSDT-aggTrades-2026-10-12.zip`.
- Companion `.zip.CHECKSUM` from same official HTTPS origin.
- Captured **2026-10-14 08:41:54 UTC**. HTTP headers saved; ZIP size **3,432,817 bytes**; one CSV member **16,655,778 uncompressed bytes**.
- `sha256sum -c ...CHECKSUM` returned **OK**, confirmed after TLS GET.
- ZIP SHA256 `a6b241b6bf911d9d58776ccd51850c5cd56b9acf0183ac51a2e3ae2ece442f7c`.
- Raw CHECKSUM file SHA256 `5e4862c46770e0e132b2b07378a3612f023af8776f1c8ddd55c3980fdf6f863d`.
- Importer canonical rows SHA256 `7999b56370cdf42967d8cdc41b400c5259d3297294f82c3470225de989ae2b50`.
- CSV contained 278,165 actual aggTrade data rows plus one header. Aggregate IDs **99,853,796 through 100,131,960, fully consecutive**.
- First actual trade timestamp `1791763200158` (2026-10-12 00:00:00.158 UTC); last `1791849595855` (2026-10-12 23:59:55.855 UTC). ZIP CRC validated with Python stdlib.
- Underlying trade-ID **gap count = 158**, each gap of one ID, **158 underlying IDs absent** from adjacent market aggTrade records; event chronology remained monotonic. The first 10 examples and SHA manifest `e3190f2a7d4e7a904ff2386e5297b46fe1e5730f8fdbcd4dbad31887b8b8a993` are retained in the JSON validator report. **No factual claim that these 158 IDs prove network packet loss**: Binance's documentation states that aggTrades cover market trades, not certain insurance-fund/ADL classes; additional classification may be necessary.

**Scientific decision:** original HTTPS-delivered archive and checksum byte-integrity pilot **PASS**; end-to-end complete underlying trade-ID grade **HOLD**. The safe parser records `HOLD_UNDERLYING_TRADE_ID_GAPS`, never silently merges/truncates gaps or invents prices. It permits provenance-bearing ingestion **without** marking the entire day an executable-fill-grade path. Verification manifest SHA256 `4fbb55f11f529aab5b542317b48ef74b63bd52732f548390b90e52ea246f792c`. `original_archive_verified=false` and `origin_and_custody_independently_verified=false` intentionally remain false inside the source ZIP parser, even when this separate TLS/certificate+checksum capture is attached: exchange cryptographic content signatures, controlled independent custody and complete executable path are distinct claims.

The first strict importer correctly HOLDed on underlying gaps. Read-only `tools/v5_g4_archive_diagnose.py` isolated the 158 breaks, enabling a **scientifically honest correction**: preserve every original row, report all gaps and independently withhold path acceptance. G4 source importer later verified the full archive byte checksum, row clocks, canonical rows, gap metadata and source manifest. This is a source-acquisition/quality result, not backtested trading profitability.

## 3. Three additional genuine public prospective source snapshots

One bounded HTTPS GET each, all ORIGINAL response bodies, HTTP headers and `request/received` UTC timestamps saved under the same private backup subfolder:

| Kind | Capture UTC | Original raw response body SHA256 | Use limitations |
|---|---|---|---|
| QNTUSDT USD-M Futures `/fapi/v1/ticker/bookTicker` | 08:49:32–08:49:33 | `801be27857243df99aadd51217ccb838a21f015095a6127eeeb73654c8635d77` | A genuine prospective quote **only when captured**; NOT proof of price at any prior stop/exit |
| QNTUSDT `/fapi/v1/fundingRate?limit=5` | 08:49:33 | `a4b442763dc5b479aaf908df8f64bde4232118a8a6cd89385ba795bf04e183ee` | Historical posted funding samples; NOT predeclared future effective funding or an account-specific actual charge |
| QNTUSDT `/fapi/v1/aggTrades?limit=10` | 08:49:33–08:49:34 | `3ce5c3f99a2828965d8178227ab161c23d469d771f82e38bb95117cb79104404` | Bounded recent market-trade sample, **not** an uninterrupted decision-to-4h-exit tape |

These are **not automatically matched to any accepted G2/G3 event** and carry zero scored labels. Fee tiers, borrow/impact costs and executable quantity remain separately unproved. The snapshots are insufficient to model all arbitrary exit-time quotes across 50 markets.

## 4. Source acquisition engineering and independent tests

G4 branch `feature/v5-g4-offline-contract-20261014` retains all prior 367/367 synthetic contract tests. New `nbot/v5/g4_https_capture.py` provides fixed-host/endpoint bounded synchronous public HTTPS requests only, content SHA and receipt metadata, exact URL/host and redirect checking, clock validation, strict max response size and no account/private/trade/order capability; injected test transport clearly marks resulting receipts **UNVERIFIED**. 20 additional negative/mock tests cover symbol, future/stale quote, malformed bodies, changed host/URL, oversized content and 429 rate limits.

`g4_archive_import.py` now rejects nonpositive or invalid Decimal price/quantity, wrong UTC trading date and non-final daily archives; imports authentic raw rows with explicit underlying-trade-ID gap manifest rather than manufacturing contiguous paths. `tools/v5_g4_archive_diagnose.py` is a read-only forensic tool, not an acceptance bypass. Original `g4_price_path.py` remains fail-closed on gaps: changing archive import policy does **not** automatically approve a fragmented price-path or scored outcome.

Official GitHub Actions 2026-10-14 at G4 SHA `9f7d630d7ee004df936ede4552e754a15557fb7a`: **391/391 PASS** in the observation/G4 suite; https://github.com/samqju/Nbot/actions/runs/38537984726. G4 draft PR https://github.com/samqju/Nbot/pull/39 stays unmerged. Earlier temporary CI failures were genuine test-fixture clock assertions (the validator now correctly refuses same-day premature archive and wrong-date rows), fixed before the 391-test green run.

## 5. Exact stage truth and next GO/HOLD

The current integrated G1/G2/G3 collector first started uninterrupted soak 2026-10-14 06:46:04 UTC. Last independently checked at 08:50:55 UTC: same PID 11327 and unchanged start, NRestarts=0. Before the new source pilot, at 08:37:27 UTC direct health PASS showed 22 events, 2,200 candidate observations, 1,100 original G2 witnesses, 22 G3 contexts and no violations. **These are not G4 labels**.

- **Completed safely:** real original historical archive HTTPS acquisition+checksum proof; actual protected source raw files, hashes/headers/clocks, independent archive forensic and fail-closed gap report; three original public source samples; audited archive/importer and HTTPS source code in draft G4 branch; 391/391 CI.
- **Still pending:** integrated 24h G1 operational gate (earliest 2026-10-15 06:46:04 UTC / 12:16:04 IST); frozen prospective risk/entry/exit/funding/cost policy before relevant future decisions; **uninterrupted** per-symbol prospective source acquisition across chosen symbols including aggTrade events and best bid/ask quotes at arbitrary exits with source epochs, reconnect/gap and bounded resource tests; independent fee/impact/funding witness and after-cost replay; isolated SQLite research ledger verified restored, no existing source mutation; real matured quote-grade outcomes and valid complete unselected denominator; formal reviewed scientific G4 GO/HOLD.
- Real USD-M websocket architecture must follow Binance's **2026** public/market host split (`wss://fstream.binance.com/market`, appropriate `@aggTrade`, `@bookTicker` and funding/markPrice streams), not silently assume old V4 paths. Future public capture MUST be separately resource-budgeted so the live 200-MiB G1 service is never starved. No durable G4 source service, scheduler or VPS worktree created by this pilot.
- **G4 operational scientific verdict: HOLD**; there are **0 verified matured after-cost research outcomes**, 0 Execution paper trades and 0 exchange fills. Do not unlock G5/G6 on the basis of 391 tests or 2,200 candidates.

**Rollback:** stop none, restore none; the original integrated release is untouched. The temporary offline G4 branch/PR can remain unmerged. The new pilot files are append-only evidence and must not be deleted during consolidation without checksum/restore and owner approval.
