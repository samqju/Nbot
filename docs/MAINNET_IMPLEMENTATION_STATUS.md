# Mainnet implementation status

The three-mode implementation now includes an explicit small mainnet trial.
Use [the complete mode setup and switching guide](TRADING_MODES.md).

This is separate from automatic Research/Paper Champion approval. Those economic
gates have not been declared passed. Publishing code does not deploy or arm a
server, prove account compatibility, or place an acceptance-test order.

The mainnet managed process still requires manual restart after a VPS reboot.
See the recovery section before using it.

## Release validation — 2026-10-02

- Full Linux regression: 1,128 tests passed.
- Targeted mainnet/learned-paper suite: 69 tests passed.
- Mainnet end-to-end test includes HTTP recommendation, simulated exchange entry
  and stop, restart, close, and durable outcome acknowledgement.
- Eight tiny-profile Observation units render; guide shell/Python examples parse;
  tracked example credential fields are blank.
- Validation used the isolated /home/ubuntu/nbot-mainnet-build checkout.
  The running /home/ubuntu/Nbot checkout was not updated or armed.
- No authenticated mainnet order acceptance test or profitability validation was run.
