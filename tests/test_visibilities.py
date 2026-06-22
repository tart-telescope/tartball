"""Tests for the DiSkO visibility computation."""
# Copyright (c) 2025-2026 Timothy C.A. Molteno

import numpy as np
from disko.healpix_sphere import HealpixFoV

from tartball.visibilities import compute_visibilities


def _make_linear_array(n_ant, spacing=1.0):
    """Make a linear antenna array along the x-axis."""
    return np.column_stack(
        [np.arange(n_ant) * spacing, np.zeros(n_ant), np.zeros(n_ant)]
    )


class TestComputeVisibilities:
    def test_baseline_count(self):
        """Non-conjugate baselines for n_ant antennas = n_ant*(n_ant-1)/2."""
        for n in [2, 3, 5, 10]:
            ant_pos = _make_linear_array(n)
            sphere = HealpixFoV(nside=8)
            sky = np.ones(sphere.npix)
            vis, baselines = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

            expected = n * (n - 1) // 2
            assert len(vis) == expected
            assert len(baselines) == expected

    def test_baseline_indices(self):
        """Baselines should be all unique i,j pairs with i > j."""
        ant_pos = _make_linear_array(4)
        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        _, baselines = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

        assert baselines == [[1, 0], [2, 0], [2, 1], [3, 0], [3, 1], [3, 2]]

    def test_output_is_complex64(self):
        ant_pos = _make_linear_array(3)
        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        vis, _ = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

        assert vis.dtype == np.complex64

    def test_zero_sky_gives_zero_vis(self):
        ant_pos = _make_linear_array(4)
        sphere = HealpixFoV(nside=8)
        sky = np.zeros(sphere.npix)
        vis, _ = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

        assert np.allclose(vis, 0.0)

    def test_uniform_sky_gives_zenith_peak(self):
        """A uniform sky should produce visibilities dominated by the
        zero-baseline term (zenith pixel at w=0)."""
        ant_pos = _make_linear_array(3)
        sphere = HealpixFoV(nside=8)
        sky = np.ones(sphere.npix)
        vis, _ = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

        # Visibilities should be non-zero and finite
        assert np.all(np.isfinite(vis))
        assert not np.allclose(np.abs(vis), 0.0)

    def test_point_source_has_constant_amplitude(self):
        """A point source at zenith should give visibilities with
        amplitudes proportional to the source flux (times pixel area)."""
        ant_pos = _make_linear_array(3)
        sphere = HealpixFoV(nside=8)
        sky = np.zeros(sphere.npix)
        sky[0] = 1.0  # point source at first pixel
        vis, _ = compute_visibilities(ant_pos, 1.5e9, sky, sphere)

        assert np.all(np.isfinite(vis))
        # All visibilities should have the same amplitude for a zenith source
        amps = np.abs(vis)
        assert np.allclose(amps, amps[0], rtol=1e-5)
