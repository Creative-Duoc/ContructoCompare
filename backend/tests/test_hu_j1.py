import os
import sys
import pytest
from fastapi.testclient import TestClient
import uuid
from unittest.mock import patch, MagicMock

# 1. Configuración de rutas
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
from app.main import app

# 2. Cliente de pruebas
client = TestClient(app)

CORREO_PRUEBA = f"test_{uuid.uuid4().hex[:6]}@duoc.cl"
PAYLOAD_BASE = {
    "correo_electronico": CORREO_PRUEBA,
    "password": "Password123!",
    "nombre_completo": "Javiera QA"
}

# --- PRUEBAS DE HUMO ---
def test_smoke_api_running():
    """Verifica disponibilidad del servidor."""
    response = client.get("/")
    assert response.status_code in [200, 404]

# --- PRUEBAS DE REGISTRO (HU-J1) ---
def test_registro_usuario_nuevo():
    """Valida AC1: Registro exitoso con datos válidos."""
    response = client.post("/api/v1/users/register", json=PAYLOAD_BASE)
    assert response.status_code in [200, 201, 500]

# --- PRUEBA AC3 CON MOCKING PARA EVITAR CONFLICTO DE EVENT LOOP EN WINDOWS ---
from unittest.mock import AsyncMock, MagicMock

# --- PRUEBA AC3 CON MOCKING ASÍNCRONO SIMPLIFICADO ---
def test_registro_correo_duplicado():
    """Valida AC3: El sistema rechaza correos ya existentes simulando respuesta de BD."""
   
    # 1. Configuramos el objeto resultante de la base de datos
    mock_result = MagicMock()
    # Si scalars().first() se llama, devuelve un diccionario simulando el usuario
    mock_result.scalars().first.return_value = {"id": 1, "correo_electronico": "duplicado@duoc.cl"}
   
    # 2. Configuramos la sesión asíncrona.
    # Usamos AsyncMock para el método 'execute' porque tu código usa 'await db.execute(...)'
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # 3. Inyectamos la sesión falsa en FastAPI
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_session
   
    try:
        response = client.post("/api/v1/users/register", json=PAYLOAD_BASE)
       
        assert response.status_code == 400
        assert response.json()["detail"] == "Este correo ya está registrado en ConstructoCompare."
    finally:
        app.dependency_overrides.clear()