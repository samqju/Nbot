# Phase 7.5D.2B.2 — Multi-Horizon Research Data Layer

## Purpose

The research-backed benchmark families adopted in Phase 7.5D.2B.1 need more
history than the legacy ~50 completed five-minute candles. B.2 adds a strictly
public, point-in-time history boundary for strategy research.

The layer exposes:

- up to 90 completed days of hourly bars;
- up to 365 completed daily bars;
- quote volume on every bar, required for liquidity-conditioned momentum;
- an explicit `as_of_ms` boundary so future or still-open bars are excluded;
- backward pagination when more than Binance's 1500-row page is required.

`COMPLETE_PHASE7_5D2B2` means the full requested history horizon is present
(currently 2160 completed hourly bars and 365 completed daily bars). Individual
strategy-readiness flags remain separate and may be true for a newer symbol that
has enough history for one benchmark but not the complete B.2 research horizon.

## Why 1h and 1d

Daily history supports the initial 14-day cross-sectional momentum/liquidity
benchmark and multi-week time-series momentum reference. Hourly history gives the
conditional intraday momentum/reversal family substantially more context without
forcing published daily/weekly ideas into the legacy 5-minute setup window.

## Safety boundary

B.2 does not:

- add or remove candidates;
- alter the ten legacy detectors;
- change `RULE_SYSTEM_V1`;
- create virtual trades;
- restart or alter automatic training;
- touch the Execution worker;
- grant paper or real-order authority.

The live check is intentionally limited to at most 20 symbols. Full-universe
refresh scheduling and caching belong to the later research-runtime integration
phase, after the data boundary is proven.
