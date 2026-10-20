# CLMS Clipping & Dissemination (EUMETSAT)

This repository contains the CLMS clipping automation and dissemination scripts used to process Copernicus Land Monitoring Service (CLMS) products (NDVI, FAPAR, FCOVER, LAI, DMP) and upload them to the EUMETCAST dissemination directory.

> 💡 **Note:** This README is written for usage on the CDSE machine (accessed via `ssh` from `s262p`).

> 📘 **Deploying on a fresh VM?** See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
> for the full step-by-step runbook (system GDAL, venv, `.env`, swap, run,
> cron, and troubleshooting).

---

## 🔌 Environment & Directory Layout

### Accessing the machine
```bash
ssh cdse
```

### Key workspace location

All configuration, logs, and output data live under a single **base directory**,
referred to below as `$CLMS_HOME`. For example, on one CDSE VM this was:
```
/home/eouser/clms
```

> ⚙️ **These paths are configurable and the values shown are only examples.**
> `$CLMS_HOME` and every sub-path are read from environment variables (see
> `.env` / `.env.template` and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)). Set
> `CLMS_HOME` (and the related `CLMS_*` variables) to a writable location
> appropriate for your machine and user account.

The CLMS clipping repository is cloned into:
```
$CLMS_HOME/CLMS_clip_disseminate
```

### Important directories (relative to `$CLMS_HOME`)
| Purpose | Example path | Env variable |
|---|---|---|
| Configuration | `$CLMS_HOME/config/` | `CLMS_CONFIG_DIR` |
| Logs | `$CLMS_HOME/logs/` | `CLMS_LOG_DIR` |
| Output (AFRI) | `$CLMS_HOME/outputs/afr/` | `CLMS_OUTPUT_AFR_DIR` |
| Output (SOAM) | `$CLMS_HOME/outputs/sam/` | `CLMS_OUTPUT_SOAM_DIR` |
| Scripts | `$CLMS_HOME/CLMS_clip_disseminate/` | — |
| Input archive | `/eodata` (read-only mount) | `EODATA_ROOT` |

---

## ⚙️ Configuration (`.env`)

Runtime paths are read from a `.env` file in the repository root (loaded via
`python-dotenv`). A committed `.env.template` documents every variable; copy it
and edit for your machine:

```bash
cp .env.template .env
# then edit .env
```

| Variable | Purpose | Example value |
|---|---|---|
| `CLMS_HOME` | Base directory for all runtime data | `/home/eouser/clms` |
| `CLMS_CONFIG_DIR` | Tracking lists (+ netrc files) | `$CLMS_HOME/config` |
| `CLMS_LOG_DIR` | Log directory | `$CLMS_HOME/logs` |
| `CLMS_PROCESSED_INPUT_FILE` | Processed-input tracking list | `$CLMS_CONFIG_DIR/processed_input_files.txt` |
| `CLMS_PROCESSED_OUTPUT_FILE` | Processed-output tracking list | `$CLMS_CONFIG_DIR/processed_output_files.txt` |
| `CLMS_LOG_FILE` | Main clipper log file | `$CLMS_LOG_DIR/clipper_automation.log` |
| `CLMS_OUTPUT_AFR_DIR` | AFRI output directory | `$CLMS_HOME/outputs/afr` |
| `CLMS_OUTPUT_SOAM_DIR` | SOAM output directory | `$CLMS_HOME/outputs/sam` |
| `EODATA_ROOT` | Root of the CDSE EODATA archive (input) | `/eodata` |

Notes:
- `.env` is **gitignored**; only `.env.template` is committed. The example values
  above are **not** production values — set them for your own machine.
- If `.env` is absent, the scripts fall back to these same example defaults, so
  bare-metal behaviour is unchanged.
- The config and log directories are **auto-created** at startup. If they point
  somewhere not writable by the current user, you'll get a `PermissionError` —
  adjust the paths in `.env`.
- Currently `automation_script.py` and `dissemination.py` (and its per-region
  duplicates `dissemination_afr.py` / `dissemination_soam.py`) read `.env`.
  `clms_clipper_unified.py` still uses hardcoded paths.

