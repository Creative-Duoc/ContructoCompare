from __future__ import annotations

import hashlib
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from core.candidate_engine import build_candidate_plans, estimate_total_candidate_pairs, iter_candidate_pairs
from core.matching import levenshtein_distance, token_similarity
from core.persistence import read_json_file, write_json_atomic
from core.normalizer import (
    clean_text,
    extract_numeric_specs,
    normalize_brand,
    normalize_category_from_url,
    normalize_name,
    normalize_unit_value,
)

BRONZE_STORE_FILES = {
    "sodimac": "bronze/sodimac_products.json",
    "easy": "bronze/easy_products.json",
    "imperial": "bronze/imperial_products.json",
}

BRONZE_CATEGORY_HINT_FILES = {
    "sodimac": "bronze/sodimac_category_hints.json",
    "easy": "bronze/easy_category_hints.json",
    "imperial": "bronze/imperial_category_hints.json",
}

BRONZE_REQUIRED_PRODUCT_KEYS = (
    "name",
    "brand",
    "sku_store",
    "product_url",
    "precio_normal",
    "precio_internet",
    "precio_oferta",
    "precio_tarjeta",
    "precio_unitario",
    "unidad_medida",
    "precio_unitario_fuente",
)


def print_progress_bar(stage: str, current: int, total: int, last_percent: int) -> int:
    if total <= 0:
        if last_percent < 100:
            print(f"{stage} [############################] 100% (0/0)", flush=True)
        return 100

    safe_current = min(max(0, current), total)
    percent = int((safe_current * 100) / total)
    if percent == last_percent and safe_current < total:
        return last_percent

    bar_width = 28
    filled = int((safe_current * bar_width) / total)
    bar = "#" * filled + "-" * (bar_width - filled)
    end_char = "\n" if safe_current >= total else "\r"
    print(f"{stage} [{bar}] {percent}% ({safe_current}/{total})", end=end_char, flush=True)
    return percent


def canonicalize_url(url: str) -> str:
    parsed = urlparse(clean_text(url or ""))
    path = parsed.path or ""

    # Easy cards can include duplicated product suffixes like /p/p.
    # Normalize to a single trailing /p so Silver/Gold don't treat them as different URLs.
    while path.lower().endswith("/p/p"):
        path = path[:-2]

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def select_effective_price(product: dict) -> int | None:
    candidates = [
        product.get("precio_oferta"),
        product.get("precio_internet"),
        product.get("precio_tarjeta"),
        product.get("precio_normal"),
    ]
    numeric = [int(value) for value in candidates if isinstance(value, (int, float)) and int(value) > 0]
    if not numeric:
        return None
    return min(numeric)


def compute_quality_flags(row: dict) -> list[str]:
    flags: list[str] = []
    if row["brand_normalized"] == "SIN MARCA":
        flags.append("missing_brand")
    if not row["sku_store"]:
        flags.append("missing_sku")
    if row["effective_price"] is None:
        flags.append("missing_effective_price")
    if row["unidad_medida"] is None and row["precio_unitario"] is not None:
        flags.append("unknown_unit")
    if not row["name_normalized"]:
        flags.append("empty_name_normalized")
    return flags


