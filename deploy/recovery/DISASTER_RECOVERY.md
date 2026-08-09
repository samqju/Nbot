# NBOT disaster recovery runbook

This runbook assumes the two-worker architecture is already deployed and a VPS
is lost or must be replaced.

The governing rule is simple: **recover code from Git; recover only role-owned
mutable state from backup; reconcile before resuming capital-bearing work.**

## 1. Observation VPS is lost

Expected behavior while it is unavailable:

- an already-open Execution position continues to use Execution's own Binance
  stream and position-management logic;
- after close, Execution persists the completed outcome locally;
- Execution remains flat for new entries while Observation is unavailable;
- the pending outcome remains in the durable outbox until a valid ACK arrives.

Recovery:

1. create a replacement Observation VPS with reliable Binance connectivity;
2. install OS prerequisites;
3. clone the exact deployed NBOT tag/SHA;
4. restore the virtualenv from `requirements.lock.txt`;
5. restore Observation `.env` and Observation-owned data/models;
6. recreate the restricted `nbot-tunnel` SSH account;
7. install/start `nbot-observer.target`;
8. verify local `/health` and `order_authority=NONE`;
9. obtain and independently verify the new Observer SSH host key;
10. on Execution, replace the pinned Observer host-key entry and update the
    configured Observer host/IP if it changed;
11. restart **only the tunnel service** if Execution has an open position;
12. verify Execution reconnects;
13. verify any pending execution outcome is delivered once and ACKed;
14. only then allow the normal flat-mode request cycle to continue.

Do not restart the Execution worker merely because the Observer address changed
if Execution is actively managing a position.

## 2. Execution VPS is lost

Observation is expected to continue:

- watching Binance directly;
- maintaining candidates/virtual trades;
- recording virtual outcomes;
- learning/training/evaluating models.

Recovery:

1. create replacement Execution VPS;
2. install OS prerequisites;
3. clone the exact same NBOT tag/SHA as Observation;
4. restore the virtualenv;
5. restore Execution `.env`;
6. restore the latest Execution-owned bot/paper/trade/outbox state;
7. restore or rotate the Execution-to-Observer tunnel key;
8. if the source IP changed, update the restricted `from=` rule on Observer;
9. independently verify/pin the Observer SSH host key;
10. install `nbot-execution.target` and services;
11. start Execution and let startup reconciliation run first;
12. verify exchange/paper truth and recovered position state;
13. verify protection and no duplicate exposure;
14. verify pending outcomes retry normally;
15. keep new entries disabled until operator acceptance succeeds.

If real exchange execution is ever enabled, exchange truth outranks a stale
backup. Never blindly open a replacement position merely because a backup says
one existed.

## 3. Both VPSs are lost

Recover **Observation first**, then Execution.

Reason:

- Observation can safely resume research without Execution;
- Execution needs a secured Observer endpoint before normal flat-mode proposal
  requests can work;
- starting Execution second simplifies token/tunnel verification.

Sequence:

1. recover Observation code, secrets, data/models and target;
2. verify Observation health and no order authority;
3. recover Execution code, secrets and state;
4. build the restricted tunnel;
5. verify both machines use the same Git SHA;
6. start Execution and reconcile;
7. verify pending outcomes;
8. only after acceptance allow new entries.

## 4. GitHub/repository unavailable

Do not substitute an unknown local code copy if the release version cannot be
verified. Preserve the surviving machine and runtime state, then restore the
exact approved Git object from a trusted repository mirror/backup.

Every operational backup should record the release SHA so the deployed version
is unambiguous.

## 5. Observer IP changes

Execution's systemd tunnel contains the Observer host passed to the installer.
Re-render/install Execution units with the new host value:

```bash
sudo /path/to/venv/bin/python deploy/execution/install_services.py \
  --repo /path/to/Nbot \
  --python /path/to/venv/bin/python \
  --user EXECUTION_USER \
  --identity-file /path/to/nbot_observer_tunnel \
  --known-hosts-file /path/to/nbot_observer_known_hosts \
  --observer-host NEW_OBSERVER_HOST \
  --observer-ssh-user nbot-tunnel \
  --enable
```

Then `systemctl daemon-reload` is performed by the installer. If a position is
open, restart only `nbot-observation-tunnel.service`; do not restart Execution.

## 6. Tunnel key is lost/compromised

1. generate a new key on Execution;
2. replace the old public key in Observer's restricted `authorized_keys`;
3. preserve `from=`, `permitopen=`, and no-pty/no-forwarding restrictions;
4. update the Execution installer argument if the private-key path changed;
5. restart only the tunnel service;
6. revoke/delete the old key material.

The application bearer token remains an independent authentication layer and
should also be rotated if compromise is suspected.

## 7. Control token is lost/rotated

Both workers must use the same new token. Update `.env` securely on both VPSs
without displaying the value. Compare SHA-256 fingerprints to prove equality.

Perform token rotation in a planned flat/disabled maintenance window whenever
possible.

## 8. Recovery acceptance checklist

Do not consider recovery complete until:

- both VPSs use the same exact approved Git SHA;
- role services/targets are enabled and active as intended;
- Observer has no Execution process/order authority;
- Execution has no Observation/learning processes;
- each worker has its own direct Binance connectivity;
- tunnel/API authentication succeeds;
- Execution reconciliation passes;
- position state is known and protected;
- pending outbox behavior is known;
- duplicate proposal/outcome protections remain intact;
- Observer learning state is writable/healthy;
- operator explicitly allows new entries only when safe.

## 9. Never do these during recovery

- never run legacy `run.py` alongside the split workers;
- never start a second Execution worker;
- never copy mutable Execution state onto Observation;
- never copy mutable Observation learning state onto Execution;
- never expose the Observation API publicly on port 8765;
- never weaken the tunnel to `StrictHostKeyChecking=no`;
- never delete a pending execution outcome merely to make the outbox empty;
- never execute a proposal just because Observation recommends it;
- never restart/stop Execution during an open position unless recovery from
  Execution failure itself makes that unavoidable;
- never change strategy/risk/trailing rules as part of infrastructure recovery.
