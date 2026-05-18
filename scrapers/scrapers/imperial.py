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


class ImperialScraper(BaseStoreScraper):
    store_name = "imperial"
    base_url = "https://www.imperial.cl"

    def __init__(self) -> None:
        super().__init__()
        self.sitemap_indexes = (
            "https://www.imperial.cl/sitemap.xml",
        )
        self.selectors = {
            "listing_link": [
                "a[href*='/product/']",
                "article a[href*='/product/']",
                "main a[href*='/product/']",
            ],
            "listing_name": [
                "h1",
                "[itemprop='name']",
                ".product-name",
            ],
            "listing_image": [
                "img.osf__sc-1d18s5c-2",
                "img.osf__sc-p8pmzu-5",
                "img[src*='/products/']",
                "img.product-image",
                ".product-image img",
                "img[itemprop='image']",
                "img",
            ],
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
        first = clean_text(name).split(" ")[0].strip()
        if len(first) <= 1:
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

        normalized = clean_text(text).replace("\u00b2", "2").replace("\u00b3", "3")

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

        # Imperial frequently renders current price first, then "Normal $...".
        # If both exist and no explicit internet/oferta label is present,
        # map the extra lower product-level amount as oferta.
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

    async def _get_container_text(self, link: Any) -> str:
        try:
            container_text = await link.evaluate(
                """
                (el) => {
                    const container =
                        el.closest("li") ||
                        el.closest("article") ||
                        el.closest(".product") ||
                        el.closest(".item") ||
                        el.closest("div");
                    return container ? container.innerText : el.innerText;
                }
                """
            )
            return clean_text(container_text or "")
        except PlaywrightError:
            return ""

    async def _enrich_from_pdp(self, page: Any, product_url: str, current: dict[str, Any]) -> dict[str, Any]:
        loaded = await self.goto_safe(page, product_url)
        if not loaded:
            return current

        pdp_text = ""
        try:
            await page.wait_for_selector("body", timeout=12_000)
            pdp_text = clean_text(await page.inner_text("body"))
        except PlaywrightError:
            pdp_text = ""

        pdp_name = await self.first_text(page, self.selectors["listing_name"])
        if not pdp_name and pdp_text:
            h1_guess = re.search(r"##\s+(.+?)\s+SKU:", pdp_text)
            if h1_guess:
                pdp_name = clean_text(h1_guess.group(1))

        pdp_sku = self._extract_sku_from_text(pdp_text) if pdp_text else ""
        pdp_prices = self.extract_prices_from_text(pdp_text)
        
        pdp_img_url = await self.extract_image_url(page, self.selectors["listing_image"])

        pdp_brand = ""
        if pdp_text:
            brand_match = re.search(
                r"Marca\s*([A-Za-z0-9\-\s]{2,40}?)\s*(?:Largo|Alto|Ancho|Modelo|Unidad|Peso|Servicios|Linea|Color|$)",
                pdp_text,
                flags=re.IGNORECASE,
            )
            if brand_match:
                pdp_brand = clean_text(brand_match.group(1))
        if not pdp_brand:
            pdp_brand = self._extract_brand_from_name(pdp_name)

        merged = dict(current)
        if pdp_name:
            merged["name"] = self._extract_name_from_text(pdp_name)
        if pdp_brand:
            merged["brand"] = pdp_brand
        if pdp_sku:
            merged["sku_store"] = pdp_sku
        if pdp_img_url:
            merged["image_url"] = urljoin(self.base_url, pdp_img_url)

        for key in [
            "precio_normal",
            "precio_internet",
            "precio_oferta",
            "precio_tarjeta",
            "precio_unitario",
            "unidad_medida",
            "precio_unitario_fuente",
        ]:
            if merged.get(key) is None and pdp_prices.get(key) is not None:
                merged[key] = pdp_prices[key]

        if not merged.get("sku_store"):
            merged["sku_store"] = self.extract_sku_from_url(product_url)

        return merged

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

    async def _find_listing_links(self, page: Any, category_url: str) -> list[Any]:
        any_link_selector = ", ".join(self.selectors["listing_link"])
        try:
            await page.wait_for_selector(any_link_selector, timeout=6_000)
        except PlaywrightTimeoutError:
            return []

        for link_selector in self.selectors["listing_link"]:
            try:
                links = await page.query_selector_all(link_selector)
                if links:
                    return links
            except PlaywrightError as exc:
                log_failed_url(self.logger, category_url, f"selector error: {exc}")

        return []

    async def scrape(
        self,
        queries: list[str],
        max_products: int = 0,
        max_category_urls: int = 0,
        headless: bool = True,
        fallback_pdp: bool = True,
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
                pdp_page = await context.new_page()

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

                            links = await self._find_listing_links(page, category_url)

                            if not links:
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

                                log_failed_url(self.logger, category_url, "no product links found")
                                continue

                            for _ in range(2):
                                await page.mouse.wheel(0, 1800)
                                await page.wait_for_timeout(300)

                            refreshed = await page.query_selector_all(self.selectors["listing_link"][0])
                            if refreshed:
                                links = refreshed

                            for link in links:
                                if stop_scraping.is_set():
                                    break
                                try:
                                    raw_url = await link.get_attribute("href")
                                    if not raw_url:
                                        continue

                                    product_url = self.canonicalize_url(
                                        self._clean_url(urljoin(self.base_url, raw_url)),
                                        drop_all_query=True,
                                    )
                                    if not self._is_product_url(product_url):
                                        continue

                                    link_text = clean_text(await link.inner_text())
                                    if not link_text:
                                        image = await link.query_selector("img[alt]")
                                        if image:
                                            link_text = clean_text(await image.get_attribute("alt") or "")

                                    container_text = await self._get_container_text(link)
                                    combined_text = clean_text(f"{link_text} {container_text}")

                                    name = self._extract_name_from_text(link_text)
                                    if not name and container_text:
                                        name = self._extract_name_from_text(container_text)

                                    prices = self.extract_prices_from_text(combined_text)
                                    sku_store = (
                                        self._extract_sku_from_text(container_text)
                                        or self.extract_sku_from_url(product_url)
                                    )
                                    brand = self._extract_brand_from_name(name)
                                    
                                    image_url = await self.extract_image_url(link, self.selectors["listing_image"])

                                    current: dict[str, Any] = {
                                        "name": name,
                                        "brand": brand,
                                        "sku_store": sku_store,
                                        "precio_normal": prices["precio_normal"],
                                        "precio_internet": prices["precio_internet"],
                                        "precio_oferta": prices["precio_oferta"],
                                        "precio_tarjeta": prices["precio_tarjeta"],
                                        "precio_unitario": prices["precio_unitario"],
                                        "unidad_medida": prices["unidad_medida"],
                                        "precio_unitario_fuente": prices["precio_unitario_fuente"],
                                        "image_url": image_url,
                                    }

                                    has_any_price = any(
                                        [
                                            current["precio_normal"],
                                            current["precio_internet"],
                                            current["precio_oferta"],
                                            current["precio_tarjeta"],
                                            current["precio_unitario"],
                                        ]
                                    )

                                    needs_pdp = fallback_pdp and (
                                        not current["name"]
                                        or not current["sku_store"]
                                        or not has_any_price
                                        or not current["image_url"]
                                    )

                                    if needs_pdp:
                                        current = await self._enrich_from_pdp(pdp_page, product_url, current)

                                    if (
                                        current["precio_normal"] is None
                                        and current["precio_internet"] is None
                                        and current["precio_oferta"] is None
                                        and current["precio_tarjeta"] is None
                                        and current["precio_unitario"] is None
                                    ):
                                        continue

                                    if not current["name"]:
                                        slug = (
                                            unquote(urlparse(product_url).path)
                                            .split("/product/", 1)[0]
                                            .split("/")[-1]
                                        )
                                        current["name"] = clean_text(slug.replace("-", " "))
                                    if not current["sku_store"]:
                                        current["sku_store"] = self.extract_sku_from_url(product_url)

                                    record = ProductRecord(
                                        store=self.store_name,
                                        name=current["name"],
                                        brand=current["brand"] or "",
                                        sku_store=current["sku_store"] or "",
                                        product_url=product_url,
                                        precio_normal=current["precio_normal"],
                                        precio_internet=current["precio_internet"],
                                        precio_oferta=current["precio_oferta"],
                                        precio_tarjeta=current["precio_tarjeta"],
                                        precio_unitario=current["precio_unitario"],
                                        unidad_medida=current["unidad_medida"],
                                        precio_unitario_fuente=current["precio_unitario_fuente"],
                                        image_url=current["image_url"],
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
                    for closer in (pdp_page.close, page.close):
                        try:
                            await closer()
                        except PlaywrightError:
                            continue

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
