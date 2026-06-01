import requests

BASE_URL = "http://127.0.0.1:8000"

def test_smoke():
    print("Iniciando prueba de humo...")
    # Probamos el login primero
    payload = {"correo_electronico": "javiera.nueva@constructocompare.cl", "password": "Password123!"}
    response = requests.post(f"{BASE_URL}/api/v1/users/login", json=payload)
    
    print(f"Respuesta Login: {response.status_code}")
    print(f"Detalle: {response.text}")

    if response.status_code == 200:
        print("¡Login exitoso! Procediendo a testear /me...")
        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        resp_me = requests.get(f"{BASE_URL}/api/v1/users/me", headers=headers)
        print(f"Respuesta /me: {resp_me.status_code}")
    else:
        print("El login falló, por eso fallan las pruebas de estrés.")

if __name__ == "__main__":
    test_smoke()