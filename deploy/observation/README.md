# Observation VPS deployment

These files are the reproducible Phase 6A.0 Observation-role deployment.
They intentionally contain no provider username, home directory, or repository
path. Render them for the current machine with explicit values.

Example (substitute paths appropriate for the current VPS):

```bash
sudo /path/to/venv/bin/python deploy/observation/install_services.py \
  --repo /path/to/Nbot \
  --python /path/to/venv/bin/python \
  --user "$(id -un)" \
  --enable
```

Use `--start` only after manually started Observation/learning processes have
been stopped. A replacement VPS can use a different repo path or service user
by changing only these arguments. The renderer preserves the supplied virtualenv
Python launcher path instead of resolving it to the underlying system interpreter.
Runtime `.env`, Observation-owned data, and models must be restored separately
from backup.

The installer also writes `nbot-observer.target`, which groups all four
Observation-role services. On a completed installation the role can be started
with one command:

```bash
sudo systemctl start nbot-observer.target
```

For a fresh install, `--enable --start` enables/starts the role target rather
than four independent boot entries. See `deploy/README.md` for the complete
two-VPS build procedure and `deploy/recovery/` for backup/disaster recovery.
