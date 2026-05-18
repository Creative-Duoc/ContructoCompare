import os
import random
import string

import httpx

QUOTES_BASE_URL = os.getenv("QUOTES_BASE_URL", "http://127.0.0.1:8002/api/v1")
USERS_BASE_URL = os.getenv("USERS_BASE_URL", "http://127.0.0.1:8001/api/v1")
INVENTORY_BASE_URL = os.getenv("INVENTORY_BASE_URL", "http://127.0.0.1:8001/api/v1")

TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "usuario.prueba@gmail.com")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "a12345678")
TEST_USER_TIPO = int(os.getenv("TEST_USER_TIPO", "1"))

RETAILER_ID_BY_NAME = {
    "Sodimac": 1,
    "Easy": 2,
    "Imperial": 3,
}

def _random_suffix(length: int = 6) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def _get_token(client: httpx.Client) -> str:
    payload = {
        "nombre_completo": "Usuario Prueba",
        "correo_electronico": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "id_tipo_usuario": TEST_USER_TIPO,
    }
    register = client.post(f"{USERS_BASE_URL}/users/register", json=payload)
    if register.status_code not in {200, 201, 400}:
        register.raise_for_status()

    login = client.post(
        f"{USERS_BASE_URL}/users/login",
        json={"correo_electronico": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    login.raise_for_status()
    token = login.json().get("access_token")
    if not token:
        raise RuntimeError("Token no recibido desde login")
    return token

def _pick_product_detail(client: httpx.Client) -> dict:
    resp = client.get(f"{INVENTORY_BASE_URL}/inventory/all/productos")
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise RuntimeError("No hay productos en inventario para crear cotizacion")

    for item in data:
        retailer_name = item.get("retailer")
        retailer_id = RETAILER_ID_BY_NAME.get(retailer_name)
        if retailer_id:
            return {
                "id_producto_maestro": int(item["id_producto"]),
                "id_retailer": retailer_id,
                "cantidad": 2,
            }

    raise RuntimeError("No se pudo mapear retailer a ID")

def test_quotes_crud_smoke():
    with httpx.Client(timeout=30) as client:
        print("[smoke] Registrando/login usuario de prueba")
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        print("[smoke] Obteniendo producto para detalle")
        detalle = _pick_product_detail(client)

        nombre_proyecto = f"Smoke Quote {_random_suffix()}"
        print(f"[smoke] Creando cotizacion: {nombre_proyecto}")
        create_resp = client.post(
            f"{QUOTES_BASE_URL}/cotizaciones",
            headers=headers,
            json={"nombre_proyecto": nombre_proyecto, "detalles": [detalle]},
        )
        create_resp.raise_for_status()
        created = create_resp.json()
        quote_id = created["id_cotizacion"]

        print("[smoke] Listando cotizaciones")
        list_resp = client.get(f"{QUOTES_BASE_URL}/cotizaciones", headers=headers)
        list_resp.raise_for_status()
        assert any(q["id_cotizacion"] == quote_id for q in list_resp.json())

        print(f"[smoke] Obteniendo cotizacion {quote_id}")
        get_resp = client.get(f"{QUOTES_BASE_URL}/cotizaciones/{quote_id}", headers=headers)
        get_resp.raise_for_status()
        fetched = get_resp.json()
        assert fetched["id_cotizacion"] == quote_id
        assert fetched["detalles"]

        updated_name = f"Smoke Quote Updated {_random_suffix()}"
        updated_detail = dict(detalle)
        updated_detail["cantidad"] = 3
        print(f"[smoke] Actualizando cotizacion {quote_id}")
        update_resp = client.put(
            f"{QUOTES_BASE_URL}/cotizaciones/{quote_id}",
            headers=headers,
            json={"nombre_proyecto": updated_name, "detalles": [updated_detail]},
        )
        update_resp.raise_for_status()
        assert update_resp.json()["nombre_proyecto"] == updated_name

        print(f"[smoke] Eliminando cotizacion {quote_id}")
        delete_resp = client.delete(f"{QUOTES_BASE_URL}/cotizaciones/{quote_id}", headers=headers)
        assert delete_resp.status_code in {200, 204}

        print("[smoke] Verificando que no exista en listado")
        final_list = client.get(f"{QUOTES_BASE_URL}/cotizaciones", headers=headers)
        final_list.raise_for_status()
        assert all(q["id_cotizacion"] != quote_id for q in final_list.json())