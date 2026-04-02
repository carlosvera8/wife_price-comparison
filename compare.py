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
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _validate_env() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key:\n\n"
            "  cp .env.example .env\n"
        )
        return False
    return True


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
            "Limit to specific retailer IDs. "
            "Available: walmart, target, giant_food. "
            "Default: all enabled retailers."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=3,
        metavar="N",
        help="Max results per retailer (default: 3)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use built-in mock data instead of scraping (for development/testing)",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show the browser window while scraping (useful for debugging)",
    )

    args = parser.parse_args()

    if args.headful:
        os.environ["PLAYWRIGHT_HEADLESS"] = "false"

    if not args.mock and not _validate_env():
        sys.exit(1)

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
