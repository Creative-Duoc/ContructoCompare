"""
Lee gold_products.json y carga los datos a la base de datos.
Permite que un ProductoMaestro tenga múltiples precios de diferentes retailers.
"""
from __future__ import annotations

import asyncio
import json
import sys
import re
import hashlib
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
DEFAULT_GOLD_JSON = ROOT_DIR / "scrapers" / "data" / "gold" / "gold_products.json"

RETAILER_METADATA = {
    "sodimac": {"name": "Sodimac", "url": "https://www.sodimac.cl", "logo": "logos/sodimac.png"},
    "easy": {"name": "Easy", "url": "https://www.easy.cl", "logo": "logos/easy.png"},
    "imperial": {"name": "Imperial", "url": "https://www.imperial.cl", "logo": "logos/imperial.png"}
}

DEFAULT_CATEGORY = "General"

def _hash_to_int(hash_str: str) -> int:
    """Convierte un hash hexadecimal corto a un entero positivo para sku_maestro."""
    return int(hash_str, 16) % (10**9)

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

async def load_gold(json_path: Path = DEFAULT_GOLD_JSON) -> None:
    if not json_path.exists():
        print(f"Error: No se encuentra el archivo Gold en {json_path}")
        return

    print(f"Leyendo archivo Gold: {json_path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    gold_products = data.get("gold_products", [])
    total_gold = len(gold_products)
    print(f"Productos maestros encontrados en Gold: {total_gold}")

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
            # Obtenemos el último precio capturado para cada combinación producto/retailer
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
            print(f"Caché cargada: {len(producto_cache)} productos maestros y {len(precio_cache)} precios retail.")

            # --- 2. PASADA 1: IDENTIFICAR PRODUCTOS MAESTROS NUEVOS ---
            nuevos_maestros_objs = {}
            
            for gold_entry in gold_products:
                gold_id_hex = gold_entry.get("gold_product_id")
                if not gold_id_hex: continue
                
                sku_maestro = _hash_to_int(gold_id_hex)
                
                if sku_maestro not in producto_cache and sku_maestro not in nuevos_maestros_objs:
                    canonical = gold_entry.get("canonical_product", {})
                    cat_name = canonical.get("category_normalized") or DEFAULT_CATEGORY
                    
                    if cat_name not in category_map:
                        category_map[cat_name] = await get_or_create_categoria(session, cat_name)
                    
                    nuevos_maestros_objs[sku_maestro] = ProductoMaestro(
                        sku_maestro=sku_maestro,
                        nombre_producto=canonical.get("name_canonical"),
                        foto_url=canonical.get("image_url"),
                        id_categoria=category_map[cat_name].id_categoria
                    )

            if nuevos_maestros_objs:
                print(f"Insertando {len(nuevos_maestros_objs)} nuevos productos maestros...")
                session.add_all(nuevos_maestros_objs.values())
                await session.flush()
                for sku, obj in nuevos_maestros_objs.items():
                    producto_cache[sku] = obj.id_producto

            # --- 3. PASADA 2: PROCESAR PRECIOS DE CADA RETAILER ---
            precios_a_insertar = []
            new_prices_count = 0
            unchanged_prices = 0
            
            for gold_entry in gold_products:
                gold_id_hex = gold_entry.get("gold_product_id")
                sku_maestro = _hash_to_int(gold_id_hex)
                id_producto_maestro = producto_cache.get(sku_maestro)
                
                if not id_producto_maestro: continue
                
                variants = gold_entry.get("store_variants", [])
                for var in variants:
                    store_key = var.get("store")
                    price = var.get("effective_price")
                    
                    if not store_key or price is None: continue
                    
                    if store_key not in retailer_map:
                        retailer_map[store_key] = await get_or_create_retailer(session, store_key)
                    retailer = retailer_map[store_key]
                    
                    ultimo_precio = precio_cache.get((id_producto_maestro, retailer.id_retailer))
                    if ultimo_precio is not None and float(ultimo_precio) == float(price):
                        unchanged_prices += 1
                        continue
                        
                    precios_a_insertar.append(PrecioRetailer(
                        id_producto_maestro=id_producto_maestro,
                        id_retailer=retailer.id_retailer,
                        precio_clp=price,
                        disponibilidad=True,
                        link_producto=var.get("product_url"),
                        fecha_captura=datetime.now(timezone.utc)
                    ))
                    new_prices_count += 1

            if precios_a_insertar:
                print(f"Guardando {len(precios_a_insertar)} registros de precios multitienda...")
                session.add_all(precios_a_insertar)
            
            print(f"\n--- RESUMEN DE CARGA GOLD ---")
            print(f"Nuevos Productos Maestros: {len(nuevos_maestros_objs)}")
            print(f"Precios nuevos/actualizados: {new_prices_count}")
            print(f"Precios sin cambios: {unchanged_prices}")
            print(f"-----------------------------\n")
            
            # High-signal summary for file log
            import logging
            loader_logger = logging.getLogger("constructocompare.loader")
            loader_logger.info(
                "LOAD_SUMMARY | new_masters=%d | prices_updated=%d | prices_unchanged=%d",
                len(nuevos_maestros_objs),
                new_prices_count,
                unchanged_prices
            )

if __name__ == "__main__":
    asyncio.run(load_gold())
