from locust import HttpUser, task, between

class UserBehavior(HttpUser):
    wait_time = between(1, 2)
    token = None

    def on_start(self):
        """Este método corre al iniciar cada usuario simulado"""
        response = self.client.post("/api/v1/users/login", json={
            "correo_electronico": "javiera.nueva@constructocompare.cl",
            "password": "Password123!"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    @task(3)
    def test_get_profile(self):
        if self.token:
            self.client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {self.token}"})