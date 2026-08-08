# NBOT Execution VPS deployment

Phase 6A.0.9 runs only the capital-owning Execution Worker on the Execution VPS.
Observation remains reachable to Execution only through a loopback SSH tunnel:

    Execution 127.0.0.1:8765
        -> SSH local forward
        -> Observer 127.0.0.1:8765

The Observation HTTP server and `ObservationClient` therefore remain
loopback-only. The SSH connection supplies transport encryption and machine
authentication; the existing Observation bearer token remains the application
authentication layer.

The deployment intentionally uses `Wants=` rather than `Requires=`/`BindsTo=`
between Execution and the tunnel. If Observation or the tunnel disappears while
a position is open, systemd must not stop Execution. Flat-mode trade requests
will fail closed until the tunnel returns.

Render the units without starting them:

    python deploy/execution/install_services.py \
      --repo /path/to/Nbot \
      --python /path/to/venv/bin/python \
      --user ubuntu \
      --ssh-bin /usr/bin/ssh \
      --identity-file /home/ubuntu/.ssh/nbot_observer_tunnel \
      --known-hosts-file /home/ubuntu/.ssh/nbot_observer_known_hosts \
      --observer-host 203.0.113.10 \
      --observer-ssh-user nbot-tunnel \
      --destination /tmp/nbot-execution-units

Install to systemd by changing only `--destination`:

    sudo python deploy/execution/install_services.py \
      ...same arguments... \
      --destination /etc/systemd/system

Do not use `--start` until:

1. the repository and virtualenv have been validated;
2. the pinned Observer host key and restricted tunnel private key are present;
3. the project-local `.env` has been restored securely;
4. Execution-owned state has been restored;
5. any manually-created test tunnel on local port 8765 has been stopped.

Runtime secrets are never stored in this deployment package. In particular:

- the tunnel private key is machine-local;
- the pinned known-hosts file is machine-local;
- `OBSERVATION_CONTROL_TOKEN` remains in the project-local `.env`;
- exchange credentials, when future TRADE mode requires them, remain
  Execution-VPS-only.

Execution-owned recovery data is restored separately from Git. This includes
bot/open-position state, paper account/trade history in SHADOW mode, processed
proposal IDs, and the durable pending execution-outcome outbox.

A replacement VPS may use different repository, virtualenv, user, SSH-key, and
Observer host paths by changing installer arguments only.
