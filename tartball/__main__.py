"""CLI entry point for tartball."""

import argparse
import json
import logging
import os
import shutil
import sys

import numpy as np
from casacore.tables import table
from disko import DiSkO, Resolution
from disko.healpix_sphere import create_fov
from tart.operation import settings
from tart2ms import ms_from_json
from tart_tools import api_handler

logger = logging.getLogger("tartball")


def load_model_json(model_path):
    """Load a sky model JSON file.

    Expected format:
    {
        "model": [
            {"a": 0.23, "az": -16.2, "el": 59.0, "p": 1.5},
            ...
        ],
        "time": "2026-06-18T09:57:45.893912+00:00"
    }

    Returns a list of (el_deg, az_deg, amplitude) tuples.
    """
    with open(model_path, "r") as f:
        data = json.load(f)

    model_entries = data.get("model", [])
    sources = []
    for src in model_entries:
        el = src.get("el", 0.0)
        az = src.get("az", 0.0)
        amp = src.get("a", 1.0)
        sources.append((el, az, amp))

    logger.info("Loaded %d model sources from %s", len(sources), model_path)
    return sources


def project_model_to_sphere(sources, sphere):
    """Project model sources onto a healpix sphere.

    Each source's amplitude is accumulated into the nearest healpix pixel.
    """
    pixels = np.zeros(sphere.npix, dtype=np.float64)
    for el, az, amp in sources:
        idx = sphere.index_of(np.radians(el), np.radians(az))
        pixels[idx] += amp
    logger.info(
        "Projected %d sources onto %d healpix pixels", len(sources), sphere.npix
    )
    return pixels


def compute_visibilities(ant_pos, frequency, sky_pixels, sphere):
    """Use DiSkO's telescope operator to compute visibilities from a healpix sky model.

    Parameters
    ----------
    ant_pos : ndarray (n_ant, 3)
        Antenna positions in ENU coordinates.
    frequency : float
        Observing frequency in Hz.
    sky_pixels : ndarray (n_pix,)
        Sky model pixel values.
    sphere : HealpixFoV or HealpixSubFoV
        The healpix sphere representation.

    Returns
    -------
    vis : ndarray (n_vis,)
        Complex visibilities for non-conjugate baselines (i > j).
    baselines : list of [i, j]
        The baseline pairs.
    """
    n_ant = len(ant_pos)

    # Build non-conjugate baselines and UVW (i > j only)
    baselines = []
    u_arr = []
    v_arr = []
    w_arr = []
    for i in range(n_ant):
        for j in range(i):
            baselines.append([i, j])
            du = ant_pos[i, 0] - ant_pos[j, 0]
            dv = ant_pos[i, 1] - ant_pos[j, 1]
            dw = ant_pos[i, 2] - ant_pos[j, 2]
            u_arr.append(du)
            v_arr.append(dv)
            w_arr.append(dw)

    u_arr = np.array(u_arr)
    v_arr = np.array(v_arr)
    w_arr = np.array(w_arr)

    # Create DiSkO operator and compute gamma (harmonics matrix)
    disko = DiSkO(u_arr, v_arr, w_arr, frequency)
    gamma = disko.get_harmonics(sphere)  # shape (n_vis, n_pix), complex

    # Forward predict: vis = gamma @ sky_pixels
    vis = gamma @ sky_pixels  # (n_vis, n_pix) @ (n_pix,) -> (n_vis,)
    vis = vis.astype(np.complex64)

    logger.info("Computed %d visibilities from %d sky pixels", len(vis), sphere.npix)
    logger.info("Vis amp range: %.2e to %.2e", np.min(np.abs(vis)), np.max(np.abs(vis)))
    return vis, baselines


