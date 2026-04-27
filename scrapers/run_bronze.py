from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core.persistence import write_json_atomic
from scrapers_retail.base_scraper import ProductRecord
from scrapers_retail.easy import EasyScraper
from scrapers_retail.imperial import ImperialScraper
from scrapers_retail.sodimac import SodimacScraper

DATA_DIR = Path(__file__).resolve().parent / "data"
BRONZE_DIR = DATA_DIR / "bronze"
DEFAULT_MAX_PRODUCTS = 0
ALL_STORES = ["sodimac", "easy", "imperial"]


def deduplicate(products: Iterable[ProductRecord]) -> list[ProductRecord]:
    seen_urls: set[str] = set()
    result: list[ProductRecord] = []
    for product in products:
        if product.product_url in seen_urls:
            continue
        seen_urls.add(product.product_url)
        result.append(product)
    return result


def compute_metrics(store: str, products: list[ProductRecord]) -> dict[str, int | str]:
    return {
        "store": store,
        "total_products": len(products),
        "with_any_price": sum(
            1
            for p in products
            if any([p.precio_normal, p.precio_internet, p.precio_oferta, p.precio_tarjeta, p.precio_unitario])
        ),
        "with_sku": sum(1 for p in products if bool(p.sku_store)),
        "with_precio_tarjeta": sum(1 for p in products if p.precio_tarjeta is not None),
        "with_precio_unitario": sum(1 for p in products if p.precio_unitario is not None),
    }


def save_store_output(store: str, products: list[ProductRecord]) -> dict[str, int | str]:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(store, products)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_products": len(products),
        "metrics": metrics,
        "products": [asdict(product) for product in products],
    }
    write_json_atomic(BRONZE_DIR / f"{store}_products.json", payload)
    return metrics


def save_store_category_hints(store: str, hints_by_product_url: dict[str, str]) -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "store": store,
        "total_hints": len(hints_by_product_url),
        "hints_by_product_url": dict(sorted(hints_by_product_url.items())),
    }
    write_json_atomic(BRONZE_DIR / f"{store}_category_hints.json", payload)


def resolve_selected_stores(args: argparse.Namespace) -> list[str]:
    if args.stores:
        return args.stores
    return list(ALL_STORES)


async def run_bronze_stage(args: argparse.Namespace) -> dict[str, dict[str, int | str]]:
    metrics_by_store: dict[str, dict[str, int | str]] = {}
    scrapers: list[tuple[str, object]] = []

    if "sodimac" in args.stores:
        scrapers.append(("sodimac", SodimacScraper()))
    if "easy" in args.stores:
        scrapers.append(("easy", EasyScraper()))
    if "imperial" in args.stores:
        scrapers.append(("imperial", ImperialScraper()))

    for store_name, scraper in scrapers:
        scrape_kwargs: dict[str, int | bool] = {
            "max_products": args.max_products,
            "headless": not args.headful,
        }
        if store_name == "sodimac":
            scrape_kwargs["max_category_urls"] = args.sodimac_max_category_urls
            scrape_kwargs["category_workers"] = args.sodimac_category_workers
        elif store_name == "easy":
            scrape_kwargs["max_category_urls"] = args.easy_max_category_urls
            scrape_kwargs["category_workers"] = args.easy_category_workers
        else:
            scrape_kwargs["max_category_urls"] = args.imperial_max_category_urls
            scrape_kwargs["category_workers"] = args.imperial_category_workers

        products = await scraper.scrape([], **scrape_kwargs)
        products = deduplicate(products)

        category_hints: dict[str, str] = {}
        for product in products:
            category_url = scraper.category_hints.get(product.product_url)
            if category_url:
                category_hints[product.product_url] = category_url

        metrics = save_store_output(store_name, products)
        save_store_category_hints(store_name, category_hints)
        metrics_by_store[store_name] = metrics

        print("=" * 60)
        print(f"Store: {store_name}")
        print(f"Products: {len(products)}")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))

    return metrics_by_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 2 Bronze: scrape 3 retail stores")
    parser.add_argument("--max-products", "--max", dest="max_products", type=int, default=DEFAULT_MAX_PRODUCTS)
    parser.add_argument("--stores", nargs="+", choices=ALL_STORES, default=ALL_STORES)
    parser.add_argument("--headful", action="store_true")

    parser.add_argument("--sodimac-max-category-urls", type=int, default=0)
    parser.add_argument("--sodimac-category-workers", type=int, default=4)
    parser.add_argument("--easy-max-category-urls", type=int, default=0)
    parser.add_argument("--easy-category-workers", type=int, default=4)
    parser.add_argument("--imperial-max-category-urls", type=int, default=0)
    parser.add_argument("--imperial-category-workers", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.stores = resolve_selected_stores(args)
    asyncio.run(run_bronze_stage(args))


if __name__ == "__main__":
    main()
