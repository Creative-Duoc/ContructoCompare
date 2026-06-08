"""
Lee gold_products.json y carga los datos a la base de datos.
Permite que un ProductoMaestro tenga múltiples precios de diferentes retailers.
"""
from __future__ import annotations

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

# Permite ejecutar desde cualquier lugar dentro del proyecto
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.future import select
from sqlalchemy import func

from backend.inventory.database import SessionLocal
from backend.inventory.models.inventory import Categoria, PrecioRetailer, ProductoMaestro, Retailer, Marca, UnidadMedida
from core.normalizer import extract_numeric_specs
from core.transformer import select_effective_price

# Configuración de archivos
DEFAULT_GOLD_JSON = ROOT_DIR / "scrapers" / "data" / "gold" / "gold_products.json"
DEFAULT_BRONZE_DIR = ROOT_DIR / "scrapers" / "data" / "bronze"

RETAILER_METADATA = {
    "sodimac": {"name": "Sodimac", "url": "https://www.sodimac.cl", "logo": "logos/sodimac.png"},
    "easy": {"name": "Easy", "url": "https://www.easy.cl", "logo": "logos/easy.png"},
    "imperial": {"name": "Imperial", "url": "https://www.imperial.cl", "logo": "logos/imperial.png"}
}

DEFAULT_CATEGORY = "General"

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

async def get_or_create_marca(session, nombre: str) -> Marca | None:
    if not nombre or nombre.upper() == "SIN MARCA":
        return None
    result = await session.execute(select(Marca).where(Marca.nombre_marca == nombre))
    marca = result.scalars().first()
    if not marca:
        marca = Marca(nombre_marca=nombre)
        session.add(marca)
        await session.flush()
        print(f"  [+] Marca creada: {nombre}")
    return marca

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

