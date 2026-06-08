from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from core.normalizer import clean_text, normalize_name
from scrapers.base_scraper import BaseStoreScraper, ProductRecord, log_failed_url


class SodimacScraper(BaseStoreScraper):
    store_name = "sodimac"
    base_url = "https://www.sodimac.cl"

    def __init__(self) -> None:
        super().__init__()
        self.sitemap_indexes = (
            "https://www.sodimac.cl/static/site/sitemaps/categories/categories_cl_SO_COM-0.xml",
        )
        self.selectors = {
            "listing_card": [
                "div[data-testid='ssr-pod']",
                "li.search-results-4-grid__item",
                "article.pod",
            ],
            "listing_name": [
                ".pod-subTitle",
                "h3",
                "a[href*='/articulo/'] span",
            ],
            "listing_brand": [
                ".pod-title",
                "span[data-testid='brand']",
            ],
            "listing_url": [
                "a.pod-link",
                "a[href*='/articulo/']",
            ],
            "listing_image": [
                "img[id*='pod-image']",
                "div[data-testid='image'] img",
                "img[data-testid='image']",
                "picture img",
                ".pod-image img",
                "img",
            ],
        }

    async def collect_category_urls(self, queries: list[str], max_category_urls: int) -> list[str]:
        normalized_queries = [normalize_name(query) for query in queries if normalize_name(query)]
        limit_categories = max_category_urls > 0
        candidates: list[str] = []
        seen: set[str] = set()

        for sitemap_url in self.sitemap_indexes:
            xml_text = await self.fetch_sitemap(sitemap_url)
            if not xml_text:
                continue
            for location in self.parse_sitemap_locations(xml_text):
                if location in seen:
                    continue
                seen.add(location)
                if not self.url_matches_queries(location, normalized_queries):
                    continue
                candidates.append(location)
                if limit_categories and len(candidates) >= max_category_urls:
                    return candidates

        self.logger.info("Categories found for Sodimac: %d", len(candidates))
        return candidates

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
        for attr, key in [
            ("data-cmr-price", "precio_tarjeta"),
            ("data-internet-price", "precio_internet"),
            ("data-event-price", "precio_oferta"),
            ("data-normal-price", "precio_normal"),
        ]:
            raw = await self.first_attr(card, [f"li[{attr}]"], attr)
            prices[key] = self.parse_price(raw)

        unit_text = await self.first_text(
            card,
            [
                "li[data-testid='price-per-unit']",
                "span[data-testid='price-per-unit']",
                ".pod-prices__price-per-unit",
                ".pod-prices__unit-price",
                "[class*='price-per-unit']",
            ],
        )
        unit_price, unit = self.extract_unit_price_from_text(unit_text)
        if unit_price is not None and unit is not None:
            prices["precio_unitario"] = unit_price
            prices["unidad_medida"] = unit
            prices["precio_unitario_fuente"] = "listing"
            return prices

        text = clean_text(await card.inner_text())
        unit_price, unit = self.extract_unit_price_from_text(text)
        if unit_price is not None and unit is not None:
            prices["precio_unitario"] = unit_price
            prices["unidad_medida"] = unit
            prices["precio_unitario_fuente"] = "listing"

        return prices

    async def _find_listing_cards(self, page: Any, category_url: str) -> list[Any]:
        any_card_selector = ", ".join(self.selectors["listing_card"])
        try:
            await page.wait_for_selector(any_card_selector, timeout=6_000)
        except PlaywrightTimeoutError:
            return []

        for card_selector in self.selectors["listing_card"]:
            try:
                cards = await page.query_selector_all(card_selector)
                if cards:
                    return cards
            except PlaywrightError as exc:
                log_failed_url(self.logger, category_url, f"selector error: {exc}")

        return []

    async def scrape(
        self,
        queries: list[str],
        max_products: int = 0,
        max_category_urls: int = 0,
        headless: bool = True,
        category_workers: int = 4,
    ) -> list[ProductRecord]:
        self.category_hints = {}
        category_urls = await self.collect_category_urls(queries, max_category_urls=max_category_urls)
        if not category_urls:
            self.logger.warning("No candidate categories found for Sodimac.")
            return []

        products: list[ProductRecord] = []
        seen_urls: set[str] = set()
        total_categories = len(category_urls)
        safe_workers = max(1, category_workers)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(user_agent=self.user_agent, locale="es-CL")
            category_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
            for category_index, category_url in enumerate(category_urls, start=1):
                category_queue.put_nowait((category_index, category_url))

            state_lock = asyncio.Lock()
            stop_scraping = asyncio.Event()

            async def worker() -> None:
                page = await context.new_page()
                try:
                    while not stop_scraping.is_set():
                        try:
                            category_index, category_url = category_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                        try:
                            self.log_category_progress(category_index, total_categories, category_url)

                            loaded = await self.goto_safe(page, category_url)
                            if not loaded:
                                continue

                            cards = await self._find_listing_cards(page, category_url)
                            if not cards:
                                log_failed_url(self.logger, category_url, "no cards found")
                                continue

                            for _ in range(2):
                                await page.mouse.wheel(0, 1400)
                                await page.wait_for_timeout(250)

                            refreshed_cards = await page.query_selector_all(self.selectors["listing_card"][0])
                            if refreshed_cards:
                                cards = refreshed_cards

                            for card in cards:
                                if stop_scraping.is_set() or page.is_closed():
                                    break
                                try:
                                    name = await self.first_text(card, self.selectors["listing_name"])
                                    if not name:
                                        continue

                                    raw_url = await self.first_attr(card, self.selectors["listing_url"], "href")
                                    if not raw_url:
                                        continue
                                    product_url = self.canonicalize_url(
                                        urljoin(self.base_url, raw_url),
                                        drop_all_query=True,
                                    )

                                    prices = await self.extract_prices(card)
                                    if not any(prices.values()):
                                        continue

                                    brand = await self.first_text(card, self.selectors["listing_brand"])
                                    
                                    image_url = await self.extract_image_url(card, self.selectors["listing_image"])

                                    category_hint_url = self.canonicalize_url(category_url, drop_all_query=True)
                                    record = ProductRecord(
                                        store=self.store_name,
                                        name=name,
                                        brand=brand,
                                        sku_store=self.extract_sku_from_url(product_url),
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
                                        self.category_hints.setdefault(product_url, category_hint_url)
                                        products.append(record)
                                        if max_products > 0 and len(products) >= max_products:
                                            stop_scraping.set()
                                            break
                                except PlaywrightError as exc:
                                    log_failed_url(self.logger, category_url, f"card error: {exc}")
                        finally:
                            category_queue.task_done()
                finally:
                    await page.close()

            try:
                workers_count = min(safe_workers, total_categories)
                self.logger.info(
                    "Sodimac category workers started: %d | total_categories=%d",
                    workers_count,
                    total_categories,
                )
                workers = [asyncio.create_task(worker()) for _ in range(workers_count)]
                await asyncio.gather(*workers)
            finally:
                await context.close()
                await browser.close()

        self.logger.info("Sodimac products extracted: %d", len(products))
        return products

    async def _extract_pdp_prices(self, page: Any) -> dict:
        prices: dict = {
            "precio_tarjeta": None, "precio_internet": None,
            "precio_oferta": None, "precio_normal": None,
            "precio_unitario": None, "unidad_medida": None,
            "precio_unitario_fuente": None,
        }

        # Layout legacy: <li data-cmr-price="..."> etc.
        for attr, key in [
            ("data-cmr-price",      "precio_tarjeta"),
            ("data-internet-price", "precio_internet"),
            ("data-event-price",    "precio_oferta"),
            ("data-normal-price",   "precio_normal"),
        ]:
            raw = await self.first_attr(page, [f"li[{attr}]"], attr)
            prices[key] = self.parse_price(raw)

        # Layout nuevo: <div data-variant="PDP_MAIN"> con spans semánticos
        if not any([prices["precio_tarjeta"], prices["precio_internet"],
                    prices["precio_oferta"], prices["precio_normal"]]):
            internet_text = await self.first_text(page, [
                "[data-variant='PDP_MAIN'] span[class*='internetPrice']",
                "span[class*='internetPrice']",
            ])
            prices["precio_internet"] = self.parse_price(internet_text) if internet_text else None

            normal_text = await self.first_text(page, [
                "[data-variant='PDP_MAIN'] span[class*='copy12']",
                "[data-variant='PDP_MAIN'] span",
            ])
            prices["precio_normal"] = self.parse_price(normal_text) if normal_text else None

        # Precio unitario (ambos layouts)
        unit_text = await self.first_text(page, [
            "div[class*='pumPrice']",
            "li[data-testid='price-per-unit']",
            "[class*='price-per-unit']",
            "[data-variant='PDP_MAIN'] [class*='pum-price'] span",
            "[class*='pum-price'] span",
        ])
        unit_price, unit = self.extract_unit_price_from_text(unit_text)
        if unit_price is not None and unit is not None:
            prices["precio_unitario"]        = unit_price
            prices["unidad_medida"]          = unit
            prices["precio_unitario_fuente"] = "pdp"
        return prices

    async def scrape_pdp_batch(
        self,
        products: list[dict],
        headless: bool = True,
        workers: int = 4,
        on_progress: Any | None = None,
    ) -> list[dict]:
        total = len(products)
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
                            if on_progress:
                                on_progress(len(results), total)
                        queue.task_done()
                finally:
                    await page.close()

            worker_count = min(max(1, workers), len(products))
            tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
            await asyncio.gather(*tasks)
            await context.close()
            await browser.close()

        self.logger.info("Sodimac PDP batch: %d processed", len(results))
        return results