def model_to_ms(
    model_path,
    ms_name,
    api_url="https://api.elec.ac.nz/tart/mu-udm/",
    fov_str="180deg",
    res_str="2deg",
    nside=None,
    clobber=False,
):
    """Generate a measurement set from a sky model JSON file.

    Uses the DiSkO healpix telescope operator to convert the sky model
    into predicted visibilities, then writes them to a measurement set.
    """
    # --- Validation ---
    if os.path.isdir(ms_name):
        if not clobber:
            raise RuntimeError(
                f"Measurement set '{ms_name}' exists. Use --clobber to overwrite."
            )
        logger.info("Clobbering existing '%s'", ms_name)
        shutil.rmtree(ms_name)

    # --- Load the model ---
    sources = load_model_json(model_path)

    # --- Fetch telescope configuration from the TART API ---
    logger.info("Fetching telescope config from API: %s", api_url)
    api = api_handler.APIhandler(api_url)

    info = api.get("info")
    ant_pos_raw = api.get("imaging/antenna_positions")
    config = settings.from_api_json(info["info"], ant_pos_raw)

    ant_pos = np.array(ant_pos_raw)
    frequency = config.get_operating_frequency()

    logger.info("Telescope: %s", info["info"].get("name", "Unknown"))
    logger.info("Antennas: %d", info["info"].get("num_antenna", len(ant_pos)))
    logger.info("Frequency: %.3f MHz", frequency / 1e6)

    # Get a real visibility snapshot to extract timing info
    vis_json_live = api.get("imaging/vis")
    gains_json = api.get("calibration/gain")

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
    vis_pred, baselines = compute_visibilities(ant_pos, frequency, sky_pixels, sphere)

    # --- Build synthetic observation for MS creation ---
    # We use a dummy source so the SOURCE table won't be empty
    # (tart2ms requires at least one source entry for MS creation)
    dummy_sources = [{"name": "TARTBALL_MODEL", "az": 0.0, "el": 90.0}]

    json_data = {
        "info": info,
        "ant_pos": ant_pos_raw,
        "gains": gains_json,
        "data": [[vis_json_live, dummy_sources]],
    }

    logger.info("Creating measurement set '%s'...", ms_name)

    ms_from_json(
        ms_name,
        None,  # json_filename
        False,  # pol2
        "instantaneous-zenith",
        "TART",
        json_data=json_data,
        applycal=False,
        fill_model=False,
        writemodelcatalog=False,
        fetch_sources=False,
        write_extragalactic_catalogs=False,
    )

    # --- Overwrite DATA and MODEL_DATA with predicted visibilities ---
    logger.info("Overwriting DATA with predicted visibilities...")
    _write_predicted_vis(ms_name, vis_pred)

    logger.info("Measurement set '%s' created successfully.", ms_name)


def _write_predicted_vis(ms_name, vis_pred):
    """Write the predicted visibilities into the MS DATA and MODEL_DATA columns.

    The vis_pred array should match the number of rows in the MS
    (non-conjugate baselines, n_ant * (n_ant - 1) / 2).
    """
    ms = table(ms_name, readonly=False, lockoptions="auto")
    try:
        data = ms.getcol("DATA")
        n_rows = data.shape[0]

        # vis_pred is shape (n_vis,) or (n_vis, 1)
        vis_pred = np.asarray(vis_pred).ravel()

        if len(vis_pred) != n_rows:
            raise RuntimeError(
                f"Visibility count mismatch: predicted {len(vis_pred)} "
                f"but MS has {n_rows} rows"
            )

        # Reshape to MS format: (n_rows, 1, 1) for single pol, single channel
        vis_col = vis_pred.reshape(n_rows, 1, 1).astype(np.complex64)

        ms.lock(write=True)
        ms.putcol("DATA", vis_col)

        # Also write MODEL_DATA if it exists
        if "MODEL_DATA" in ms.colnames():
            ms.putcol("MODEL_DATA", vis_col)
            logger.info("MODEL_DATA column also updated.")

        ms.unlock()
        logger.info("DATA column updated with %d predicted visibilities.", n_rows)

    finally:
        ms.close()


def main():
    """Main entry point for the tartball script."""
    parser = argparse.ArgumentParser(
        description="Prediction code to simulate TART data using DiSkO healpix telescope operator"
    )
    parser.add_argument(
        "--model",
        required=False,
        default=None,
        help="Path to sky model JSON file (az/el sources with fluxes)",
    )
    parser.add_argument(
        "--ms",
        required=False,
        default="tartball.ms",
        help="Output measurement set name",
    )
    parser.add_argument(
        "--api",
        required=False,
        default="https://api.elec.ac.nz/tart/mu-udm/",
        help="TART telescope API URL",
    )
    parser.add_argument(
        "--fov",
        type=str,
        default="180deg",
        help="Field of view (e.g. 10deg, 30arcmin, 180deg)",
    )
    parser.add_argument(
        "--res",
        type=str,
        default="2deg",
        help="Maximum resolution of the sky (e.g. 1deg, 30arcmin, 2arcmin)",
    )
    parser.add_argument(
        "--nside",
        type=int,
        default=None,
        help="Healpix nside parameter (overrides --fov/--res for pixel count)",
    )
    parser.add_argument(
        "--clobber",
        "-c",
        action="store_true",
        help="Overwrite output MS if it exists",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.model:
        model_to_ms(
            model_path=args.model,
            ms_name=args.ms,
            api_url=args.api,
            fov_str=args.fov,
            res_str=args.res,
            nside=args.nside,
            clobber=args.clobber,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
