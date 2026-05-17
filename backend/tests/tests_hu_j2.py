import os
import sys
import time
import concurrent.futures
import pytest

from fastapi.testclient import TestClient

# 1. Configuración de rutas para que reconozca la carpeta 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

# 2. Inicializamos el cliente
client = TestClient(app)

def realizar_login_stres():
    """Simula un intento de login al endpoint de autenticación"""
    # Nota: Asegúrate de que este endpoint coincida con tu ruta real (ej: /api/v1/users/login)
    payload = {
        "username": "test_qa@duoc.cl",
        "password": "Password123!"
    }
    # Usamos la ruta de OAuth2 o la que definiste para el login
    return client.post("/api/v1/users/login", data=payload)

def test_stress_concurrencia_login():
    """
    PRUEBA DE ESTRÉS (HU-J1):
    Simula 100 usuarios intentando loguearse simultáneamente.
    """
    numero_usuarios = 100
    inicio = time.time()
   
    print(f"\n Lanzando ataque de estrés: {numero_usuarios} peticiones concurrentes...")

    # Usamos ThreadPoolExecutor para disparar las peticiones en paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # Creamos una lista de tareas
        tareas = [executor.submit(realizar_login_stres) for _ in range(numero_usuarios)]
       
        # Recolectamos los resultados a medida que terminan
        resultados = [f.result() for f in concurrent.futures.as_completed(tareas)]
    fin = time.time()
    tiempo_total = fin - inicio
   
    # Análisis de resultados
    exitos = [r for r in resultados if r.status_code in [200, 201]]
    fallos_401 = [r for r in resultados if r.status_code == 401]
    errores_500 = [r for r in resultados if r.status_code == 500]
   
    print(f"\n--- REPORTE DE ESTRÉS TÉCNICO (HU-J1) ---")
    print(f"Peticiones totales : {numero_usuarios}")
    print(f"Logins Exitosos    : {len(exitos)}")
    print(f"Errores 401 (Creds): {len(fallos_401)}")
    print(f"Errores 500 (Caída): {len(errores_500)}")
    print(f"Tiempo total       : {tiempo_total:.2f} segundos")
    print(f"----------------------------------------")
   
    # CRITERIOS DE ACEPTACIÓN DEL TEST
    # 1. El servidor no debe morir (0 errores 500)
    assert len(errores_500) == 0, "¡El servidor colapsó y devolvió Error 500!"
   
    # 2. El tiempo debe ser razonable (ajustado a 10s por si la máquina es lenta)
    assert tiempo_total < 10, f"El login está demasiado lento: {tiempo_total:.2f}s"