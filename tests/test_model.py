"""Tests for model loading and healpix projection."""
# Copyright (c) 2025-2026 Timothy C.A. Molteno

import json
import tempfile
from pathlib import Path

import numpy as np
from disko.healpix_sphere import HealpixFoV

from tartball.model import load_model_json, project_model_to_sphere


def _write_temp_json(data):
    """Write a dict to a temporary JSON file, return the path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    return Path(tmp.name)


class TestLoadModelJson:
    def test_loads_sources(self):
        data = {
            "model": [
                {"a": 0.5, "az": -16.2, "el": 59.0, "p": 1.5},
                {"a": 0.2, "az": -254.9, "el": 5.1, "p": 0.87},
            ],
            "time": "2026-06-18T09:57:45Z",
        }
        path = _write_temp_json(data)
        try:
            sources = load_model_json(str(path))
            assert len(sources) == 2
            assert sources[0] == (59.0, -16.2, 0.5)
            assert sources[1] == (5.1, -254.9, 0.2)
        finally:
            path.unlink()

    def test_empty_model(self):
        data = {"model": [], "time": "2026-01-01T00:00:00Z"}
        path = _write_temp_json(data)
        try:
            sources = load_model_json(str(path))
            assert sources == []
        finally:
            path.unlink()

    def test_missing_keys_default(self):
        data = {"model": [{"a": 1.0}]}
        path = _write_temp_json(data)
        try:
            sources = load_model_json(str(path))
            assert sources[0] == (0.0, 0.0, 1.0)
        finally:
            path.unlink()


class TestProjectModelToSphere:
    def test_projects_single_source(self):
        sphere = HealpixFoV(nside=8)
        sources = [(45.0, 0.0, 1.0)]  # el, az, amp
        pixels = project_model_to_sphere(sources, sphere)
        assert isinstance(pixels, np.ndarray)
        assert pixels.dtype == np.float64
        assert len(pixels) == sphere.npix
        # Exactly one pixel should be non-zero
        assert np.count_nonzero(pixels) == 1
        assert pixels.sum() == 1.0

    def test_accumulates_same_pixel(self):
        sphere = HealpixFoV(nside=8)
        sources = [(45.0, 0.0, 0.3), (45.0, 0.0, 0.7)]
        pixels = project_model_to_sphere(sources, sphere)
        assert np.count_nonzero(pixels) == 1
        assert pixels.sum() == 1.0

    def test_distinct_pixels(self):
        sphere = HealpixFoV(nside=8)
        sources = [
            (80.0, 0.0, 1.0),
            (10.0, 90.0, 2.0),
            (-30.0, 180.0, 3.0),
        ]
        pixels = project_model_to_sphere(sources, sphere)
        assert np.count_nonzero(pixels) == 3
        assert pixels.sum() == 6.0

    def test_all_zero_for_no_sources(self):
        sphere = HealpixFoV(nside=8)
        pixels = project_model_to_sphere([], sphere)
        assert np.all(pixels == 0.0)
