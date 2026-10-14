# NBOT V5 — G2 Prospective Live Source-Evidence Acceptance (14 October 2026)

**Scope:** Observation-only G2, before G3/G4 or model learning. **Acceptance:** PASS for two independently verified live five-minute events on a frozen 50-market cohort, with explicit limits. Persistent production witness rollout is a separate, not-yet-performed operational step.

## Immutable original evidence and qualification boundary

The original G1f continuous collector /home/ubuntu/nbot_v5_sandbox and its existing SQLite at /home/ubuntu/nbot_v5_data/g1f_observe.sqlite were left running, unmodified. Older observations lack original exchange-wide ranking source and per-event quotes; they REMAIN source-unqualified for strict prospective G2/G4 use. No historical data was rewritten.

Independent opt-in G2 code ran from /home/ubuntu/nbot_v5_g2_audit_dev into a NEW private 0700 proof directory /home/ubuntu/nbot_v5_g2_proof_20261014 and 0600 proof file g2_witnessed.sqlite. Source selection captured original exchangeInfo and 24h ticker public REST payloads with original selection/server clocks and immutable SHA256; original quote/trade WSS receipt samples and epoch identities were archived BEFORE delayed REST finality checks. All Binance access was public market data; no trading keys or order APIs.

The independent replay of the frozen original source snapshot found: **927 exchange-info market rows; 525 rankable positive-turnover TRADING USDT-margined USDT perpetual markets; top 50 selected; other 475 explicitly excluded, not considered evaluated**. BTC was included. Frozen selected cohort digest 82176070c5454a174701d4e5b9e49396f070945db62cfd7372a9aac0ff9f7a82; original snapshot payload SHA256 8bf5dab15452f2f49770e56f71f2b1fa6fc1b27ace92aadde576707cc472797d.

## Two genuine, full 50-coin five-minute events

Real event opens 2026-10-14 **05:45 UTC and 05:50 UTC**. Each passed 50 WSS final candles and three separately checked REST verification stages, BTC good, 50/50 source-verified symbols, zero quarantine/health hold, 100 LONG/SHORT observed candidate slots, no UNSCORABLE. The independent read-only source acceptance program produced PASS, violations=[], exactly 2/2 fully source-verified OBSERVE_ONLY event manifests, 200/200 candidate records, 100/100 original bid/ask, quote/trade receipt and source-generation witnesses, zero source-held rows, no unrepresented time slots. Separate 96-bar past-only feature/detector replay matched **200 of 200** originally recorded directional observations. Witness data is explicitly **local WSS/REST observational evidence, NOT cryptographically exchange-signed quotes or confirmed executable fills**.

The bounded observer reported result OBSERVATION_ONLY_RUN_COMPLETED, reason null, reconnect_attempts=0, trade_gaps=0, peak RSS 61.33 MiB, final data footprint 7.65 MiB including WAL, no training labels, research_ready=false, order_authority=NONE and both market/public sources disconnected cleanly at planned test end. After clean shutdown, SQLite PRAGMA integrity_check=ok. **Preserved evidence SHA256** of g2_witnessed.sqlite: acc7dcb1e7de9c8a7f65041dffa1ca38a267d8bfa4c252d84e8500562995664f. Never delete or mutate this proof file.

GitHub isolated Observation code SHA 9b890098e1050a84de30d788ff32fbf6866b7b49 passed **206/206 automated Python 3.12 tests**, https://github.com/samqju/Nbot/actions/runs/38519602049. Separate remote VPS G2 replay/acceptance tests 30/30 PASS, read-only actual database source acceptance and independent feature replay both PASS. Original V5 service remained active/enabled PID1082, zero restarts, hourly G1g health PASS and legacy V4 units inactive. Execution VPS untouched. Temporary G2 data capture process stopped by SIGINT after both windows, exit 0.

## Formal STOP/GO and scope

**G2 SCIENTIFIC candidate-population and prospective at-event market-source acceptance: PASS for these two bounded live windows and the specifically frozen 50-member cohort.** This meets the original G2 rule that each accepted event has full symbol-by-side candidate records, original immutable as-of evidence, source/feature digests, reproducible policy-selected membership and explicit exclusions. The original roadmap permits bounded claims where historical evidence cannot recover all records. G2 does NOT confer source qualification on preexisting unwitnessed historical records, any opportunity classification for the excluded 475 markets, or executable bid/ask/fill/funding certainty. It does not establish any matured trading outcomes, statistically valid edge, profitability, calibrated Champion or permission to place paper/real orders.

**Remaining operational dependency (not a retroactive G2 research PASS claim):** The existing long-lived G1f service has not yet been migrated to G2 source witnessing. Before future continuous observations feed G4 economic labels, a separately tested restorable operational rollout must enable the opt-in G2 witness with a matching health monitor, preserve old files and verify new genuine sustained observations. One-time proof cannot assert a production service upgrade.

**Next original roadmap stage:** G3 BTC-aware regime and per-coin structure may begin OFFLINE using only appropriately qualified G2 cohorts. No G4/G5 economic learning, G6 training, E6B operational Execution integration or live/paper authority is implied.
