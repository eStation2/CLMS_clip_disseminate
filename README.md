# CLMS Clipping & Dissemination (EUMETSAT)

This repository contains the CLMS clipping automation and dissemination scripts used to process Copernicus Land Monitoring Service (CLMS) products (NDVI, FAPAR, FCOVER, LAI, DMP) and upload them to the EUMETCAST dissemination directory.

> 💡 **Note:** This README is written for usage on the CDSE machine (accessed via `ssh` from `s262p`).

---

## 🔌 Environment & Directory Layout

### Accessing the machine
```bash
ssh cdse
```

### Key workspace location
All the configuration, logs, scripts, and output data live under:
```
/home/eouser/clms
```

The CLMS clipping repository is cloned into:
```
/home/eouser/clms/CLMS_clip_disseminate
```

### Important directories
- **Configuration:** `/home/eouser/clms/config/`
- **Logs:** `/home/eouser/clms/logs/`
- **Output:** `/home/eouser/clms/outputs/`
- **Scripts:** `/home/eouser/clms/CLMS_clip_disseminate/`

---

## 🛠️ How the Automation Runs (cron)

The system is driven by cron jobs that run the main automation script on a schedule designed around “dekads” (10-day periods).

### Cron schedule (as seen in `crontab -l`)
```cron
# m h  dom mon dow   command
# Run once in the evening (7 PM) on the 1st, 11th and 21st
0 19 1,11,21 * * /usr/bin/python3 /home/eouser/clms/CLMS_clip_disseminate/automation_script.py

# Run 4 times (every 6 hours) on the 2nd, 12th and 22nd
0 */6 2,12,22 * * /usr/bin/python3 /home/eouser/clms/CLMS_clip_disseminate/automation_script.py

# Run twice  (1 AM and 3AM) on the 3rd, 13th and 23rd
0 1,3 3,13,23 * * /usr/bin/python3 /home/eouser/clms/CLMS_clip_disseminate/automation_script.py

# Africa Dissemination (4am, 2am) on the 2nd,3rd, 12th, 13th, 22nd and 23rd for Africa
0 2,4 2,3,12,13,22,23 * * /usr/bin/python3 /home/eouser/clms/CLMS_clip_disseminate/dissemination_afr.py

# South America Dissemination (5am and 2am) on the 4th, 14th and 24th for SOAM
0 2,5 4,14,24 * * /usr/bin/python3 /home/eouser/clms/CLMS_clip_disseminate/dissemination_soam.py
```

> ✅ The scripts may run multiple times for the same dekad, but the process is idempotent: it checks configuration lists before doing work and will skip already-processed products.

---

## 🧩 Configuration Files

The process is managed via two main tracking files located in `config/`:

### `processed_input_files.txt`
- Tracks **all global source files** that have been processed.
- Entries are appended and never removed.

### `processed_output_files.txt`
- Tracks the **AFR / SOAM output ZIP files** produced by clipping.
- This list is dynamic: once files are successfully uploaded to EUMETCAST, they are moved from here into:
  - `ftp_uploaded_afr.list`
  - `ftp_uploaded_soam.list`

---

## 🗂️ Output Folder Layout

All outputs are written under:
```
/home/eouser/clms/outputs/
```

### Africa (AFR)
- `afr/` – processed output files ready for dissemination
- `afr/uploaded/` – files moved here after successful upload

### South America (SOAM)
- `sam/` – processed output files ready for dissemination
- `sam/uploaded/` – files moved here after successful upload

---

## 📄 Logging

All clipping logs are written to:
- `/home/eouser/clms/logs/clipper_automation.log`

Upload logs are produced for each run and include a timestamp:
- `/home/eouser/clms/logs/ftp_upload_AFR_<TIMESTAMP>.log`
- `/home/eouser/clms/logs/ftp_upload_SOAM_<TIMESTAMP>.log`

---

## ✅ Comparing Results (VITO script)

To validate that two ZIP outputs are identical (or to compare expected vs generated), use the `compareProduct.py` script.

Example:
```bash
python compareProduct.py -t /tmp -r reference/c_gls_FAPAR300-RT0_202505100000_AFRI_OLCI_V1.1.1.zip new/c_gls_FAPAR300-RT0_202505100000_AFRI_OLCI_V1.1.1.zip
```

---

## 🧭 Key Scripts

- `automation_script.py` – orchestrates processing across products/ROIs (NDVI, FAPAR, FCOVER, LAI, DMP).
- `dissemination_afr.py` – performs upload/dissemination for AFR outputs.
- `dissemination_soam.py` – performs upload/dissemination for SOAM outputs.

---

## 🚀 Quick Start (Manual Run)

From the CDSE machine:
```bash
cd /home/eouser/clms/CLMS_clip_disseminate
python3 automation_script.py
```

### Running a specific clipper script directly

You can also run individual clipper scripts for a single product/ROI combination. Each script takes the full path to the input NetCDF file as an argument.

Example (NDVI for AFRI):
```bash
python3 NDVI/clip_clms_NDVI_AFRI_V3.py \
  /path/to/c_gls_NDVI300_<YYYY><MM><DD>0000_GLOBE_OLCI_V3.0.1.nc
```

See the individual product READMEs (e.g., `NDVI/README.md`) for more examples and details on each script.

---

## 🐳 Docker Deployment

Instead of running on the host machine, you can deploy the CLMS clipping system in a Docker container.

### Prerequisites
- Docker and Docker Compose installed on the host.
- Ensure the host directories exist: `/home/eouser/clms/config`, `/home/eouser/clms/logs`, `/home/eouser/clms/outputs`, `/eodata/CLMS`.

### Build and Run
1. **Build the image:**
   ```bash
   docker-compose build
   ```

2. **Run the container (manual execution):**
   ```bash
   docker-compose run --rm clms-clipper
   ```
   This runs the automation script once and exits.

3. **For cron-like scheduling inside the container:**
   - Modify the `docker-compose.yml` to use `command: cron -f`.
   - Copy your crontab into the container (e.g., via a custom entrypoint script).
   - Run: `docker-compose up -d`

### Volume Mappings
- **Config:** `/home/eouser/clms/config` (host) → `/home/eouser/clms/config` (container)
- **Logs:** `/home/eouser/clms/logs` (host) → `/home/eouser/clms/logs` (container)
- **Outputs:** `/home/eouser/clms/outputs` (host) → `/home/eouser/clms/outputs` (container)
- **Input Data:** `/eodata/CLMS` (host, read-only) → `/eodata/CLMS` (container)

### Notes
- The container runs as user `eouser` to match the host setup.
- For production, consider using a proper container orchestration tool like Kubernetes for scheduling.
- Ensure the host's `/eodata/CLMS` is accessible and has the correct permissions.

---



