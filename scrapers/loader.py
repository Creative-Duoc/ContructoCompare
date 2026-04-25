"""
Lee sodimac_products.json y carga los datos a la base de datos.

Lógica de precios Sodimac:
- precio_tarjeta   → precio con tarjeta CMR, siempre el más bajo
- precio_oferta    → precio en oferta activa
- precio_internet  → precio normal cuando NO hay oferta (es el precio actual)
- precio_normal    → precio original ANTES de la oferta (el "tachado"), NO se usa como precio real

Prioridad para precio_clp: precio_tarjeta → precio_oferta → precio_internet
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Permite ejecutar desde cualquier lugar dentro del proyecto
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.future import select

from backend.app.database import SessionLocal
from backend.app.models.inventory import Categoria, PrecioRetailer, ProductoMaestro, Retailer

DEFAULT_JSON = ROOT_DIR / "scrapers" / "data" / "bronze" / "sodimac_products.json"
SODIMAC_NAME = "Sodimac"
SODIMAC_URL = "https://www.sodimac.cl"
SODIMAC_LOGO = "logos/sodimac.png"
DEFAULT_CATEGORY = "General"


def pick_price(product: dict) -> int | None:
    # Prioridad: tarjeta (más bajo) -> oferta -> internet (normal)
    for key in ("precio_tarjeta", "precio_oferta", "precio_internet"):
        value = product.get(key)
        if value is not None:
            return int(value)
    return None


async def get_or_create_categoria(session, nombre: str) -> Categoria:
    result = await session.execute(select(Categoria).where(Categoria.nombre_categoria == nombre))
    categoria = result.scalars().first()
    if not categoria:
        categoria = Categoria(nombre_categoria=nombre)
        session.add(categoria)
        await session.flush()
        print(f"  [+] Categoria creada: {nombre}")
    return categoria


async def get_or_create_retailer(session) -> Retailer:
    result = await session.execute(
        select(Retailer).where(Retailer.nombre_retailer == SODIMAC_NAME)
    )
    retailer = result.scalars().first()
    if not retailer:
        retailer = Retailer(
            nombre_retailer=SODIMAC_NAME,
            url_base=SODIMAC_URL,
            logo_path=SODIMAC_LOGO,
        )
        session.add(retailer)
        await session.flush()
        print(f"  [+] Retailer creado: {SODIMAC_NAME}")
    return retailer


async def upsert_producto(session, sku: int, nombre: str, id_categoria: int) -> ProductoMaestro:
    result = await session.execute(
        select(ProductoMaestro).where(ProductoMaestro.sku_maestro == sku)
    )
    producto = result.scalars().first()
    if not producto:
        producto = ProductoMaestro(
            sku_maestro=sku,
            nombre_producto=nombre,
            id_categoria=id_categoria,
        )
        session.add(producto)
        await session.flush()
    return producto


async def load(json_path: Path = DEFAULT_JSON) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    products = data.get("products", [])
    print(f"Productos en JSON: {len(products)}")

    async with SessionLocal() as session:
        async with session.begin():
            categoria = await get_or_create_categoria(session, DEFAULT_CATEGORY)
            retailer = await get_or_create_retailer(session)

            # --- OPTIMIZACIÓN: Cargar todos los SKUs y sus ÚLTIMOS precios ---
            print("Cargando caché de productos y precios desde la base de datos...")
            result = await session.execute(select(ProductoMaestro.sku_maestro, ProductoMaestro.id_producto))
            producto_cache = {sku: pid for sku, pid in result.all()}
            
            # Cargar el último precio registrado para cada producto de este retailer
            from sqlalchemy import func
            subq = select(
                PrecioRetailer.id_producto_maestro,
                func.max(PrecioRetailer.fecha_captura).label("max_fecha")
            ).where(PrecioRetailer.id_retailer == retailer.id_retailer).group_by(PrecioRetailer.id_producto_maestro).subquery()

            last_prices_query = select(PrecioRetailer.id_producto_maestro, PrecioRetailer.precio_clp).join(
                subq, (PrecioRetailer.id_producto_maestro == subq.c.id_producto_maestro) & 
                      (PrecioRetailer.fecha_captura == subq.c.max_fecha)
            )
            result_prices = await session.execute(last_prices_query)
            # Cache de precios: {id_producto: precio_actual}
            precio_cache = {row.id_producto_maestro: float(row.precio_clp) for row in result_prices.all()}

            print(f"Caché cargada: {len(producto_cache)} productos y {len(precio_cache)} precios históricos.")

            inserted = 0
            skipped = 0
            unchanged = 0
            total_products = len(products)
            
            # Acumularemos aquí los productos nuevos que necesitan ser guardados en la BD
            nuevos_productos = {}

            # PRIMERA PASADA: Identificar qué productos no existen en la BD
            for product in products:
                sku_raw = product.get("sku_store", "")
                if not sku_raw or not str(sku_raw).isdigit():
                    continue

                sku = int(sku_raw)
                if sku not in producto_cache and sku not in nuevos_productos:
                    nuevos_productos[sku] = ProductoMaestro(
                        sku_maestro=sku,
                        nombre_producto=product["name"],
                        id_categoria=categoria.id_categoria,
                    )

            # Si hay productos nuevos, los insertamos de una sola vez y actualizamos la caché
            if nuevos_productos:
                print(f"Insertando {len(nuevos_productos)} productos nuevos...")
                session.add_all(nuevos_productos.values())
                await session.flush() # Guardamos para que se generen los ID
                for sku, prod in nuevos_productos.items():
                    producto_cache[sku] = prod.id_producto

            # SEGUNDA PASADA: Preparar e insertar los precios solo si cambiaron
            precios_a_insertar = []
            for i, product in enumerate(products, 1):
                progress = i / total_products
                bar_length = 40
                filled_length = int(bar_length * progress)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                print(f'\r  Progreso: [{bar}] {i}/{total_products} ({(progress * 100):.1f}%)', end='', flush=True)

                sku_raw = product.get("sku_store", "")
                if not sku_raw or not str(sku_raw).isdigit():
                    skipped += 1
                    continue

                precio = pick_price(product)
                if precio is None:
                    skipped += 1
                    continue

                sku = int(sku_raw)
                id_producto = producto_cache.get(sku)

                # VERIFICACIÓN DE CAMBIO DE PRECIO
                ultimo_precio = precio_cache.get(id_producto)
                if ultimo_precio is not None and float(ultimo_precio) == float(precio):
                    unchanged += 1
                    continue

                precios_a_insertar.append(PrecioRetailer(
                    id_producto_maestro=id_producto,
                    id_retailer=retailer.id_retailer,
                    precio_clp=precio,
                    disponibilidad=True,
                    link_producto=product["product_url"],
                ))
                inserted += 1
            
            print() # Salto de línea al terminar la barra de progreso
            
            # Guardamos todos los precios de golpe
            if precios_a_insertar:
                print(f"Guardando {len(precios_a_insertar)} nuevos registros de precios...")
                session.add_all(precios_a_insertar)
            else:
                print("No hay cambios de precios para registrar.")

    print(f"Precios nuevos/cambiados: {inserted} | Sin cambios: {unchanged} | Omitidos: {skipped}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Carga productos Sodimac desde JSON a la BD.")
    parser.add_argument("--json", default=str(DEFAULT_JSON), help="Ruta al archivo JSON del scraper")
    args = parser.parse_args()

    asyncio.run(load(Path(args.json)))