def load_bronze_category_hints(data_dir: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    hints_by_store: dict[str, dict[str, str]] = {}
    load_warnings: list[str] = []

    for store, filename in BRONZE_CATEGORY_HINT_FILES.items():
        source_path = data_dir / filename
        if not source_path.exists():
            hints_by_store[store] = {}
            continue

        try:
            payload = read_json_file(source_path)
        except json.JSONDecodeError:
            load_warnings.append(f"CATEGORY_HINT_INVALID_JSON | store={store} | file={filename}")
            hints_by_store[store] = {}
            continue

        raw_hints = payload.get("hints_by_product_url") or payload.get("hints") or {}
        if not isinstance(raw_hints, dict):
            load_warnings.append(f"CATEGORY_HINT_INVALID_FORMAT | store={store} | file={filename}")
            hints_by_store[store] = {}
            continue

        normalized_hints: dict[str, str] = {}
        for product_url, category_url in raw_hints.items():
            product_key = canonicalize_url(str(product_url or ""))
            category_value = canonicalize_url(str(category_url or ""))
            if product_key and category_value:
                normalized_hints[product_key] = category_value

        hints_by_store[store] = normalized_hints

    return hints_by_store, load_warnings


def resolve_category(
    store: str,
    product_url: str,
    category_hints_by_store: dict[str, dict[str, str]],
) -> tuple[str, str]:
    sidecar_hints = category_hints_by_store.get(store, {})
    sidecar_url = sidecar_hints.get(product_url)
    if sidecar_url:
        category_from_sidecar = normalize_category_from_url(sidecar_url)
        if category_from_sidecar:
            return category_from_sidecar, "sidecar"

    category_from_product_url = normalize_category_from_url(product_url)
    if category_from_product_url:
        return category_from_product_url, "product_url"

    return "", "empty"


def build_silver_row(
    product: dict,
    store: str,
    source_file: str,
    generated_at_utc: str,
    category_hints_by_store: dict[str, dict[str, str]],
) -> dict:
    name_original = clean_text(str(product.get("name") or ""))
    brand_original = clean_text(str(product.get("brand") or ""))
    product_url = canonicalize_url(str(product.get("product_url") or ""))

    name_normalized = normalize_name(name_original)
    brand_normalized = normalize_brand(brand_original)
    sku_store = clean_text(str(product.get("sku_store") or ""))
    unidad_medida = normalize_unit_value(product.get("unidad_medida"))
    category_normalized, category_source = resolve_category(
        store=store,
        product_url=product_url,
        category_hints_by_store=category_hints_by_store,
    )

    silver_key = f"{store}|{sku_store}|{product_url}"
    silver_row_id = hashlib.sha1(silver_key.encode("utf-8")).hexdigest()[:16]

    row = {
        "silver_row_id": silver_row_id,
        "store": store,
        "name_original": name_original,
        "name_normalized": name_normalized,
        "brand_original": brand_original,
        "brand_normalized": brand_normalized,
        "sku_store": sku_store,
        "product_url": product_url,
        "precio_normal": product.get("precio_normal"),
        "precio_internet": product.get("precio_internet"),
        "precio_oferta": product.get("precio_oferta"),
        "precio_tarjeta": product.get("precio_tarjeta"),
        "precio_unitario": product.get("precio_unitario"),
        "unidad_medida": unidad_medida,
        "precio_unitario_fuente": product.get("precio_unitario_fuente"),
        "image_url": product.get("image_url"),
        "effective_price": select_effective_price(product),
        "category_normalized": category_normalized,
        "category_source": category_source,
        "numeric_specs": extract_numeric_specs(name_original),
        "raw_source_store": store,
        "raw_source_file": source_file,
        "generated_at_utc": generated_at_utc,
    }
    row["quality_flags"] = compute_quality_flags(row)
    return row


def validate_bronze_product(
    product: object,
    *,
    store: str,
    source_file: str,
    row_index: int,
) -> tuple[dict | None, str | None]:
    if not isinstance(product, dict):
        return None, (
            f"BRONZE_INVALID_PRODUCT_TYPE | store={store} | file={source_file} "
            f"| row_index={row_index} | type={type(product).__name__}"
        )

    missing_keys = [key for key in BRONZE_REQUIRED_PRODUCT_KEYS if key not in product]
    if missing_keys:
        return None, (
            f"BRONZE_INVALID_PRODUCT_SCHEMA | store={store} | file={source_file} "
            f"| row_index={row_index} | missing_keys={','.join(missing_keys)}"
        )

    product_url = clean_text(str(product.get("product_url") or ""))
    if not product_url:
        return None, (
            f"BRONZE_INVALID_PRODUCT_SCHEMA | store={store} | file={source_file} "
            f"| row_index={row_index} | reason=empty_product_url"
        )

    return product, None


def load_bronze_rows(data_dir: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    seen_row_ids: set[str] = set()
    load_warnings: list[str] = []
    generated_at_utc = datetime.now(timezone.utc).isoformat()
    category_hints_by_store, category_hint_warnings = load_bronze_category_hints(data_dir)
    load_warnings.extend(category_hint_warnings)
    store_products: list[tuple[str, str, list[dict]]] = []

    for store, filename in BRONZE_STORE_FILES.items():
        source_path = data_dir / filename
        if not source_path.exists():
            load_warnings.append(f"BRONZE_FILE_MISSING | store={store} | file={filename}")
            continue

        try:
            payload = read_json_file(source_path)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in Bronze file: {source_path}") from exc

        products = payload.get("products") or []
        if not isinstance(products, list):
            raise ValueError(f"Invalid Bronze format in {source_path}: 'products' must be a list")
        if not products:
            load_warnings.append(f"BRONZE_EMPTY_PRODUCTS | store={store} | file={filename}")

        store_products.append((store, filename, products))

    total_products = sum(len(products) for _, _, products in store_products)
    processed_products = 0
    last_percent = -1

    for store, filename, products in store_products:
        for row_index, product in enumerate(products):
            valid_product, warning = validate_bronze_product(
                product,
                store=store,
                source_file=filename,
                row_index=row_index,
            )
            if warning:
                load_warnings.append(warning)
                continue

            row = build_silver_row(
                valid_product,
                store=store,
                source_file=filename,
                generated_at_utc=generated_at_utc,
                category_hints_by_store=category_hints_by_store,
            )
            row_id = str(row.get("silver_row_id") or "")
            if row_id in seen_row_ids:
                continue

            seen_row_ids.add(row_id)
            rows.append(row)
            processed_products += 1
            last_percent = print_progress_bar("SILVER", processed_products, total_products, last_percent)

    if total_products == 0:
        print_progress_bar("SILVER", 0, 0, -1)

    return rows, load_warnings


def build_silver_payload(
    rows: list[dict],
    expected_stores: list[str] | None = None,
    load_warnings: list[str] | None = None,
) -> dict:
    per_store_counts: dict[str, int] = {}
    for row in rows:
        per_store_counts[row["store"]] = per_store_counts.get(row["store"], 0) + 1

    expected = expected_stores or list(BRONZE_STORE_FILES.keys())
    available = [store for store in expected if store in per_store_counts]
    missing = [store for store in expected if store not in per_store_counts]

    quality_metrics = {
        "with_effective_price": sum(1 for row in rows if row["effective_price"] is not None),
        "with_brand_normalized": sum(1 for row in rows if row["brand_normalized"] != "SIN MARCA"),
        "with_numeric_specs": sum(1 for row in rows if bool(row["numeric_specs"])),
        "with_unit_price": sum(1 for row in rows if row["precio_unitario"] is not None),
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(rows),
        "per_store_counts": per_store_counts,
        "expected_stores": expected,
        "available_stores": available,
        "missing_stores": missing,
        "coverage_complete": len(missing) == 0,
        "data_warnings": load_warnings or [],
        "quality_metrics": quality_metrics,
        "rows": rows,
    }


def write_silver_dataset(
    data_dir: Path,
    output_file: str = "silver/silver_products.json",
    strict_missing_stores: bool = False,
) -> dict:
    rows, load_warnings = load_bronze_rows(data_dir)
    payload = build_silver_payload(
        rows,
        expected_stores=list(BRONZE_STORE_FILES.keys()),
        load_warnings=load_warnings,
    )

    for warning_message in payload.get("data_warnings", []):
        warnings.warn(warning_message, RuntimeWarning, stacklevel=2)

    if strict_missing_stores and payload.get("missing_stores"):
        missing_stores = ", ".join(payload["missing_stores"])
        raise FileNotFoundError(f"Missing Bronze store files for: {missing_stores}")

    output_path = data_dir / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_path, payload)
    return payload


def build_matching_preview(rows: list[dict], threshold: int = 60, max_pairs: int = 400) -> dict:
    pairs: list[dict] = []
    fallback_candidates: list[dict] = []

    def _candidate_filter(left: dict, right: dict) -> bool:
        left_brand = left.get("brand_normalized") or "SIN MARCA"
        right_brand = right.get("brand_normalized") or "SIN MARCA"
        if left_brand != "SIN MARCA" and right_brand != "SIN MARCA" and left_brand != right_brand:
            return False

        unit_left = left.get("unidad_medida")
        unit_right = right.get("unidad_medida")
        if unit_left and unit_right and unit_left != unit_right:
            return False

        return True

    plans, token_cache = build_candidate_plans(rows)
    total_pairs = estimate_total_candidate_pairs(plans, token_cache, candidate_filter=_candidate_filter)
    processed_pairs = 0
    last_percent = -1

    for left, right in iter_candidate_pairs(plans, token_cache, candidate_filter=_candidate_filter):
        processed_pairs += 1
        last_percent = print_progress_bar("SILVER PREVIEW", processed_pairs, total_pairs, last_percent)

        left_name = left["name_normalized"]
        right_name = right["name_normalized"]
        if not left_name or not right_name:
            continue

        brand_left = left["brand_normalized"]
        brand_right = right["brand_normalized"]

        unit_left = left.get("unidad_medida")
        unit_right = right.get("unidad_medida")

        name_score = token_similarity(left_name, right_name)
        if name_score < max(45, threshold - 25):
            continue

        lev = levenshtein_distance(left_name, right_name)
        lev_score = max(0, 100 - lev * 3)

        brand_score = 0
        reasons: list[str] = [f"name_score={name_score}"]

        if brand_left == brand_right and brand_left != "SIN MARCA":
            brand_score = 100
            reasons.append("brand_exact")
        elif brand_left == "SIN MARCA" or brand_right == "SIN MARCA":
            brand_score = 50
            reasons.append("brand_missing_side")
        else:
            brand_score = 20
            reasons.append("brand_mismatch")

        unit_penalty = 0
        if unit_left and unit_right and unit_left == unit_right:
            reasons.append("unit_match")

        composite_score = round(name_score * 0.75 + brand_score * 0.15 + lev_score * 0.1) - unit_penalty
        candidate = {
            "left_row_id": left["silver_row_id"],
            "right_row_id": right["silver_row_id"],
            "left_store": left["store"],
            "right_store": right["store"],
            "left_name": left["name_original"],
            "right_name": right["name_original"],
            "left_brand": brand_left,
            "right_brand": brand_right,
            "score": composite_score,
            "reasons": reasons,
        }

        if composite_score < threshold:
            if composite_score >= max(25, threshold - 30):
                fallback_candidates.append(candidate)
            continue

        pairs.append(candidate)

    if total_pairs == 0:
        print_progress_bar("SILVER PREVIEW", 0, 0, -1)

    pairs.sort(key=lambda item: item["score"], reverse=True)
    if not pairs and fallback_candidates:
        fallback_candidates.sort(key=lambda item: item["score"], reverse=True)
        pairs = fallback_candidates[: min(max_pairs, 50)]
        for pair in pairs:
            pair["reasons"] = pair["reasons"] + ["below_threshold_fallback"]

    pairs = pairs[:max_pairs]

    pairs_by_store_combo: dict[str, int] = {}
    for pair in pairs:
        stores = sorted([pair["left_store"], pair["right_store"]])
        combo = f"{stores[0]}-{stores[1]}"
        pairs_by_store_combo[combo] = pairs_by_store_combo.get(combo, 0) + 1

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "total_pairs": len(pairs),
        "pairs_by_store_combo": pairs_by_store_combo,
        "pairs": pairs,
    }


def write_matching_preview(
    data_dir: Path,
    rows: list[dict],
    threshold: int = 60,
    max_pairs: int = 400,
    output_file: str = "silver/silver_matching_preview.json",
) -> dict:
    payload = build_matching_preview(rows=rows, threshold=threshold, max_pairs=max_pairs)
    output_path = data_dir / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_path, payload)
    return payload
