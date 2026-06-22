"""Tests for measurement set creation helpers."""

import json
import tempfile
from pathlib import Path

import numpy as np

from tartball.ms import _load_gains, _load_telescope_from_files, _synthesize_vis_json

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
# helpers
# ---------------------------------------------------------------------------


def _write_json(data):
    """Write a JSON-serializable object to a temp file, return its Path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    return Path(tmp.name)
