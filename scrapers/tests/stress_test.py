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

# Agregar el directorio actual al path para importar sodimac.py
SCRAPERS_DIR = Path(__file__).resolve().parent.parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

try:
    from sodimac import SodimacSprint1Scraper
except ImportError as e:
    print(f"Error al importar SodimacSprint1Scraper: {e}")
    sys.exit(1)

def get_resource_usage():
    if not psutil:
        return {"cpu": 0, "ram_p": 0, "ram_gb": 0}
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    ram_gb = psutil.virtual_memory().used / (1024**3)
    return {"cpu": cpu, "ram_p": ram, "ram_gb": ram_gb}

async def monitor_resources(stop_event, stats_list):
    """Tarea en segundo plano para registrar el consumo de recursos."""
    if not psutil:
        return
    while not stop_event.is_set():
        stats_list.append(get_resource_usage())
        await asyncio.sleep(1)

async def stress_test_sodimac():
    print("=== PRUEBA DE ESTRÉS CON MONITOREO DE RECURSOS: SODIMAC (SPRINT 1) ===")
    if not psutil:
        print("⚠️ Nota: 'psutil' no está instalado o no se pudo importar. No se medirán CPU/RAM.")
    
    scraper = SodimacSprint1Scraper()
    
    # Parámetros de carga para meta de 70k/hora
    # - 25 workers para alcanzar ~1,167 productos/minuto
    queries = ["taladro", "cemento", "pintura", "madera", "climatizacion", "iluminacion", "muebles", "baño", "cocina", "herramientas"]
    workers = 5
    max_categories = 40
    max_products = 500

    print(f"Configuración de ALTO RENDIMIENTO (Meta 70k/hora):")
    print(f"   - Workers (Navegadores simultáneos): {workers}")
    print(f"   - Categorías Máximas: {max_categories}")
    print(f"   - Productos Máximos: {max_products}")
    print(f"   - Temas de búsqueda: {', '.join(queries)}")
    print("-" * 40)
    
    resource_stats = []
    stop_monitoring = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_resources(stop_monitoring, resource_stats))
    
    start_time = time.time()
    initial_res = get_resource_usage() if psutil else None
    
    try:
        print(f"Iniciando extracción con {workers} workers...")
        products = await scraper.scrape(
            queries=queries,
            max_products=max_products,
            max_category_urls=max_categories,
            headless=True,
            category_workers=workers
        )
        
        end_time = time.time()
        stop_monitoring.set()
        await monitor_task
        
        duration = end_time - start_time
        
        print("-" * 40)
        print("RESULTADOS DE LA PRUEBA DE ESTRÉS:")
        print(f"   - Tiempo total: {duration:.2f} segundos")
        print(f"   - Productos extraídos: {len(products)}")
        print(f"   - Cantidad de workers usados: {workers}")
        
        if len(products) > 0:
            rate = len(products) / (duration / 60)
            print(f"   - Velocidad promedio: {rate:.2f} productos/minuto")
            print(f"   - Proyección horaria: {rate * 60:,.0f} productos/hora")

        if psutil and resource_stats:
            # Filtrar el primer valor si es 0 (psutil a veces da 0 al inicio)
            cpu_values = [s["cpu"] for s in resource_stats if s["cpu"] > 0]
            avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
            max_cpu = max([s["cpu"] for s in resource_stats]) if resource_stats else 0
            max_ram = max([s["ram_gb"] for s in resource_stats]) if resource_stats else 0
            
            print(f"\nIMPACTO EN HARDWARE:")
            print(f"   - CPU Promedio: {avg_cpu:.1f}% | Pico: {max_cpu:.1f}%")
            print(f"   - RAM Máxima usada durante la prueba: {max_ram:.2f} GB")
            if initial_res:
                incremento_ram = max_ram - initial_res["ram_gb"]
                print(f"   - Incremento de RAM estimado por el proceso: {incremento_ram:.2f} GB")
            
        if len(products) >= max_products:
            print(f"\n✅ ÉXITO: El sistema soportó los {workers} workers")
        elif len(products) > 0:
            print(f"\n⚠️ AVISO: El scraper terminó sin alcanzar el límite de productos, pero se registraron métricas.")
        else:
            print("\n❌ FALLO: No se extrajeron productos.")
            return False
            
        print("\nPrueba de estrés FINALIZADA.")
        return True
        
    except Exception as e:
        print(f"❌ FALLO CRÍTICO: {e}")
        stop_monitoring.set()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(stress_test_sodimac())
