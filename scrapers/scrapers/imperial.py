from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote_plus, unquote, urljoin, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from core.normalizer import clean_text, normalize_name
from scrapers.base_scraper import BaseStoreScraper, ProductRecord
from scrapers.base_scraper import log_failed_url

_PRODUCT_TYPE_WORDS = frozenset({
    "cemento", "tornillo", "clavo", "pintura", "fierro", "tubo", "pvc",
    "madera", "placa", "ladrillo", "mortero", "adhesivo", "sellador",
    "taladro", "sierra", "disco", "electrodo", "cable", "tuberia", "malla",
    "bisagra", "cerradura", "llave", "griferia", "teja", "panel", "perfil",
    "angulo", "canal", "lija", "brocha", "rodillo", "impermeabilizante",
    "hormigon", "arena", "piedra", "cal", "yeso", "ceramica", "porcelanato",
    "grifo", "cinta", "espuma", "silicona", "foco", "lampara", "interruptor",
    "enchufe", "breaker", "tablero", "varilla", "alambre", "candado", "perno",
    "tuerca", "arandela", "remache", "anclaje", "taco", "fijacion", "producto",
    "pincel", "impermeabilizante", "cañeria", "union", "codo", "reduccion",
    "soporte", "grapas", "grapa", "taco", "peldaño", "escalera",
})


