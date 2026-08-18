# NBOT V3 Operations

V3.0 supports foundation-only commands:

```bash
./nbotctl bootstrap
./nbotctl doctor <profile>
./nbotctl status
./nbotctl arm testnet-trade
./nbotctl disarm testnet-trade
./nbotctl arm live-trade
./nbotctl disarm live-trade
```

`bootstrap` creates only ignored role-owned runtime directories and enforces their foundation permissions. It does not create credentials, databases, state, arm files, orders, or worker authority.

`doctor` verifies the V3 foundation that can already be proven: role/profile validity, local virtualenv, runtime layout, secret-directory permissions, absence of legacy root `.env`, Observation order-secret separation, disk headroom, clock synchronization, Git cleanliness, and the profile arm gate. Exchange/state/database/protocol checks remain explicitly reported as deferred until the phase that implements them.

Worker start/restart/cluster commands intentionally fail closed until their roadmap phases are implemented.
