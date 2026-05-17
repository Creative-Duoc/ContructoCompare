import uuid
from locust import HttpUser, task, between

class ConstructoCompareUser(HttpUser):
    # Tiempo de espera entre peticiones (1 a 3 segundos por usuario)
    wait_time = between(1, 3)

    @task
    def stress_test_registro(self):
        # Generamos datos únicos para cada petición de estrés
        user_id = str(uuid.uuid4())[:8]
        payload = {
            "correo_electronico": f"stress_{user_id}@constructo.cl",
            "password": "Password123!",
            "nombre_completo": f"Usuario Estrés {user_id}"
        }
       
        # Realizamos la petición POST
        with self.client.post("/api/v1/users/register", json=payload, catch_response=True) as response:
            if response.status_code == 201 or response.status_code == 200:
                response.success()
            elif response.status_code == 400:
                # Si el correo ya existe, es un fallo de lógica pero no de servidor
                response.failure("Email duplicado en prueba de estrés")
            else:
                response.failure(f"Fallo crítico: {response.status_code}")