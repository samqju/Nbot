# Observation VPS deployment

These files are the reproducible Phase 6A.0 Observation-role deployment.
They intentionally contain no provider username, home directory, or repository
path. Render them for the current machine with explicit values.

Example for the current Observer:

```bash
sudo /opt/nbot/.venv/bin/python deploy/observation/install_services.py \
  --repo /root/Nbot \
  --python /opt/nbot/.venv/bin/python \
  --user root \
  --enable
```

Use `--start` only after manually started Observation/learning processes have
been stopped. A replacement VPS can use a different repo path or service user
by changing only these arguments. The renderer preserves the supplied virtualenv
Python launcher path instead of resolving it to the underlying system interpreter.
Runtime `.env`, Observation-owned data, and models must be restored separately
from backup.
