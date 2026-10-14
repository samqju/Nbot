# NBOT V5 — G1G 12-hour checkpoint and G2 population audit (14 October 2026)

**Safety:** Observation-only engineering; no training, recommendation producer, model or order authority. No change to running V5 collector, historical V4 or Execution VPS.

## Twelve-hour G1G checkpoint

Direct Observation VPS inspection at 2026-10-14 05:00:52 UTC / 10:30:52 IST: host base, 12h14m uptime, boot ID 9bc008f6-eaa2-4ced-8a9d-c3f54f3b5a6e. V5 observer active and enabled, MainPID 1082, NRestarts=0, MemoryCurrent 101195776 and MemoryPeak 111292416 bytes versus 209715200-byte limit. All seven known old V4 Observation units were inactive; all five retired boot entries disabled. The hourly health timer active/enabled, most recent audit triggered at 04:57:56 UTC. Direct read-only G1G health result PASS: SQLite quick_check=ok, 152 persisted five-minute event manifests, 15,090 OBSERVED and 110 UNSCORABLE two-sided candidate records, order_authority=NONE and research_ready=false. Live heartbeat showed both public Binance WSS routes connected, reconnect_attempts=0, trade_gaps=0. Hourly audit journal showed successive PASS checks.

**Disposition:** The owner replaced the intended 24h soak with a 12-hour check at 10:30 AM IST, so this is a 12h operational PASS, NOT a proven 24h soak or a real disconnect/recovery qualification, and NOT model or order readiness.

## Initial G2 independent full-denominator audit

Created isolated GitHub Observation branch feature/v5-observation-g2-20261014, without merging into the running V5 or Execution workstreams. G2 audit module reads the existing SQLite database read-only to verify single frozen BTC+coin cohort; full LONG/SHORT candidate records, 24 pattern slots per record; frozen cohort and event/candidate SHA proofs; as-of event/source clocks; evidence immutability; all missing/unavailable reasons; permitted HOLD events and visible initial setup periods; and zero orders, model training or recommendation authority. Missing/tampered slots cause HOLD rather than apparent profit.

Synthetic regression: 10/10 tests PASS on Observation VPS. GitHub Actions isolation workflow at commit 80277c2826b56a928d10e65d84794fb11d80b640: 166/166 tests SUCCESS (https://github.com/samqju/Nbot/actions/runs/38515064045).

Live G2 audit run from isolated worktree /home/ubuntu/nbot_v5_g2_audit_dev returned **PASS with no violations**: 154 consecutive five-minute event manifests, 50 symbols, expected/present 15,400 two-sided candidate slots, 15,290 OBSERVED + 110 UNSCORABLE. Six events had explicit HOLDs. The 110 UNSCORABLE records consist of 100 in an earlier declared offline event and 10 with TRADE_NOT_FRESH. Multiple reasons can describe the same candidate, so reason counts are not additive. No gaps exist between committed five-minute manifests. The frozen cohort's bootstrap was two five-minute slots before the first committed observation; these setup slots are explicitly excluded and no pseudo-records fabricated. SQLite integrity and candidate SHA proofs PASS. No mature financial outcome labels, trading decisions or authenticated recommendation outputs exist.

## E6 interface and future work

Separate Execution branch feature/v5-execution-foundation-20261014 previously passed E1-E5 72/72 synthetic tests. **E6A offline signed protocol/security compatibility development can proceed. E6B operational integration remains HOLD**, because Observation has not yet built a validated first Champion and compatible authenticated recommendation producer. The 15,290 observation slots are *not* 15,290 matured, after-cost economic outcomes.

Next Observation steps: independently design frozen hypothetical outcome labels, maturity/censoring, verified forward price paths, conservative fees/slippage/funding and chronological training cuts; validate baselines before first model; implement a versioned paper-only recommendation producer only after the scientific gates. Do not restart Observation or activate Execution paper/live services without independent readiness evidence.

**Overall:** G1G 12h operational PASS; G2 candidate population integrity PASS; complete G2 outcome learning and all G5/G6 model gates HOLD; E6A OFFLINE ALLOWED, E6B operational connection HOLD.