### Dissemination (FTP) variables

The dissemination scripts read their FTP endpoint and credentials from `.env`
too. The log/config/output directories are reused from the variables above.

| Variable | Purpose | Example value |
|---|---|---|
| `CLMS_FTP_SERVER` | EUMETCAST FTP host | `ofids.eumetsat.int` |
| `CLMS_FTP_LOCAL_IP` | This machine's reachable IP (FTP active mode) | `46.60.20.214` |
| `CLMS_FTP_PORT_RANGE_START` | Active-mode port range start | `50000` |
| `CLMS_FTP_PORT_RANGE_END` | Active-mode port range end | `50100` |
| `CLMS_AFR_REMOTE_DIR` | AFR remote upload directory | `/out/groups/vito-open-afr-test` |
| `CLMS_AFR_USER_PWD` | AFR credentials, `user:password` (**secret**) | `user:pwd` |
| `CLMS_SOAM_REMOTE_DIR` | SOAM remote upload directory | `/out/groups/vito-open-sam-test` |
| `CLMS_SOAM_USER_PWD` | SOAM credentials, `user:password` (**secret**) | `user:pwd` |

> ⚠️ **FTP active mode:** `CLMS_FTP_LOCAL_IP` must be this machine's own
> externally reachable IP, and the port range (`50000–50100`) must be open in
> the firewall, or uploads will hang/fail.
>
> 🔐 **Credentials** (`CLMS_*_USER_PWD`) are secrets — set real values only in
> `.env` (gitignored), never in `.env.template` or committed code.

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full setup runbook.

---

## 🛠️ How the Automation Runs (cron)

The system is driven by cron jobs that run the main automation script on a schedule designed around “dekads” (10-day periods).

### Cron schedule (as seen in `crontab -l`)

> The absolute paths below are an **example** from one deployment. Adapt them to
> your repo location. Two requirements for cron: (1) **`cd` into the repo root**
> before running (so `DMP`/`NDVI`/… package imports resolve), and (2) use the
> **venv interpreter** (`.venv/bin/python3`), not `/usr/bin/python3`, so the
> GDAL/netCDF dependencies are available. See `docs/DEPLOYMENT.md` §8 for a
> ready-to-install crontab (with `cd $REPO && $PY ...`) and the cleanup jobs.

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

All outputs are written under the configured output directories (example paths —
set via `CLMS_OUTPUT_AFR_DIR` / `CLMS_OUTPUT_SOAM_DIR`, defaulting under
`$CLMS_HOME/outputs/`):
```
$CLMS_HOME/outputs/
```

### Africa (AFR)
- `afr/` – processed output files ready for dissemination
- `afr/uploaded/` – files moved here after successful upload

### South America (SOAM)
- `sam/` – processed output files ready for dissemination
- `sam/uploaded/` – files moved here after successful upload

---

## 📄 Logging

All clipping logs are written to the configured log directory (`CLMS_LOG_DIR`;
`CLMS_LOG_FILE` for the main log). Example:
- `$CLMS_HOME/logs/clipper_automation.log`

Upload logs are produced for each run and include a timestamp, e.g.:
- `$CLMS_HOME/logs/ftp_upload_AFR_<TIMESTAMP>.log`
- `$CLMS_HOME/logs/ftp_upload_SOAM_<TIMESTAMP>.log`

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

From the machine where the repo is deployed (replace `$CLMS_HOME` with your
actual base directory):
```bash
cd $CLMS_HOME/CLMS_clip_disseminate
source .venv/bin/activate        # activate the virtual environment first
python3 automation_script.py
```

> See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for first-time setup (system
> GDAL, venv, `.env`, swap) before running.

### Running a specific clipper script directly

You can also run individual clipper scripts for a single product/ROI combination. Each script takes the full path to the input NetCDF file as an argument.

Example (NDVI for AFRI):
```bash
python3 NDVI/clip_clms_NDVI_AFRI_V3.py \
  /path/to/c_gls_NDVI300_<YYYY><MM><DD>0000_GLOBE_OLCI_V3.0.1.nc
```

See the individual product READMEs (e.g., `NDVI/README.md`) for more examples and details on each script.

---


