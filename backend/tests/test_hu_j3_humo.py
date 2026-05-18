import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_smoke_agrupacion_productos():
    """
    Validación de Humo HU-J3.1
    Verifica que el endpoint de búsqueda devuelve productos agrupados por ID Maestro.
    """
    # Simulamos una búsqueda que debería traer equivalencias
    response = client.get("/api/v1/inventory/search?q=sierra")
   
    # 1. El endpoint debe estar vivo (Smoke)
    assert response.status_code == 200, "El endpoint de búsqueda está caído"
   
    data = response.json()
    resultados = data.get("results", [])
   
    # 2. AC1 y AC4: No debe estar vacío y debe agrupar
    assert len(resultados) > 0, "No se encontraron resultados para la prueba"
   
    # Tomamos el primer grupo de productos
    primer_grupo = resultados[0]
   
    # 3. AC2: Validar que existan equivalencias (ofertas de distintas tiendas)
    ofertas = primer_grupo.get("retailer_offers", [])
    assert len(ofertas) >= 1, "El producto no tiene ofertas asociadas"
   
    # 4. Validar que no hay IDs de tienda duplicados innecesariamente en el mismo grupo
    tiendas = [oferta["store"] for oferta in ofertas]
    assert len(tiendas) == len(set(tiendas)), "AC4 Fallido: Hay productos duplicados de la misma tienda en el grupo"
