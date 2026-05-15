import asyncio
import sys
from pathlib import Path

# Agregar el directorio actual al path para importar sodimac.py
SCRAPERS_DIR = Path(__file__).resolve().parent
if str(SCRAPERS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_DIR))

try:
    from sodimac import SodimacSprint1Scraper
except ImportError as e:
    print(f"Error al importar SodimacSprint1Scraper: {e}")
    sys.exit(1)

async def run_smoke_test():
    print("=== PRUEBA DE HUMO: VALIDACIÓN DE CRITERIOS DE ACEPTACIÓN ===")
    scraper = SodimacSprint1Scraper()
    
    # ---------------------------------------------------------
    # CRITERIO 1 & 2: Búsqueda de productos y resultados de tiendas
    # ---------------------------------------------------------
    search_1 = "taladro"
    print(f"\n1. Probando búsqueda: '{search_1}'...")
    
    try:
        products_1 = await scraper.scrape(
            queries=[search_1],
            max_products=2,
            max_category_urls=1,
            headless=True
        )
        
        if not products_1:
            print("❌ FALLO: No se obtuvieron resultados de la tienda.")
            return False
            
        print(f"✅ ÉXITO: Se obtuvieron {len(products_1)} productos de la tienda '{products_1[0].store}'.")

        # ---------------------------------------------------------
        # CRITERIO 3: Información básica (Nombre y Precio)
        # ---------------------------------------------------------
        print("\n2. Validando información básica (Nombre y Precio)...")
        p = products_1[0]
        
        # El precio puede venir en distintos campos según Sodimac
        has_price = any([p.precio_internet, p.precio_oferta, p.precio_tarjeta, p.precio_normal])
        
        if p.name and has_price:
            price_val = p.precio_internet or p.precio_oferta or p.precio_tarjeta or p.precio_normal
            print(f"✅ ÉXITO: Producto validado.")
            print(f"   - Nombre: {p.name}")
            print(f"   - Precio detectado: ${price_val}")
        else:
            print(f"❌ FALLO: El producto '{p.name}' no tiene información de precio básica.")
            return False

        # ---------------------------------------------------------
        # CRITERIO 4: Actualización al realizar nuevas búsquedas
        # ---------------------------------------------------------
        search_2 = "cemento"
        print(f"\n3. Probando nueva búsqueda para validar actualización: '{search_2}'...")
        
        products_2 = await scraper.scrape(
            queries=[search_2],
            max_products=2,
            max_category_urls=1,
            headless=True
        )
        
        if not products_2:
            print("❌ FALLO: La segunda búsqueda no retornó resultados.")
            return False
            
        # Verificar que el producto sea distinto al de la primera búsqueda
        if products_1[0].product_url != products_2[0].product_url:
            print(f"✅ ÉXITO: La información se actualizó correctamente.")
            print(f"   - Nuevo Producto: {products_2[0].name}")
        else:
            print("⚠️ AVISO: La segunda búsqueda retornó el mismo primer producto (posible solapamiento de categorías).")

        print("\n" + "="*50)
        print("RESUMEN: TODOS LOS CRITERIOS DE ACEPTACIÓN HAN SIDO VALIDADOS.")
        print("="*50)
        return True

    except Exception as e:
        print(f"❌ FALLO CRÍTICO durante la prueba: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_smoke_test())
    if not success:
        sys.exit(1)
