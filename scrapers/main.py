from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure the root directory is in sys.path for database and model imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.gold import write_gold_datasets
from core.persistence import read_json_file, write_json_atomic
from core.transformer import write_matching_preview, write_silver_dataset
from utils.run_gold_review_llm import run_gold_review_llm
from utils.loader import load_daily_prices, load_gold
from scrapers.base_scraper import ProductRecord
from scrapers.easy import EasyScraper
from scrapers.imperial import ImperialScraper
from scrapers.sodimac import SodimacScraper

DATA_DIR = Path(__file__).resolve().parent / "data"
BRONZE_DIR = DATA_DIR / "bronze"
DEFAULT_QUERIES = [
     "herramienta",   # taladros, sierras, lijadoras, destornilladores, etc.
    "pintura",       # pinturas, esmaltes, barnices, selladores
    "cemento",       # cemento, hormigon, mortero, estuco
    "madera",        # tableros, molduras, vigas, parquet
    "ceramica",      # ceramica, porcelanato, baldosa
    "fierro",        # fierro, acero, barra, perfil metalico
    "tubo",          # tuberias, canerias, pvc, cobre
    "cable",         # cables, conductores, electricidad
    "tornillo",      # tornillos, fijaciones, anclajes, tarugo
    "puerta",        # puertas, ventanas, marcos
    "aislacion",     # aislacion termica, acustica, poliestireno
    "techo",         # planchas, cubierta, zinc, pizarreno
    "adhesivo",      # adhesivos, pegamento, silicona, masilla
    "grifo",         # griferia, lavamanos, sanitario, wc
    "ladrillo",      # ladrillo, bloque, piso
]
DEFAULT_MAX_PRODUCTS = 0
FAST_CATEGORY_LIMIT = 20
ALL_STORES = ["sodimac", "easy", "imperial"]



def compute_metrics(store: str, records: list[dict]) -> dict[str, int | str]:
    return {
        "store": store,
        "total_products": len(records),
        "with_any_price": sum(
            1 for p in records
            if any([p.get("precio_normal"), p.get("precio_internet"),
                    p.get("precio_oferta"), p.get("precio_tarjeta"), p.get("precio_unitario")])
        ),
        "with_sku": sum(1 for p in records if bool(p.get("sku_store"))),
        "with_precio_tarjeta": sum(1 for p in records if p.get("precio_tarjeta") is not None),
        "with_precio_unitario": sum(1 for p in records if p.get("precio_unitario") is not None),
    }


def save_store_output(store: str, products: list[ProductRecord], today: str) -> dict[str, int | str]:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    # Cargar registro acumulativo existente
    output_path = BRONZE_DIR / f"{store}_products.json"
    existing_map: dict[str, dict] = {}
    if output_path.exists():
        try:
            existing_data = read_json_file(output_path)
            for p in existing_data.get("products", []):
                url = p.get("product_url")
                if url:
                    existing_map[url] = p
        except Exception:
            pass

    # Upsert: productos nuevos sobreescriben los existentes y marcan la fecha
    for product in products:
        record = asdict(product)
        record["fecha_ultima_revision"] = today
        existing_map[product.product_url] = record

    merged = list(existing_map.values())
    metrics = compute_metrics(store, merged)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_products": len(merged),
        "metrics": metrics,
        "products": merged,
    }
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
    today: str | None = None,
) -> dict[str, dict[str, int | str]]:
    if not today:
        today = datetime.now(timezone.utc).date().isoformat()
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

        category_hints: dict[str, str] = {}
        for product in products:
            category_url = scraper.category_hints.get(product.product_url)
            if category_url:
                category_hints[product.product_url] = category_url

        metrics = save_store_output(store_name, products, today)
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
    bronze_group.add_argument(
        "--daily-refresh",
        action="store_true",
        dest="daily_refresh",
        help="Modo diario: refresca precios via PDP para productos no visitados hoy. No corre descubrimiento.",
    )
    bronze_group.add_argument(
        "--pdp-workers",
        type=int,
        default=4,
        dest="pdp_workers",
        help="Workers paralelos para el pase de PDP en --daily-refresh (default: 4).",
    )
    bronze_group.add_argument(
        "--fast",
        action="store_true",
        help="Modo rapido: limita a 20 categorias por tienda si no se especifica otro limite.",
    )
    
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


