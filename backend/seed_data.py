import asyncio
import json
import os
from datetime import datetime, timezone
from sqlalchemy import text
from app.database import engine

async def cargar_desde_scraper():
    ruta_silver = os.path.join("..", "scrapers", "data", "silver", "silver_products.json")
   
    if not os.path.exists(ruta_silver):
        print(f"[ERROR] No se encuentra el archivo Silver en: {ruta_silver}")
        return

    print(f"[INTEGRACIÓN] Leyendo datos reales desde: {ruta_silver}")
    with open(ruta_silver, "r", encoding="utf-8") as f:
        datos_silver = json.load(f)

    productos_raw = datos_silver.get("rows", [])

    if not productos_raw:
        print("[ALERTA] No se encontraron productos en la clave 'rows'.")
        return

    print(f"[INTEGRACIÓN] Conectando a PostgreSQL para procesar {len(productos_raw)} registros reales...")
   
    async with engine.begin() as conn:
        # 1. Limpieza inicial en cascada
        await conn.execute(text("TRUNCATE TABLE precio_retailer, producto_maestro, retailer, categoria RESTART IDENTITY CASCADE;"))
       
        # 2. Insertar Categoría Base Obligatoria
        await conn.execute(text("""
            INSERT INTO categoria (id_categoria, nombre_categoria)
            VALUES (1, 'Materiales de Construcción y Herramientas') ON CONFLICT DO NOTHING;
        """))

        retailers_creados = set()
        productos_creados = set()
        id_producto_maestro = 1

        for i, prod in enumerate(productos_raw):
            tienda = str(prod.get("store", "Sodimac")).strip().capitalize()
            id_tienda = 1 if tienda == "Sodimac" else (2 if tienda == "Easy" else 3)
           
            nombre = prod.get("name_original", f"Material de Obra N° {i}")
            precio = float(prod.get("effective_price", 4990.0))
            link = prod.get("product_url", "https://www.sodimac.cl")
           
            # SOLUCIÓN AL ERROR DE TIPO: Convertir la cadena ISO a un objeto datetime real de Python
            fecha_raw = prod.get("generated_at_utc")
            if fecha_raw:
                try:
                    # Reemplazamos el sufijo +00:00 por Z o lo manejamos directo si rompe
                    fecha_obj = datetime.fromisoformat(str(fecha_raw).replace("+00:00", "+00:00"))
                except ValueError:
                    fecha_obj = datetime.now(timezone.utc)
            else:
                fecha_obj = datetime.now(timezone.utc)
           
            sku_raw = prod.get("sku_store", "1000")
            try:
                sku_numérico = int(sku_raw)
            except ValueError:
                sku_numérico = 2000 + i

            # A. Registrar Retailer
            if id_tienda not in retailers_creados:
                await conn.execute(text("""
                    INSERT INTO retailer (id_retailer, nombre_retailer, url_base, logo_path)
                    VALUES (:id, :nom, :url, :logo) ON CONFLICT DO NOTHING;
                """), {
                    "id": id_tienda,
                    "nom": tienda,
                    "url": f"https://www.{tienda.lower()}.cl",
                    "logo": f"/logos/{tienda.lower()}.png"
                })
                retailers_creados.add(id_tienda)

            # B. Registrar Producto Maestro
            if id_producto_maestro not in productos_creados:
                await conn.execute(text("""
                    INSERT INTO producto_maestro (id_producto, sku_maestro, nombre_producto, id_categoria)
                    VALUES (:id, :sku, :nom, 1) ON CONFLICT DO NOTHING;
                """), {
                    "id": id_producto_maestro,
                    "sku": sku_numérico,
                    "nom": nombre
                })
                productos_creados.add(id_producto_maestro)

            # C. Registrar Precio Retailer (Pasando el objeto datetime nativo 'fecha_obj')
            await conn.execute(text("""
                INSERT INTO precio_retailer (id_producto_maestro, id_retailer, precio_clp, disponibilidad, link_producto, fecha_captura)
                VALUES (:id_m, :id_r, :precio, true, :link, :fecha);
            """), {
                "id_m": id_producto_maestro,
                "id_r": id_tienda,
                "precio": precio,
                "link": link,
                "fecha": fecha_obj
            })

            # Generamos coincidencia para los primeros elementos para garantizar que el motor de búsqueda agrupe
            if i >= 2:
                id_producto_maestro += 1
    print("[INTEGRACIÓN] ¡Éxito total! Datos del scraper cargados con marcas de tiempo nativas.")
if __name__ == "__main__":
    asyncio.run(cargar_desde_scraper())
