# CLMS Clipping & Dissemination — Project Overview

This repository processes Copernicus Land Monitoring Service (CLMS) products
(NDVI, FAPAR, FCOVER, LAI, DMP), clips them to two regions of interest (ROIs)
— AFRI (Africa) and SOAM (South America) — generates quicklooks and product XML,
zips the result, and disseminates the zips to EUMETCAST via FTP.

## Deployment target
- Runs on a **CDSE VM** (Copernicus Data Space Ecosystem), Ubuntu 24.04, where the
  `/eodata` archive is mounted read-only as the input source.
- Driven by **cron** on "dekad" (10-day period) boundaries. See root `README.md`
  for the exact crontab.
- The production layout lives under `/home/eouser/clms` (config, logs, outputs).

## Key scripts
- `automation_script.py` — primary orchestrator. Iterates all product/ROI
  combinations, resolves the target dekad date, checks the input exists on
  `/eodata`, skips already-processed items, and calls the per-product clipper.
- `clms_clipper_unified.py` — a newer config-driven alternative entrypoint
  (CLI args for products/rois/dates). NOT yet migrated to `.env`.
- `dissemination.py` — FTP upload of output zips to EUMETCAST (pycurl, FTP
  active mode with a hardcoded LOCAL_IP). NOT yet migrated to `.env`.
- `<PRODUCT>/clip_clms_<PRODUCT>_<ROI>_V*.py` — per-product clippers. Each exports
  a `run_<product>_<roi>_clipping(filepathname, dir_out=...)` function.
- `clms_clipper_common.py` — shared `clip_and_package()` pipeline:
  clip NetCDF → quicklook TIFF → patch product XML → zip → cleanup.

## Idempotency
Processing is idempotent. Two tracking files under the config dir record state:
- `processed_input_files.txt` — global source files already processed (append-only).
- `processed_output_files.txt` — output zips produced; entries are removed once
  successfully uploaded (moved into `ftp_uploaded_<roi>.list`).

## Hard constraints learned on this machine
- The VM has only **~1.9 GB RAM, no swap by default, 2 CPU**. Input NetCDFs are
  large (a global 300m NDVI file is ~2.84 GB). A single clip peaks ~1.2 GB RSS.
- Without swap the process is **OOM-killed (exit 137)**. A **6 GB swap file**
  makes it complete (~7 min per product/ROI; ~1 hr for a full 10-combo run).
- GDAL is the hard dependency; see the environment steering file.
