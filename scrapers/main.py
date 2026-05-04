from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Ensure the root directory is in sys.path for database and model imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.gold import write_gold_datasets
from core.persistence import write_json_atomic
from core.transformer import write_matching_preview, write_silver_dataset
from utils.run_gold_review_llm import run_gold_review_llm
from utils.loader import load_gold
from scrapers.base_scraper import ProductRecord
from scrapers.easy import EasyScraper
from scrapers.imperial import ImperialScraper
from scrapers.sodimac import SodimacScraper

DATA_DIR = Path("data")
BRONZE_DIR = DATA_DIR / "bronze"
DEFAULT_QUERIES = ["cemento", "taladro", "pintura", "fierro", "pvc"]
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
            if any(
                [
                    p.precio_normal,
                    p.precio_internet,
                    p.precio_oferta,
                    p.precio_tarjeta,
                    p.precio_unitario,
                ]
            )
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

    output_path = BRONZE_DIR / f"{store}_products.json"
    write_json_atomic(output_path, payload)
    return metrics


def save_store_category_hints(store: str, hints_by_product_url: dict[str, str]) -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRONZE_DIR / f"{store}_category_hints.json"
    sorted_hints = dict(sorted(hints_by_product_url.items()))
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "store": store,
        "total_hints": len(sorted_hints),
        "hints_by_product_url": sorted_hints,
    }
    write_json_atomic(output_path, payload)


def resolve_selected_stores(args: argparse.Namespace) -> list[str]:
    selected: list[str] = []

    if args.only_sodimac:
        selected.append("sodimac")
    if args.only_easy:
        selected.append("easy")
    if args.only_imperial:
        selected.append("imperial")

    if selected:
        ordered = [store for store in ALL_STORES if store in selected]
        return ordered

    if args.stores:
        seen: set[str] = set()
        ordered_stores: list[str] = []
        for store in args.stores:
            if store in seen:
                continue
            seen.add(store)
            ordered_stores.append(store)
        return ordered_stores

    return list(ALL_STORES)


