"""
Lee silver_products.json y carga los datos a la base de datos.
Versión Multi-Retailer (Sodimac, Easy, Imperial) con procesamiento por lotes (Two-Pass).
"""
from __future__ import annotations

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

# Permite ejecutar desde cualquier lugar dentro del proyecto
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.future import select
from sqlalchemy import func

from backend.app.database import SessionLocal
from backend.app.models.inventory import Categoria, PrecioRetailer, ProductoMaestro, Retailer

# Configuración de archivos
DEFAULT_SILVER_JSON = ROOT_DIR / "scrapers" / "data" / "silver" / "silver_products.json"

RETAILER_METADATA = {
    "sodimac": {"name": "Sodimac", "url": "https://www.sodimac.cl", "logo": "logos/sodimac.png"},
    "easy": {"name": "Easy", "url": "https://www.easy.cl", "logo": "logos/easy.png"},
    "imperial": {"name": "Imperial", "url": "https://www.imperial.cl", "logo": "logos/imperial.png"}
}

DEFAULT_CATEGORY = "General"

def clean_sku_to_int(sku_str: str) -> int | None:
    """Extrae solo los números de un SKU para cumplir con el tipo Integer de la BD."""
    digits = re.sub(r"\D", "", str(sku_str))
    return int(digits) if digits else None

async def get_or_create_categoria(session, nombre: str) -> Categoria:
    nombre = nombre or DEFAULT_CATEGORY
    result = await session.execute(select(Categoria).where(Categoria.nombre_categoria == nombre))
    categoria = result.scalars().first()
    if not categoria:
        categoria = Categoria(nombre_categoria=nombre)
        session.add(categoria)
        await session.flush()
        print(f"  [+] Categoria creada: {nombre}")
    return categoria

async def get_or_create_retailer(session, store_key: str) -> Retailer:
    meta = RETAILER_METADATA.get(store_key.lower(), {"name": store_key.capitalize(), "url": "", "logo": ""})
    result = await session.execute(select(Retailer).where(Retailer.nombre_retailer == meta["name"]))
    retailer = result.scalars().first()
    if not retailer:
        retailer = Retailer(nombre_retailer=meta["name"], url_base=meta["url"], logo_path=meta["logo"])
        session.add(retailer)
        await session.flush()
        print(f"  [+] Retailer creado: {meta['name']}")
    return retailer

async def load_silver(json_path: Path = DEFAULT_SILVER_JSON) -> None:
    if not json_path.exists():
        print(f"Error: No se encuentra el archivo Silver en {json_path}")
        return

    print(f"Leyendo archivo Silver: {json_path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    total_rows = len(rows)
    print(f"Productos encontrados en Silver: {total_rows}")

    async with SessionLocal() as session:
        async with session.begin():
            # --- 1. PREPARACIÓN Y CACHÉ ---
            retailer_map = {}
            category_map = {}
            
            print("Cargando caché de productos y precios actuales...")
            # Caché de productos (SKU_MAESTRO -> ID)
            res_prod = await session.execute(select(ProductoMaestro.sku_maestro, ProductoMaestro.id_producto))
            producto_cache = {sku: pid for sku, pid in res_prod.all()}

            # Caché de precios (ID_PROD, ID_RETAIL -> PRECIO)
            subq = select(
                PrecioRetailer.id_producto_maestro, PrecioRetailer.id_retailer,
                func.max(PrecioRetailer.fecha_captura).label("max_fecha")
            ).group_by(PrecioRetailer.id_producto_maestro, PrecioRetailer.id_retailer).subquery()

            res_prices = await session.execute(
                select(PrecioRetailer.id_producto_maestro, PrecioRetailer.id_retailer, PrecioRetailer.precio_clp)
                .join(subq, (PrecioRetailer.id_producto_maestro == subq.c.id_producto_maestro) & 
                            (PrecioRetailer.id_retailer == subq.c.id_retailer) &
                            (PrecioRetailer.fecha_captura == subq.c.max_fecha))
            )
            precio_cache = {(r.id_producto_maestro, r.id_retailer): float(r.precio_clp) for r in res_prices.all()}
            print(f"Caché cargada: {len(producto_cache)} productos y {len(precio_cache)} precios.")

            # --- 2. PASADA 1: IDENTIFICAR PRODUCTOS NUEVOS ---
            nuevos_productos_objs = {}
            skipped = 0

            for row in rows:
                sku_raw = row.get("sku_store")
                sku_int = clean_sku_to_int(sku_raw)
                store_key = row.get("store")
                
                if sku_int is None or not store_key:
                    skipped += 1
                    continue
                
                # Para el Sprint 2, usamos el SKU numérico directamente.
                # Si hay colisión de SKUs entre tiendas, compartirán el mismo ProductoMaestro.
                if sku_int not in producto_cache and sku_int not in nuevos_productos_objs:
                    cat_name = row.get("category_normalized") or DEFAULT_CATEGORY
                    if cat_name not in category_map:
                        category_map[cat_name] = await get_or_create_categoria(session, cat_name)
                    
                    nuevos_productos_objs[sku_int] = ProductoMaestro(
                        sku_maestro=sku_int,
                        nombre_producto=row.get("name_original"),
                        id_categoria=category_map[cat_name].id_categoria
                    )

            if nuevos_productos_objs:
                print(f"Insertando {len(nuevos_productos_objs)} productos nuevos en lote...")
                session.add_all(nuevos_productos_objs.values())
                await session.flush()
                for sku, obj in nuevos_productos_objs.items():
                    producto_cache[sku] = obj.id_producto

            # --- 3. PASADA 2: PROCESAR PRECIOS ---
            precios_a_insertar = []
            unchanged_prices = 0
            new_prices_count = 0
            
            for i, row in enumerate(rows, 1):
                sku_int = clean_sku_to_int(row.get("sku_store"))
                store_key = row.get("store")
                price = row.get("effective_price")
                
                if sku_int is None or not store_key or price is None:
                    continue

                id_producto = producto_cache.get(sku_int)
                
                if store_key not in retailer_map:
                    retailer_map[store_key] = await get_or_create_retailer(session, store_key)
                retailer = retailer_map[store_key]

                ultimo_precio = precio_cache.get((id_producto, retailer.id_retailer))
                if ultimo_precio is not None and float(ultimo_precio) == float(price):
                    unchanged_prices += 1
                    continue

                precios_a_insertar.append(PrecioRetailer(
                    id_producto_maestro=id_producto,
                    id_retailer=retailer.id_retailer,
                    precio_clp=price,
                    disponibilidad=True,
                    link_producto=row.get("product_url"),
                    fecha_captura=datetime.now(timezone.utc)
                ))
                new_prices_count += 1

                if i % 500 == 0:
                    print(f"  Analizando precios: {i}/{total_rows}...")

            if precios_a_insertar:
                print(f"Guardando {len(precios_a_insertar)} registros de precios en lote...")
                session.add_all(precios_a_insertar)
            
            print(f"\n--- RESUMEN DE CARGA (BATCH) ---")
            print(f"Productos nuevos creados: {len(nuevos_productos_objs)}")
            print(f"Precios nuevos/actualizados: {new_prices_count}")
            print(f"Precios sin cambios: {unchanged_prices}")
            print(f"Productos omitidos: {skipped}")
            print(f"--------------------------------\n")

if __name__ == "__main__":
    asyncio.run(load_silver())
