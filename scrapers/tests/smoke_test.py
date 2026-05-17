import asyncio
import sys
from pathlib import Path

# Configurar paths para importación
SCRAPERS_DIR = Path(__file__).resolve().parent.parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

try:
    from scrapers_retail.sodimac import SodimacScraper
    from scrapers_retail.easy import EasyScraper
    from scrapers_retail.imperial import ImperialScraper
except ImportError as e:
    print(f"Error al importar los scrapers del Sprint 2: {e}")
    sys.exit(1)

async def test_store_with_retries(name, scraper, queries):
    print(f"\n--- Probando tienda: {name.upper()} ---")
    
    for query in queries:
        print(f"Intentando con búsqueda: '{query}' (revisando hasta 3 categorías)...")
        try:
            # max_category_urls=3 permite que si la primera categoría está vacía, pase a la siguiente automáticamente
            products = await scraper.scrape([query], max_products=1, max_category_urls=3, headless=True)
            
            if products:
                p = products[0]
                # Validar Nombre y Precio
                has_price = any([p.precio_internet, p.precio_oferta, p.precio_tarjeta, p.precio_normal])
                
                if p.name and has_price and p.store == name.lower():
                    price_val = p.precio_internet or p.precio_oferta or p.precio_tarjeta or p.precio_normal
                    print(f"✅ ÉXITO con '{query}': {name} validado.")
                    print(f"   - Producto: {p.name}")
                    print(f"   - Precio: ${price_val}")
                    print(f"   - SKU: {p.sku_store}")
                    return True
                else:
                    print(f"⚠️ AVISO: {name} retornó datos incompletos para '{query}'. Reintentando con otra búsqueda...")
            else:
                print(f"⚠️ AVISO: No se encontraron productos para '{query}' en {name}. Pasando a la siguiente opción...")
                
        except Exception as e:
            print(f"❌ ERROR durante el intento con '{query}': {e}")
            # Continuamos al siguiente query si hay error
            continue
            
    print(f"❌ FALLO DEFINITIVO: {name} no pudo validar ningún producto tras varios intentos.")
    return False

async def run_sprint2_smoke_test():
    print("="*60)
    print("PRUEBA DE HUMO - SPRINT 2: VALIDACIÓN RESILIENTE")
    print("="*60)
    
    # Lista de queries para reintentos en caso de que una categoría falle o esté vacía
    test_queries = ["taladro", "pintura", "cemento", "escalera"]
    
    stores = [
        ("sodimac", SodimacScraper()),
        ("easy", EasyScraper()),
        ("imperial", ImperialScraper())
    ]
    
    results = {}
    for name, scraper in stores:
        results[name] = await test_store_with_retries(name, scraper, test_queries)
        print("-" * 40)
    
    print("\n" + "="*30)
    print("RESUMEN SPRINT 2")
    print("="*30)
    all_passed = True
    for name, passed in results.items():
        status = "PASSED ✅" if passed else "FAILED ❌"
        print(f"{name.capitalize()}: {status}")
        if not passed:
            all_passed = False
            
    if all_passed:
        print("\nCONCLUSIÓN: Todos los criterios de aceptación del Sprint 2 han sido validados con éxito.")
    else:
        print("\nCONCLUSIÓN: Se detectaron fallos persistentes en algunos scrapers.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_sprint2_smoke_test())
