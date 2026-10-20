---
inclusion: auto
name: memory-and-performance
description: >-
  Memory, OOM, swap, performance and crash troubleshooting for the CLMS clippers.
  Use when a clip/automation run is killed, slow, hangs, exits with code 137,
  or when tuning the VM for the large global 300m NetCDF inputs.
---

# Memory, OOM & Performance Notes

## The core constraint
The CDSE VM has **~1.9 GB RAM, 2 CPU**. CLMS global 300m NetCDF inputs are large
(NDVI ~2.84 GB on disk). The clippers read full variable arrays / full quicklook
bands into memory despite "chunked" comments, so a single clip peaks **~1.2 GB
RSS**. With no swap, the OS **OOM-kills** the process.

## Symptom → diagnosis
- **Process "Killed", exit code 137** = SIGKILL from the OOM killer, not a code
  bug. Confirm with `dmesg | grep -i "killed process"` (needs sudo) or by
  watching `MemAvailable` drop to near zero in `/proc/meminfo` right before death.
- A memory trace that jumps (e.g. 106 MB → 498 MB → killed between 2 s samples)
  indicates a single large array allocation, not a gradual leak.

## The fix in place: 6 GB swap file
```bash
sudo fallocate -l 6G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# persist across reboots:
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
Verify: `swapon --show` and `free -h`.

With swap, a single NDVI-AFRI clip completed: **exit 0, ~436 s (~7 min), peak
~1.2 GB RSS + ~0.7 GB swap**, producing a ~505 MB output zip. Memory is freed
between products, so a full 10-combination run does not stack — expect **~1 hr**.

## Why NOT Docker / conda here
Docker would hit the **same OOM** (constraint is RAM, not packaging) plus add
daemon overhead; its image is ~2 GB. Conda bundles duplicate C libs (~2-3 GB).
The pip venv + system GDAL footprint is ~178 MB. For this VM, venv wins.

## Disk: outputs must go on the mounted data volume
The root disk is small (~15 GB) and cannot hold a dekad of outputs (zips
~300–500 MB each + an equally large intermediate NetCDF before zipping). A
**separate ~100 GB volume** (`/dev/sdb1`, label `localdata`, UUID
`5e02eeb0-072f-477c-b1f9-7ad8d5f284f3`) is mounted at `/localdata`; `.env`
output paths point there (`/localdata/afr`, `/localdata/sam`).

Symptom when the volume is NOT mounted (writes hit the full root disk):
`NetCDF: HDF error` on write, then `ERROR 4: ... No such file or directory` in
the quicklook step. Fix = mount `/localdata` (fstab: `defaults,nofail` — no
space in options, or the line is silently ignored and the mount won't persist).
Validate with `sudo mount -a` (silent = OK). Full runbook: `docs/DEPLOYMENT.md`
section 4b.

## Production recommendation
Swap is a safety net but swap-thrashing a 2.84 GB read is slow and hard on disk.
For regular dekadal runs, **resize the VM to 8 GB+ RAM** so clips run in-memory
with no swap and finish several times faster. (VM resize is a cloud-console
action, not doable from the shell.)

## How to do a safe "dry run" (no expensive clipping)
`automation_script.py` has no `--dry-run` flag. To preview what a run would do,
replicate its date logic (`get_target_date` for NDVI, `get_fapar_target_date`
for the rest), build the `EODATA_ROOT`-based path, and just `os.path.exists()`
each input. This confirms inputs, `.env`, and path wiring without clipping.

## Monitoring a live run
Sample `/proc/<pid>/status` (VmRSS, State) and `/proc/meminfo` (MemAvailable,
SwapFree) on an interval. A `State: D` (uninterruptible sleep) means disk I/O
wait — expected while paging to swap.
