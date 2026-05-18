import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_smoke_flujo_cotizaciones():
    """
    PRUEBA DE HUMO SPRINT 4: Gestión de Cotizaciones.
    Verifica los AC: Crear cotización, guardar correctamente y recuperar.
    """
    transport = ASGITransport(app=app)
    
    # Para esta prueba asumiremos que tienes un usuario de prueba en la BD 
    # o que pasas un token JWT válido. Aquí simularemos el payload.
    headers = {"Authorization": "Bearer token_de_prueba_o_mock"}
    
    payload_cotizacion = {
        "titulo": "Materiales Ampliación Baño",
        "productos": [
            {"id_producto_maestro": 1, "cantidad": 5},
            {"id_producto_maestro": 2, "cantidad": 1}
        ]
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # PASO 1: Crear la cotización (AC1 y AC2)
        print("\n[SMOKE] Intentando crear una nueva cotización...")
        response_post = await client.post(
            "/api/v1/quotes", # Ajusta esta ruta a tu endpoint real
            json=payload_cotizacion,
            headers=headers
        )
        
        assert response_post.status_code in [200, 201], f"Fallo al crear cotización: {response_post.text}"
        data_creada = response_post.json()
        id_cotizacion = data_creada.get("id_cotizacion", 1)
        print(f"[SMOKE] Cotización creada con éxito. ID: {id_cotizacion}")

        # PASO 2: Recuperar las cotizaciones guardadas (AC3 y AC4)
        print("[SMOKE] Recuperando cotizaciones del usuario...")
        response_get = await client.get(
            "/api/v1/quotes", # Ajusta esta ruta a tu endpoint real
            headers=headers
        )
        
        assert response_get.status_code == 200, "Fallo al recuperar las cotizaciones"
        cotizaciones_recuperadas = response_get.json()
        
        # Validar que la cotización que acabamos de crear está en la lista devuelta
        assert any(c.get("titulo") == "Materiales Ampliación Baño" for c in cotizaciones_recuperadas), \
            "La cotización guardada no apareció al recuperarla (Pérdida de datos)."
            
        print("[SMOKE] ¡Cotización recuperada correctamente!")