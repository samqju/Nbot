# Observation VPS services

The V3.8 Observation base role has only two boot-managed responsibilities:

1. `nbot-observation-live.service` — continuous LIVE raw-evidence collector.
2. `nbot-research-epoch.timer` — low-priority scheduler. It starts the
   `nbot-research-epoch.service` oneshot only when systemd checks the schedule;
   the command itself exits cheaply with `WAIT_FOR_MATURE_EPOCH` until 96 mature
   targets exist.

There is no SQLite/"atomic split" daemon. The bounded epoch command copies the
required raw window into a disposable SQLite workspace, builds derived research,
commits compact permanent memory, removes the scratch database after success,
and prunes raw evidence only behind the qualified dependency watermark.

The optional `nbot-observation-live-paper-control.service` is continuous only
when LIVE_PAPER Execution integration is deliberately active. Testnet control is
a regression-only service and is not part of the base boot target.

Render without starting:

```bash
sudo /root/Nbot/.venv/bin/python deploy/observation/install_services.py \
  --repo /root/Nbot \
  --python /root/Nbot/.venv/bin/python \
  --user root
```

Enable the base role for reboot persistence:

```bash
sudo /root/Nbot/.venv/bin/python deploy/observation/install_services.py \
  --repo /root/Nbot \
  --python /root/Nbot/.venv/bin/python \
  --user root \
  --enable
```

Use `--start` only after any manually launched LIVE collector has been stopped,
otherwise the Observation runtime lock will correctly reject a duplicate writer.

When LIVE_PAPER control is intentionally enabled later, add
`--enable-live-paper-control`; add `--start-live-paper-control` only after the
control-link secret exists and the control path is ready.