def _make_progress_bar(store: str, total: int):
    start = time.monotonic()

    def on_progress(done: int, _total: int) -> None:
        elapsed = time.monotonic() - start
        rate = done / elapsed if elapsed > 0 else 0
        remaining = (_total - done) / rate if rate > 0 else 0
        bar_width = 28
        filled = int(bar_width * done / _total) if _total else bar_width
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = int(100 * done / _total) if _total else 100
        mins, secs = divmod(int(remaining), 60)
        eta = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        speed = f"{rate:.1f}/s"
        line = f"\r[{store}] [{bar}] {done}/{_total} ({pct}%) · {speed} · ETA {eta}   "
        print(line, end="", flush=True)
        if done >= _total:
            print()

    return on_progress


async def run_daily_refresh(
    selected_stores: list[str],
    headless: bool = True,
    pdp_workers: int = 4,
) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"\n{'='*60}\nDAILY REFRESH — {today}\n{'='*60}")

    scrapers_map = {
        "sodimac": SodimacScraper,
        "easy": EasyScraper,
        "imperial": ImperialScraper,
    }

    for store in selected_stores:
        path = BRONZE_DIR / f"{store}_products.json"
        if not path.exists():
            print(f"[{store}] Sin registro Bronze, omitiendo.")
            continue

        data = read_json_file(path)
        all_products = data.get("products", [])
        stale = [p for p in all_products if p.get("fecha_ultima_revision") != today]
        print(f"[{store}] {len(stale)} productos desactualizados / {len(all_products)} total")
        if not stale:
            print(f"[{store}] Todo actualizado, omitiendo.")
            continue

        scraper = scrapers_map[store]()
        on_progress = _make_progress_bar(store, len(stale))
        updated = await scraper.scrape_pdp_batch(stale, headless=headless, workers=pdp_workers, on_progress=on_progress)

        # Upsert en el registro
        product_map = {p["product_url"]: p for p in all_products}
        refreshed = 0
        for upd in updated:
            url = upd.get("product_url")
            if not url or url not in product_map:
                continue
            product_map[url].update({
                "precio_normal":          upd.get("precio_normal"),
                "precio_internet":        upd.get("precio_internet"),
                "precio_oferta":          upd.get("precio_oferta"),
                "precio_tarjeta":         upd.get("precio_tarjeta"),
                "precio_unitario":        upd.get("precio_unitario"),
                "unidad_medida":          upd.get("unidad_medida"),
                "precio_unitario_fuente": upd.get("precio_unitario_fuente"),
                "disponibilidad":         upd.get("disponibilidad", True),
                "fecha_ultima_revision":  today,
            })
            refreshed += 1

        merged = list(product_map.values())
        metrics = compute_metrics(store, merged)
        write_json_atomic(path, {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_products": len(merged),
            "metrics": metrics,
            "products": merged,
        })
        print(f"[{store}] {refreshed} productos refrescados. Registro: {len(merged)} total.")

    print("\nCargando precios actualizados a la BD...")
    await load_daily_prices(today)
    print("Daily refresh completado.")


async def main() -> None:
    args = parse_args()

    # --- MODO DIARIO: bypasa todo el pipeline de descubrimiento ---
    if args.daily_refresh:
        selected_stores = resolve_selected_stores(args)
        await run_daily_refresh(
            selected_stores,
            headless=not args.headful,
            pdp_workers=args.pdp_workers,
        )
        return

    if args.fast:
        if args.sodimac_max_category_urls == 0:
            args.sodimac_max_category_urls = FAST_CATEGORY_LIMIT
        if args.easy_max_category_urls == 0:
            args.easy_max_category_urls = FAST_CATEGORY_LIMIT
        if args.imperial_max_category_urls == 0:
            args.imperial_max_category_urls = FAST_CATEGORY_LIMIT

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
        today = datetime.now(timezone.utc).date().isoformat()
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
            today=today,
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
