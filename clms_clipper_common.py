"""Shared helper utilities for CLMS clipper scripts.

This module contains shared helpers used by the per-product clipper scripts
(e.g. NDVI/clip_clms_NDVI_*.py, FAPAR/clip_clms_FAPAR_*.py, etc.).

The goal is to centralize common operations like output path construction, thumbnail
creation, zipping, and running a clipping+packaging pipeline.

Each per-product script should keep its product-specific constants (paths, identifiers,
variable names, etc.) but can call the shared `clip_and_package()` helper to
avoid repeating the same boilerplate logic.
"""

import os
import shutil
from typing import Callable, Dict, List, Optional


def _ensure_trailing_sep(path: str) -> str:
    return path if path.endswith(os.sep) else path + os.sep


def _replace_roi_in_filename(filename: str, roi: str) -> str:
    """Replace the GLOBE token in an input filename with the requested ROI."""
    return filename.replace("GLOBE", roi)


def _get_date_str_from_input_path(filepathname: str) -> str:
    """Extract the date string from an input filename.

    The input filenames are expected to have the date token as the 4th part when
    splitting on "_" (e.g., ..._202505010000_...).
    """
    return os.path.basename(filepathname).split("_")[3]


def _make_thumbnail_filename(output_file: str) -> str:
    """Build the thumbnail base filename by inserting 'QL' after the date token."""
    parts = os.path.splitext(output_file)[0].split("_")
    if len(parts) > 3:
        parts.insert(3, "QL")
    return "_".join(parts)


def zip_files_with_prefix(source_directory: str, zip_file_name: str, prefix: str = "") -> None:
    """Zip all files in a directory and add a prefix to each archive entry."""
    import zipfile

    with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_directory):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, source_directory)
                arcname = f"{prefix}{relative_path}"
                zipf.write(file_path, arcname)


def clip_and_package(
    filepathname: str,
    dir_in: str,
    dir_out: str,
    roi: str,
    desired_width: int,
    desired_height: int,
    origin_lat: float,
    origin_lon: float,
    data_vars: List[str],
    identifier: str,
    parent_identifier: str,
    color_table: str,
    destination_xml: str,
    clip_func: Callable,
    thumbnail_func: Callable,
    xml_modifier: Callable,
    xml_modifier_args: Optional[List] = None,
    xml_modifier_kwargs: Optional[Dict] = None,
    cleanup: bool = True,
) -> str:
    """Run clipping, thumbnail creation, XML patching, and zipping.

    This function wraps the common logic used by all per-product clipper scripts.

    Parameters are intentionally verbose so that callers explicitly provide
    the correct per-product values. This keeps product scripts easy to reason about.
    """

    dir_in = _ensure_trailing_sep(dir_in)
    dir_out = _ensure_trailing_sep(dir_out)

    date_str = _get_date_str_from_input_path(filepathname)
    output_dir = os.path.join(dir_out, date_str[0:8])
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(
        output_dir, _replace_roi_in_filename(os.path.basename(filepathname), roi)
    )

    # Run the clipping step (caller provides the clip function)
    clip_func(
        filepathname,
        output_file,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        clip_width=desired_width,
        clip_height=desired_height,
        data_vars=data_vars,
        identifier=identifier,
        parent_identifier=parent_identifier,
    )

    # Thumbnail creation
    thumb_base = _make_thumbnail_filename(output_file)
    thumbnail_func(output_file, thumb_base, color_table)

    # Clean up auxiliary file if created during thumbnail generation
    aux_file = thumb_base + ".tiff.aux.xml"
    if os.path.exists(aux_file):
        try:
            os.remove(aux_file)
        except OSError:
            pass

    ql_filename = os.path.basename(thumb_base) + ".tiff"

    # Modify the XML product description (caller provides the correct modifier)
    args = xml_modifier_args or []
    kwargs = xml_modifier_kwargs or {}

    # If caller is passing a params_dict, ensure it contains a correct ql_filename.
    # This saves callers from having to compute and inject the ql_filename themselves.
    params_dict = kwargs.get("params_dict")
    if isinstance(params_dict, dict):
        params_dict["ql_filename"] = ql_filename

    # By design the modifier signature should be:
    #   fn(date_str, ql_filename, destination_xml, ...)
    xml_modifier(date_str, ql_filename, destination_xml, *args, **kwargs)

    # Zip and clean up
    output_zip_name = os.path.join(output_dir, os.path.splitext(os.path.basename(output_file))[0])
    zip_files_with_prefix(output_dir, output_zip_name + ".zip", prefix=date_str[0:8] + "/")

    if cleanup:
        shutil.rmtree(output_dir)

    return output_zip_name + ".zip"
