"""Unified CLMS clipping automation.

This script provides a single entrypoint for running clipping workflows for
all CLMS products (NDVI, FAPAR, FCOVER, LAI, DMP) and both ROIs (AFRI, SOAM).

It is designed to be used instead of the older `automation_script.py`, but
without modifying any of the existing per-product clipper scripts.

The script uses a config-driven approach, centralized date logic, and a
consistent processed-file tracking mechanism.

Usage:
    python clms_clipper_unified.py --products NDVI,LAI --rois AFRI,SOAM

See `--help` for more options.
"""

import argparse
import datetime
import importlib
import logging
import os
from typing import Callable, Dict, List, Optional, Set


# -----------------------------------------------------------------------------
# Helper utilities (logging + processed tracking)
# -----------------------------------------------------------------------------

DEFAULT_PROCESSED_INPUT_FILE = "/home/eouser/clms/config/processed_input_files.txt"
DEFAULT_PROCESSED_OUTPUT_FILE = "/home/eouser/clms/config/processed_output_files.txt"
DEFAULT_LOG_FILE = "/home/eouser/clms/logs/clipper_automation.log"


def setup_logging(log_file: str = DEFAULT_LOG_FILE, level: int = logging.INFO) -> None:
    """Configure logging to file + console."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


def load_processed_list(file_path: str) -> Set[str]:
    """Load a set of already-processed keys (input filenames, output archive names, etc.)."""
    if not os.path.exists(file_path):
        logging.info("Processed list file not found at %s. Starting with empty list.", file_path)
        return set()

    try:
        with open(file_path, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except IOError as e:
        logging.error("Failed to load processed list from %s: %s", file_path, e)
        return set()


def write_to_processed_list(file_path: str, entry: str) -> None:
    """Append a single entry to the processed list file."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "a") as f:
            f.write(entry + "\n")
        logging.info("Successfully logged '%s' to processed list %s", entry, file_path)
    except IOError as e:
        logging.error("Failed to write '%s' to processed list file %s: %s", entry, file_path, e)


# -----------------------------------------------------------------------------
# Date selection logic (shared by all products)
# -----------------------------------------------------------------------------

def get_ndvi_target_date(current_date: datetime.date) -> datetime.date:
    """Return the target date for NDVI products.

    - Days 1-10 -> third dekad of previous month (21st of previous month)
    - Days 11-20 -> first dekad of current month (1st)
    - Days 21+ -> second dekad of current month (11th)
    """
    current_day = current_date.day

    if 1 <= current_day <= 10:
        first_day_current_month = current_date.replace(day=1)
        last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
        return last_day_prev_month.replace(day=21)

    if 11 <= current_day <= 20:
        return current_date.replace(day=1)

    # day >= 21
    return current_date.replace(day=11)


def get_fapar_target_date(current_date: datetime.date) -> datetime.date:
    """Return the target date for FAPAR / FCOVER / LAI / DMP products.

    - Days 1-11 -> third dekad of previous month (last day of previous month)
    - Days 12-21 -> first dekad of current month (10th)
    - Days 22+ -> second dekad of current month (20th)
    """
    current_day = current_date.day

    if 1 <= current_day <= 11:
        first_of_month = current_date.replace(day=1)
        return first_of_month - datetime.timedelta(days=1)

    if 12 <= current_day <= 21:
        return current_date.replace(day=10)

    return current_date.replace(day=20)


# -----------------------------------------------------------------------------
# Clip run configuration
# -----------------------------------------------------------------------------

