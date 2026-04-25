# Sprint 2 - Bronze + Silver (3 Retail)

Este sprint incluye la fase Bronze y Silver para las tres tiendas:
- Sodimac
- Easy
- Imperial

Todo lo necesario para este sprint esta en esta carpeta.

## Estructura

- `run_bronze.py`: ejecuta scraping Bronze de 3 retail.
- `run_silver.py`: unifica Bronze a Silver.
- `run_sprint2.py`: orquesta Bronze + Silver en una sola corrida.
- `core/`: logica de normalizacion, matching y transformacion Silver.
- `scrapers/`: scrapers base + tiendas.
- `data/bronze/`: salidas Bronze.
- `data/silver/`: salida Silver.

## Ejecutar

Desde la carpeta `sprint 2`:

```powershell
python run_sprint2.py
```

Solo Bronze:

```powershell
python run_bronze.py
```

Solo Silver (desde Bronze existente):

```powershell
python run_silver.py
```

## Flags utiles

Limitar productos por tienda:

```powershell
python run_bronze.py --max-products 200
```

Limitar categorias por tienda:

```powershell
python run_bronze.py --sodimac-max-category-urls 20 --easy-max-category-urls 20 --imperial-max-category-urls 20
```

Mostrar navegador:

```powershell
python run_bronze.py --headful
```

Generar preview de matching en Silver:

```powershell
python run_silver.py --preview-matching
```
