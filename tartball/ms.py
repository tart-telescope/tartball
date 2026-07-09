"""Measurement set creation from predicted visibilities."""
# Copyright (c) 2025-2026 Timothy C.A. Molteno

import json
import logging
import os
import shutil
from datetime import datetime, timezone

import numpy as np
from casacore.tables import table
from disko import Resolution
from disko.healpix_sphere import create_fov
from tart.operation import settings
from tart2ms import ms_from_json
from tart_tools import api_handler

from .model import load_model_json, project_model_to_sphere
from .visibilities import compute_visibilities

logger = logging.getLogger("tartball")


def model_to_ms(
    model_path,
    ms_name,
    api_url=None,
    info_path=None,
    ant_pos_path=None,
    gains_path=None,
    noise_amplitude=0.0,
    fov_str="180deg",
    res_str="2deg",
    nside=None,
    clobber=False,
):
    """Generate a measurement set from a sky model JSON file.

    Telescope configuration (info + antenna positions) comes from either
    --api or --info/--antenna-positions.  Calibration gains are optional;
    unity gains are used if --gains is not provided.

    The model is the *only* source of visibilities — a zero-visibility
    scaffold is synthesized for the measurement set structure, then
    overwritten with DiSkO-predicted visibilities from the healpix model.
    """
    # --- Validation ---
    if os.path.isdir(ms_name):
        if not clobber:
            raise RuntimeError(
                f"Measurement set '{ms_name}' exists. Use --clobber to overwrite."
            )
        logger.info("Clobbering existing '%s'", ms_name)
        shutil.rmtree(ms_name)

    if api_url is None and (info_path is None or ant_pos_path is None):
        raise RuntimeError(
            "Either --api or both --info and --antenna-positions must be provided."
        )

    # --- Load the model ---
    sources = load_model_json(model_path)

    # --- Obtain telescope info and antenna positions ---
    if info_path and ant_pos_path:
        info, ant_pos_raw = _load_telescope_from_files(info_path, ant_pos_path)
    else:
        logger.info("Fetching telescope config from API: %s", api_url)
        info, ant_pos_raw = _fetch_telescope_from_api(api_url)

    config = settings.from_api_json(info["info"], ant_pos_raw)
    ant_pos = np.array(ant_pos_raw)
    n_ant = len(ant_pos)
    frequency = config.get_operating_frequency()

    logger.info("Telescope: %s", info["info"].get("name", "Unknown"))
    logger.info("Antennas: %d", n_ant)
    logger.info("Frequency: %.3f MHz", frequency / 1e6)

    # --- Load or default calibration gains ---
    gains_json = _load_gains(gains_path, n_ant)

    # --- Synthesize a zero-visibility scaffold for the MS ---
    vis_json = _synthesize_vis_json(n_ant)

    # --- Create the healpix sphere ---
    fov = Resolution.from_string(fov_str)
    res = Resolution.from_string(res_str)

    logger.info("FoV: %s (%.4f deg)", fov, fov.degrees())
    logger.info("Resolution: %s", res)

    if nside is not None:
        sphere = create_fov(nside=nside, fov=fov, res=res)
    else:
        sphere = create_fov(nside=None, fov=fov, res=res)

    logger.info("Healpix sphere: %s (npix=%d)", sphere, sphere.npix)

    # --- Project model sources onto healpix ---
    sky_pixels = project_model_to_sphere(sources, sphere)

    # --- Compute predicted visibilities ---
    vis_pred, _ = compute_visibilities(ant_pos, frequency, sky_pixels, sphere)

    # --- Add Gaussian noise if requested ---
    if noise_amplitude > 0.0:
        rng = np.random.default_rng()
        noise = noise_amplitude * (
            rng.standard_normal(len(vis_pred))
            + 1j * rng.standard_normal(len(vis_pred))
        ).astype(np.complex64)
        vis_pred = vis_pred + noise
        logger.info("Added Gaussian noise (amplitude=%.2e)", noise_amplitude)

    # --- Build synthetic observation for MS creation ---
    dummy_sources = [{"name": "TARTBALL_MODEL", "az": 0.0, "el": 90.0}]

    json_data = {
        "info": info,
        "ant_pos": ant_pos_raw,
        "gains": gains_json,
        "data": [[vis_json, dummy_sources]],
    }

    logger.info("Creating measurement set '%s'...", ms_name)

    ms_from_json(
        ms_name,
        None,
        False,
        "instantaneous-zenith",
        "TART",
        json_data=json_data,
        applycal=False,
        fill_model=False,
        writemodelcatalog=False,
        fetch_sources=False,
        write_extragalactic_catalogs=False,
    )

    # --- Overwrite DATA with predicted visibilities ---
    logger.info("Overwriting DATA with predicted visibilities...")
    _write_predicted_vis(ms_name, vis_pred)

    logger.info("Measurement set '%s' created successfully.", ms_name)


