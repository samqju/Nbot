# Phase 7.1A — Universe Warmup Admission Hardening

Phase 7.1 runtime validation exposed a pre-existing Observation startup failure:
a newly listed/prospective symbol can satisfy universe ranking filters while still
having fewer than Strategy's required 50 completed five-minute candles.  The
previous hot-reload path warmed prospective additions before committing the new
universe, but allowed a warmup failure to escape and terminate the Observation
Worker.

This hardening keeps the existing 50-candle Strategy requirement unchanged.
Universe refresh is treated transactionally:

- build the prospective execution/observation universes;
- warm only newly added candle symbols;
- if every new symbol warms successfully, commit the new universes/snapshots;
- if any warmup fails, record `FAILED_WARMUP`, log
  `UNIVERSE_REFRESH_WARMUP_REJECTED`, keep the current proven universes and
  persisted snapshots unchanged, and continue Observation startup/runtime.

No candidate rules, model vectors, market-context values, risk rules, Execution
logic, or order authority change in this patch.
