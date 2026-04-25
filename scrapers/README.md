# 🕵️ ConstructoCompare - Scrapers

Este módulo contiene la lógica para la extracción automática de datos desde sitios web de retailers y su posterior carga en la base de datos central.

## 📁 Flujo de Datos

1. **Extracción (Bronze):** Los scripts de scraping extraen datos y los guardan en formato JSON en `data/bronze/`.
2. **Carga (Database):** El cargador procesa los archivos JSON y sincroniza la información con la base de datos.

## 🛠️ Scripts Principales

### 1. `sodimac.py` (Scraper)
Utiliza **Playwright** para navegar por las categorías de Sodimac y extraer productos.

**Uso:**
```bash
python sodimac.py --max-categories 25
```
- `--max-categories`: Limita el número de categorías a procesar (útil para pruebas).

### 2. `loader.py` (Cargador a DB)
Procesa los archivos JSON generados y los inserta en las tablas correspondientes (`productos_maestros`, `precios_retailer`, etc.).

**Uso:**
```bash
python loader.py --json data/bronze/sodimac_products.json
```

## 📈 Lógica de Precios (Sodimac)

El cargador implementa una prioridad para determinar el precio real (`precio_clp`):

1. **Precio Tarjeta:** Precio exclusivo con tarjeta CMR (siempre es el más bajo).
2. **Precio Oferta:** Precio en oferta activa para todo medio de pago.
3. **Precio Internet:** Precio normal de venta online.
4. **Precio Normal:** Precio de referencia (tachado), no se utiliza como precio actual.

## ⚙️ Configuración

Asegúrate de tener instalados los navegadores de Playwright:
```bash
playwright install chromium
```