class ImperialScraper(BaseStoreScraper):
    store_name = "imperial"
    base_url = "https://www.imperial.cl"

    def __init__(self) -> None:
        super().__init__()
        self.sitemap_indexes = (
            "https://www.imperial.cl/sitemap.xml",
        )
        self.selectors = {
            "listing_card":         "div.osf__sc-1d18s5c-0",
            "listing_url":          "a.osf__sc-1d18s5c-3[href*='/product/']",
            "listing_name":         "h2.osf__sc-1d18s5c-4",
            "listing_brand":        "small.osf__sc-1d18s5c-5",
            "listing_sku":          "p.osf__sc-1d18s5c-13 strong",
            "listing_image":        "img.osf__sc-1d18s5c-2",
            "listing_offer_price":  "p.bqUKNq",
            "listing_normal_price": "p.fJeIUt",
            "listing_unavailable":  "button[disabled]",
        }

    @staticmethod
    def _is_sitemap_url(url: str) -> bool:
        return url.lower().endswith(".xml")

    @staticmethod
    def _is_category_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.query:
            return False
        return "/category/" in parsed.path.lower()

    @staticmethod
    def _is_product_url(url: str) -> bool:
        return "/product/" in urlparse(url).path.lower()

    @staticmethod
    def _clean_url(url: str) -> str:
        return url.split("#", 1)[0].split("?", 1)[0]

    @staticmethod
    def _extract_category_slug(url: str) -> str:
        path = unquote(urlparse(url).path).strip("/")
        if "/category/" in path:
            left = path.split("/category/", 1)[0]
            slug = left.split("/")[-1] if left else ""
            return normalize_name(slug.replace("-", " "))
        slug = path.split("/")[-1] if path else ""
        return normalize_name(slug.replace("-", " "))

    @classmethod
    def _category_matches_queries(cls, url: str, normalized_queries: list[str]) -> bool:
        if not normalized_queries:
            return True

        slug = cls._extract_category_slug(url)
        if not slug:
            return False

        slug_tokens = set(slug.split())
        for query in normalized_queries:
            query_tokens = set(query.split())
            if slug_tokens & query_tokens:
                return True
            if query in slug:
                return True
        return False

    def _build_query_fallback_urls(self, queries: list[str]) -> list[str]:
        fallback_urls: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = normalize_name(query)
            if not normalized:
                continue
            url = f"{self.base_url}/search?q={quote_plus(normalized)}"
            if url in seen:
                continue
            seen.add(url)
            fallback_urls.append(url)
        return fallback_urls

    async def collect_category_urls(self, queries: list[str], max_category_urls: int) -> list[str]:
        normalized_queries = [normalize_name(query) for query in queries if normalize_name(query)]
        limit_categories = max_category_urls > 0

        sitemap_queue = list(self.sitemap_indexes)
        visited_sitemaps: set[str] = set()
        seen_categories: set[str] = set()
        category_urls: list[str] = []

        while sitemap_queue and (not limit_categories or len(category_urls) < max_category_urls):
            sitemap_url = sitemap_queue.pop(0)
            if sitemap_url in visited_sitemaps:
                continue
            visited_sitemaps.add(sitemap_url)

            xml_text = await self.fetch_sitemap(sitemap_url)
            if not xml_text:
                continue

            for location in self.parse_sitemap_locations(xml_text):
                if location in visited_sitemaps:
                    continue

                if self._is_sitemap_url(location):
                    sitemap_queue.append(location)
                    continue

                if not location.startswith(self.base_url):
                    continue
                if not self._is_category_url(location):
                    continue
                if not self._category_matches_queries(location, normalized_queries):
                    continue
                if location in seen_categories:
                    continue

                seen_categories.add(location)
                category_urls.append(location)
                if limit_categories and len(category_urls) >= max_category_urls:
                    break

        if not limit_categories or len(category_urls) < max_category_urls:
            for fallback_url in self._build_query_fallback_urls(queries):
                if fallback_url in seen_categories:
                    continue
                seen_categories.add(fallback_url)
                category_urls.append(fallback_url)
                if limit_categories and len(category_urls) >= max_category_urls:
                    break

        self.logger.info("Categories found for Imperial: %d", len(category_urls))
        return category_urls

    @staticmethod
    def _extract_name_from_text(text: str) -> str:
        if not text:
            return ""
        cleaned = clean_text(text)
        cleaned = re.sub(r"^\s*\d+%\s*dcto\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*products?\s+", "", cleaned, flags=re.IGNORECASE)
        return clean_text(cleaned)

    @staticmethod
    def _extract_brand_from_name(name: str) -> str:
        if not name:
            return ""
        parts = clean_text(name).split()
        if not parts:
            return ""
        first = parts[0].strip()
        if len(first) <= 1 or first.lower() in _PRODUCT_TYPE_WORDS:
            return ""
        return first

    @staticmethod
    def _extract_sku_from_text(text: str) -> str:
        if not text:
            return ""
        match = re.search(r"\bSKU\s*:\s*([0-9]{3,})\b", text, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    def extract_prices_from_text(self, text: str) -> dict[str, int | str | None]:
        prices: dict[str, int | str | None] = {
            "precio_tarjeta": None,
            "precio_internet": None,
            "precio_oferta": None,
            "precio_normal": None,
            "precio_unitario": None,
            "unidad_medida": None,
            "precio_unitario_fuente": None,
        }
        if not text:
            return prices

        normalized = clean_text(text).replace("²", "2").replace("³", "3")

        normal_match = re.search(r"\bNormal\b\s*:?\s*\$\s*([\d\.,]+)", normalized, flags=re.IGNORECASE)
        if normal_match:
            prices["precio_normal"] = self.parse_price(normal_match.group(1))

        internet_match = re.search(
            r"\b(?:Internet|Online)\b\s*:?\s*\$\s*([\d\.,]+)",
            normalized,
            flags=re.IGNORECASE,
        )
        if internet_match:
            prices["precio_internet"] = self.parse_price(internet_match.group(1))

        oferta_match = re.search(
            r"\b(?:Oferta|Promo(?:cion)?)\b\s*:?\s*\$\s*([\d\.,]+)",
            normalized,
            flags=re.IGNORECASE,
        )
        if oferta_match:
            prices["precio_oferta"] = self.parse_price(oferta_match.group(1))

        tarjeta_match = re.search(
            r"\b(?:Tarjeta|Credito|CMR)\b[^\$]{0,40}\$\s*([\d\.,]+)",
            normalized,
            flags=re.IGNORECASE,
        )
        if tarjeta_match:
            prices["precio_tarjeta"] = self.parse_price(tarjeta_match.group(1))

        unit_price, unit = self.extract_unit_price_from_text(normalized)
        if unit_price is not None and unit is not None:
            prices["precio_unitario"] = unit_price
            prices["unidad_medida"] = unit
            prices["precio_unitario_fuente"] = "listing"

        amounts = [self.parse_price(v) for v in re.findall(r"\$\s*[\d\.,]+", normalized)]
        amounts = [v for v in amounts if v is not None]

        remaining = list(amounts)
        for used_value in [
            prices["precio_normal"],
            prices["precio_internet"],
            prices["precio_oferta"],
            prices["precio_tarjeta"],
            prices["precio_unitario"],
        ]:
            if used_value is None:
                continue
            removed = False
            filtered: list[int] = []
            for amount in remaining:
                if not removed and amount == used_value:
                    removed = True
                    continue
                filtered.append(amount)
            remaining = filtered

        if (
            prices["precio_oferta"] is None
            and prices["precio_internet"] is None
            and prices["precio_normal"] is not None
            and remaining
        ):
            normal_value = prices["precio_normal"]
            candidate = min(remaining)
            if candidate < normal_value:
                prices["precio_oferta"] = candidate

        if prices["precio_normal"] is None and remaining:
            prices["precio_normal"] = remaining[0]

        if (
            prices["precio_normal"] is not None
            and prices["precio_oferta"] is not None
            and prices["precio_oferta"] > prices["precio_normal"]
        ):
            prices["precio_oferta"] = None

        return prices

    async def extract_prices(self, card: Any) -> dict[str, int | str | None]:
        prices: dict[str, int | str | None] = {
            "precio_tarjeta": None,
            "precio_internet": None,
            "precio_oferta": None,
            "precio_normal": None,
            "precio_unitario": None,
            "unidad_medida": None,
            "precio_unitario_fuente": None,
        }
        offer_text = await self.first_text(card, [self.selectors["listing_offer_price"]])
        if offer_text:
            prices["precio_oferta"] = self.parse_price(offer_text)

        normal_text = await self.first_text(card, [self.selectors["listing_normal_price"]])
        if normal_text:
            prices["precio_normal"] = self.parse_price(normal_text)

        # Si sólo hay un precio visible, promover oferta → normal
        if prices["precio_normal"] is None and prices["precio_oferta"] is not None:
            prices["precio_normal"] = prices["precio_oferta"]
            prices["precio_oferta"] = None

        return prices

    async def _extract_child_category_urls(self, page: Any, current_url: str) -> list[str]:
        try:
            hrefs = await page.eval_on_selector_all(
                "a[href*='/category/']",
                "els => els.map((e) => e.getAttribute('href') || '').filter(Boolean)",
            )
        except PlaywrightError:
            return []

        current_clean = self.canonicalize_url(current_url, drop_all_query=True)
        seen: set[str] = set()
        result: list[str] = []
        for href in hrefs:
            candidate = self.canonicalize_url(urljoin(self.base_url, href), drop_all_query=True)
            if candidate == current_clean:
                continue
            if not candidate.startswith(self.base_url):
                continue
            if not self._is_category_url(candidate):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            result.append(candidate)
        return result

    async def _find_listing_cards(self, page: Any, category_url: str) -> list[Any]:
        try:
            await page.wait_for_selector(self.selectors["listing_card"], timeout=6_000)
        except PlaywrightTimeoutError:
            return []
        try:
            return await page.query_selector_all(self.selectors["listing_card"])
        except PlaywrightError as exc:
            log_failed_url(self.logger, category_url, f"selector error: {exc}")
            return []

    async def scrape(
        self,
        queries: list[str],
        max_products: int = 0,
        max_category_urls: int = 0,
        headless: bool = True,
        category_workers: int = 3,
    ) -> list[ProductRecord]:
        self.category_hints = {}
        category_urls = await self.collect_category_urls(queries, max_category_urls=max_category_urls)
        if not category_urls:
            self.logger.warning("No candidate categories found for Imperial.")
            return []

        products: list[ProductRecord] = []
        seen_urls: set[str] = set()
        safe_workers = max(1, category_workers)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(user_agent=self.user_agent, locale="es-CL")
            category_queue: asyncio.Queue[str | None] = asyncio.Queue()
            seen_categories: set[str] = set()
            for category_url in category_urls:
                if category_url in seen_categories:
                    continue
                seen_categories.add(category_url)
                category_queue.put_nowait(category_url)

            state_lock = asyncio.Lock()
            stop_scraping = asyncio.Event()
            processed_categories = 0

            async def worker() -> None:
                nonlocal processed_categories
                page = await context.new_page()

                try:
                    while True:
                        category_url = await category_queue.get()
                        if category_url is None:
                            category_queue.task_done()
                            break

                        try:
                            if stop_scraping.is_set():
                                continue

                            async with state_lock:
                                processed_categories += 1
                                completed_categories = processed_categories
                                total_categories = len(seen_categories)
                            self.log_category_progress(completed_categories, total_categories, category_url)

                            if max_products > 0:
                                async with state_lock:
                                    if len(products) >= max_products:
                                        stop_scraping.set()
                                        continue

                            loaded = await self.goto_safe(page, category_url)
                            if not loaded:
                                continue

                            cards = await self._find_listing_cards(page, category_url)

                            if not cards:
                                child_categories = await self._extract_child_category_urls(page, category_url)
                                new_children = 0
                                async with state_lock:
                                    for child_url in child_categories:
                                        if child_url in seen_categories:
                                            continue
                                        seen_categories.add(child_url)
                                        category_queue.put_nowait(child_url)
                                        new_children += 1

                                if new_children:
                                    self.logger.info(
                                        "Expanded Imperial category tree | parent=%s | children_added=%d",
                                        category_url,
                                        new_children,
                                    )
                                    continue

                                log_failed_url(self.logger, category_url, "no product cards found")
                                continue

                            for _ in range(2):
                                await page.mouse.wheel(0, 1800)
                                await page.wait_for_timeout(300)

                            refreshed = await page.query_selector_all(self.selectors["listing_card"])
                            if refreshed:
                                cards = refreshed

                            for card in cards:
                                if stop_scraping.is_set():
                                    break
                                try:
                                    link_el = await card.query_selector(self.selectors["listing_url"])
                                    if not link_el:
                                        continue

                                    raw_url = await link_el.get_attribute("href")
                                    if not raw_url:
                                        continue

                                    product_url = self.canonicalize_url(
                                        self._clean_url(urljoin(self.base_url, raw_url)),
                                        drop_all_query=True,
                                    )
                                    if not self._is_product_url(product_url):
                                        continue

                                    unavailable_btn = await card.query_selector(self.selectors["listing_unavailable"])
                                    if unavailable_btn:
                                        continue

                                    name_raw = await self.first_text(card, [self.selectors["listing_name"]])
                                    name = self._extract_name_from_text(name_raw) if name_raw else ""

                                    brand = clean_text(
                                        await self.first_text(card, [self.selectors["listing_brand"]]) or ""
                                    )
                                    if not brand:
                                        brand = self._extract_brand_from_name(name)

                                    sku_raw = clean_text(
                                        await self.first_text(card, [self.selectors["listing_sku"]]) or ""
                                    )
                                    sku_store = sku_raw or self.extract_sku_from_url(product_url)

                                    prices = await self.extract_prices(card)
                                    if not any([
                                        prices["precio_normal"],
                                        prices["precio_internet"],
                                        prices["precio_oferta"],
                                        prices["precio_tarjeta"],
                                        prices["precio_unitario"],
                                    ]):
                                        continue

                                    if not name:
                                        slug = (
                                            unquote(urlparse(product_url).path)
                                            .split("/product/", 1)[0]
                                            .split("/")[-1]
                                        )
                                        name = clean_text(slug.replace("-", " "))

                                    image_url = await self.extract_image_url(
                                        card, [self.selectors["listing_image"]]
                                    )

                                    record = ProductRecord(
                                        store=self.store_name,
                                        name=name,
                                        brand=brand,
                                        sku_store=sku_store,
                                        product_url=product_url,
                                        precio_normal=prices["precio_normal"],
                                        precio_internet=prices["precio_internet"],
                                        precio_oferta=prices["precio_oferta"],
                                        precio_tarjeta=prices["precio_tarjeta"],
                                        precio_unitario=prices["precio_unitario"],
                                        unidad_medida=prices["unidad_medida"],
                                        precio_unitario_fuente=prices["precio_unitario_fuente"],
                                        image_url=image_url,
                                    )

                                    async with state_lock:
                                        if max_products > 0 and len(products) >= max_products:
                                            stop_scraping.set()
                                            break
                                        if product_url in seen_urls:
                                            continue
                                        seen_urls.add(product_url)
                                        self.category_hints.setdefault(
                                            product_url,
                                            self.canonicalize_url(category_url, drop_all_query=True),
                                        )
                                        products.append(record)
                                        if max_products > 0 and len(products) >= max_products:
                                            stop_scraping.set()
                                            break
                                except PlaywrightError as exc:
                                    log_failed_url(self.logger, category_url, f"card error: {exc}")
                        finally:
                            category_queue.task_done()
                finally:
                    try:
                        await page.close()
                    except PlaywrightError:
                        pass

            try:
                workers_count = min(safe_workers, max(1, len(seen_categories)))
                self.logger.info(
                    "Imperial category workers started: %d | initial_categories=%d",
                    workers_count,
                    len(seen_categories),
                )
                workers = [asyncio.create_task(worker()) for _ in range(workers_count)]
                await category_queue.join()
                for _ in range(workers_count):
                    category_queue.put_nowait(None)
                await asyncio.gather(*workers)
            finally:
                for closer in (context.close, browser.close):
                    try:
                        await closer()
                    except PlaywrightError:
                        continue

        self.logger.info("Imperial products extracted: %d", len(products))
        return products

    async def _extract_pdp_prices(self, page: Any) -> dict:
        text = ""
        for sel in ["div[class*='osf__sc-1kvhwj2']", "main", "body"]:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = clean_text(await el.inner_text())
                    break
            except PlaywrightError:
                pass
        return self.extract_prices_from_text(text)

    async def scrape_pdp_batch(
        self,
        products: list[dict],
        headless: bool = True,
        workers: int = 4,
    ) -> list[dict]:
        results: list[dict] = []
        queue: asyncio.Queue = asyncio.Queue()
        for product in products:
            queue.put_nowait(product)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(user_agent=self.user_agent, locale="es-CL")
            lock = asyncio.Lock()

            async def worker() -> None:
                page = await context.new_page()
                try:
                    while True:
                        try:
                            product = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        url = product.get("product_url", "")
                        try:
                            loaded = await self.goto_safe(page, url)
                            if not loaded:
                                result = {**product, "disponibilidad": False}
                            else:
                                prices = await self._extract_pdp_prices(page)
                                has_price = any(
                                    prices.get(k) for k in
                                    ["precio_normal", "precio_internet", "precio_oferta",
                                     "precio_tarjeta", "precio_unitario"]
                                )
                                result = {**product, **prices, "disponibilidad": has_price}
                        except Exception as exc:
                            self.logger.error("PDP error | url=%s | %s", url, exc)
                            result = {**product, "disponibilidad": False}
                        async with lock:
                            results.append(result)
                        queue.task_done()
                finally:
                    try:
                        await page.close()
                    except PlaywrightError:
                        pass

            worker_count = min(max(1, workers), len(products))
            tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
            await asyncio.gather(*tasks)
            for closer in (context.close, browser.close):
                try:
                    await closer()
                except PlaywrightError:
                    pass

        self.logger.info("Imperial PDP batch: %d processed", len(results))
        return results
