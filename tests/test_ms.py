"""Tests for measurement set creation helpers."""
# Copyright (c) 2025-2026 Timothy C.A. Molteno

import json
import tempfile
from pathlib import Path

import numpy as np

from tartball.ms import _apply_beam, _load_gains, _load_telescope_from_files, _synthesize_vis_json

# ---------------------------------------------------------------------------
# _load_telescope_from_files
# ---------------------------------------------------------------------------


class TestLoadTelescopeFromFiles:
    def test_loads_info_and_ant_pos(self):
        info_data = {
            "info": {
                "name": "Test Telescope",
                "operating_frequency": 1.5e9,
                "num_antenna": 3,
                "location": {"lat": -45.0, "lon": 170.0, "alt": 100.0},
            }
        }
        ant_data = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]

        info_path = _write_json(info_data)
        ant_path = _write_json(ant_data)
        try:
            info, ant_pos = _load_telescope_from_files(str(info_path), str(ant_path))
            assert info == info_data
            assert ant_pos == ant_data
        finally:
            info_path.unlink()
            ant_path.unlink()


# ---------------------------------------------------------------------------
# _load_gains
# ---------------------------------------------------------------------------


class TestLoadGains:
    def test_returns_unity_when_no_path(self):
        gains = _load_gains(None, 5)
        assert gains["gain"] == [1.0] * 5
        assert gains["phase_offset"] == [0.0] * 5

    def test_returns_unity_for_empty_string(self):
        gains = _load_gains("", 3)
        assert gains["gain"] == [1.0] * 3
        assert gains["phase_offset"] == [0.0] * 3

    def test_loads_from_file(self):
        data = {"gain": [1.5, 0.8, 1.2], "phase_offset": [0.1, -0.2, 0.0]}
        path = _write_json(data)
        try:
            gains = _load_gains(str(path), 3)
            assert gains == data
        finally:
            path.unlink()

    def test_unity_length_matches_n_ant(self):
        gains = _load_gains(None, 10)
        assert len(gains["gain"]) == 10
        assert len(gains["phase_offset"]) == 10


# ---------------------------------------------------------------------------
# _synthesize_vis_json
# ---------------------------------------------------------------------------


class TestSynthesizeVisJson:
    def test_baseline_count(self):
        for n_ant in [2, 3, 5, 24]:
            vis = _synthesize_vis_json(n_ant)
            expected = n_ant * (n_ant - 1) // 2
            assert len(vis["data"]) == expected

    def test_structure(self):
        vis = _synthesize_vis_json(4)
        assert "data" in vis
        assert "timestamp" in vis
        assert isinstance(vis["timestamp"], str)

    def test_all_zero_and_i_gt_j(self):
        vis = _synthesize_vis_json(4)
        indices = []
        for entry in vis["data"]:
            assert entry["re"] == 0.0
            assert entry["im"] == 0.0
            assert entry["i"] > entry["j"]
            indices.append((entry["i"], entry["j"]))

        # 4 antennas => 6 unique i>j pairs
        assert len(indices) == 6
        assert len(set(indices)) == 6
        assert sorted(indices) == [
            (1, 0),
            (2, 0),
            (2, 1),
            (3, 0),
            (3, 1),
            (3, 2),
        ]


# ---------------------------------------------------------------------------
# _apply_beam
# ---------------------------------------------------------------------------


class TestApplyBeam:
    def test_tart_alias_uses_builtin_beam(self):
        """--beam tart loads base_tart_beam, not a file."""
        from disko.healpix_sphere import HealpixFoV

        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        result = _apply_beam(sky, sphere, "tart")

        assert result is not None
        assert result.shape == sky.shape
        # Beam should leave zenith pixel ~1 and zero out behind-the-antenna pixels
        assert np.all(result >= 0.0)
        # Fitted spherical harmonics can overshoot slightly at band edges
        assert np.all(result <= 1.05)

    def test_default_alias_is_same_as_tart(self):
        """--beam default is an alias for tart."""
        from disko.healpix_sphere import HealpixFoV

        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        result_tart = _apply_beam(sky.copy(), sphere, "tart")
        result_default = _apply_beam(sky.copy(), sphere, "default")

        np.testing.assert_array_equal(result_tart, result_default)

    def test_horizon_tapered_to_zero(self):
        """Pixels at/below the horizon (el <= 0) should have zero response."""
        from disko.healpix_sphere import HealpixFoV

        sphere = HealpixFoV(nside=32)
        sky = np.ones(sphere.npix)
        result = _apply_beam(sky, sphere, "tart")

        # Pixels with elevation <= 0 should be zero
        horizon_mask = sphere.el_r <= 0.0
        if np.any(horizon_mask):
            assert np.all(result[horizon_mask] == 0.0)

    def test_zenith_near_unity(self):
        """The pixel nearest the zenith (el ~ 90 deg) should have gain ~ 1."""
        from disko.healpix_sphere import HealpixFoV

        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        result = _apply_beam(sky, sphere, "tart")

        # Find the pixel closest to zenith
        zenith_idx = np.argmax(sphere.el_r)
        assert result[zenith_idx] > 0.9, f"zenith gain too low: {result[zenith_idx]}"

    def test_reduces_pixel_values(self):
        """The beam should reduce average pixel amplitude."""
        from disko.healpix_sphere import HealpixFoV

        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        result = _apply_beam(sky, sphere, "tart")

        # Mean response should be less than 1 (most of sphere is below zenith)
        assert np.mean(result) < 0.8

    def test_file_path_still_works(self):
        """A JSON file path should still load a custom beam."""
        from disko.healpix_sphere import HealpixFoV

        # Create a beam file with decent azimuthal coverage for a stable fit
        records = []
        for el in [90.0, 60.0, 30.0, 10.0, 0.0]:
            for az in [0.0, 90.0, 180.0, 270.0]:
                if el >= 10:
                    gain = 1.0
                elif el == 0:
                    gain = 0.0
                else:
                    gain = el / 10.0
                records.append({"el": el, "az": az, "gain": gain})
        path = _write_json(records)
        try:
            sphere = HealpixFoV(nside=8)
            sky = np.ones(sphere.npix)
            result = _apply_beam(sky, sphere, str(path))

            assert result is not None
            assert result.shape == sky.shape
            # The spherical-harmonic fit may ring near sharp edges;
            # just verify the beam was applied (some pixels changed)
            assert not np.allclose(result, sky)
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_json(data):
    """Write a JSON-serializable object to a temp file, return its Path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    return Path(tmp.name)
