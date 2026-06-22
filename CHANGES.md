# Changelog

## 0.2.0 — 2026-06-22

### Build System

- Migrated from Poetry to **uv** (`pyproject.toml` now uses `hatchling` build backend)
- Replaced `poetry.lock` with `uv.lock`
- `.gitignore`: uncommented `uv.lock`, removed `poetry.lock` tracking
- `Dockerfile`: switched to `uv pip install`

### Dependencies

- Added `tart2ms (>=0.8.1,<0.9.0)` for measurement set creation
- Added `disko (>=1.3.3,<2.0.0)` for DiSkO healpix telescope operator
- Added `healpy (>=1.15.0,<2.0.0)` for healpix sphere support

### Features

- **`--model` flag**: takes a JSON sky model file (`{model: [{a, az, el, p}, ...], time}`) and generates a measurement set
- **`--fov` flag**: field of view for the healpix sphere (e.g. `10deg`, `30arcmin`, default `180deg`)
- **`--res` flag**: healpix resolution (e.g. `1deg`, `2arcmin`, default `2deg`)
- **`--nside` flag**: explicit healpix nside parameter (overrides auto from fov/res)
- Uses **DiSkO's `TelescopeOperator`** to convert healpix sky model pixels into predicted visibilities via the gamma matrix (`vis = gamma @ sky_pixels`)
- Writes predicted visibilities to both **DATA** and **MODEL_DATA** columns of the output measurement set

## 0.1.0

- Initial release with basic CLI scaffold
