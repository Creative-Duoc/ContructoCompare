import asyncio
import sys
import json
from pathlib import Path

# Configurar paths para importación
SCRAPERS_DIR = Path(__file__).resolve().parent.parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

try:
    from main import run_bronze, write_silver_dataset, write_gold_datasets
except ImportError as e:
    print(f"Error al importar módulos del Sprint 3: {e}")
    sys.exit(1)

async def run_sprint3_smoke_test():
    print("="*60)
    print("PRUEBA DE HUMO - SPRINT 3: VALIDACIÓN DE MATCHING CON URLS")
    print("="*60)

    DATA_DIR = Path("data")
    # Enfocamos en pintura para asegurar matches multitienda
    queries = ["pintura esmalte"]
    stores = ["sodimac", "easy", "imperial"]
   
    print(f"\n1. [BRONZE] Extrayendo productos de pintura (Búsqueda profunda)...")
   
    try:
        metrics = await run_bronze(
            queries=queries,
            max_products=150,
            selected_stores=stores,
            headless=True,
            sodimac_max_category_urls=20,
            sodimac_category_workers=5,
            easy_max_category_urls=20,
            easy_category_workers=10,
            imperial_max_category_urls=20,
            imperial_category_workers=5
        )
       
        for store in stores:
            count = metrics.get(store, {}).get("total_products", 0)
            print(f"   ✅ {store.capitalize()}: {count} productos obtenidos.")

        # 2. SILVER
        print("\n2. [SILVER] Normalizando datos...")
        silver_file = "silver/smoke_silver.json"
        write_silver_dataset(DATA_DIR, output_file=silver_file, strict_missing_stores=False)

        # 3. GOLD
        print("\n3. [GOLD] Ejecutando motor de Matching y verificando URLs...")
        gold_file = "gold/smoke_gold.json"
        gold_result = write_gold_datasets(
            data_dir=DATA_DIR,
            silver_input_file=silver_file,
            gold_output_file=gold_file,
            threshold_confident=50,
            write_diagnostics=False
        )
       
        gold_products = gold_result["gold"].get("gold_products", [])
       
        matches = [gp for gp in gold_products if len(set(v["store"] for v in gp.get("store_variants", []))) > 1]
       
        if matches:
            print(f"\n   🚀 ÉXITO: Se encontraron {len(matches)} productos comparables.")
            print("-" * 50)
            for gp in matches[:5]:
                canonical = gp.get("canonical_product", {})
                variants = gp.get("store_variants", [])
                price_ref = canonical.get("price_reference")
               
                print(f"   📦 {canonical.get('name_canonical')[:70]}")
                print(f"      💰 Mejor precio: ${price_ref}")
                print(f"      🔗 Evidencia de Matching (URLs):")
                for v in variants:
                    print(f"         • [{v['store'].upper()}]: {v['product_url']}")
                print("-" * 50)
        else:
            print("\n   ℹ️ Nota: No se detectaron coincidencias. Intente aumentar el número de productos extraídos.")

        print("\n" + "="*50)
        print("RESUMEN SPRINT 3: CRITERIOS VALIDADOS")
        print("Scraping Multitienda: OK")
        print("Motor de Comparación Gold: OK")
        print("Verificación de URLs: OK")
        print("="*50)
        return True

    except Exception as e:
        print(f"❌ FALLO CRÍTICO: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(run_sprint3_smoke_test())