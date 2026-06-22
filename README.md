<!-- Copyright (c) 2025-2026 Timothy C.A. Molteno -->
# tartball

Prediction code to simulate TART radio telescope data.

Uses the [DiSkO](https://github.com/tart-telescope/disko) healpix telescope
operator to convert a sky model into predicted visibilities and writes them
to a CASA measurement set.

## Install

```bash
uv pip install tartball
```

Or for development:

```bash
git clone https://github.com/tart-telescope/tartball
cd tartball
uv sync --dev
```

## Usage

```bash
tartball --model model.json --ms output.ms
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--model` | *required* | Path to sky model JSON file |
| `--ms` | `tartball.ms` | Output measurement set name |
| `--fov` | `180deg` | Field of view (e.g. `10deg`, `30arcmin`) |
| `--res` | `2deg` | Healpix resolution (e.g. `1deg`, `2arcmin`) |
| `--nside` | *auto* | Explicit healpix nside (overrides fov/res) |
| `--clobber` / `-c` | off | Overwrite existing output MS |
| `--debug` | off | Enable debug logging |

### Telescope configuration

The telescope info and antenna positions can be provided in two ways:

**Online** — fetch from a TART API:

```bash
tartball --model model.json --api https://api.elec.ac.nz/tart/mu-udm/
```

**Offline** — load from local JSON files:

```bash
tartball --model model.json \
         --info info.json \
         --antenna-positions antenna_positions.json
```

If neither `--api` nor `--info`/`--antenna-positions` are given, the
production TART API is used by default.

### Calibration gains

Optional; unity gains are used if omitted:

```bash
tartball --model model.json --gains gains.json
```

The gains file should be a JSON object with `gain` and `phase_offset` arrays
(one entry per antenna).

## Sky model format

The `--model` file is a JSON object with a list of sources and an optional
timestamp:

```json
{
    "model": [
        {"a": 0.23, "az": -16.2, "el": 59.0, "p": 1.5},
        {"a": 0.20, "az": -254.9, "el": 5.1, "p": 0.87}
    ],
    "time": "2026-06-18T09:57:45.893912+00:00"
}
```

Each source:
- `a` — amplitude (Jy)
- `az` — azimuth (degrees)
- `el` — elevation (degrees)
- `p` — polarization fraction (unused)

## How it works

1. The sky model is loaded and each source is projected onto the nearest
   healpix pixel.
2. DiSkO's `get_harmonics()` computes the gamma matrix for the telescope's
   UVW baselines.
3. Visibilities are forward-predicted: `vis = gamma @ sky_pixels`.
4. A measurement set is created via `tart2ms` and the DATA column is
   overwritten with the predicted visibilities.

## Development

```bash
uv sync --dev     # install with test dependencies
uv run pytest     # run the test suite
```
