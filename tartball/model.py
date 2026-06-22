"""Sky model loading and healpix projection."""

import json
import logging

import numpy as np

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
