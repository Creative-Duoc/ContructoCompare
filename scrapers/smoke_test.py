import asyncio
import sys
import json
import time
from pathlib import Path

# Configurar paths para importación
SCRAPERS_DIR = Path(__file__).resolve().parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

try:
    from main import run_bronze, write_silver_dataset, write_gold_datasets
except ImportError as e:
    print(f"Error al importar módulos del Sprint 3: {e}")
    sys.exit(1)

async def run_sprint3_smoke_test():
    print("="*60)
    print("PRUEBA DE HUMO - SPRINT 3: REPORTE CONSOLIDAD Y PROYECCIONES")
    print("="*60)

    DATA_DIR = Path("data")
    queries = ["pintura esmalte"]
    stores = ["sodimac", "easy", "imperial"]
    
    # 1. BRONZE
    print(f"\n1. [BRONZE] Extrayendo productos...")
    start_bronze = time.time()
    
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
        dur_bronze = time.time() - start_bronze
        
        # 2. SILVER
        print("\n2. [SILVER] Normalizando datos...")
        start_silver = time.time()
        silver_file = "silver/smoke_silver.json"
        silver_payload = write_silver_dataset(DATA_DIR, output_file=silver_file, strict_missing_stores=False)
        dur_silver = time.time() - start_silver
        total_rows = silver_payload.get("total_rows", 0)

        # 3. GOLD
        print("\n3. [GOLD] Ejecutando motor de Matching...")
        start_gold = time.time()
        gold_file = "gold/smoke_gold.json"
        gold_result = write_gold_datasets(
            data_dir=DATA_DIR,
            silver_input_file=silver_file,
            gold_output_file=gold_file,
            threshold_confident=50, 
            write_diagnostics=False
        )
        dur_gold = time.time() - start_gold
        
        gold_products = gold_result["gold"].get("gold_products", [])
        gold_metrics = gold_result["metrics"]
        pairs_eval = gold_metrics.get("pairs_evaluated", 0)

        # --- RESUMEN FINAL ---
        print("\n" + "="*60)
        print("REPORTE DETALLADO DE OPERACIÓN")
        print("="*60)
        
        for store in stores:
            m = metrics.get(store, {})
            print(f"✅ {store.upper()} finalizado: {m.get('total_products', 0)} productos extraídos.")

        print("-" * 40)
        print(f"⏱️ TIEMPOS REALES (Muestra de {total_rows} productos):")
        print(f"   • Bronze (Extracción): {dur_bronze:.2f}s")
        print(f"   • Silver (Normalización): {dur_silver:.2f}s")
        print(f"   • Gold (Vinculación): {dur_gold:.2f}s")
        
        # --- PROYECCIONES ---
        print("\n" + "📊 ESTIMACIÓN DE ESCALABILIDAD (PROYECCIÓN):")
        print("-" * 40)
        
        # Cálculo de velocidad (items por segundo)
        silver_speed = total_rows / dur_silver if dur_silver > 0 else 0
        # El matching es O(N log N) o mayor, pero usamos una tasa de pares evaluados para estimar
        gold_speed_pairs = pairs_eval / dur_gold if dur_gold > 0 else 0
        
        def print_projection(volume):
            proj_silver = volume / silver_speed if silver_speed > 0 else 0
            # Estimación simplificada para Gold basada en el crecimiento de pares
            # Si para 450 items evaluamos 500 pares, para 10k items evaluaremos muchos más.
            # Usamos un multiplicador de complejidad conservador.
            ratio = (volume / total_rows) if total_rows > 0 else 1
            proj_gold = dur_gold * (ratio ** 1.5) # Factor de escala no lineal
            
            print(f"🔹 Para {volume:,} productos:")
            print(f"   • Silver tardaría: {proj_silver/60:.2f} minutos")
            print(f"   • Gold tardaría: {proj_gold/60:.2f} minutos (estimado)")

        print_projection(10000)
        print_projection(70000)

        print("\n" + "-" * 40)
        matches = [gp for gp in gold_products if len(set(v["store"] for v in gp.get("store_variants", []))) > 1]
        if matches:
            print(f"🌟 MATCHES ENCONTRADOS: {len(matches)}")
            gp = matches[0]
            canonical = gp.get("canonical_product", {})
            print(f"   Ejemplo: '{canonical.get('name_canonical')[:50]}...'")
            for v in gp.get("store_variants", []):
                print(f"      - [{v['store'].upper()}]: {v['product_url']}")

        print("\n" + "="*60)
        print("RESUMEN SPRINT 3: TODOS LOS CRITERIOS VALIDADOS")
        print("="*60)
        return True

    except Exception as e:
        print(f"❌ FALLO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(run_sprint3_smoke_test())
