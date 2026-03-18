# DMP Clipping Scripts

This directory contains the CLMS DMP (dry/gross dry matter productivity) clipping scripts used to produce clipped products for AFRI and SOAM.

## What’s here
- `clip_clms_DMP_AFRI.py` / `clip_clms_DMP_AFRI_V2.py` – clip and package DMP for **Africa (AFRI)**
- `clip_clms_DMP_SOAM.py` / `clip_clms_DMP_SOAM_V2.py` – clip and package DMP for **South America (SOAM)**

> The `_V2.py` variants are the versions used by the main automation workflow.

---

## Running a clipper script directly

Each script can be executed directly by supplying the input NetCDF path.

### Example (AFRI):
```bash
python3 DMP/clip_clms_DMP_AFRI_V2.py \
  /path/to/c_gls_DMP300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

### Example (SOAM):
```bash
python3 DMP/clip_clms_DMP_SOAM_V2.py \
  /path/to/c_gls_DMP300-RT0_<YYYY><MM><DD>0000_GLOBE_OLCI_V2.0.1.nc
```

Each script prints the output ZIP path on success and exits with code `0`.

---

## Programmatic usage (used by `automation_script.py`)

Each script exports a function that returns the generated output ZIP, which allows the orchestrator to track progress and avoid re-processing:
- `run_dmp_afri_clipping(filepathname, dir_out="/home/eouser/clms/outputs/afr/")`
- `run_dmp_soam_clipping(filepathname, dir_out="/home/eouser/clms/outputs/sam/")`

---

## Notes

- Output files are written by default to:
  - `/home/eouser/clms/outputs/afr/`
  - `/home/eouser/clms/outputs/sam/`

- The scripts share common clipping/packaging utilities from `clms_clipper_common.py`.
