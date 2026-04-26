# ConstructoCompare - Scrapers

Este módulo contiene los scrapers y el flujo de procesamiento Bronze/Silver del proyecto.

## Cuándo usar cada script

- `run_bronze.py`: úsalo cuando quieras extraer datos frescos desde Sodimac, Easy e Imperial y guardar los resultados en `data/bronze/`.
- `run_silver.py`: úsalo cuando ya tienes Bronze generado y quieres unificar y normalizar los datos en Silver.
- `run_sprint2.py`: úsalo cuando quieras ejecutar Bronze + Silver en una sola corrida.
- `loader.py`: úsalo cuando quieras cargar un JSON de Bronze a la base de datos.
- `scrapers_retail/sodimac.py`: implementación del scraper de Sodimac, reutilizada por los runners.

## Estructura

- `run_bronze.py`: ejecuta el scraping Bronze de las 3 tiendas.
- `run_silver.py`: transforma Bronze a Silver.
- `run_sprint2.py`: orquesta Bronze + Silver.
- `loader.py`: carga datos de un JSON a la base de datos.
- `core/`: normalización, matching, persistencia y transformaciones.
- `scrapers_retail/`: scrapers por tienda.
- `data/bronze/`: salidas Bronze por tienda.
- `data/silver/`: salida Silver consolidada.

## Requisitos

Antes de ejecutar los scrapers instala Playwright:

```powershell
playwright install chromium
```

## Uso rápido

Desde la carpeta `scrapers/`:

```powershell
python run_sprint2.py
```

### Solo Bronze

```powershell
python run_bronze.py
```

### Solo Silver

```powershell
python run_silver.py
```

### Cargar un JSON a la base de datos

```powershell
python loader.py --json data/bronze/sodimac_products.json
```

## Flags útiles

Limitar productos por tienda:

```powershell
python run_bronze.py --max-products 200
```

Limitar categorías por tienda:

```powershell
python run_bronze.py --sodimac-max-category-urls 20 --easy-max-category-urls 20 --imperial-max-category-urls 20
```

Mostrar navegador durante el scraping:

```powershell
python run_bronze.py --headful
```

Generar un preview de matching en Silver:

```powershell
python run_silver.py --preview-matching
```

Solo generar el preview sin escribir Silver:

```powershell
python run_silver.py --only-preview-matching
```

## Lógica de precios de Sodimac

El cargador de Sodimac prioriza el precio real en este orden:

1. `precio_tarjeta`
2. `precio_oferta`
3. `precio_internet`

`precio_normal` se conserva como referencia, pero no se usa como precio actual.

## Resultado esperado

- Bronze genera archivos como `data/bronze/sodimac_products.json`.
- Silver genera `data/silver/silver_products.json`.
- El cargador toma el JSON indicado y lo inserta o actualiza en la base de datos.
