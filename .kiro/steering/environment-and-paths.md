# Environment, Dependencies & Configurable Paths

## Python environment (venv, not conda, not Docker)
This project is deployed with a **pip venv backed by system GDAL** — chosen over
conda and Docker because the VM is RAM/disk constrained (venv is ~178 MB vs
conda ~2-3 GB or a ~2 GB Docker image, and Docker would hit the same OOM anyway;
the bottleneck is RAM, not packaging).

### System libraries (apt, require sudo)
```
gdal-bin libgdal-dev libnetcdf-dev libcurl4-openssl-dev
python3-venv python3-dev build-essential
```
Installed GDAL version on the VM: **3.8.4** (`gdal-config --version`).

### venv setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools
# GDAL binding MUST match the system libgdal version:
CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal \
  pip install "GDAL==$(gdal-config --version)"
pip install -r requirements.txt
```

### Dependency rules
- **GDAL** (`osgeo`): never pin a fixed version in `requirements.txt`; it must
  equal the system libgdal version. Install it separately as shown above.
- **numpy** is pinned `<2.0` (1.26.x) for ABI compatibility with GDAL/netCDF4
  binaries. Do not bump to numpy 2.x without rebuilding/verifying those.
- Other deps: netCDF4, lxml, python-dateutil, pycurl, python-dotenv.

## Path configuration via .env (only automation_script.py so far)
All runtime paths moved out of hardcoded constants into `.env`:
- `.env.template` — committed, documents all vars with production CDSE defaults.
- `.env` — gitignored, machine-specific. Loaded via `python-dotenv` at startup
  with a graceful `try/except ImportError` fallback.

Variables:
`CLMS_HOME`, `CLMS_CONFIG_DIR`, `CLMS_LOG_DIR`, `CLMS_PROCESSED_INPUT_FILE`,
`CLMS_PROCESSED_OUTPUT_FILE`, `CLMS_LOG_FILE`, `CLMS_OUTPUT_AFR_DIR`,
`CLMS_OUTPUT_SOAM_DIR`, `EODATA_ROOT`.

### Design decision ("Option A")
The per-product clipper files were **left untouched**. Their `dir_out=` defaults
remain as harmless fallbacks. `automation_script.py` passes the ROI-specific
output dir explicitly via `OUTPUT_DIRS_BY_ROI[roi]`. When adding env-config to
other entrypoints, prefer the same minimal, non-invasive approach: thread paths
from the orchestrator rather than editing every clipper.

### Defaults preserve bare-metal behaviour
Every env var falls back to the original `/home/eouser/clms` / `/eodata` value,
so if `.env` is absent the production CDSE behaviour is unchanged.

## Partially migrated to .env
`dissemination.py` reads its FTP settings and credentials from `.env`
(`CLMS_FTP_SERVER`, `CLMS_FTP_LOCAL_IP`, `CLMS_FTP_PORT_RANGE_START/END`,
`CLMS_AFR_REMOTE_DIR`, `CLMS_AFR_USER_PWD`, `CLMS_SOAM_REMOTE_DIR`,
`CLMS_SOAM_USER_PWD`), and reuses the shared path vars for log/config/output
dirs. Its per-region duplicates (`dissemination_afr.py` / `dissemination_soam.py`,
scheduled at different cron times) are copies and inherit the same `.env`.
The `netrc_file` entries are left in code (unused — upload uses USERPWD).

## NOT yet migrated to .env
`clms_clipper_unified.py` still has hardcoded paths. If asked to relocate it,
migrate it to the same `.env` vars.
