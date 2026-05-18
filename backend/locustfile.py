import os
import random
import string

from locust import HttpUser, task, between


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


class QuotesUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.user_email = self._build_user_email()
        self.token = self._get_token(self.user_email)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.detail_template = self._pick_product_detail()

    def _build_user_email(self) -> str:
        base = TEST_USER_EMAIL.split("@", 1)[0]
        domain = TEST_USER_EMAIL.split("@", 1)[1] if "@" in TEST_USER_EMAIL else "example.com"
        return f"{base}+{_random_suffix()}@{domain}"

    def _get_token(self, email: str) -> str:
        payload = {
            "nombre_completo": "Usuario Prueba",
            "correo_electronico": email,
            "password": TEST_USER_PASSWORD,
            "id_tipo_usuario": TEST_USER_TIPO,
        }
        self.client.post(f"{USERS_BASE_URL}/users/register", json=payload)
        login = self.client.post(
            f"{USERS_BASE_URL}/users/login",
            json={"correo_electronico": email, "password": TEST_USER_PASSWORD},
        )
        token = login.json().get("access_token")
        if not token:
            raise RuntimeError("Token no recibido")
        return token

    def _pick_product_detail(self) -> dict:
        resp = self.client.get(f"{INVENTORY_BASE_URL}/inventory/all/productos")
        data = resp.json() if resp.status_code == 200 else []
        for item in data:
            retailer_name = item.get("retailer")
            retailer_id = RETAILER_ID_BY_NAME.get(retailer_name)
            if retailer_id:
                return {
                    "id_producto_maestro": int(item["id_producto"]),
                    "id_retailer": retailer_id,
                    "cantidad": 1,
                }
        return {
            "id_producto_maestro": 1,
            "id_retailer": 1,
            "cantidad": 1,
        }

    @task(3)
    def list_quotes(self):
        self.client.get(f"{QUOTES_BASE_URL}/cotizaciones", headers=self.headers)

    @task(2)
    def create_quote(self):
        detalle = dict(self.detail_template)
        detalle["cantidad"] = random.randint(1, 5)
        payload = {
            "nombre_proyecto": f"LoadTest {_random_suffix()}",
            "detalles": [detalle],
        }
        self.client.post(f"{QUOTES_BASE_URL}/cotizaciones", json=payload, headers=self.headers)
