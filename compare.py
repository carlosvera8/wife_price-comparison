#!/usr/bin/env python3
"""
compare.py — Household product price comparison CLI

Usage:
    python compare.py "paper towels" --zip 19103
    python compare.py "laundry detergent" --zip 19103 --retailers walmart target
    python compare.py "paper towels" --zip 19103 --mock
"""
import argparse
import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="compare",
        description="Compare household product prices across retailers by ZIP code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python compare.py "paper towels" --zip 19103\n'
            '  python compare.py "laundry detergent" --zip 10001 --retailers walmart target\n'
            '  python compare.py "paper towels" --zip 19103 --mock\n'
        ),
    )

    parser.add_argument(
        "product",
        help='Product to search for (e.g. "paper towels", "laundry detergent")',
    )
    parser.add_argument(
        "--zip",
        required=True,
        metavar="ZIP_CODE",
        help="ZIP code for local store pricing",
    )
    parser.add_argument(
        "--retailers",
        nargs="+",
        metavar="RETAILER",
        help=(
            "Filter to specific retailers by name "
            "(e.g. walmart, target, costco, 'giant food'). "
            "Default: show all results."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=3,
        metavar="N",
        help="Max results to show (per retailer when --retailers is set, total otherwise). Default: 3",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use built-in mock data instead of calling the API (for development/testing)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed debug logs",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    from orchestrator import run_comparison

    asyncio.run(
        run_comparison(
            query=args.product,
            zip_code=args.zip,
            retailer_filter=args.retailers,
            max_results=args.max_results,
            mock=args.mock,
        )
    )


if __name__ == "__main__":
    main()