# ---------------------------------------------------------------------------
# Telescope configuration (info + antenna positions)
# ---------------------------------------------------------------------------


def _load_telescope_from_files(info_path, ant_pos_path):
    """Load telescope info and antenna positions from local JSON files."""
    logger.info("Loading telescope config from files")
    logger.info("  info: %s", info_path)
    logger.info("  antenna positions: %s", ant_pos_path)

    with open(info_path, "r") as f:
        info = json.load(f)
    with open(ant_pos_path, "r") as f:
        ant_pos_raw = json.load(f)

    return info, ant_pos_raw


def _fetch_telescope_from_api(api_url):
    """Fetch telescope info and antenna positions from the TART API.

    Only these two endpoints are used; visibilities always come
    from the model.
    """
    api = api_handler.APIhandler(api_url)
    info = api.get("info")
    ant_pos_raw = api.get("imaging/antenna_positions")
    return info, ant_pos_raw


# ---------------------------------------------------------------------------
# Calibration gains
# ---------------------------------------------------------------------------


def _load_gains(gains_path, n_ant):
    """Load calibration gains from a JSON file, or return unity gains."""
    if gains_path:
        logger.info("Loading gains from: %s", gains_path)
        with open(gains_path, "r") as f:
            return json.load(f)

    logger.info("Using unity gains (%d antennas)", n_ant)
    return {
        "gain": [1.0] * n_ant,
        "phase_offset": [0.0] * n_ant,
    }


# ---------------------------------------------------------------------------
# Visibility scaffold (zero-valued, model is the only visibility source)
# ---------------------------------------------------------------------------


def _synthesize_vis_json(n_ant):
    """Synthesize a zero-visibility snapshot for MS scaffolding.

    The actual visibilities come from the healpix model via DiSkO;
    this scaffold only exists so tart2ms can determine the MS
    dimensions (rows, columns, baselines).
    """
    data = []
    for i in range(n_ant):
        for j in range(i):
            data.append({"i": i, "j": j, "re": 0.0, "im": 0.0})

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    logger.info("Synthesized zero-visibility scaffold: %d baselines", len(data))
    return {"data": data, "timestamp": timestamp}


# ---------------------------------------------------------------------------
# MS writing
# ---------------------------------------------------------------------------


def _write_predicted_vis(ms_name, vis_pred):
    """Write the predicted visibilities into the MS DATA and MODEL_DATA columns."""
    ms = table(ms_name, readonly=False, lockoptions="auto")
    try:
        data = ms.getcol("DATA")
        n_rows = data.shape[0]

        vis_pred = np.asarray(vis_pred).ravel()

        if len(vis_pred) != n_rows:
            raise RuntimeError(
                f"Visibility count mismatch: predicted {len(vis_pred)} "
                f"but MS has {n_rows} rows"
            )

        vis_col = vis_pred.reshape(n_rows, 1, 1).astype(np.complex64)

        ms.lock(write=True)
        ms.putcol("DATA", vis_col)

        if "MODEL_DATA" in ms.colnames():
            ms.putcol("MODEL_DATA", vis_col)
            logger.info("MODEL_DATA column also updated.")

        ms.unlock()
        logger.info("DATA column updated with %d predicted visibilities.", n_rows)

    finally:
        ms.close()
