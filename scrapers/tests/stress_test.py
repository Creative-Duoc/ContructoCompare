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
SCRAPERS_DIR = Path(__file__).resolve().parent.parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

# Asegurar carpetas
(SCRAPERS_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)

try:
    from scrapers_retail.sodimac import SodimacScraper
    from scrapers_retail.easy import EasyScraper
    from scrapers_retail.imperial import ImperialScraper
except ImportError as e:
    print(f"Error al importar scrapers: {e}")
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

async def run_stress_serial():
    print("="*60)
    print("PRUEBA DE ESTRÉS - SPRINT 2: FLUJO SERIAL (TIENDA POR TIENDA)")
    print("="*60)
    
    stores_to_run = [
        ("sodimac", SodimacScraper()),
        ("easy", EasyScraper()),
        ("imperial", ImperialScraper())
    ]
    
    queries = ["taladro", "pintura", "cemento"]
    workers = 15
    max_prod = 300
    
    total_products = 0
    start_time = time.time()
    all_stats = []
    store_results = []

    for name, scraper in stores_to_run:
        print(f"\n🚀 Iniciando extracción de {name.upper()}...")
        stop_monitoring = asyncio.Event()
        store_stats = []
        monitor_task = asyncio.create_task(monitor_resources(stop_monitoring, store_stats))
        
        store_start = time.time()
        try:
            if name == "imperial":
                products = await scraper.scrape(queries, max_products=max_prod, category_workers=workers, fallback_pdp=False)
            else:
                products = await scraper.scrape(queries, max_products=max_prod, category_workers=workers)
            
            store_duration = time.time() - store_start
            count = len(products)
            total_products += count
            
            speed = (count / (store_duration / 60)) if store_duration > 0 else 0
            store_results.append({
                "name": name.upper(),
                "duration": store_duration,
                "count": count,
                "speed": speed
            })
            
            print(f"✅ {name.upper()} finalizado: {count} productos en {store_duration:.2f}s")
                
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
            store_results.append({
                "name": name.upper(),
                "duration": 0,
                "count": 0,
                "speed": 0,
                "error": str(e)
            })
        
        stop_monitoring.set()
        await monitor_task
        all_stats.extend(store_stats)

    total_duration = time.time() - start_time
    
    print("\n" + "="*50)
    print("RESUMEN DE RESULTADOS FINALES")
    print("="*50)
    print(f"1. Tiempo Total: {total_duration:.2f} segundos")
    
    if total_duration > 0:
        avg_speed = total_products / (total_duration / 60)
        print(f"2. Velocidad Promedio Combinada: {avg_speed:.2f} productos/minuto")
        print(f"3. Proyección Horaria: {avg_speed * 60:,.0f} productos/hora")
    
    print("\n4. Velocidad Promedio por Tienda:")
    for res in store_results:
        error_msg = f" (Error: {res['error']})" if "error" in res else ""
        print(f"   - {res['name']}: {res['speed']:.2f} prod/min ({res['count']} productos en {res['duration']:.2f}s){error_msg}")

    if psutil and all_stats:
        cpu_values = [s["cpu"] for s in all_stats if s["cpu"] > 0]
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        max_cpu = max(s["cpu"] for s in all_stats) if all_stats else 0
        max_ram = max(s["ram_gb"] for s in all_stats) if all_stats else 0
        print(f"\nMONITOREO HARDWARE (ACUMULADO):")
        print(f"   CPU Promedio: {avg_cpu:.1f}% | Pico: {max_cpu:.1f}%")
        print(f"   RAM Máxima: {max_ram:.2f} GB")

    print("\n" + "="*50)
    print("Prueba de estrés multitienda FINALIZADA.")

if __name__ == "__main__":
    asyncio.run(run_stress_serial())
