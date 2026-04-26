from __future__ import annotations

import argparse
import asyncio
from types import SimpleNamespace

from run_bronze import run_bronze_stage
from run_silver import run_silver_stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 2 pipeline: Bronze + Silver for 3 retail stores")
    parser.add_argument("--skip-bronze", action="store_true")
    parser.add_argument("--skip-silver", action="store_true")
    parser.add_argument("--preview-matching", action="store_true")
    parser.add_argument("--strict-missing-stores", action="store_true")
    parser.add_argument("--max-products", type=int, default=0)
    parser.add_argument("--stores", nargs="+", choices=["sodimac", "easy", "imperial"], default=["sodimac", "easy", "imperial"])
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--sodimac-max-category-urls", type=int, default=0)
    parser.add_argument("--sodimac-category-workers", type=int, default=4)
    parser.add_argument("--easy-max-category-urls", type=int, default=0)
    parser.add_argument("--easy-category-workers", type=int, default=4)
    parser.add_argument("--imperial-max-category-urls", type=int, default=0)
    parser.add_argument("--imperial-category-workers", type=int, default=3)
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    if not args.skip_bronze:
        bronze_args = SimpleNamespace(
            max_products=args.max_products,
            stores=args.stores,
            headful=args.headful,
            sodimac_max_category_urls=args.sodimac_max_category_urls,
            sodimac_category_workers=args.sodimac_category_workers,
            easy_max_category_urls=args.easy_max_category_urls,
            easy_category_workers=args.easy_category_workers,
            imperial_max_category_urls=args.imperial_max_category_urls,
            imperial_category_workers=args.imperial_category_workers,
        )
        await run_bronze_stage(bronze_args)

    if not args.skip_silver:
        silver_args = SimpleNamespace(
            data_dir="data",
            silver_output="silver/silver_products.json",
            preview_matching=args.preview_matching,
            only_preview_matching=False,
            preview_output="silver/silver_matching_preview.json",
            preview_threshold=60,
            preview_max_pairs=400,
            strict_missing_stores=args.strict_missing_stores,
        )
        run_silver_stage(silver_args)


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
