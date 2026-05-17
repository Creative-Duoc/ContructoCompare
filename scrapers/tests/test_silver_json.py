import json
import os
import pytest


# Ruta relativa correcta desde la carpeta 'scrapers'
SILVER_PATH = "data/silver/silver_products.json"


@pytest.fixture
def dataset_silver():
    """Fixture que carga el archivo JSON Silver generado en el Sprint 2."""
    assert os.path.exists(SILVER_PATH), f"Falta el archivo {SILVER_PATH}. Ejecuta run_silver.py primero."
    with open(SILVER_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_ac1_y_ac4_precios_numéricos_para_calculos(dataset_silver):
    """Valida que todos los precios calculados sean matemáticamente utilizables."""
    productos = dataset_silver.get("products", []) if isinstance(dataset_silver, dict) else dataset_silver
   
    for prod in productos:
        # El transformer calcula 'effective_price'
        precio = prod.get("effective_price")
       
        # El criterio pide que sirva para cálculos sin errores (Debe ser int o float, no texto)
        assert isinstance(precio, (int, float)), \
            f"Fallo en ID {prod.get('silver_row_id')}: El precio efectivo es tipo '{type(precio)}', no numérico."
       
        # Validar que cumpla la regla de negocio del Sprint 2: Precios cero o negativos se ignoran
        assert precio > 0, f"Error en SKU {prod.get('sku_store')}: El precio debe ser mayor a cero."


def test_ac2_limpieza_de_caracteres_y_espacios(dataset_silver):
    """Valida que 'normalize_name' removió inconsistencias y caracteres extraños."""
    productos = dataset_silver.get("products", []) if isinstance(dataset_silver, dict) else dataset_silver
   
    for prod in productos:
        nombre_original = prod.get("name_original", "")
        nombre_limpio = prod.get("name_normalized", "")
       
        # Si había texto original, el nombre normalizado no debe quedar vacío
        if nombre_original:
            assert len(nombre_limpio) > 0, f"Error: Nombre quedó vacío tras normalización en ID {prod.get('silver_row_id')}"
       
        # No deben existir espacios múltiples (clean_text lo resuelve)
        assert "  " not in nombre_limpio, f"Espacios múltiples detectados en: '{nombre_limpio}'"


def test_verificacion_cobertura_multi_retailer(dataset_silver):
    """Confirma que las tres tiendas aportaron datos al archivo final de calidad."""
    conteos = dataset_silver.get("per_store_counts", {})
   
    # Comprobar la presencia de los tres retailers requeridos en el Sprint 2
    assert conteos.get("sodimac", 0) > 0, "Faltan datos normalizados de Sodimac."
    assert conteos.get("easy", 0) > 0, "Faltan datos normalizados de Easy."
    assert conteos.get("imperial", 0) > 0, "Faltan datos normalizados de Imperial."
