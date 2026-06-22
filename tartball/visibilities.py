"""DiSkO telescope operator for forward-predicting visibilities."""

import logging

import numpy as np
from disko import DiSkO

logger = logging.getLogger("tartball")


def compute_visibilities(ant_pos, frequency, sky_pixels, sphere):
    """Use DiSkO's telescope operator to compute visibilities from a healpix sky model.

    Parameters
    ----------
    ant_pos : ndarray (n_ant, 3)
        Antenna positions in ENU coordinates.
    frequency : float
        Observing frequency in Hz.
    sky_pixels : ndarray (n_pix,)
        Sky model pixel values (per steradian).
    sphere : HealpixFoV or HealpixSubFoV
        The healpix sphere representation.

    Returns
    -------
    vis : ndarray (n_vis,)
        Complex visibilities for non-conjugate baselines (i > j).
    baselines : list of [i, j]
        The baseline pairs corresponding to each visibility.
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
