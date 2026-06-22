"""CLI entry point for tartball."""
# Copyright (c) 2025-2026 Timothy C.A. Molteno

import argparse
import logging
import sys

from .ms import model_to_ms


def main():
    """Main entry point for the tartball script."""
    parser = argparse.ArgumentParser(
        description="Prediction code to simulate TART data using DiSkO healpix telescope operator"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Path to sky model JSON file (az/el sources with fluxes)",
    )
    parser.add_argument(
        "--ms",
        default="tartball.ms",
        help="Output measurement set name",
    )
    parser.add_argument(
        "--api",
        default=None,
        help="TART telescope API URL for info and antenna positions",
    )
    parser.add_argument(
        "--info",
        default=None,
        help="Path to JSON telescope info file (alternative to --api)",
    )
    parser.add_argument(
        "--antenna-positions",
        default=None,
        help="Path to JSON antenna positions file (alternative to --api)",
    )
    parser.add_argument(
        "--gains",
        default=None,
        help="Path to JSON calibration gains file (optional; unity gains if omitted)",
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

    if not args.model:
        parser.print_help()
        sys.exit(1)

    if args.api is None and (args.info is None or args.antenna_positions is None):
        parser.error(
            "Either --api or both --info and --antenna-positions must be provided."
        )

    model_to_ms(
        model_path=args.model,
        ms_name=args.ms,
        api_url=args.api,
        info_path=args.info,
        ant_pos_path=args.antenna_positions,
        gains_path=args.gains,
        fov_str=args.fov,
        res_str=args.res,
        nside=args.nside,
        clobber=args.clobber,
    )


if __name__ == "__main__":
    main()
