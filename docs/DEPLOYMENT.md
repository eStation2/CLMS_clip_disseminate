# Deployment Guide — CLMS Clipping & Dissemination

This runbook documents how to deploy and run the CLMS clipping automation on a
**CDSE VM** (Copernicus Data Space Ecosystem). It reflects an actual deployment
on Ubuntu 24.04 and captures the decisions, commands, and pitfalls encountered.

- **Audience:** operator setting up a new VM or re-deploying.
- **Scope:** `automation_script.py` (clipping orchestrator). Dissemination
  (`dissemination.py`) is noted where relevant but is a separate step.
- **Companion docs:** root `README.md` (cron schedule, output layout, config
  lists), and the per-product `README.md` files.

---

## 0. Target machine assumptions

| Item | Value (observed) |
|---|---|
| OS | Ubuntu 24.04 LTS (KVM VM) |
| CPU / RAM | 2 vCPU / ~1.9 GB |
| Disk | ~15 GB (≈12 GB free) |
| Input archive | `/eodata` mounted **read-only** (CDSE EODATA) |
| GDAL | installed via apt → 3.8.4 |

> ⚠️ **1.9 GB RAM is below what a single clip needs at peak (~1.2 GB) plus OS
> overhead when the input is ~2.84 GB.** Swap is mandatory on this size VM — see
> step 4. For regular production use, prefer an 8 GB+ VM.

---

## 1. Why venv + system GDAL (not Docker, not conda)

We evaluated three deployment styles and chose a **pip venv backed by system
GDAL**:

| Approach | Disk | Notes |
|---|---|---|
| **apt + pip venv** (chosen) | ~178 MB venv + apt libs | lightest; no daemon |
| conda / miniforge | ~2–3 GB | bundles duplicate C libs |
| Docker | ~2 GB image + daemon | **hits the same OOM**; RAM is the limit, not packaging |

The bottleneck on this VM is **memory**, which containerization does not solve.
venv is the smallest footprint and the simplest to run under cron.

---

## 2. System libraries (requires sudo)

```bash
sudo apt-get update && sudo apt-get install -y \
  gdal-bin libgdal-dev libnetcdf-dev libcurl4-openssl-dev \
  python3-venv python3-dev build-essential
```

Confirm GDAL:
```bash
gdalinfo --version      # e.g. GDAL 3.8.4, released 2024/02/08
gdal-config --version   # 3.8.4
```

---

## 3. Python virtual environment

Ubuntu 24.04 marks the system Python as *externally managed*, so install into a
venv (never system-wide).

```bash
cd /path/to/CLMS_clip_disseminate
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools

# GDAL binding MUST equal the system libgdal version:
CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal \
  pip install "GDAL==$(gdal-config --version)"

pip install -r requirements.txt
```

Verify every import resolves:
```bash
python3 -c "from osgeo import gdal; import netCDF4, numpy, lxml, pycurl, dotenv; \
print('GDAL', gdal.__version__, '| numpy', numpy.__version__)"
```
Expected: GDAL 3.8.4, numpy 1.26.x.

### Dependency rules (important)
- **GDAL** (`osgeo`): never pin a fixed version in `requirements.txt`; it must
  match the system libgdal. Install separately as above.
- **numpy** is pinned `<2.0` (1.26.x) for ABI compatibility with the GDAL and
  netCDF4 binaries. Do not bump to 2.x without rebuilding/verifying those.

---

## 4. Swap (mandatory on a ≤2 GB VM, requires sudo)

Without swap, the clip is **OOM-killed** (process "Killed", exit code 137).
Add a 6 GB swap file:

```bash
sudo fallocate -l 6G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist across reboots:
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Confirm:
```bash
swapon --show   # should list /swapfile  6G
free -h         # Swap row shows 6.0Gi
```

---

## 5. Configure paths (`.env`)

Runtime paths are read from `.env` (loaded via `python-dotenv`). A committed
`.env.template` documents every variable with the production CDSE defaults.

```bash
cp .env.template .env
# then edit .env for this machine
```

Variables:

| Variable | Production default |
|---|---|
| `CLMS_HOME` | `/home/eouser/clms` |
| `CLMS_CONFIG_DIR` | `$CLMS_HOME/config` |
| `CLMS_LOG_DIR` | `$CLMS_HOME/logs` |
| `CLMS_PROCESSED_INPUT_FILE` | `$CLMS_CONFIG_DIR/processed_input_files.txt` |
| `CLMS_PROCESSED_OUTPUT_FILE` | `$CLMS_CONFIG_DIR/processed_output_files.txt` |
| `CLMS_LOG_FILE` | `$CLMS_LOG_DIR/clipper_automation.log` |
| `CLMS_OUTPUT_AFR_DIR` | `$CLMS_HOME/outputs/afr` |
| `CLMS_OUTPUT_SOAM_DIR` | `$CLMS_HOME/outputs/sam` |
| `EODATA_ROOT` | `/eodata` |

Notes:
- `.env` is **gitignored**; `.env.template` is committed.
- If `.env` is absent, the script falls back to these same defaults, so the
  original bare-metal CDSE behaviour is unchanged.
- The config/log directories are **auto-created** at startup. If they point
  somewhere unwritable (e.g. `/home/eouser/clms` as a different user), you get
  `PermissionError` at the `os.makedirs` call — fix the paths in `.env`.
- For local testing as a non-`eouser` account, point `CLMS_*` at a writable
  location (e.g. `/home/<user>/clms`) and keep `EODATA_ROOT=/eodata`.

### Design note ("Option A")
The per-product clipper scripts were **not modified**. Their `dir_out=` defaults
remain as harmless fallbacks. `automation_script.py` passes the ROI-specific
output directory explicitly. Only `automation_script.py` is `.env`-driven so far;
`dissemination.py` and `clms_clipper_unified.py` still use hardcoded paths.

---

## 6. Dry-run: verify inputs exist (fast, no clipping)

`automation_script.py` has no `--dry-run` flag. Before a real run, confirm the
current dekad's inputs are present on `/eodata`. The script skips any missing
input (logs `SKIP: Target Input File does NOT exist`), so this preview mirrors
what a run would actually do.

The date each product targets:
- **NDVI** → `get_target_date` (dekads land on the 1st / 11th / 21st, or 21st of
  previous month early in the month).
- **FAPAR / FCOVER / LAI / DMP** → `get_fapar_target_date` (10th / 20th / last of
  previous month).

A check script builds each product's path from `EODATA_ROOT` and
`os.path.exists()`-tests it. Example observed output (all five present):

```
NDVI    target=YYYY-10-01  [FOUND]
DMP     target=YYYY-10-10  [FOUND]
FAPAR   target=YYYY-10-10  [FOUND]
FCOVER  target=YYYY-10-10  [FOUND]
LAI     target=YYYY-10-10  [FOUND]
```

---

## 7. Run

Full run — all 5 products × {AFRI, SOAM} = 10 combinations:
```bash
cd /path/to/CLMS_clip_disseminate
source .venv/bin/activate
python3 automation_script.py
```

Cron-friendly form (no `activate` needed — cron has no shell profile):
```bash
.venv/bin/python3 /path/to/CLMS_clip_disseminate/automation_script.py
```

Single product/ROI (faster sanity check, ~7 min) — call a clipper directly:
```python
from NDVI.clip_clms_NDVI_AFRI_V3 import run_ndvi_afri_clipping
run_ndvi_afri_clipping(
    "/eodata/.../c_gls_NDVI300_YYYYMMDD0000_GLOBE_OLCI_V3.0.1.nc",
    dir_out="/home/<user>/clms/outputs/afr",
)
```

Output zips are written to `CLMS_OUTPUT_AFR_DIR` / `CLMS_OUTPUT_SOAM_DIR`, e.g.
`c_gls_NDVI300_YYYYMMDD0000_AFRI_OLCI_V3.0.1.zip` (~505 MB each).

### Observed performance (with 6 GB swap)
- Single NDVI-AFRI clip: **exit 0, ~436 s (~7 min)**, peak **~1.2 GB RSS +
  ~0.7 GB swap**, output ~505 MB.
- Full 10-combination run: **~1 hour**. Memory is released between products, so
  peaks do not stack; swap absorbs each clip's overflow one at a time.

---

## 7b. Dissemination (FTP upload to EUMETCAST)

After clipping, the output zips are uploaded to the EUMETCAST FTP server by the
dissemination scripts. This step is **separate** from clipping and has its own
cron schedule.

### Script layout
- `dissemination.py` — the template: contains the FTP upload logic and a
  `REGIONS` dict with profiles for **AFR** and **SOAM**.
- `dissemination_afr.py` / `dissemination_soam.py` — **duplicates** of the
  template, scheduled at different cron times so each region uploads
  independently. They inherit the same `.env` configuration (they must live in
  the repo root next to `.env`).

> If `dissemination_afr.py` / `dissemination_soam.py` do not exist yet on a new
> deployment, create them by copying `dissemination.py` (that is the intended
> model — the differences are only in schedule and the per-region `.env` values).

### Configuration (`.env`)
Credentials and FTP settings are read from `.env` (see also the root README):

| Variable | Purpose |
|---|---|
| `CLMS_FTP_SERVER` | FTP host (`ofids.eumetsat.int`) |
| `CLMS_FTP_LOCAL_IP` | **This machine's** externally reachable IP (active mode) |
| `CLMS_FTP_PORT_RANGE_START` / `_END` | Active-mode data port range |
| `CLMS_AFR_REMOTE_DIR` / `CLMS_SOAM_REMOTE_DIR` | Remote upload directories |
| `CLMS_AFR_USER_PWD` / `CLMS_SOAM_USER_PWD` | Credentials `user:password` (**secret**) |

Log/config/output directories reuse the shared `CLMS_LOG_DIR`,
`CLMS_CONFIG_DIR`, `CLMS_OUTPUT_AFR_DIR`, `CLMS_OUTPUT_SOAM_DIR`.

### Critical networking requirement (FTP active mode)
The upload uses FTP **active mode** with `pycurl.FTPPORT`. This means:
- `CLMS_FTP_LOCAL_IP` **must** be the IP the FTP server can connect back to
  (this VM's reachable address) — not `127.0.0.1`.
- The port range (default `50000–50100`) **must be open inbound** in the VM's
  firewall / security group.

If either is wrong, uploads hang or fail with a pycurl error and nothing is
transferred. This is the most common dissemination failure on a fresh VM.

### Credentials handling (security)
- Set real `CLMS_*_USER_PWD` values **only in `.env`** (gitignored). Never put
  them in `.env.template` or commit them.
- Any `.netrc` files placed in the config dir are also gitignored (`*.netrc`).
  Note the current code uses `USERPWD`, not the netrc file.

### How upload tracking works
- A zip is uploaded only if it is in `processed_output_files.txt` and not already
  in `ftp_uploaded_<afr|soam>.list`.
- On success the zip is moved to `<output_dir>/uploaded/`, added to
  `ftp_uploaded_<region>.list`, and removed from `processed_output_files.txt`.
- Per-run upload logs: `$CLMS_LOG_DIR/ftp_upload_<REGION>_<TIMESTAMP>.log`.

### Run manually
```bash
source .venv/bin/activate
python3 dissemination_afr.py      # or dissemination_soam.py
```

---

## 8. Scheduling (cron)

The production schedule runs on dekad boundaries. See the root `README.md` for
the exact crontab. Use the venv interpreter directly in cron entries:

```cron
# Clipper — 1st/11th/21st at 19:00
0 19 1,11,21 * * /path/to/CLMS_clip_disseminate/.venv/bin/python3 \
  /path/to/CLMS_clip_disseminate/automation_script.py

