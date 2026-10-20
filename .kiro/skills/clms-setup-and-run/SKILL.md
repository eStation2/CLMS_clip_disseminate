---
name: clms-setup-and-run
description: >-
  Deploy, configure, run, and schedule the full CLMS clipping AND dissemination
  stack on a CDSE VM: system GDAL + pip venv, mounting the large data volume for
  outputs, swap to avoid OOM, path/credential config via .env, dry-run input
  check, running automation_script.py, dissemination (FTP) setup, and cron.
  Use when setting up a new machine, deploying, running the clipper/dissemination,
  or diagnosing a killed/slow/HDF-error/disk-full run.
---

# CLMS Deploy, Run & Schedule

End-to-end playbook for the full clipping + dissemination stack. Repo root is the
workspace folder (e.g. `/home/venkavi/CLMS_clip_disseminate`). The authoritative,
detailed runbook is **`docs/DEPLOYMENT.md`** — this skill is the condensed agent
checklist; defer to that doc for specifics.

IMPORTANT: this skill guides the agent; it is not autonomous. Steps needing
**sudo** (apt, swap, mount, fstab) or **network/NAT** or **crontab** must be run
by the user — the agent cannot enter a sudo password.

## 1. System libraries (one-time, sudo)
```bash
sudo apt-get update && sudo apt-get install -y \
  gdal-bin libgdal-dev libnetcdf-dev libcurl4-openssl-dev \
  python3-venv python3-dev build-essential
```
Confirm: `gdal-config --version` (3.8.4 on this VM).

## 2. Python venv (no sudo)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip wheel setuptools
CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal \
  pip install "GDAL==$(gdal-config --version)"   # MUST match system libgdal
pip install -r requirements.txt                   # numpy stays <2.0
```
Verify: `python3 -c "from osgeo import gdal; import netCDF4,numpy,lxml,pycurl,dotenv; print(gdal.__version__)"`

## 3. Mount the data volume for outputs (sudo) — DEPLOYMENT.md §4b
The ~15 GB root disk CANNOT hold outputs; a full disk causes a misleading
`NetCDF: HDF error` on write. A separate large volume must be mounted.
```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT   # find the unmounted volume
# e.g. /dev/sdb1, 100G, ext4, label "localdata"
sudo mount /dev/sdb1 /localdata
df -h /localdata                                   # confirm ~98G free
```
Persist in `/etc/fstab` (NO space in options — `defaults,nofail`):
```
LABEL=localdata  /localdata  ext4  defaults,nofail  0  2
```
Validate without reboot: `sudo mount -a` (silent = OK; `parse error at line N`
= fix the line, usually a space in the options field).

## 4. Swap (critical on ~1.9 GB VM, sudo)
Without swap the clip is OOM-killed (exit 137).
```bash
sudo fallocate -l 6G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
Confirm: `swapon --show`. NOTE: on a small root disk, swap + outputs compete —
keep outputs on `/localdata`, not root. Never `swapoff` while a clip is running.

## 5. Configure .env (paths + dissemination creds)
```bash
cp .env.template .env   # edit for this machine
```
- Point outputs at the data volume: `CLMS_OUTPUT_AFR_DIR=/localdata/outputs/afr`,
  `CLMS_OUTPUT_SOAM_DIR=/localdata/outputs/sam`.
- `CLMS_CONFIG_DIR` / `CLMS_LOG_DIR` at a writable path (e.g. `/home/<user>/clms/...`).
- `EODATA_ROOT=/eodata`.
- Dissemination (read by `dissemination.py` and its duplicates): `CLMS_FTP_SERVER`,
  `CLMS_FTP_LOCAL_IP`, `CLMS_FTP_PORT_RANGE_START/END`, `CLMS_AFR_REMOTE_DIR`,
  `CLMS_AFR_USER_PWD`, `CLMS_SOAM_REMOTE_DIR`, `CLMS_SOAM_USER_PWD`.
