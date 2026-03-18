# LAI Clipping Scripts

This directory contains the CLMS LAI clipping scripts used to produce clipped products for AFRI and SOAM.

## What’s here
- `clip_clms_LAI_AFRI.py` / `clip_clms_LAI_AFRI_V2.py` – clip and package LAI for **Africa (AFRI)**
- `clip_clms_LAI_SOAM.py` / `clip_clms_LAI_SOAM_V2.py` – clip and package LAI for **South America (SOAM)**

> The `_V2.py` variants are the versions used by the main automation workflow.

---

## Running a clipper script directly

Each script can be run directly by supplying the input NetCDF path.

### Example (AFRI):
```bash
python3 LAI/clip_clms_LAI_AFRI_V2.py \
  /path/to/c_gls_LAI300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

### Example (SOAM):
```bash
python3 LAI/clip_clms_LAI_SOAM_V2.py \
  /path/to/c_gls_LAI300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

Each script prints the output ZIP path on success and exits with code `0`.

---

## Programmatic usage (used by `automation_script.py`)

Each script exposes a function that returns the generated output ZIP, which allows the orchestrator to track progress and avoid re-processing:
- `run_lai_afri_clipping(filepathname, dir_out="/home/eouser/clms/outputs/afr/")`
- `run_lai_soam_clipping(filepathname, dir_out="/home/eouser/clms/outputs/sam/")`

---

## Notes

- Output files are written by default to:
  - `/home/eouser/clms/outputs/afr/`
  - `/home/eouser/clms/outputs/sam/`

- The scripts share common clipping/packaging utilities from `clms_clipper_common.py`.
