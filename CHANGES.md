# Changelog

## 0.2.0 — 2026-06-22

### Build System

- Migrated from Poetry to **uv** (`pyproject.toml` now uses `hatchling` build backend)
- Replaced `poetry.lock` with `uv.lock`
- `Dockerfile`: switched to `uv pip install`

### Dependencies

- Added `tart2ms (>=0.8.1,<0.9.0)` for measurement set creation
- Added `disko (>=1.3.3,<2.0.0)` for DiSkO healpix telescope operator
- Added `healpy (>=1.15.0,<2.0.0)` for healpix sphere support
- Added `pytest>=8.0` for development testing

### Features

- **`--model` flag**: takes a JSON sky model file (`{model: [{a, az, el, p}, ...], time}`) and generates a measurement set
- **`--fov` flag**: field of view for the healpix sphere (e.g. `10deg`, `30arcmin`, default `180deg`)
- **`--res` flag**: healpix resolution (e.g. `1deg`, `2arcmin`, default `2deg`)
- **`--nside` flag**: explicit healpix nside parameter (overrides auto from fov/res)
- **`--api` flag**: TART telescope API URL for fetching `info` and antenna positions
- **`--info` / `--antenna-positions` flags**: load telescope configuration from local JSON files (alternative to `--api`)
- **`--gains` flag**: optional calibration gains JSON file (defaults to unity gains if omitted)
- Uses **DiSkO's healpix telescope operator** (`get_harmonics`) to convert healpix sky model pixels into predicted visibilities via `vis = gamma @ sky_pixels`
- Writes predicted visibilities to both **DATA** and **MODEL_DATA** columns of the output measurement set
- **Offline mode**: no network required when `--info` and `--antenna-positions` are provided

### Architecture

- Code refactored into separate modules:
  - `tartball/__main__.py` — CLI argument parsing only
  - `tartball/model.py` — sky model loading and healpix projection
  - `tartball/visibilities.py` — DiSkO forward prediction via gamma matrix
  - `tartball/ms.py` — measurement set creation orchestration

### Tests

- Added 21 unit tests covering all modules
  - `tests/test_model.py` — JSON loading, healpix projection
  - `tests/test_visibilities.py` — baseline counts, dtypes, zero/uniform/point-source sky models
  - `tests/test_ms.py` — telescope config loading, gains, visibility scaffold synthesis

## 0.1.0

- Initial release with basic CLI scaffold
