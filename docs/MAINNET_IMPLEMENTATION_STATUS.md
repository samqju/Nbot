# Mainnet implementation status

The three-mode implementation now includes an explicit small mainnet trial.
Use [the complete mode setup and switching guide](TRADING_MODES.md) and
[the all-mode command reference](ALL_MODES_COMMANDS.md).

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


## Current three-mode command boundary

The existence of the bounded mainnet route does not replace the other profiles:

~~~bash
# Testnet
./nbotctl arm testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl entries enable testnet-trade

# LIVE paper
./nbotctl cluster start live-paper
./nbotctl entries enable live-paper

# bounded LIVE trade
./nbotctl arm live-trade --confirm-real-money
./nbotctl cluster start live-trade
./nbotctl entries enable live-trade
~~~

Only one Execution mode may run at a time. Follow the full doctor/status/safe-stop
sequence in `ALL_MODES_COMMANDS.md`; these short examples do not waive safety
checks or economic limitations.