# NOTE: This config dictionary is the single place to keep the filename patterns,
# base input directories, and module/function mapping. It is intentionally
# separate from the older per-product clipping scripts.
CONFIG: Dict[str, Dict] = {
    "NDVI": {
        "base_dir": "/eodata/CLMS/bio-geophysical/vegetation_indices/ndvi_global_300m_10daily_v3",
        "filename_template": (
            "c_gls_NDVI300_{year}{month}{day}0000_GLOBE_OLCI_V3.0.1_nc/"
            "c_gls_NDVI300_{year}{month}{day}0000_GLOBE_OLCI_V3.0.1.nc"
        ),
        "date_func": get_ndvi_target_date,
        "rois": {
            "AFRI": {
                "module": "NDVI.clip_clms_NDVI_AFRI_V3",
                "function": "run_ndvi_afri_clipping",
            },
            "SOAM": {
                "module": "NDVI.clip_clms_NDVI_SOAM_V3",
                "function": "run_ndvi_soam_clipping",
            },
        },
    },
    "DMP": {
        "base_dir": "/eodata/CLMS/bio-geophysical/dry-gross_dry_matter_productivity/dmp_global_300m_10daily_v2",
        "filename_template": (
            "c_gls_DMP300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1_nc/"
            "c_gls_DMP300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1.nc"
        ),
        "date_func": get_fapar_target_date,
        "rois": {
            "AFRI": {
                "module": "DMP.clip_clms_DMP_AFRI_V2",
                "function": "run_dmp_afri_clipping",
            },
            "SOAM": {
                "module": "DMP.clip_clms_DMP_SOAM_V2",
                "function": "run_dmp_soam_clipping",
            },
        },
    },
    "FAPAR": {
        "base_dir": "/eodata/CLMS/bio-geophysical/vegetation_properties/fapar_global_300m_10daily_v2",
        "filename_template": (
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1_nc/"
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1.nc"
        ),
        "date_func": get_fapar_target_date,
        "rois": {
            "AFRI": {
                "module": "FAPAR.clip_clms_FAPAR_AFRI_V2",
                "function": "run_fapar_afri_clipping",
            },
            "SOAM": {
                "module": "FAPAR.clip_clms_FAPAR_SOAM_V2",
                "function": "run_fapar_soam_clipping",
            },
        },
    },
    "FCOVER": {
        "base_dir": "/eodata/CLMS/bio-geophysical/vegetation_properties/fcover_global_300m_10daily_v2",
        "filename_template": (
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1_nc/"
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1.nc"
        ),
        "date_func": get_fapar_target_date,
        "rois": {
            "AFRI": {
                "module": "FCOVER.clip_clms_FCOVER_AFRI_V2",
                "function": "run_fcover_afri_clipping",
            },
            "SOAM": {
                "module": "FCOVER.clip_clms_FCOVER_SOAM_V2",
                "function": "run_fcover_soam_clipping",
            },
        },
    },
    "LAI": {
        "base_dir": "/eodata/CLMS/bio-geophysical/vegetation_properties/lai_global_300m_10daily_v2",
        "filename_template": (
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1_nc/"
            "c_gls_{var}300-RT0_{year}{month}{day}0000_GLOBE_OLCI_V2.0.1.nc"
        ),
        "date_func": get_fapar_target_date,
        "rois": {
            "AFRI": {
                "module": "LAI.clip_clms_LAI_AFRI_V2",
                "function": "run_lai_afri_clipping",
            },
            "SOAM": {
                "module": "LAI.clip_clms_LAI_SOAM_V2",
                "function": "run_lai_soam_clipping",
            },
        },
    },
}


# -----------------------------------------------------------------------------
# Runtime helpers
# -----------------------------------------------------------------------------

def _import_clipper(product: str, roi: str) -> Callable[[str], str]:
    """Import and return the clipper function for a product/ROI."""
    product_cfg = CONFIG.get(product)
    if not product_cfg:
        raise KeyError(f"Unknown product '{product}'. Available: {sorted(CONFIG)}")

    roi_cfg = product_cfg.get("rois", {}).get(roi)
    if not roi_cfg:
        raise KeyError(f"Unknown ROI '{roi}' for product '{product}'. Available: {sorted(product_cfg.get('rois', {}))}")

    module_name = roi_cfg["module"]
    function_name = roi_cfg["function"]

    module = importlib.import_module(module_name)
    func = getattr(module, function_name, None)
    if func is None:
        raise AttributeError(f"Module '{module_name}' does not export function '{function_name}'")

    return func


def _build_input_path(product: str, target_date: datetime.date) -> str:
    """Build the full path to the input NetCDF file using the configured template."""
    product_cfg = CONFIG[product]
    base_dir = product_cfg["base_dir"]
    date_str = {
        "year": target_date.strftime("%Y"),
        "month": target_date.strftime("%m"),
        "day": target_date.strftime("%d"),
    }

    # Build the relative filename and join with base_dir / year / month / day.
    filename = product_cfg["filename_template"].format(var=product, **date_str)
    file_dir = os.path.join(base_dir, date_str["year"], date_str["month"], date_str["day"])
    return os.path.join(file_dir, filename)


