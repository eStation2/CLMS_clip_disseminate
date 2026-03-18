# NDVI Clipping Scripts

This directory contains CLMS NDVI clipping scripts that generate clipped products for AFRI and SOAM regions.

## What’s here
- `clip_clms_NDVI_AFRI.py` / `clip_clms_NDVI_AFRI_V3.py` – clip and package NDVI for **Africa (AFRI)**
- `clip_clms_NDVI_SOAM.py` / `clip_clms_NDVI_SOAM_V3.py` – clip and package NDVI for **South America (SOAM)**

> The `*_V3.py` variants implement the latest naming/version conventions and are the ones currently used by the main automation workflow.

---

## Running a clipper script directly

Each script can be executed on its own to process a single NetCDF input file and produce a ZIP + metadata package.

### Example (AFRI):
```bash
python3 NDVI/clip_clms_NDVI_AFRI_V3.py \
  /path/to/c_gls_NDVI300_<YYYY><MM><DD>0000_GLOBE_OLCI_V3.0.1.nc
```

### Example (SOAM):
```bash
python3 NDVI/clip_clms_NDVI_SOAM_V3.py \
  /path/to/c_gls_NDVI300_<YYYY><MM><DD>0000_GLOBE_OLCI_V3.0.1.nc
```

Each script prints the output ZIP path on success and exits with `0`.

---

## Programmatic usage (used by `automation_script.py`)

Each script exposes a function that returns the generated ZIP file path (so the caller can track success and avoid re-processing):
- `run_ndvi_afri_clipping(filepathname, dir_out="/home/eouser/clms/outputs/afr/")`
- `run_ndvi_soam_clipping(filepathname, dir_out="/home/eouser/clms/outputs/sam/")`

The top-level automation script (`automation_script.py`) calls these functions to perform automated dekad-based processing and record successful outputs.

---

## Logs / Outputs

Output files are written into the global output directory (by default):
- `/home/eouser/clms/outputs/afr/` (AFRI)
- `/home/eouser/clms/outputs/sam/` (SOAM)

The clipping script itself will print diagnostic messages to STDOUT and will also return a non-zero exit code on failure.