# Dissemination — AFR and SOAM on separate days/times (duplicated scripts)
0 2,4 2,3,12,13,22,23 * * /path/to/CLMS_clip_disseminate/.venv/bin/python3 \
  /path/to/CLMS_clip_disseminate/dissemination_afr.py
0 2,5 4,14,24 * * /path/to/CLMS_clip_disseminate/.venv/bin/python3 \
  /path/to/CLMS_clip_disseminate/dissemination_soam.py
```

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'osgeo'` | venv not active | `source .venv/bin/activate` or use `.venv/bin/python3` |
| Process "Killed", exit code **137** | OOM killer (RAM exhausted) | add swap (step 4); longer term resize VM |
| `PermissionError` at `os.makedirs` on startup | `.env` paths not writable by current user | point `CLMS_*` at a writable dir |
| `ModuleNotFoundError: No module named 'DMP'` (or NDVI, …) | not run from repo root | `cd` to the repository root first |
| `SKIP: Target Input File does NOT exist` | input not yet published for this dekad | expected; re-run later (cron retries) |
| GDAL `FutureWarning`, `LENGTH_BEFORE not found ... Skipping` | harmless deprecation / optional var | ignore |
| Dissemination upload hangs or pycurl error, nothing transferred | wrong `CLMS_FTP_LOCAL_IP` or firewall blocks the active-mode port range | set the IP to this VM's reachable address; open ports `50000–50100` |
| Dissemination skips files: "NOT in the Processed output list" | zip not recorded in `processed_output_files.txt` (clip didn't complete, or already uploaded) | confirm clipping succeeded; check `ftp_uploaded_<region>.list` |

### Confirming an OOM kill
```bash
dmesg | grep -i "killed process"     # needs sudo
# or watch MemAvailable in /proc/meminfo collapse right before the kill
```

### Monitoring a live run
Sample `/proc/<pid>/status` (`VmRSS`, `State`) and `/proc/meminfo`
(`MemAvailable`, `SwapFree`) on an interval. `State: D` = uninterruptible sleep
= disk I/O wait, expected while paging to swap.

---

## 10. Production recommendation

Swap makes the job complete on a 1.9 GB VM, but swap-thrashing a ~2.84 GB read is
slow and hard on the disk. For regular dekadal operation, **resize the VM to
8 GB+ RAM** so clips run in-memory without swap and finish several times faster.
(VM resize is a cloud-console action.)