- `.env` is gitignored; `.env.template` is committed (placeholders only, no secrets).
Config/log dirs auto-create on startup; unwritable paths → `PermissionError`.

## 6. Dry-run input check (fast, no clipping)
Confirm the current dekad's inputs exist on `/eodata`: replicate the date logic
(`get_target_date` for NDVI; `get_fapar_target_date` for FAPAR/FCOVER/LAI/DMP),
build paths from `EODATA_ROOT`, `os.path.exists()` each. Validates `.env`/wiring.

## 7. Run clipping
```bash
cd <repo> && source .venv/bin/activate
python3 automation_script.py                 # full: 5 products × AFRI/SOAM, ~1 hr
# cron-friendly: .venv/bin/python3 automation_script.py
```
Single product/ROI (~7 min): import the clipper and call
`run_<prod>_<roi>_clipping(input_nc, dir_out=<CLMS_OUTPUT_*_DIR>)`.
Idempotent — processed inputs are skipped via the tracking lists.

## 8. Dissemination (FTP → EUMETCAST) — DEPLOYMENT.md §7b
`dissemination.py` is the template; `dissemination_afr.py` / `dissemination_soam.py`
are duplicates scheduled separately (each may comment out the other region in
`__main__`). Run: `cd <repo> && .venv/bin/python3 dissemination_afr.py`.
- Active FTP mode (`pycurl.FTPPORT`), data ports `50000–50100`.
- **NAT caveat:** the VM is behind NAT and owns no public IP. Active-mode data
  callbacks require FTP ALG / port-forwarding on the CDSE-managed NAT gateway,
  or they time out (`PycURL Error 12`). This is a CDSE request, not a code fix.
  `CLMS_FTP_LOCAL_IP` must be the address the server can reach.
- Upload tracking: zip uploaded only if in `processed_output_files.txt` and not
  in `ftp_uploaded_<region>.list`; on success moved to `<out>/uploaded/`.

## 9. Schedule (cron)
Each entry MUST `cd` to the repo (for `DMP`/`NDVI`/… imports) and use the venv
python. Logging is internal (no stdout redirect needed). See DEPLOYMENT.md §8 and
the example `~/clms_crontab.txt`:
```cron
REPO=<repo>; PY=<repo>/.venv/bin/python3
0 19 1,11,21 * *          cd $REPO && $PY automation_script.py
0 */6 2,12,22 * *         cd $REPO && $PY automation_script.py
0 1,3 3,13,23 * *         cd $REPO && $PY automation_script.py
0 2,4 2,3,12,13,22,23 * * cd $REPO && $PY dissemination_afr.py
0 2,5 4,14,24 * *         cd $REPO && $PY dissemination_soam.py
30 2 1 * * find /localdata/outputs/afr/uploaded/ -type f -mtime +30 -delete
30 2 1 * * find /localdata/outputs/sam/uploaded/ -type f -mtime +30 -delete
```
Install: `crontab ~/clms_crontab.txt`; verify: `crontab -l`; check daemon:
`systemctl status cron`.

## Gotchas / troubleshooting
- `ModuleNotFoundError: osgeo` → venv not active; use `.venv/bin/python3`.
- `ModuleNotFoundError: DMP` (or NDVI…) → not run from repo root; `cd` first.
- Process "Killed" / exit 137 → OOM; ensure swap; never swapoff during a run.
- `NetCDF: HDF error` on write, then `ERROR 4: ... No such file or directory` →
  disk full / `/localdata` not mounted; mount the volume, free root disk.
- Dissemination `PycURL Error 12` (accept timeout) → NAT not delivering the
  active-mode callback; CDSE NAT/ALG reconfig needed (see `docs/tickets/`).
- Harmless noise: GDAL `FutureWarning`, `LENGTH_BEFORE not found ... Skipping`.
- `clms_clipper_unified.py` still has hardcoded paths (not `.env`-driven).
