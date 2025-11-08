# Config validator (Ubuntu / Linux usage)

This folder contains `validate_configs.py`, a small helper that scans the repository
for common configuration files (.json, .yml/.yaml, .hcl, .conf/.ini, Dockerfile, .ctx)
and performs basic syntactic checks.

This README provides Linux/Ubuntu-specific instructions (no Windows/PowerShell commands).

Quick start (recommended):

```bash
# ensure you have Python 3.8+ installed; use python3 on Ubuntu
python3 --version

# optional: create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# optional: install dependencies manually (or let the script install them)
python3 -m pip install --upgrade pip
python3 -m pip install pyyaml python-hcl2

# run the validator
python3 scripts/validate_configs.py

# if you prefer the script to attempt installing missing deps itself:
python3 scripts/validate_configs.py --install-deps
```

Notes:
- The script uses `pyyaml` to validate YAML and `python-hcl2` to validate HCL files. If
  these packages are missing the script will skip those checks and report skipped files.
- `sealed.ctx` files and other non-text/binary artifacts are skipped by the validator.
- The healthcheck commands in `keylime-server.yml` use `curl` (a standard Linux tool).
  Ensure `curl` is available in your container images or host environment if you run
  docker-compose healthchecks.

If you'd like, I can:
- Add a minimal GitHub Actions workflow to run this validator on every PR (Linux runners).
- Add stricter checks (hadolint for Dockerfiles) and wire them into the script.
