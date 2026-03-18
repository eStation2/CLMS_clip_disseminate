# FAPAR Clipping Scripts

This folder contains the CLMS FAPAR clipping scripts used to generate clipped products for AFRI and SOAM.

## What’s here
- `clip_clms_FAPAR_AFRI.py` / `clip_clms_FAPAR_AFRI_V2.py` – clip and package FAPAR for **Africa (AFRI)**
- `clip_clms_FAPAR_SOAM.py` / `clip_clms_FAPAR_SOAM_V2.py` – clip and package FAPAR for **South America (SOAM)**

> The `_V2.py` variants are the currently used versions in the automation workflow.

---

## Running a clipper script directly

Each script can be executed standalone by passing it the full path to the input NetCDF file.

### Example (AFRI):
```bash
python3 FAPAR/clip_clms_FAPAR_AFRI_V2.py \
  /path/to/c_gls_FAPAR300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

### Example (SOAM):
```bash
python3 FAPAR/clip_clms_FAPAR_SOAM_V2.py \
  /path/to/c_gls_FAPAR300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

Each script prints the output ZIP path on success and exits with `0`.

---

## Programmatic usage (used by `automation_script.py`)

Each script exports a function that returns the output zip path (used by the automation driver to track success):
- `run_fapar_afri_clipping(filepathname, dir_out="/home/eouser/clms/outputs/afr/")`
- `run_fapar_soam_clipping(filepathname, dir_out="/home/eouser/clms/outputs/sam/")`

---

## Notes

- Output ZIPs are written by default to the global output folders:
  - `/home/eouser/clms/outputs/afr/`
  - `/home/eouser/clms/outputs/sam/`

- The scripts rely on `clms_clipper_common.py` for shared clipping/packaging utilities.
