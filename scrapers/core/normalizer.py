from __future__ import annotations

import re
import unicodedata
from html import unescape
from urllib.parse import unquote, urlparse

MIN_QUERY_TOKEN_LEN = 3

STOP_WORDS = {
    "de", "del", "la", "las", "el", "los", "para", "con",
    "sin", "en", "por", "y", "o", "un", "una", "x",
    "tipo", "modelo", "kit", "set", "pack",
}

BRAND_ALIASES = {
    "black and decker": "BLACK+DECKER",
    "black decker": "BLACK+DECKER",
    "black+decker": "BLACK+DECKER",
    "dewalt": "DEWALT",
    "makita": "MAKITA",
    "stanley": "STANLEY",
    "bosch": "BOSCH",
    "sika": "SIKA",
    "ceresita": "CERESITA",
    "tricolor": "TRICOLOR",
    "sherwin": "SHERWIN",
    "sherwin williams": "SHERWIN WILLIAMS",
    "sin marca": "SIN MARCA",
    "sinmarca": "SIN MARCA",
    "generico": "GENERICO",
}

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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    cleaned = strip_accents(unescape(name).lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    tokens = [
        t for t in cleaned.split()
        if t not in STOP_WORDS and len(t) >= MIN_QUERY_TOKEN_LEN
    ]
    return " ".join(tokens)


def normalize_brand(brand: str) -> str:
    base = clean_text(strip_accents(unescape(brand or "")).lower())
    base = re.sub(r"\s+", " ", base)
    if not base:
        return "SIN MARCA"
    if base in BRAND_ALIASES:
        return BRAND_ALIASES[base]
    return base.upper()


def normalize_unit_value(raw_unit: str | None) -> str | None:
    if not raw_unit:
        return None
    unit = clean_text(raw_unit).lower()
    unit = unit.replace("\u00b2", "2").replace("\u00b3", "3")
    unit = re.sub(r"[^a-z0-9]", "", unit)
    return UNIT_ALIASES.get(unit)


def normalize_category_from_url(url: str) -> str:
    path = unquote(urlparse(url).path).strip("/")
    if not path:
        return ""
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return ""

    lowered = [segment.lower() for segment in segments]

    if "articulo" in lowered:
        return ""

    if "lista" in lowered:
        idx = lowered.index("lista")
        tail_segments = segments[idx + 1 :]

        # Sodimac usually exposes category URLs like:
        # /sodimac-cl/lista/cat3035/Batidoras-Manuales
        # where cat3035 is just an internal code and the next segment is the category name.
        for segment in reversed(tail_segments):
            cleaned = re.sub(r"[^a-z0-9]", "", strip_accents(segment.lower()))
            if not cleaned:
                continue
            if cleaned.isdigit():
                continue
            if re.fullmatch(r"cat[a-z0-9]*", cleaned):
                continue

            normalized = normalize_name(segment.replace("-", " "))
            if normalized:
                return normalized

    if "category" in lowered:
        idx = lowered.index("category")
        if idx > 0:
            return normalize_name(segments[idx - 1].replace("-", " "))

    if "product" in lowered:
        idx = lowered.index("product")
        if idx >= 2:
            return normalize_name(segments[idx - 2].replace("-", " "))
        if idx >= 1:
            return normalize_name(segments[idx - 1].replace("-", " "))

    if len(segments) <= 2 and segments[-1].lower() in {"p", "pdp"}:
        return ""

    for segment in segments:
        cleaned = re.sub(r"[^a-z0-9-]", "", strip_accents(segment.lower()))
        if not cleaned or cleaned.isdigit():
            continue
        if cleaned in {"sodimac-cl", "articulo", "product", "category", "lista"}:
            continue
        return normalize_name(segment.replace("-", " "))

    return ""


def extract_numeric_specs(name: str) -> dict[str, str]:
    text = clean_text(strip_accents(unescape(name or "")).lower())
    specs: dict[str, str] = {}

    voltage = re.search(r"(\d+(?:[\.,]\d+)?)\s*v\b", text)
    if voltage:
        specs["voltaje"] = f"{voltage.group(1).replace(',', '.')}V"

    capacity_ah = re.search(r"(\d+(?:[\.,]\d+)?)\s*ah\b", text)
    if capacity_ah:
        specs["capacidad"] = f"{capacity_ah.group(1).replace(',', '.')}Ah"

    diameter_mm = re.search(r"(\d+(?:[\.,]\d+)?)\s*mm\b", text)
    if diameter_mm:
        specs["diametro"] = f"{diameter_mm.group(1).replace(',', '.')}mm"

    weight_kg = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:kg|kilo(?:s)?)\b", text)
    if weight_kg:
        specs["peso"] = f"{weight_kg.group(1).replace(',', '.')}kg"

    volume_lt = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:lt|l|litro(?:s)?)\b", text)
    if volume_lt:
        specs["volumen"] = f"{volume_lt.group(1).replace(',', '.')}lt"

    fraction_gal = re.search(r"(\d+\s*/\s*\d+)\s*gal\b", text)
    if fraction_gal:
        specs["presentacion_galon"] = f"{fraction_gal.group(1).replace(' ', '')}gal"

    return specs
