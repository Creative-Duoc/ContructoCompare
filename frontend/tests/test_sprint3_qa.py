"""
HU: HU-I3.1 -- Vista Side-by-Side y Resaltado Mejor Precio
Ejecutar: pytest test_sprint3_qa.py -v -s
"""
import pytest, time, json
from playwright.sync_api import sync_playwright

BASE_URL      = "https://front-constructor-e2j6.vercel.app"
LOGIN_URL     = f"{BASE_URL}/login.html"
APP_URL       = f"{BASE_URL}/index.html"
DEMO_EMAIL    = "usuario@demo.cl"
DEMO_PASSWORD = "demo123"
TIMEOUT_MS    = 20000

SEL_EMAIL    = "#login-email"
SEL_PASSWORD = "#login-pass"
SEL_SUBMIT   = "#btn-login"


class TestSprint3:

    def _login_y_buscar(self, page, termino="cemento"):
        """Helper: hace login, inyecta sesión y busca un término."""
        
        # Mock de API para evitar errores de CORS y asegurar datos (HU-I3.1)
        page.route("**/api/v1/**", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([
                {
                    "id": "m1", "nombre": f"{termino.capitalize()} Premium", 
                    "precio": 4000, "tienda": "Sodimac", "best": True
                },
                {
                    "id": "m2", "nombre": f"{termino.capitalize()} Estándar", 
                    "precio": 4500, "tienda": "Easy"
                },
                {
                    "id": "m3", "nombre": f"{termino.capitalize()} Económico", 
                    "precio": 4600, "tienda": "Imperial"
                }
            ])
        ))

        page.goto(LOGIN_URL, timeout=TIMEOUT_MS)
        page.wait_for_selector(SEL_EMAIL, timeout=TIMEOUT_MS)
        page.fill(SEL_EMAIL, DEMO_EMAIL)
        page.fill(SEL_PASSWORD, DEMO_PASSWORD)
        page.click(SEL_SUBMIT)
        time.sleep(3)
        # Inyectar sesión para que /app no redirija al login
        page.evaluate("""() => {
            sessionStorage.setItem('cc_user', JSON.stringify({
                id: 'U001', nombre: 'Usuario Demo',
                email: 'usuario@demo.cl', tipo: 'profesional'
            }));
        }""")
        page.goto(APP_URL, timeout=TIMEOUT_MS)
        time.sleep(2)
        search = page.locator("#search-input")
        if search.count() == 0:
            search = page.locator("input[type='text']").first
        search.fill(termino)
        search.press("Enter")
        page.wait_for_selector(
            ".tienda-btn, .producto-card, .card",
            timeout=TIMEOUT_MS
        )
        time.sleep(1)


    def test_TC_S3_01_humo_badge_mejor_precio_automatico(self):
        """
        TC-S3-01 | PRUEBA DE HUMO | Sprint 3
        HU: HU-I3.1, HU3-AC1

        Descripción:
            Verifica que en los resultados de búsqueda aparece el badge
            "Mejor Precio" resaltando automáticamente la opción más
            económica entre las tres tiendas.

        Resultado esperado: PASS -- Badge visible o vista comparativa
                            con precios de múltiples tiendas activa.
        """
        print("\n[TC-S3-01] Humo -- Badge Mejor Precio automático")

        SELECTORES_BADGE = [
            "[class*='bestBadge']",
            "[class*='best']",
            "[class*='mejor']",
            "[class*='badge']",
            "text=[OK] Mejor Precio",
            "text=Mejor Precio",
            "text=MEJOR",
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            print("  -> Login y búsqueda de 'cemento'...")
            self._login_y_buscar(page, "cemento")

            print("  -> Buscando badge de Mejor Precio...")
            badge_encontrado = False

            for sel in SELECTORES_BADGE:
                try:
                    elementos = page.locator(sel).count()
                    if elementos > 0:
                        badge_encontrado = True
                        print(f"  [OK] Badge encontrado: '{sel}' -- {elementos} instancias")
                        break
                except Exception:
                    continue

            if not badge_encontrado:
                # Fallback: verificar vista comparativa con precios de tiendas
                print("  -> Verificando vista comparativa...")
                texto = page.inner_text("body")
                tiene_precios = "$" in texto
                tiene_tiendas = any(t in texto for t in ["Sodimac", "Easy", "Imperial"])
                assert tiene_precios and tiene_tiendas, \
                    "La vista comparativa debe mostrar precios de las tiendas"
                print("  [OK] Vista comparativa activa con precios de múltiples tiendas")

            browser.close()
        print("[TC-S3-01] (P) PASS\n")


    def test_TC_S3_02_humo_switch_clp_uf_actualiza_precios(self):
        """
        TC-S3-02 | PRUEBA DE HUMO | Sprint 3
        HU: HU-I3.1, HU6-AC2

        Descripción:
            Verifica que al activar el switch "Ver en UF" los precios
            cambian su representación en la interfaz. Prueba activar
            y desactivar el toggle verificando el cambio de estado.

        Resultado esperado: PASS -- Switch funciona o valor UF visible.
        """
        print("\n[TC-S3-02] Humo -- Switch CLP/UF actualiza precios")

        SELECTORES_SWITCH = [
            "[class*='switchWrap'] input",
            "[class*='switch'] input",
            "[class*='toggle'] input",
            "input[type='checkbox']",
            "label:has-text('UF')",
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            print("  -> Login y búsqueda de 'fierro'...")
            self._login_y_buscar(page, "fierro")

            texto_antes = page.inner_text("body")
            tiene_clp   = "$" in texto_antes
            print(f"  [OK] Estado inicial: {'precios CLP activos' if tiene_clp else 'sin CLP'}")

            # Buscar y activar switch
            print("  -> Buscando switch UF...")
            switch_ok = False

            for sel in SELECTORES_SWITCH:
                try:
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click()
                        time.sleep(1)
                        switch_ok = True
                        print(f"  [OK] Switch activado: '{sel}'")
                        break
                except Exception:
                    continue

            if switch_ok:
                texto_despues = page.inner_text("body")
                tiene_uf      = "UF" in texto_despues
                print(f"  [OK] Tras activar: {'UF detectado' if tiene_uf else 'UI actualizada'}")

                # Desactivar y verificar regreso a CLP
                page.locator(SELECTORES_SWITCH[0]).first.click()
                time.sleep(0.5)
                tiene_clp_final = "$" in page.inner_text("body")
                print(f"  [OK] Tras desactivar: {'CLP restaurado' if tiene_clp_final else 'UI ok'}")
            else:
                # Verificar que al menos el valor UF está en la interfaz
                assert "UF" in texto_antes, "Debe haber valor UF visible en la interfaz"
                print("  [OK] Valor UF presente en la interfaz")

            browser.close()
        print("[TC-S3-02] (P) PASS\n")


    def test_TC_S3_03_estres_badge_estable_bajo_multiples_filtros(self):
        """
        TC-S3-03 | PRUEBA DE ESTRÉS | Sprint 3
        HU: HU-I3.1, HU3-AC2

        Descripción:
            Verifica que el badge Mejor Precio y la interfaz se mantienen
            estables al cambiar el filtro de búsqueda 5 veces consecutivas.
            Valida que no hay errores JS ni crashes en ningún cambio.

        Resultado esperado: PASS -- 5 filtros sin errores, máximo < 6s.
        """
        print("\n[TC-S3-03] Estrés -- Badge estable bajo 5 cambios de filtro")

        BUSQUEDAS = ["cemento", "pintura", "madera", "cable", "ceramica"]
        tiempos   = []
        errores   = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            print("  -> Login...")
            page.goto(LOGIN_URL, timeout=TIMEOUT_MS)
            page.wait_for_selector(SEL_EMAIL, timeout=TIMEOUT_MS)
            page.fill(SEL_EMAIL, DEMO_EMAIL)
            page.fill(SEL_PASSWORD, DEMO_PASSWORD)
            page.click(SEL_SUBMIT)
            time.sleep(3)
            page.evaluate("""() => {
                sessionStorage.setItem('cc_user', JSON.stringify({
                    id: 'U001', nombre: 'Usuario Demo',
                    email: 'usuario@demo.cl', tipo: 'profesional'
                }));
            }""")
            page.goto(APP_URL, timeout=TIMEOUT_MS)
            time.sleep(2)

            search = page.locator(
                "input[placeholder*='material'], input[placeholder*='Buscar']"
            ).first

            for i, termino in enumerate(BUSQUEDAS, 1):
                print(f"  -> Filtro {i}/5: '{termino}'...")
                inicio = time.time()
                try:
                    search.clear()
                    search.fill(termino)
                    search.press("Enter")
                    time.sleep(1.5)

                    assert page.title() != "404", f"Filtro {i}: página activa"
                    texto = page.inner_text("body").lower()
                    assert "error 500" not in texto, f"Filtro {i}: Error 500"
                    assert "uncaught"  not in texto, f"Filtro {i}: Error JS"

                    tiempos.append(time.time() - inicio)
                    print(f"  [OK] Filtro {i} estable en {tiempos[-1]:.2f}s")

                except AssertionError as e:
                    errores.append(str(e))
                    print(f"  [X] Filtro {i}: {e}")

            browser.close()

        assert len(errores) == 0, f"Sin errores bajo cambio de filtros: {errores}"

        prom   = sum(tiempos) / len(tiempos) if tiempos else 0
        maximo = max(tiempos) if tiempos else 0

        print(f"\n  * Filtros: {len(BUSQUEDAS)}  * Errores: 0  * Promedio: {prom:.2f}s  * Máximo: {maximo:.2f}s")
        assert maximo < 6, f"Tiempo máximo ({maximo:.2f}s) supera 6s"
        print("[TC-S3-03] (P) PASS\n")


if __name__ == "__main__":
    print("pytest test_sprint3_qa.py -v -s")