from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from core.normalizer import clean_text, normalize_name
from scrapers.base_scraper import BaseStoreScraper, ProductRecord, log_failed_url



class EasyScraper(BaseStoreScraper):
    store_name = "easy"
    base_url = "https://www.easy.cl"

    def __init__(self) -> None:
        super().__init__()
        self.sitemap_indexes = (
            "https://www.easy.cl/sitemap.xml",
        )
        self.selectors = {
            "listing_card": [
                "[data-testid='products-plp'] a[href*='/p']",
                "a.sc-94b513d4-38[href$='/p']",
                "main a[href*='/p']",
                "a[href*='/p']",
            ],
            "listing_name": [
                "span[data-id^='product-name-']",
                "img[alt]",
            ],
            "listing_brand": [
                "span[data-id^='product-brand-']",
            ],
            "listing_url": [
                "a[href$='/p']",
            ],
            "listing_image": [
                "img[data-nimg]",
                "img[alt][src*='/arquivos/ids/']",
                "img[data-id^='product-image-']",
                "img",
            ],
        }

    @staticmethod
    def _is_sitemap_url(url: str) -> bool:
        return url.lower().endswith(".xml")

    @staticmethod
    def _is_listing_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.query:
            return False
        path = parsed.path.lower().strip("/")
        if not path:
            return False
        if path.endswith("/p") or "/p/" in path:
            return False
        return True

    @staticmethod
    def _is_product_url(url: str) -> bool:
        path = urlparse(url).path.lower().strip("/")
        if not path:
            return False

        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            return False

        # Easy product URLs end with a single trailing /p segment.
        return parts[-1] == "p" and parts[-2] != "p"

    @staticmethod
    def _normalize_product_url(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path

        # Some listing cards expose duplicated suffixes like /p/p.
        while path.lower().endswith("/p/p"):
            path = path[:-2]

        return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))

    def _is_disallowed_pattern(self, url: str) -> bool:
        lowered = url.lower()
        parsed = urlparse(lowered)

        for blocked_prefix in [
            "/_next/",
            "/login/",
            "/checkout/",
            "/quick-view/",
            "/espiar/",
            "/tienda/",
            "/cluster/",
            "/eventos/",
            "/account/",
        ]:
            if parsed.path.startswith(blocked_prefix):
                return True

        if "/filter/" in parsed.path:
            return True

        blocked_params = {
            "sort",
            "shop",
            "page",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "utm_id",
            "gclid",
            "gclsrc",
            "gbraid",
            "wbraid",
            "gad_source",
            "gad_campaignid",
            "fbclid",
            "fbadid",
            "srsltid",
            "ref",
            "idsku",
            "skuid",
        }
        if parsed.query:
            params = set(re.findall(r"([a-z0-9_]+)=", parsed.query))
            if params & blocked_params:
                return True

        return False

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
                if self._is_disallowed_pattern(location):
                    continue
                if not self._is_listing_url(location):
                    continue
                if not self.url_matches_queries(location, normalized_queries):
                    continue
                if location in seen_categories:
                    continue

                seen_categories.add(location)
                category_urls.append(location)
                if limit_categories and len(category_urls) >= max_category_urls:
                    break

        self.logger.info("Categories found for Easy: %d", len(category_urls))
        return category_urls

    async def _read_name(self, card: Any) -> str:
        name = await self.first_text(card, ["span[data-id^='product-name-']"])
        if name:
            return name

        image = await card.query_selector("img[alt]")
        if image:
            raw_alt = await image.get_attribute("alt")
            cleaned = clean_text(raw_alt or "")
            if cleaned:
                return cleaned

        return ""

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

        text = clean_text(await card.inner_text())
        if not text:
            return prices

        # Detect dual-unit blocks like "$ 19.990 m2 | $ 57.571 Caja".
        normalized_dual_text = text.replace("²", "2").replace("³", "3")
        compact_m2_caja_match = re.search(
            r"\$\s*([\d\.\,]+)\s*(m(?:2|3))\s*(?:\|\s*)?caja\s*:\s*\$\s*([\d\.\,]+)",
            normalized_dual_text,
            flags=re.IGNORECASE,
        )
        if compact_m2_caja_match:
            unit_amount = self.parse_price(compact_m2_caja_match.group(1))
            unit_label = self.normalize_unit(compact_m2_caja_match.group(2))
            caja_amount = self.parse_price(compact_m2_caja_match.group(3))
            if unit_amount is not None and unit_label is not None and caja_amount is not None:
                prices["precio_unitario"] = unit_amount
                prices["unidad_medida"] = unit_label
                prices["precio_unitario_fuente"] = "listing"
                prices["precio_normal"] = caja_amount

        dual_unit_matches = list(
            re.finditer(
                r"\$\s*([\d\.\,]+)\s*(m(?:2|3)?|kg|kgs?|kilos?|kilo|gr|gramos?|g|lt|lts?|litros?|litro|ml|un(?:idad(?:es)?)?|u|caja(?:s)?)\b",
                normalized_dual_text,
                flags=re.IGNORECASE,
            )
        )
        dual_caja_amount: int | None = None
        dual_unit_amount: int | None = None
        dual_unit_label: str | None = None
        for match in dual_unit_matches:
            amount = self.parse_price(match.group(1))
            raw_unit = clean_text(match.group(2)).lower()
            if amount is None:
                continue
            if raw_unit.startswith("caja") and dual_caja_amount is None:
                dual_caja_amount = amount
                continue
            normalized_unit = self.normalize_unit(raw_unit)
            if normalized_unit and dual_unit_amount is None:
                dual_unit_amount = amount
                dual_unit_label = normalized_unit

        if (
            prices["precio_normal"] is None
            and prices["precio_unitario"] is None
            and dual_caja_amount is not None
            and dual_unit_amount is not None
            and dual_unit_label is not None
        ):
            prices["precio_normal"] = dual_caja_amount
            prices["precio_unitario"] = dual_unit_amount
            prices["unidad_medida"] = dual_unit_label
            prices["precio_unitario_fuente"] = "listing"

        unit_price, unit = self.extract_unit_price_from_text(text)
        if prices["precio_unitario"] is None and unit_price is not None and unit is not None:
            prices["precio_unitario"] = unit_price
            prices["unidad_medida"] = unit
            prices["precio_unitario_fuente"] = "listing"

        normal_match = re.search(r"Normal:\s*\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        if prices["precio_normal"] is None and normal_match:
            prices["precio_normal"] = self.parse_price(normal_match.group(1))

        internet_match = re.search(r"(?:Internet|Online):\s*\$\s*([\d\.\,]+)", text, flags=re.IGNORECASE)
        if internet_match:
            prices["precio_internet"] = self.parse_price(internet_match.group(1))

        card_labeled_match = re.search(
            r"(?:CAT|CMR|Cencosud|Tarjeta)[^\$]{0,24}\$\s*([\d\.\,]+)",
            text,
            flags=re.IGNORECASE,
        )
        if card_labeled_match:
            prices["precio_tarjeta"] = self.parse_price(card_labeled_match.group(1))

        all_amounts_raw = re.findall(r"\$\s*[\d\.\,]+", text)
        all_amounts = [self.parse_price(value) for value in all_amounts_raw]
        all_amounts = [value for value in all_amounts if value is not None]
        if not all_amounts:
            return prices

        remaining_amounts = list(all_amounts)
        if prices["precio_normal"] is not None:
            removed = False
            filtered: list[int] = []
            for amount in remaining_amounts:
                if not removed and amount == prices["precio_normal"]:
                    removed = True
                    continue
                filtered.append(amount)
            remaining_amounts = filtered

        if prices["precio_internet"] is not None:
            removed = False
            filtered: list[int] = []
            for amount in remaining_amounts:
                if not removed and amount == prices["precio_internet"]:
                    removed = True
                    continue
                filtered.append(amount)
            remaining_amounts = filtered

        # Exclude per-unit amount from product-level price inference.
        if prices["precio_unitario"] is not None:
            removed = False
            filtered: list[int] = []
            for amount in remaining_amounts:
                if not removed and amount == prices["precio_unitario"]:
                    removed = True
                    continue
                filtered.append(amount)
            remaining_amounts = filtered

        # Exclude caja price from product-level inference when dual-unit block was detected.
        if dual_caja_amount is not None:
            removed = False
            filtered: list[int] = []
            for amount in remaining_amounts:
                if not removed and amount == dual_caja_amount:
                    removed = True
                    continue
                filtered.append(amount)
            remaining_amounts = filtered

        has_cencosud_badge = bool(
            await card.query_selector(
                "svg[data-testid='CAT-icon'], [data-testid='CAT-icon'], [class*='cat-icon']"
            )
        )
        has_card_text_signal = bool(re.search(r"\b(?:cat|cmr|cencosud|tarjeta)\b", text, flags=re.IGNORECASE))
        if prices["precio_tarjeta"] is None and (has_cencosud_badge or has_card_text_signal) and remaining_amounts:
            candidate = min(remaining_amounts)
            prices["precio_tarjeta"] = candidate

            removed = False
            filtered: list[int] = []
            for amount in remaining_amounts:
                if not removed and amount == candidate:
                    removed = True
                    continue
                filtered.append(amount)
            remaining_amounts = filtered

        if prices["precio_normal"] is None and prices["precio_tarjeta"] is None and len(remaining_amounts) == 1:
            prices["precio_normal"] = remaining_amounts[0]
            return prices

        if prices["precio_normal"] is not None and remaining_amounts:
            prices["precio_oferta"] = remaining_amounts[0]
        elif prices["precio_normal"] is None and remaining_amounts:
            prices["precio_normal"] = remaining_amounts[0]
            if len(remaining_amounts) > 1:
                prices["precio_oferta"] = remaining_amounts[1]

        if (
            prices["precio_normal"] is not None
            and prices["precio_oferta"] is not None
            and prices["precio_oferta"] > prices["precio_normal"]
        ):
            self.logger.warning(
                "Easy pricing fallback produced oferta > normal; dropping oferta (normal=%s, oferta=%s)",
                prices["precio_normal"],
                prices["precio_oferta"],
            )
            prices["precio_oferta"] = None

        return prices

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
            self.logger.warning("No candidate categories found for Easy.")
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
                                try:
                                    await page.wait_for_load_state("networkidle", timeout=8_000)
                                except PlaywrightError:
                                    pass

                                for _ in range(2):
                                    await page.mouse.wheel(0, 1800)
                                    await page.wait_for_timeout(350)

                                for fallback_selector in ["main a[href*='/p']", "a[href*='/p']"]:
                                    try:
                                        cards = await page.query_selector_all(fallback_selector)
                                        if cards:
                                            break
                                    except PlaywrightError:
                                        continue

                            if not cards:
                                log_failed_url(self.logger, category_url, "no cards found")
                                continue

                            for _ in range(2):
                                await page.mouse.wheel(0, 1800)
                                await page.wait_for_timeout(350)

                            refreshed_cards = await page.query_selector_all(self.selectors["listing_card"][0])
                            if refreshed_cards:
                                cards = refreshed_cards

                            for card in cards:
                                if stop_scraping.is_set():
                                    break
                                try:
                                    raw_url = await card.get_attribute("href")
                                    if not raw_url:
                                        raw_url = await self.first_attr(card, self.selectors["listing_url"], "href")
                                    if not raw_url:
                                        continue

                                    product_url = self.canonicalize_url(
                                        urljoin(self.base_url, raw_url),
                                        drop_all_query=True,
                                    )
                                    product_url = self._normalize_product_url(product_url)
                                    if not self._is_product_url(product_url):
                                        continue

                                    name = await self._read_name(card)
                                    if not name:
                                        continue

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
                    try:
                        await page.close()
                    except PlaywrightError:
                        pass

            try:
                workers_count = min(safe_workers, total_categories)
                self.logger.info(
                    "Easy category workers started: %d | total_categories=%d",
                    workers_count,
                    total_categories,
                )
                workers = [asyncio.create_task(worker()) for _ in range(workers_count)]
                await asyncio.gather(*workers)
            finally:
                for closer in (context.close, browser.close):
                    try:
                        await closer()
                    except PlaywrightError:
                        continue

        self.logger.info("Easy products extracted: %d", len(products))
        return products
