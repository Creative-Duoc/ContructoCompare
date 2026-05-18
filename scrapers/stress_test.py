import asyncio
import sys
import time
import os
from pathlib import Path

# Intentar importar psutil para métricas de hardware
try:
    import psutil
except ImportError:
    psutil = None

# Configurar paths
SCRAPERS_DIR = Path(__file__).resolve().parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

# Asegurar carpetas
(SCRAPERS_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)

try:
    from main import run_bronze, write_silver_dataset, write_gold_datasets
except ImportError as e:
    print(f"Error al importar módulos del Sprint 3: {e}")
    sys.exit(1)

def get_resource_usage():
    if not psutil: return {"cpu": 0, "ram_gb": 0}
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "ram_gb": psutil.virtual_memory().used / (1024**3)
    }

async def monitor_resources(stop_event, stats_list):
    if not psutil: return
    while not stop_event.is_set():
        stats_list.append(get_resource_usage())
        await asyncio.sleep(1)

async def run_sprint3_stress():
    print("="*60)
    print("PRUEBA DE ESTRÉS FINAL - SPRINT 3: PIPELINE COMPLETO")
    print("="*60)
    
    DATA_DIR = Path("data")
    queries = ["pintura esmalte", "esmalte al agua", "oleo brillante", "pintura latex", "esmalte sintetico"]
    workers = 10 
    max_prod_per_store = 500
    
    all_stats = []
    store_timings = []
    total_products = 0
    
    # 1. ETAPA BRONZE
    print("\n--- ETAPA 1: BRONZE (Extracción Masiva Serial) ---")
    start_pipeline = time.time()
    
    for store in ["sodimac", "easy", "imperial"]:
        print(f"🚀 Extrayendo {store.upper()}...")
        stop_monitoring = asyncio.Event()
        store_stats = []
        monitor_task = asyncio.create_task(monitor_resources(stop_monitoring, store_stats))
        
        t0 = time.time()
        try:
            m = await run_bronze(
                queries=queries,
                max_products=max_prod_per_store,
                selected_stores=[store],
                headless=True,
                sodimac_max_category_urls=10,
                sodimac_category_workers=workers,
                easy_max_category_urls=10,
                easy_category_workers=workers,
                imperial_max_category_urls=10,
                imperial_category_workers=workers
            )
            dur = time.time() - t0
            count = m.get(store, {}).get("total_products", 0)
            total_products += count
            
            speed = (count / (dur / 60)) if dur > 0 else 0
            store_timings.append({
                "name": store.upper(),
                "duration": dur,
                "count": count,
                "speed": speed
            })
            print(f"✅ {store.upper()} finalizado: {count} productos en {dur:.2f}s")
        except Exception as e:
            print(f"❌ Error en {store}: {e}")
            store_timings.append({"name": store.upper(), "duration": 0, "count": 0, "speed": 0, "error": str(e)})
        
        stop_monitoring.set()
        await monitor_task
        all_stats.extend(store_stats)

    # 2. ETAPA SILVER
    print("\n--- ETAPA 2: SILVER (Normalización) ---")
    t0_silver = time.time()
    silver_payload = write_silver_dataset(DATA_DIR, output_file="silver/stress_silver.json", strict_missing_stores=False)
    dur_silver = time.time() - t0_silver
    total_silver = silver_payload.get("total_rows", 0)
    print(f"✅ Silver procesado en {dur_silver:.2f}s")

    # 3. ETAPA GOLD
    print("\n--- ETAPA 3: GOLD (Matching) ---")
    t0_gold = time.time()
    gold_res = write_gold_datasets(
        data_dir=DATA_DIR,
        silver_input_file="silver/stress_silver.json",
        gold_output_file="gold/stress_gold.json",
        threshold_confident=50,
        write_diagnostics=False
    )
    dur_gold = time.time() - t0_gold
    total_matches = gold_res["gold"].get("total_gold_products", 0)
    print(f"✅ Gold procesado en {dur_gold:.2f}s. Productos Maestros: {total_matches}")

    total_duration = time.time() - start_pipeline

    # --- INFORME FINAL ---
    print("\n" + "="*55)
    print("REPORTE CONSOLIDADO DE ESTRÉS - SPRINT 3")
    print("="*55)
    print(f"1. Tiempo Total Pipeline: {total_duration:.2f} segundos")
    
    if total_duration > 0:
        avg_speed = total_products / (total_duration / 60)
        print(f"2. Velocidad Promedio Combinada: {avg_speed:.2f} productos/minuto")
        print(f"3. Proyección Horaria (Actual): {avg_speed * 60:,.0f} productos/hora")
    
    print("\n4. Desglose de Extracción (Bronze):")
    for res in store_timings:
        err = f" (Error: {res['error']})" if "error" in res else ""
        print(f"   • {res['name']}: {res['speed']:.2f} prod/min ({res['count']} prod en {res['duration']:.2f}s){err}")

    print(f"\n5. Rendimiento Procesamiento Interno:")
    print(f"   • Normalización (Silver): {dur_silver:.2f}s ({total_silver} items)")
    print(f"   • Vinculación (Gold): {dur_gold:.2f}s ({total_matches} matches)")

    # --- PROYECCIONES DE ESCALABILIDAD ---
    print("\n" + "📊 PROYECCIÓN DE ESCALABILIDAD (Estimación):")
    print("-" * 45)
    def print_proj(volume):
        # Silver es lineal O(N)
        speed_s = total_silver / dur_silver if dur_silver > 0 else 1
        p_silver = volume / speed_s
        # Gold es cuadrático/logarítmico O(N log N o N^2) dependiendo del motor
        # Usamos un factor de escala moderado para ser realistas
        ratio = (volume / total_silver) if total_silver > 0 else 1
        p_gold = dur_gold * (ratio ** 1.3) 
        
        print(f"🔹 Para {volume:,} productos:")
        print(f"   - Silver: {p_silver/60:.2f} min | Gold: {p_gold/60:.2f} min")

    print_proj(10000)
    print_proj(70000)

    if psutil and all_stats:
        avg_cpu = sum(s["cpu"] for s in all_stats if s["cpu"] > 0) / len(all_stats)
        max_cpu = max([s["cpu"] for s in all_stats])
        max_ram = max([s["ram_gb"] for s in all_stats])
        print(f"\n6. Impacto en Hardware:")
        print(f"   • CPU Promedio: {avg_cpu:.1f}% | Pico Máximo: {max_cpu:.1f}%")
        print(f"   • RAM Máxima usada: {max_ram:.2f} GB")

    print("\n" + "="*55)
    print("FIN DEL REPORTE - PIPELINE SPRINT 3 VALIDADO")
    print("="*55)

if __name__ == "__main__":
    asyncio.run(run_sprint3_stress())