async def get_unit_id(session, abreviatura: str | None) -> int | None:
    if not abreviatura:
        return None
    res = await session.execute(select(UnidadMedida.id_unidad).where(UnidadMedida.abreviatura == abreviatura))
    return res.scalar()

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
            marca_map = {}
            
            print("Cargando caché de productos y precios actuales...")
            # Caché de productos (NOMBRE, ID_CAT -> ID)
            res_prod = await session.execute(select(ProductoMaestro.nombre_producto, ProductoMaestro.id_categoria, ProductoMaestro.id_producto))
            producto_cache = {(name, cat_id): pid for name, cat_id, pid in res_prod.all()}

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
            print(f"Caché cargada: {len(producto_cache)} productos maestros.")

            # --- 2. PASADA 1: IDENTIFICAR PRODUCTOS MAESTROS NUEVOS ---
            nuevos_maestros_objs = {}
            
            for gold_entry in gold_products:
                canonical = gold_entry.get("canonical_product", {})
                nombre = canonical.get("name_canonical")
                cat_name = canonical.get("category_normalized") or DEFAULT_CATEGORY
                brand_name = canonical.get("brand_normalized")
                
                if not nombre: continue
                
                if cat_name not in category_map:
                    category_map[cat_name] = await get_or_create_categoria(session, cat_name)
                cat_id = category_map[cat_name].id_categoria

                cache_key = (nombre, cat_id)
                if cache_key not in producto_cache and cache_key not in nuevos_maestros_objs:
                    if brand_name not in marca_map:
                        marca_map[brand_name] = await get_or_create_marca(session, brand_name)
                    marca = marca_map[brand_name]
                    
                    # --- EXTRAER MEDIDA ---
                    specs = extract_numeric_specs(nombre)
                    valor_num = None
                    id_uni = None
                    
                    # Intentar peso, luego volumen
                    if "peso" in specs:
                        match = re.search(r"(\d+(?:\.\d+)?)", specs["peso"])
                        if match: 
                            valor_num = float(match.group(1))
                            id_uni = await get_unit_id(session, "kg")
                    elif "volumen" in specs:
                        match = re.search(r"(\d+(?:\.\d+)?)", specs["volumen"])
                        if match:
                            valor_num = float(match.group(1))
                            id_uni = await get_unit_id(session, "lt")

                    nuevos_maestros_objs[cache_key] = ProductoMaestro(
                        nombre_producto=nombre,
                        foto_url=canonical.get("image_url"),
                        id_categoria=cat_id,
                        id_marca=marca.id_marca if marca else None,
                        id_unidad=id_uni,
                        valor_medida=valor_num
                    )

            if nuevos_maestros_objs:
                print(f"Insertando {len(nuevos_maestros_objs)} nuevos productos maestros...")
                session.add_all(nuevos_maestros_objs.values())
                await session.flush()
                for (name, cat_id), obj in nuevos_maestros_objs.items():
                    producto_cache[(name, cat_id)] = obj.id_producto

            # --- 3. PASADA 2: PROCESAR PRECIOS DE CADA RETAILER ---
            precios_a_insertar = []
            new_prices_count = 0
            unchanged_prices = 0
            
            for gold_entry in gold_products:
                canonical = gold_entry.get("canonical_product", {})
                nombre = canonical.get("name_canonical")
                cat_name = canonical.get("category_normalized") or DEFAULT_CATEGORY
                
                if not nombre: continue
                
                cat_id = category_map[cat_name].id_categoria
                id_producto_maestro = producto_cache.get((nombre, cat_id))
                
                if not id_producto_maestro: continue
                
                variants = gold_entry.get("store_variants", [])
                for var in variants:
                    store_key = var.get("store")
                    price = var.get("effective_price")
                    sku_tienda = var.get("sku_store")
                    
                    if not store_key or price is None: continue
                    
                    if store_key not in retailer_map:
                        retailer_map[store_key] = await get_or_create_retailer(session, store_key)
                    retailer = retailer_map[store_key]
                    
                    ultimo_precio = precio_cache.get((id_producto_maestro, retailer.id_retailer))
                    if ultimo_precio is not None and round(float(ultimo_precio)) == round(float(price)):
                        unchanged_prices += 1
                        continue
                        
                    precios_a_insertar.append(PrecioRetailer(
                        id_producto_maestro=id_producto_maestro,
                        id_retailer=retailer.id_retailer,
                        sku_tienda=str(sku_tienda),
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

async def load_daily_prices(today: str) -> None:
    """Carga precios actualizados hoy desde Bronze directamente a la BD, sin pasar por Silver/Gold."""
    stores = ["sodimac", "easy", "imperial"]
    retailer_name_map = {"sodimac": "Sodimac", "easy": "Easy", "imperial": "Imperial"}

    for store in stores:
        path = DEFAULT_BRONZE_DIR / f"{store}_products.json"
        if not path.exists():
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        updated = [
            p for p in data.get("products", [])
            if p.get("fecha_ultima_revision") == today
        ]
        if not updated:
            continue

        inserted = 0
        skipped_no_db = 0
        skipped_unchanged = 0
        marked_unavailable = 0
        skipped_no_price = 0

        async with SessionLocal() as session:
            async with session.begin():
                # Query 1: obtener retailer
                res_r = await session.execute(
                    select(Retailer).where(Retailer.nombre_retailer == retailer_name_map[store])
                )
                retailer = res_r.scalars().first()
                if not retailer:
                    print(f"[daily_load] Retailer '{retailer_name_map[store]}' no encontrado en DB, omitiendo.")
                    continue

                all_urls = [p["product_url"] for p in updated if p.get("product_url")]
                skipped_no_url = len(updated) - len(all_urls)
                if not all_urls:
                    continue

                # Query 2: URL → id_producto_maestro para todas las URLs de golpe
                res_url = await session.execute(
                    select(PrecioRetailer.link_producto, PrecioRetailer.id_producto_maestro)
                    .where(PrecioRetailer.link_producto.in_(all_urls))
                )
                url_to_product: dict[str, int] = {}
                for link, pid in res_url.all():
                    if link not in url_to_product:
                        url_to_product[link] = pid

                # Query 3: último precio por producto para este retailer, de golpe
                product_ids = list(set(url_to_product.values()))
                latest_prices: dict[int, float] = {}
                if product_ids:
                    subq = (
                        select(
                            PrecioRetailer.id_producto_maestro,
                            func.max(PrecioRetailer.fecha_captura).label("max_fecha"),
                        )
                        .where(
                            PrecioRetailer.id_producto_maestro.in_(product_ids),
                            PrecioRetailer.id_retailer == retailer.id_retailer,
                        )
                        .group_by(PrecioRetailer.id_producto_maestro)
                        .subquery()
                    )
                    res_prices = await session.execute(
                        select(PrecioRetailer.id_producto_maestro, PrecioRetailer.precio_clp)
                        .join(
                            subq,
                            (PrecioRetailer.id_producto_maestro == subq.c.id_producto_maestro)
                            & (PrecioRetailer.fecha_captura == subq.c.max_fecha),
                        )
                        .where(PrecioRetailer.id_retailer == retailer.id_retailer)
                    )
                    latest_prices = {pid: float(clp) for pid, clp in res_prices.all()}

                # Procesar en memoria — sin más round-trips a la BD
                to_insert: list[PrecioRetailer] = []
                unavailable_ids: list[int] = []
                matched_in_db = 0

                for product in updated:
                    url = product.get("product_url")
                    if not url:
                        continue

                    id_producto = url_to_product.get(url)
                    if not id_producto:
                        skipped_no_db += 1
                        continue
                    matched_in_db += 1

                    if not product.get("disponibilidad", True):
                        unavailable_ids.append(id_producto)
                        continue

                    price = select_effective_price(product)
                    if price is None:
                        skipped_no_price += 1
                        continue

                    latest = latest_prices.get(id_producto)
                    if latest is not None and round(float(latest)) == round(float(price)):
                        skipped_unchanged += 1
                        continue

                    to_insert.append(PrecioRetailer(
                        id_producto_maestro=id_producto,
                        id_retailer=retailer.id_retailer,
                        sku_tienda=str(product.get("sku_store") or ""),
                        precio_clp=price,
                        disponibilidad=True,
                        link_producto=url,
                        fecha_captura=datetime.now(timezone.utc),
                    ))
                    inserted += 1

                # Bulk insert de nuevos precios
                if to_insert:
                    session.add_all(to_insert)

                # Marcar no disponibles (son pocos, queries individuales están bien)
                for id_producto in unavailable_ids:
                    res_last = await session.execute(
                        select(PrecioRetailer)
                        .where(
                            PrecioRetailer.id_producto_maestro == id_producto,
                            PrecioRetailer.id_retailer == retailer.id_retailer,
                        )
                        .order_by(PrecioRetailer.fecha_captura.desc())
                        .limit(1)
                    )
                    precio_rec = res_last.scalars().first()
                    if precio_rec and precio_rec.disponibilidad:
                        precio_rec.disponibilidad = False
                        marked_unavailable += 1

        print(
            f"[daily_load][{store}] insertados={inserted} sin_cambio={skipped_unchanged} "
            f"sin_db={skipped_no_db} matched_in_db={matched_in_db} "
            f"sin_precio={skipped_no_price} sin_url={skipped_no_url} no_disponibles={marked_unavailable}"
        )


if __name__ == "__main__":
    asyncio.run(load_gold())
