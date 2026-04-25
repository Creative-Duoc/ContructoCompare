from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from core.matching import token_similarity
from core.normalizer import clean_text, normalize_name

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_MS = 45_000
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.8


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


class RobotsGuard:
    def __init__(self, user_agent: str, logger: logging.Logger) -> None:
        self.user_agent = user_agent
        self.logger = logger
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._retry_after_by_domain: dict[str, float] = {}
        self._robots_fetch_attempts = 3
        self._retry_cooldown_seconds = 120

    def _domain_key(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_parser(self, url: str) -> RobotFileParser | None:
        domain = self._domain_key(url)
        if domain in self._parsers and self._parsers[domain] is not None:
            return self._parsers[domain]

        now = time.monotonic()
        retry_after = self._retry_after_by_domain.get(domain, 0.0)
        if retry_after > now:
            return None

        parser = RobotFileParser()
        robots_url = f"{domain}/robots.txt"
        last_error: Exception | None = None
        for attempt in range(1, self._robots_fetch_attempts + 1):
            try:
                req = Request(robots_url, headers={"User-Agent": self.user_agent})
                with urlopen(req, timeout=30) as response:
                    content = response.read().decode("utf-8", errors="ignore")
                parser.set_url(robots_url)
                parser.parse(content.splitlines())
                self._retry_after_by_domain.pop(domain, None)
                self._parsers[domain] = parser
                return parser
            except Exception as exc:
                last_error = exc

        self.logger.error(
            "robots.txt unavailable for %s after %d attempts: %s | retry_in_seconds=%d",
            robots_url,
            self._robots_fetch_attempts,
            last_error,
            self._retry_cooldown_seconds,
        )
        self._retry_after_by_domain[domain] = now + self._retry_cooldown_seconds
        self._parsers[domain] = None
        return None

    def can_fetch(self, url: str) -> bool:
        parser = self._get_parser(url)
        if parser is None:
            return False
        try:
            return parser.can_fetch(self.user_agent, url)
        except ValueError:
            return False


def setup_logger(name: str, error_log_file: Path) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(error_log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def log_failed_url(logger: logging.Logger, url: str, reason: str) -> None:
    logger.error("FAILED | url=%s | reason=%s", url, reason)


class BaseStoreScraper:
    store_name = "store"
    base_url = ""
    UNIT_ALIASES = {
        "m": "m",
        "mt": "m",
        "metro": "m",
        "metros": "m",
        "m2": "m2",
        "m3": "m3",
        "kg": "kg",
        "kgs": "kg",
        "kilo": "kg",
        "kilos": "kg",
        "g": "gr",
        "gr": "gr",
        "gramo": "gr",
        "gramos": "gr",
        "lt": "lt",
        "lts": "lt",
        "litro": "lt",
        "litros": "lt",
        "ml": "ml",
        "u": "un",
        "un": "un",
        "unidad": "un",
        "unidades": "un",
    }
    TRACKING_QUERY_PREFIXES = (
        "utm_",
    )
    TRACKING_QUERY_KEYS = {
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

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        request_timeout_ms: int = REQUEST_TIMEOUT_MS,
        error_log_file: Path = Path("scraping_errors.log"),
    ) -> None:
        self.user_agent = user_agent
        self.request_timeout_ms = request_timeout_ms
        self.logger = setup_logger(f"constructocompare.{self.store_name}", error_log_file)
        self.robots_guard = RobotsGuard(user_agent=user_agent, logger=self.logger)
        self.category_hints: dict[str, str] = {}

    @staticmethod
    def parse_price(raw: str | int | float | None) -> int | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return int(round(float(raw)))
        digits = re.sub(r"[^\d]", "", str(raw))
        return int(digits) if digits else None

    @classmethod
    def canonicalize_url(cls, url: str, drop_all_query: bool = False) -> str:
        parsed = urlparse(clean_text(url or ""))
        query = ""

        if not drop_all_query and parsed.query:
            kept_params: list[tuple[str, str]] = []
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                lowered_key = key.lower()
                if lowered_key in cls.TRACKING_QUERY_KEYS:
                    continue
                if any(lowered_key.startswith(prefix) for prefix in cls.TRACKING_QUERY_PREFIXES):
                    continue
                kept_params.append((key, value))
            query = urlencode(kept_params, doseq=True)

        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))

    @classmethod
    def normalize_unit(cls, raw_unit: str | None) -> str | None:
        if not raw_unit:
            return None
        unit = clean_text(raw_unit).lower()
        unit = unit.replace("²", "2").replace("³", "3")
        unit = re.sub(r"[^a-z0-9]", "", unit)
        return cls.UNIT_ALIASES.get(unit)

    @classmethod
    def extract_unit_price_from_text(cls, text: str) -> tuple[int | None, str | None]:
        if not text:
            return None, None

        normalized = clean_text(text).lower().replace("²", "2").replace("³", "3")
        pattern = re.compile(
            r"\$\s*([\d\.,]+)\s*(?:por|/)\s*"
            r"(m(?:2|3)?|kg|kgs?|kilos?|kilo|gr|gramos?|g|lt|lts?|litros?|litro|ml|un(?:idad(?:es)?)?|u)\b"
        )

        for match in pattern.finditer(normalized):
            amount = cls.parse_price(match.group(1))
            unit = cls.normalize_unit(match.group(2))
            if amount is None or unit is None:
                continue
            return amount, unit

        return None, None

    @staticmethod
    def extract_sku_from_url(product_url: str) -> str:
        path = unquote(urlparse(product_url).path)
        for pattern in [
            r"/articulo/\d+/[^/]+/(\d+)",
            r"-([0-9]{5,})/p",
            r"/(\d{5,})$",
        ]:
            match = re.search(pattern, path)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def parse_sitemap_locations(xml_text: str) -> list[str]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        return [
            clean_text(node.text)
            for node in root.iter()
            if node.tag.endswith("loc") and node.text
        ]

    @staticmethod
    def extract_slug(url: str) -> str:
        path = unquote(urlparse(url).path).strip("/")
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            return ""
        slug = segments[-1]
        if slug.isdigit() and len(segments) >= 2:
            slug = segments[-2]
        return normalize_name(slug.replace("-", " "))

    def url_matches_queries(self, url: str, normalized_queries: list[str]) -> bool:
        if not normalized_queries:
            return True

        slug = self.extract_slug(url)
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

    def download_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

    async def fetch_sitemap(self, url: str) -> str:
        if not self.robots_guard.can_fetch(url):
            log_failed_url(self.logger, url, "blocked by robots.txt")
            return ""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return await asyncio.to_thread(self.download_text, url)
            except Exception as exc:
                message = str(exc)
                if "404" in message:
                    self.logger.warning("SITEMAP_NOT_FOUND | url=%s | reason=%s", url, message)
                    return ""
                if attempt < RETRY_ATTEMPTS:
                    self.logger.warning(
                        "SITEMAP_RETRY | url=%s | attempt=%d/%d | reason=%s",
                        url,
                        attempt,
                        RETRY_ATTEMPTS,
                        message,
                    )
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                log_failed_url(self.logger, url, f"sitemap download failed: {exc}")
                return ""
        return ""

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
        last_error = "unknown"
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self.request_timeout_ms)
                return True
            except PlaywrightTimeoutError:
                last_error = "timeout"
                if attempt < RETRY_ATTEMPTS:
                    self.logger.warning(
                        "GOTO_RETRY_TIMEOUT | url=%s | attempt=%d/%d",
                        url,
                        attempt,
                        RETRY_ATTEMPTS,
                    )
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
            except PlaywrightError as exc:
                last_error = f"playwright error: {exc}"
                if attempt < RETRY_ATTEMPTS:
                    self.logger.warning(
                        "GOTO_RETRY_ERROR | url=%s | attempt=%d/%d | reason=%s",
                        url,
                        attempt,
                        RETRY_ATTEMPTS,
                        exc,
                    )
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                break

        log_failed_url(self.logger, url, last_error)
        return False

    def log_category_progress(self, completed: int, total: int, current_url: str) -> None:
        safe_total = max(1, total)
        safe_completed = min(max(0, completed), safe_total)
        ratio = safe_completed / safe_total
        bar_width = 28
        filled = int(round(ratio * bar_width))
        filled = min(bar_width, max(0, filled))
        bar = "#" * filled + "-" * (bar_width - filled)
        percent = int(round(ratio * 100))
        self.logger.info(
            "CATEGORY_PROGRESS | store=%s | [%s] %d%% (%d/%d) | current=%s",
            self.store_name,
            bar,
            percent,
            safe_completed,
            safe_total,
            current_url,
        )

    async def scrape(self, queries: list[str], **kwargs: Any) -> list[ProductRecord]:
        raise NotImplementedError
