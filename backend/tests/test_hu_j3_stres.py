import time
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

# Configuración explícita para que Pytest use ÚNICAMENTE asyncio
@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_stress_motor_matching():
    """
    PRUEBA DE ESTRÉS ASÍNCRONA (HU-J3.1):
    Simula 50 usuarios buscando simultáneamente usando la sintaxis moderna de HTTPX.
    """
    numero_busquedas = 50
    inicio = time.time()
   
    print(f"\n[STRESS TEST] Lanzando {numero_busquedas} búsquedas simultáneas asíncronas...")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tareas = [client.get("/api/v1/inventory/search?q=sierra") for _ in range(numero_busquedas)]
        resultados = await asyncio.gather(*tareas)
   
    fin = time.time()
    tiempo_total = fin - inicio
   
    errores_500 = [r for r in resultados if r.status_code >= 500]
   
    print(f"\n--- REPORTE DE ESTRÉS MATCHING (HU-J3.1) ---")
    print(f"Búsquedas totales : {numero_busquedas}")
    print(f"Errores de DB 500 : {len(errores_500)}")
    print(f"Tiempo total      : {tiempo_total:.2f} segundos")
    print(f"Promedio por req  : {(tiempo_total/numero_busquedas):.3f} segundos")
    print(f"--------------------------------------------")
   
    assert len(errores_500) == 0, "La base de datos arrojó errores bajo estrés."
    assert tiempo_total < 15.0, f"El motor superó el tiempo máximo tolerado: {tiempo_total:.2f}s"
