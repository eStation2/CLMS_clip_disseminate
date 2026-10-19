---
name: clms-setup-and-run
description: >-
  Set up, configure, and run the CLMS clipping automation on a CDSE VM:
  installing system GDAL + a pip venv, configuring paths via .env, adding swap
  to avoid OOM, doing a safe dry-run input check, and running automation_script.py
  (full or a single product/ROI). Use when setting up a new machine, deploying,
  running the clipper, or diagnosing a killed/slow run.
---

# CLMS Setup & Run

End-to-end playbook for standing up and running the CLMS clippers. Repo root is
the workspace folder (e.g. `/home/venkavi/CLMS_clip_disseminate`).

## 1. System libraries (one-time, needs sudo)
The agent cannot enter a sudo password — give these to the user to run:
```bash
sudo apt-get update && sudo apt-get install -y \
  gdal-bin libgdal-dev libnetcdf-dev libcurl4-openssl-dev \
  python3-venv python3-dev build-essential
```
Then confirm: `gdal-config --version` (expected 3.8.4 on this VM).

## 2. Python venv (no sudo)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools
CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal \
  pip install "GDAL==$(gdal-config --version)"   # MUST match system libgdal
pip install -r requirements.txt
```
Verify imports: `python3 -c "from osgeo import gdal; import netCDF4, numpy, lxml, pycurl, dotenv; print(gdal.__version__)"`

## 3. Configure paths (.env)
```bash
cp .env.template .env   # then edit for this machine
```
- Production CDSE: keep the `/home/eouser/clms` defaults.
- Local testing as a non-eouser user: point `CLMS_*` at a writable dir (e.g.
  `/home/<user>/clms`); leave `EODATA_ROOT=/eodata`.
Config/log dirs are auto-created on startup. If paths point somewhere
unwritable you'll get `PermissionError` at the `os.makedirs` line — fix `.env`.

## 4. Swap (critical on the 1.9 GB VM, needs sudo)
Without swap the clip is OOM-killed (exit 137). Have the user run:
```bash
sudo fallocate -l 6G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab   # persist
```
Confirm with `swapon --show`.

## 5. Dry-run input check (fast, no clipping)
Before a real run, confirm the current dekad's inputs exist on `/eodata` by
replicating the date logic and `os.path.exists()`-checking each product's path
(NDVI uses `get_target_date`; FAPAR/FCOVER/LAI/DMP use `get_fapar_target_date`).
Build paths from `EODATA_ROOT`. This validates `.env` and wiring without cost.

## 6. Run
Full run (all 5 products × AFRI/SOAM, ~1 hr with swap):
```bash
source .venv/bin/activate
python3 automation_script.py
# or, cron-friendly (no activate needed):
.venv/bin/python3 automation_script.py
```
Single product/ROI (faster, ~7 min) — call the clipper directly, passing the
ROI output dir from `.env`:
```python
from NDVI.clip_clms_NDVI_AFRI_V3 import run_ndvi_afri_clipping
run_ndvi_afri_clipping("/eodata/.../c_gls_NDVI300_...GLOBE...nc",
                       dir_out="/home/.../clms/outputs/afr")
```
Output zips land in `CLMS_OUTPUT_AFR_DIR` / `CLMS_OUTPUT_SOAM_DIR`.

## Gotchas
- Always activate the venv (or use `.venv/bin/python3`), else
  `ModuleNotFoundError: No module named 'osgeo'`.
- Run from the repo root so the `NDVI/`, `DMP/`, … packages import.
- Harmless log noise: GDAL `FutureWarning`, `LENGTH_BEFORE not found ... Skipping`.
- `dissemination.py` and `clms_clipper_unified.py` are NOT yet `.env`-driven.
- Processing is idempotent — already-processed inputs are skipped via the
  tracking files in the config dir.