def run_clipper(
    product: str,
    roi: str,
    target_date: Optional[datetime.date] = None,
    dir_out: str = "/home/eouser/clms/outputs",
    processed_input_file: str = DEFAULT_PROCESSED_INPUT_FILE,
    processed_output_file: str = DEFAULT_PROCESSED_OUTPUT_FILE,
    skip_if_missing_input: bool = True,
) -> Optional[str]:
    """Run a single clipper for a product/ROI.

    Returns the output zip path if successful (and found), otherwise None.
    """
    if target_date is None:
        target_date = datetime.date.today()

    product_cfg = CONFIG.get(product)
    if not product_cfg:
        raise KeyError(f"Unknown product '{product}'")

    date_func = product_cfg["date_func"]
    effective_date = date_func(target_date)

    input_path = _build_input_path(product, effective_date)
    log_prefix = f"[{product}-{roi} | {effective_date.isoformat()}]"

    if skip_if_missing_input and not os.path.exists(input_path):
        logging.error("%s SKIP: Input file does not exist: %s", log_prefix, input_path)
        return None

    processed = load_processed_list(processed_input_file)
    processed_key = f"{os.path.basename(input_path)}_{roi}"
    if processed_key in processed:
        logging.info("%s SKIP: already processed", log_prefix)
        return None

    clipper_fn = _import_clipper(product, roi)

    logging.info("%s Running clipper func %s", log_prefix, clipper_fn.__name__)

    try:
        output_zip = clipper_fn(input_path, dir_out)
    except Exception as e:
        logging.error("%s Clipper failed: %s", log_prefix, e)
        return None

    if not output_zip:
        logging.error("%s Clipper returned no output path", log_prefix)
        return None

    if not os.path.exists(output_zip):
        logging.error("%s Expected output zip not found: %s", log_prefix, output_zip)
        return None

    # Update processed lists
    write_to_processed_list(processed_input_file, processed_key)
    write_to_processed_list(processed_output_file, os.path.basename(output_zip))

    logging.info("%s SUCCESS: %s", log_prefix, output_zip)
    return output_zip


def run_all(
    products: List[str],
    rois: List[str],
    target_date: Optional[datetime.date] = None,
    dir_out: str = "/home/eouser/clms/outputs",
    processed_input_file: str = DEFAULT_PROCESSED_INPUT_FILE,
    processed_output_file: str = DEFAULT_PROCESSED_OUTPUT_FILE,
    skip_if_missing_input: bool = True,
) -> None:
    """Run clipping for all combinations of products and ROIs."""
    for product in products:
        for roi in rois:
            run_clipper(
                product=product,
                roi=roi,
                target_date=target_date,
                dir_out=dir_out,
                processed_input_file=processed_input_file,
                processed_output_file=processed_output_file,
                skip_if_missing_input=skip_if_missing_input,
            )


# -----------------------------------------------------------------------------
# CLI entrypoint
# -----------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CLMS clipping workflows for NDVI/FAPAR/FCOVER/LAI/DMP.")
    parser.add_argument(
        "--products",
        default="NDVI,FAPAR,FCOVER,LAI,DMP",
        help="Comma-separated list of products to process (default: all).",
    )
    parser.add_argument(
        "--rois",
        default="AFRI,SOAM",
        help="Comma-separated list of ROIs to process (default: AFRI,SOAM).",
    )
    parser.add_argument(
        "--date",
        help="Optional fixed date (YYYY-MM-DD). If omitted, today is used.",
    )
    parser.add_argument(
        "--dir-out",
        default="/home/eouser/clms/outputs",
        help="Base output directory for clipped products.",
    )
    parser.add_argument(
        "--processed-input",
        default=DEFAULT_PROCESSED_INPUT_FILE,
        help="Path to the processed input list file.",
    )
    parser.add_argument(
        "--processed-output",
        default=DEFAULT_PROCESSED_OUTPUT_FILE,
        help="Path to the processed output list file.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help="Path to the log file.",
    )
    parser.add_argument(
        "--skip-missing-input",
        action="store_true",
        help="Skip processing if input file is missing (default: True).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    setup_logging(args.log_file, level=logging.INFO)

    target_date = None
    if args.date:
        target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()

    products = [p.strip() for p in args.products.split(",") if p.strip()]
    rois = [r.strip() for r in args.rois.split(",") if r.strip()]

    run_all(
        products=products,
        rois=rois,
        target_date=target_date,
        dir_out=args.dir_out,
        processed_input_file=args.processed_input,
        processed_output_file=args.processed_output,
        skip_if_missing_input=args.skip_missing_input,
    )


if __name__ == "__main__":
    main()
