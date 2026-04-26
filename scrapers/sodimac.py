from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_MS = 45_000
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.8

STOP_WORDS = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "para",
    "con",
    "sin",
    "en",
    "por",
    "y",
    "o",
    "un",
    "una",
    "x",
    "tipo",
    "modelo",
    "kit",
    "set",
    "pack",
}


@dataclass
class ProductRecord:
    store: str
    name: str
    brand: str
    sku_store: str
    product_url: str
    precio_normal: int | None
    precio_internet: int | None
    precio_oferta: int | None
    precio_tarjeta: int | None
    precio_unitario: int | None = None
    unidad_medida: str | None = None
    precio_unitario_fuente: str | None = None


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_name(name: str) -> str:
    text = strip_accents(unescape(clean_text(name)).lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [token for token in text.split() if token not in STOP_WORDS and len(token) >= 3]
    return " ".join(tokens)


def token_similarity(left: str, right: str) -> int:
    if not left or not right:
        return 0
    return int(SequenceMatcher(None, left, right).ratio() * 100)


def parse_price(raw: str | int | float | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(round(float(raw)))
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def canonicalize_url(url: str, drop_all_query: bool = False) -> str:
    tracking_keys = {
        "sponsoredclickdata",
        "gclid",
        "gclsrc",
        "gbraid",
        "wbraid",
        "fbclid",
        "gad_source",
        "gad_campaignid",
        "srsltid",
        "ref",
        "source",
    }
    parsed = urlparse(clean_text(url or ""))
    if drop_all_query:
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    kept_params: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in tracking_keys or lowered.startswith("utm_"):
            continue
        kept_params.append((key, value))
    query = urlencode(kept_params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def extract_sku_from_url(product_url: str) -> str:
    path = unquote(urlparse(product_url).path)
    for pattern in [r"/articulo/\d+/[^/]+/(\d+)", r"-([0-9]{5,})/p", r"/(\d{5,})$"]:
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    return ""


def parse_sitemap_locations(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    return [clean_text(node.text) for node in root.iter() if node.tag.endswith("loc") and node.text]


def extract_slug(url: str) -> str:
    path = unquote(urlparse(url).path).strip("/")
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return ""
    slug = segments[-1]
    if slug.isdigit() and len(segments) >= 2:
        slug = segments[-2]
    return normalize_name(slug.replace("-", " "))


def url_matches_queries(url: str, normalized_queries: list[str]) -> bool:
    if not normalized_queries:
        return True
    slug = extract_slug(url)
    if not slug:
        return False

    slug_tokens = set(slug.split())
    for query in normalized_queries:
        query_tokens = set(query.split())
        if slug_tokens & query_tokens:
            return True
        if token_similarity(slug, query) >= 72:
            return True
    return False


def setup_logger(name: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Crear el directorio si no existe
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def log_failed_url(logger: logging.Logger, url: str, reason: str) -> None:
    logger.error("FAILED | url=%s | reason=%s", url, reason)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


class RobotsGuard:
    def __init__(self, user_agent: str, logger: logging.Logger) -> None:
        self.user_agent = user_agent
        self.logger = logger
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._retry_after_by_domain: dict[str, float] = {}

    @staticmethod
    def _domain_key(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_parser(self, url: str) -> RobotFileParser | None:
        domain = self._domain_key(url)
        if domain in self._parsers:
            return self._parsers[domain]

        now = time.monotonic()
        if self._retry_after_by_domain.get(domain, 0.0) > now:
            return None

        robots_url = f"{domain}/robots.txt"
        parser = RobotFileParser()
        try:
            request = Request(robots_url, headers={"User-Agent": self.user_agent})
            with urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8", errors="ignore")
            parser.set_url(robots_url)
            parser.parse(content.splitlines())
            self._parsers[domain] = parser
            self._retry_after_by_domain.pop(domain, None)
            return parser
        except Exception as exc:
            self.logger.warning("ROBOTS_UNAVAILABLE | url=%s | reason=%s", robots_url, exc)
            self._parsers[domain] = None
            self._retry_after_by_domain[domain] = now + 120
            return None

    def can_fetch(self, url: str) -> bool:
        parser = self._get_parser(url)
        if parser is None:
            return False
        try:
            return parser.can_fetch(self.user_agent, url)
        except ValueError:
            return False


class SodimacSprint1Scraper:
    store_name = "sodimac"
    base_url = "https://www.sodimac.cl"

    def __init__(self) -> None:
        self.root_dir = Path(__file__).resolve().parents[1]
        self.logger = setup_logger("sodimac_sprint1", self.root_dir / "scrapers/data/logs/craping_errors.log")
        self.robots_guard = RobotsGuard(USER_AGENT, self.logger)
        self.request_timeout_ms = REQUEST_TIMEOUT_MS

        self.sitemap_indexes = (
            "https://www.sodimac.cl/static/site/sitemaps/categories/categories_cl_SO_COM-0.xml",
        )
        self.selectors = {
            "listing_card": [
                "div[data-testid='ssr-pod']",
                "li.search-results-4-grid__item",
                "article.pod",
            ],
            "listing_name": [".pod-subTitle", "h3", "a[href*='/articulo/'] span"],
            "listing_brand": [".pod-title", "span[data-testid='brand']"],
            "listing_url": ["a.pod-link", "a[href*='/articulo/']"],
        }

    async def fetch_sitemap(self, url: str) -> str:
        if not self.robots_guard.can_fetch(url):
            log_failed_url(self.logger, url, "blocked by robots.txt")
            return ""

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return await asyncio.to_thread(self._download_text, url)
            except Exception as exc:
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                log_failed_url(self.logger, url, f"sitemap download failed: {exc}")
                return ""
        return ""

    @staticmethod
    def _download_text(url: str) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

    async def first_text(self, container: Any, selectors: Iterable[str]) -> str:
        for selector in selectors:
            try:
                element = await container.query_selector(selector)
                if not element:
                    continue
                value = clean_text(await element.inner_text())
                if value:
                    return value
            except PlaywrightError:
                continue
        return ""

    async def first_attr(self, container: Any, selectors: Iterable[str], attr: str) -> str:
        for selector in selectors:
            try:
                element = await container.query_selector(selector)
                if not element:
                    continue
                value = await element.get_attribute(attr)
                if value:
                    return clean_text(value)
            except PlaywrightError:
                continue
        return ""

    async def goto_safe(self, page: Page, url: str) -> bool:
        if not self.robots_guard.can_fetch(url):
            log_failed_url(self.logger, url, "blocked by robots.txt")
            return False

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.request_timeout_ms)
                return True
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                log_failed_url(self.logger, url, f"goto failed: {exc}")
                return False
        return False

    async def collect_category_urls(self, queries: list[str], max_category_urls: int) -> list[str]:
        normalized_queries = [normalize_name(query) for query in queries if normalize_name(query)]
        limit_categories = max_category_urls > 0
        candidates: list[str] = []
        seen: set[str] = set()

        for sitemap_url in self.sitemap_indexes:
            xml_text = await self.fetch_sitemap(sitemap_url)
            if not xml_text:
                continue
            for location in parse_sitemap_locations(xml_text):
                if location in seen:
                    continue
                seen.add(location)
                if not url_matches_queries(location, normalized_queries):
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
            prices[key] = parse_price(raw)

        return prices

    async def _find_listing_cards(self, page: Page, category_url: str) -> list[Any]:
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
        queries: list[str] | None = None,
        max_products: int = 0,
        max_category_urls: int = 0,
        headless: bool = True,
        category_workers: int = 4,
    ) -> list[ProductRecord]:
        query_values = queries or []
        category_urls = await self.collect_category_urls(query_values, max_category_urls)
        if not category_urls:
            self.logger.warning("No candidate categories found for Sodimac.")
            return []

        products: list[ProductRecord] = []
        seen_urls: set[str] = set()
        total_categories = len(category_urls)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(user_agent=USER_AGENT, locale="es-CL")

            queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
            for index, category_url in enumerate(category_urls, start=1):
                queue.put_nowait((index, category_url))

            lock = asyncio.Lock()
            stop = asyncio.Event()

            async def worker() -> None:
                page = await context.new_page()
                try:
                    while not stop.is_set():
                        try:
                            category_index, category_url = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                        try:
                            self.logger.info("CATEGORY_PROGRESS | %d/%d | %s", category_index, total_categories, category_url)
                            if not await self.goto_safe(page, category_url):
                                continue

                            cards = await self._find_listing_cards(page, category_url)
                            if not cards:
                                continue

                            for card in cards:
                                if stop.is_set():
                                    break

                                name = await self.first_text(card, self.selectors["listing_name"])
                                if not name:
                                    continue

                                raw_url = await self.first_attr(card, self.selectors["listing_url"], "href")
                                if not raw_url:
                                    continue

                                product_url = canonicalize_url(urljoin(self.base_url, raw_url), drop_all_query=True)
                                prices = await self.extract_prices(card)
                                if not any(prices.values()):
                                    continue

                                brand = await self.first_text(card, self.selectors["listing_brand"])
                                record = ProductRecord(
                                    store=self.store_name,
                                    name=name,
                                    brand=brand,
                                    sku_store=extract_sku_from_url(product_url),
                                    product_url=product_url,
                                    precio_normal=prices["precio_normal"],
                                    precio_internet=prices["precio_internet"],
                                    precio_oferta=prices["precio_oferta"],
                                    precio_tarjeta=prices["precio_tarjeta"],
                                    precio_unitario=prices["precio_unitario"],
                                    unidad_medida=prices["unidad_medida"],
                                    precio_unitario_fuente=prices["precio_unitario_fuente"],
                                )

                                async with lock:
                                    if max_products > 0 and len(products) >= max_products:
                                        stop.set()
                                        break
                                    if product_url in seen_urls:
                                        continue
                                    seen_urls.add(product_url)
                                    products.append(record)
                                    if max_products > 0 and len(products) >= max_products:
                                        stop.set()
                                        break
                        finally:
                            queue.task_done()
                finally:
                    await page.close()

            workers_count = min(max(1, category_workers), total_categories)
            workers = [asyncio.create_task(worker()) for _ in range(workers_count)]
            await asyncio.gather(*workers)
            await context.close()
            await browser.close()

        self.logger.info("Sodimac products extracted: %d", len(products))
        return products

    @staticmethod
    def deduplicate(products: list[ProductRecord]) -> list[ProductRecord]:
        seen_urls: set[str] = set()
        result: list[ProductRecord] = []
        for product in products:
            if product.product_url in seen_urls:
                continue
            seen_urls.add(product.product_url)
            result.append(product)
        return result

    @staticmethod
    def compute_metrics(products: list[ProductRecord]) -> dict[str, int | str]:
        return {
            "store": "sodimac",
            "total_products": len(products),
            "with_any_price": sum(
                1
                for p in products
                if any([p.precio_normal, p.precio_internet, p.precio_oferta, p.precio_tarjeta, p.precio_unitario])
            ),
            "with_sku": sum(1 for p in products if bool(p.sku_store)),
            "with_precio_tarjeta": sum(1 for p in products if p.precio_tarjeta is not None),
            "with_precio_unitario": sum(1 for p in products if p.precio_unitario is not None),
        }

    def write_output(self, products: list[ProductRecord], output_file: Path) -> None:
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_products": len(products),
            "metrics": self.compute_metrics(products),
            "products": [asdict(product) for product in products],
        }
        write_json_atomic(output_file, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone Sprint 1 Sodimac scraper.")
    parser.add_argument("--queries", nargs="+", default=[], help="Búsqueda de productos específicos.")
    parser.add_argument("--search-categories", type=str, default="", help="Lista de categorías separadas por coma (ej: taladro,cemento,fierro).")
    parser.add_argument("--max-products", "--max", dest="max_products", type=int, default=0)
    parser.add_argument(
        "--max-category-urls",
        "--max-categories",
        "--limit-categories",
        dest="max_category_urls",
        type=int,
        default=0,
        help="Maximo de categorias a procesar (0 = sin limite).",
    )
    parser.add_argument("--category-workers", type=int, default=4)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--output", default="scrapers/data/bronze/sodimac_products.json")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    scraper = SodimacSprint1Scraper()

    # Combinar queries normales con las categorías de búsqueda por coma
    search_queries = args.queries
    if args.search_categories:
        extra_queries = [q.strip() for q in args.search_categories.split(",") if q.strip()]
        search_queries.extend(extra_queries)

    products = await scraper.scrape(
        queries=search_queries,
        max_products=args.max_products,
        max_category_urls=args.max_category_urls,
        headless=not args.headful,
        category_workers=args.category_workers,
    )
    products = scraper.deduplicate(products)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (Path(__file__).resolve().parents[1] / output_path).resolve()

    scraper.write_output(products, output_path)
    print("=" * 60)
    print("Store: sodimac")
    print(f"Products: {len(products)}")
    print(f"Output: {output_path}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