async def run_bronze(
    queries: list[str],
    max_products: int,
    selected_stores: list[str],
    headless: bool,
    sodimac_max_category_urls: int,
    sodimac_category_workers: int,
    easy_max_category_urls: int,
    easy_category_workers: int,
    imperial_max_category_urls: int,
    imperial_category_workers: int,
) -> dict[str, dict[str, int | str]]:
    metrics_by_store: dict[str, dict[str, int | str]] = {}
    scrapers_to_run: list[tuple[str, object]] = []
    if "sodimac" in selected_stores:
        scrapers_to_run.append(("sodimac", SodimacScraper()))
    if "easy" in selected_stores:
        scrapers_to_run.append(("easy", EasyScraper()))
    if "imperial" in selected_stores:
        scrapers_to_run.append(("imperial", ImperialScraper()))

    for store_name, scraper in scrapers_to_run:
        scraper_queries = queries
        scrape_kwargs: dict[str, int | bool] = {
            "max_products": max_products,
            "headless": headless,
        }
        if store_name == "sodimac":
            scrape_kwargs["max_category_urls"] = sodimac_max_category_urls
            scrape_kwargs["category_workers"] = sodimac_category_workers
        elif store_name == "easy":
            scrape_kwargs["max_category_urls"] = easy_max_category_urls
            scrape_kwargs["category_workers"] = easy_category_workers
        elif store_name == "imperial":
            scrape_kwargs["max_category_urls"] = imperial_max_category_urls
            scrape_kwargs["category_workers"] = imperial_category_workers

        products = await scraper.scrape(scraper_queries, **scrape_kwargs)
        products = deduplicate(products)

        category_hints: dict[str, str] = {}
        for product in products:
            category_url = scraper.category_hints.get(product.product_url)
            if category_url:
                category_hints[product.product_url] = category_url

        metrics = save_store_output(store_name, products)
        save_store_category_hints(store_name, category_hints)
        metrics_by_store[store_name] = metrics

        # Log high-signal summary to file and terminal
        scraper.log_final_metrics(len(products), scrape_kwargs.get("category_workers", 1))

        print("=" * 60)
        print(f"Store: {store_name}")
        print(f"Products: {len(products)}")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))

    return metrics_by_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full ContructoCompare pipeline (Bronze -> Silver -> Gold -> Load).")
    
    # Global Stage Control
    stage_group = parser.add_argument_group("Stage Control")
    stage_group.add_argument("--only-bronze", action="store_true", help="Run only Bronze (scraping) stage.")
    stage_group.add_argument("--only-silver", action="store_true", help="Run only Silver (normalization) stage.")
    stage_group.add_argument("--only-gold", action="store_true", help="Run only Gold (linking) stage.")
    stage_group.add_argument("--only-llm", action="store_true", help="Run only Gold LLM (AI review) stage.")
    stage_group.add_argument("--only-load", action="store_true", help="Run only Load (database import) stage.")
    
    stage_group.add_argument("--skip-bronze", action="store_true", help="Skip Bronze stage.")
    stage_group.add_argument("--skip-silver", action="store_true", help="Skip Silver stage.")
    stage_group.add_argument("--skip-gold", action="store_true", help="Skip Gold stage.")
    stage_group.add_argument("--skip-llm", action="store_true", help="Skip Gold LLM stage.")
    stage_group.add_argument("--skip-load", action="store_true", help="Skip Load stage.")

    # Bronze Args
    bronze_group = parser.add_argument_group("Bronze (Scraping) Settings")
    bronze_group.add_argument(
        "--queries",
        nargs="+",
        default=DEFAULT_QUERIES,
        help="Queries para discovery de categorias (default: cemento taladro pintura fierro pvc)",
    )
    bronze_group.add_argument(
        "--max-products",
        "--max",
        dest="max_products",
        type=int,
        default=DEFAULT_MAX_PRODUCTS,
        help="Maximo de productos por tienda (default: 0 = sin limite)",
    )
    bronze_group.add_argument(
        "--stores",
        nargs="+",
        choices=ALL_STORES,
        help="Limita scraping Bronze a tiendas especificas. Default: todas.",
    )
    bronze_group.add_argument("--only-sodimac", action="store_true")
    bronze_group.add_argument("--only-easy", action="store_true")
    bronze_group.add_argument("--only-imperial", action="store_true")
    bronze_group.add_argument("--headful", action="store_true", help="Run visible browser.")
    
    bronze_group.add_argument("--sodimac-max-category-urls", type=int, default=0)
    bronze_group.add_argument("--sodimac-category-workers", type=int, default=4)
    bronze_group.add_argument("--easy-max-category-urls", type=int, default=0)
    bronze_group.add_argument("--easy-category-workers", type=int, default=4)
    bronze_group.add_argument("--imperial-max-category-urls", type=int, default=0)
    bronze_group.add_argument("--imperial-category-workers", type=int, default=3)

    # Silver Args
    silver_group = parser.add_argument_group("Silver (Normalization) Settings")
    silver_group.add_argument("--silver-output", default="silver/silver_products.json")
    silver_group.add_argument("--preview-matching", action="store_true")
    silver_group.add_argument("--preview-output", default="silver/silver_matching_preview.json")
    silver_group.add_argument("--preview-threshold", type=int, default=60)
    silver_group.add_argument("--preview-max-pairs", type=int, default=400)
    silver_group.add_argument("--strict-missing-stores", action="store_true")

    # Gold Args
    gold_group = parser.add_argument_group("Gold (Linking) Settings")
    gold_group.add_argument("--gold-output", default="gold/gold_products.json")
    gold_group.add_argument("--review-output", default="gold/gold_review_queue.json")
    gold_group.add_argument("--metrics-output", default="gold/gold_metrics.json")
    gold_group.add_argument("--diagnostics-output", default="gold/gold_diagnostics.json")
    gold_group.add_argument("--threshold-confident", type=int, default=90)
    gold_group.add_argument("--threshold-review", type=int, default=78)
    gold_group.add_argument("--max-review-pairs", type=int, default=0)
    gold_group.add_argument("--max-diagnostic-pairs", type=int, default=500)
    gold_group.add_argument("--strict-silver-coverage", action="store_true")
    gold_group.add_argument("--write-gold-diagnostics", action="store_true")

    # LLM Args
    llm_group = parser.add_argument_group("LLM (AI Review) Settings")
    llm_group.add_argument("--llm-model", default="gemma3:27b")
    llm_group.add_argument("--llm-ollama-url", default="http://localhost:11434/api/generate")
    llm_group.add_argument("--llm-max-items", type=int, default=500)
    llm_group.add_argument("--llm-start-index", type=int, default=0)
    llm_group.add_argument("--llm-min-confidence-accept", type=int, default=90)
    llm_group.add_argument("--llm-min-confidence-reject", type=int, default=92)
    llm_group.add_argument("--llm-min-gold-score-accept", type=int, default=90)
    llm_group.add_argument("--llm-min-gold-score-review", type=int, default=85)
    llm_group.add_argument("--llm-temperature", type=float, default=0.0)
    llm_group.add_argument("--llm-timeout-seconds", type=int, default=180)
    llm_group.add_argument("--llm-decisions-output", default="gold/gold_review_llm_decisions.json")
    llm_group.add_argument("--llm-remaining-output", default="gold/gold_review_queue_remaining.json")
    llm_group.add_argument("--llm-ledger-file", default="gold/gold_llm_decision_ledger.json")

    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    
    # Logic to determine which stages to run
    run_all = not any([args.only_bronze, args.only_silver, args.only_gold, args.only_llm, args.only_load])
    
    do_bronze = (run_all or args.only_bronze) and not args.skip_bronze
    do_silver = (run_all or args.only_silver) and not args.skip_silver
    do_gold   = (run_all or args.only_gold)   and not args.skip_gold
    do_llm    = (run_all or args.only_llm)    and not args.skip_llm
    do_load   = (run_all or args.only_load)   and not args.skip_load

    # --- 1. BRONZE ---
    if do_bronze:
        print("\n" + "="*60 + "\nSTAGE: BRONZE (SCRAPING)\n" + "="*60)
        selected_stores = resolve_selected_stores(args)
        await run_bronze(
            queries=args.queries,
            max_products=args.max_products,
            selected_stores=selected_stores,
            headless=not args.headful,
            sodimac_max_category_urls=args.sodimac_max_category_urls,
            sodimac_category_workers=args.sodimac_category_workers,
            easy_max_category_urls=args.easy_max_category_urls,
            easy_category_workers=args.easy_category_workers,
            imperial_max_category_urls=args.imperial_max_category_urls,
            imperial_category_workers=args.imperial_category_workers,
        )

    # --- 2. SILVER ---
    silver_payload = None
    if do_silver:
        print("\n" + "="*60 + "\nSTAGE: SILVER (NORMALIZATION)\n" + "="*60)
        silver_payload = write_silver_dataset(
            DATA_DIR,
            output_file=args.silver_output,
            strict_missing_stores=args.strict_missing_stores,
        )
        print(json.dumps({
            "output": str(DATA_DIR / args.silver_output),
            "total_rows": silver_payload.get("total_rows", 0),
            "coverage_complete": silver_payload.get("coverage_complete", False),
        }, indent=2))

        if args.preview_matching:
            write_matching_preview(
                DATA_DIR,
                rows=silver_payload.get("rows", []),
                threshold=args.preview_threshold,
                max_pairs=args.preview_max_pairs,
                output_file=args.preview_output,
            )

    # --- 3. GOLD ---
    gold_result = None
    if do_gold:
        print("\n" + "="*60 + "\nSTAGE: GOLD (LINKING)\n" + "="*60)
        gold_result = write_gold_datasets(
            data_dir=DATA_DIR,
            silver_input_file=args.silver_output,
            gold_output_file=args.gold_output,
            review_output_file=args.review_output,
            metrics_output_file=args.metrics_output,
            diagnostics_output_file=args.diagnostics_output,
            threshold_confident=args.threshold_confident,
            threshold_review=args.threshold_review,
            strict_silver_coverage=args.strict_silver_coverage,
            max_review_pairs=args.max_review_pairs,
            max_diagnostic_pairs=args.max_diagnostic_pairs,
            write_diagnostics=args.write_gold_diagnostics,
        )
        print(json.dumps({
            "gold_products": gold_result["gold"].get("total_gold_products", 0),
            "pending_review": gold_result["review"].get("total_pending", 0),
        }, indent=2))

    # --- 4. GOLD LLM ---
    if do_llm:
        print("\n" + "="*60 + "\nSTAGE: GOLD LLM (AI REVIEW)\n" + "="*60)
        # If we skipped gold stage in this run, we need to check if review file exists
        review_path = DATA_DIR / args.review_output
        if not review_path.exists():
            print(f"Skipping LLM: Review file not found at {review_path}")
        else:
            llm_args = argparse.Namespace(
                data_dir=str(DATA_DIR),
                review_input=args.review_output,
                decisions_output=args.llm_decisions_output,
                remaining_output=args.llm_remaining_output,
                model=args.llm_model,
                ollama_url=args.llm_ollama_url,
                max_items=args.llm_max_items,
                start_index=args.llm_start_index,
                min_llm_confidence_accept=args.llm_min_confidence_accept,
                min_llm_confidence_reject=args.llm_min_confidence_reject,
                min_gold_score_accept=args.llm_min_gold_score_accept,
                min_gold_score_review=args.llm_min_gold_score_review,
                temperature=args.llm_temperature,
                timeout_seconds=args.llm_timeout_seconds,
                silver_input=args.silver_output,
                gold_input=args.gold_output,
                gold_output=args.gold_output,
                ledger_file=args.llm_ledger_file,
                dry_run=False,
            )
            llm_result = run_gold_review_llm(llm_args)
            print(f"LLM Processed: {llm_result.get('processed_items')}, Accepted: {llm_result.get('accepted')}")

    # --- 5. LOAD ---
    if do_load:
        print("\n" + "="*60 + "\nSTAGE: LOAD (DATABASE)\n" + "="*60)
        gold_path = DATA_DIR / args.gold_output
        await load_gold(gold_path)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
