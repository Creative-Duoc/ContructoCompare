import time
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_stress_guardado_cotizaciones():
    """
    PRUEBA DE ESTRÉS SPRINT 4: Persistencia Concurrente.
    Verifica que la base de datos soporte múltiples guardados simultáneos sin perder data.
    """
    numero_guardados = 50
    inicio = time.time()
    
    print(f"\n[STRESS TEST] Simulando {numero_guardados} usuarios guardando cotizaciones...")

    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer token_de_prueba_o_mock"}
    
    payload_base = {
        "titulo": "Cotización de Prueba Estrés",
        "productos": [{"id_producto_maestro": 1, "cantidad": 10}]
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Disparamos 50 peticiones POST concurrentes
        tareas = [
            client.post("/api/v1/quotes", json=payload_base, headers=headers) 
            for _ in range(numero_guardados)
        ]
        resultados = await asyncio.gather(*tareas)
    
    fin = time.time()
    tiempo_total = fin - inicio
    
    # Verificamos cuántas fallaron (500 Error Interno o 422 Error de Validación)
    errores_db = [r for r in resultados if r.status_code >= 500]
    guardados_exitosos = [r for r in resultados if r.status_code in [200, 201]]
    
    print(f"\n--- REPORTE DE ESTRÉS COTIZACIONES (SPRINT 4) ---")
    print(f"Peticiones de guardado : {numero_guardados}")
    print(f"Guardados exitosos     : {len(guardados_exitosos)}")
    print(f"Errores de DB 500      : {len(errores_db)}")
    print(f"Tiempo total           : {tiempo_total:.2f} segundos")
    print(f"Promedio por guardado  : {(tiempo_total/numero_guardados):.3f} segundos")
    print(f"-------------------------------------------------")
    
    # Criterios de aceptación técnica
    assert len(errores_db) == 0, "La base de datos colapsó al guardar cotizaciones concurrentes."
    assert len(guardados_exitosos) == numero_guardados, "Se perdieron cotizaciones durante el guardado masivo."
    assert tiempo_total < 15.0, f"El proceso de guardado es demasiado lento: {tiempo_total:.2f}s"