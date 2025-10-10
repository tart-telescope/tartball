"""CLI entry point for tartball."""

import argparse


def main():
    """Main entry point for the tartball script."""
    parser = argparse.ArgumentParser(description="Prediction code to simulate TART data")
    parser.add_argument("--ms", help="Path to measurement set")
    args = parser.parse_args()
    
    print(f"Measurement set: {args.ms}")


if __name__ == "__main__":
    main()
