from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from core.candidate_engine import build_candidate_plans, estimate_total_candidate_pairs, iter_candidate_pairs
from core.matching import levenshtein_distance, token_similarity
from core.persistence import read_json_file, write_json_atomic

EXPECTED_STORES = ("sodimac", "easy", "imperial")
REQUIRED_SILVER_FIELDS = (
    "silver_row_id",
    "store",
    "name_normalized",
    "brand_normalized",
    "product_url",
)


def _print_progress_bar(stage: str, current: int, total: int, last_percent: int) -> int:
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_short(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _validate_silver_row(row: object, row_index: int) -> str | None:
    if not isinstance(row, dict):
        return f"row_index={row_index}: expected object, got {type(row).__name__}"

    missing_fields = [
        field
        for field in REQUIRED_SILVER_FIELDS
        if not str((row or {}).get(field) or "").strip()
    ]
    if missing_fields:
        return f"row_index={row_index}: missing required fields ({', '.join(missing_fields)})"

    return None


def _parse_numeric_spec(value: str) -> tuple[float | None, str]:
    raw = (value or "").strip().lower().replace(",", ".")
    if not raw:
        return None, ""

    fraction_match = re.match(r"^(\d+)\s*/\s*(\d+)", raw)
    if fraction_match:
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        if denominator != 0:
            parsed = numerator / denominator
        else:
            parsed = None
    else:
        number_match = re.search(r"(\d+(?:\.\d+)?)", raw)
        parsed = float(number_match.group(1)) if number_match else None

    cleaned = raw.replace(" ", "")
    unit_match = re.search(r"[a-z]+$", cleaned)
    unit = unit_match.group(0) if unit_match else ""
    return parsed, unit


def _quality_penalty(row: dict[str, Any]) -> int:
    penalty_map = {
        "missing_brand": 5,
        "missing_sku": 3,
        "missing_effective_price": 2,
        "unknown_unit": 2,
        "empty_name_normalized": 10,
    }
    flags = row.get("quality_flags") or []
    return sum(penalty_map.get(flag, 0) for flag in flags)


def _price_outlier(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_price = left.get("effective_price")
    right_price = right.get("effective_price")
    if not isinstance(left_price, int) or not isinstance(right_price, int):
        return False
    if left_price <= 0 or right_price <= 0:
        return False
    ratio = max(left_price, right_price) / min(left_price, right_price)
    return ratio > 3.0


def _score_name(left_name: str, right_name: str) -> tuple[int, int, int, int]:
    token_score = token_similarity(left_name, right_name)
    lev_distance = levenshtein_distance(left_name, right_name)
    lev_penalty = max(0, (lev_distance - 14) * 2) if token_score >= 50 else 0
    adjusted = max(0, token_score - lev_penalty)
    return adjusted, token_score, lev_distance, lev_penalty


def _score_brand(left_brand: str, right_brand: str) -> tuple[int, str]:
    if left_brand == right_brand and left_brand != "SIN MARCA":
        return 100, "brand_exact"
    if left_brand == "SIN MARCA" and right_brand == "SIN MARCA":
        return 40, "brand_both_missing"
    if left_brand == "SIN MARCA" or right_brand == "SIN MARCA":
        return 25, "brand_one_missing"
    return 0, "brand_mismatch"


def _spec_conflicts(
    left_specs: dict[str, str],
    right_specs: dict[str, str],
) -> tuple[list[str], int]:
    conflicts: list[str] = []
    shared_exact = 0
    shared_keys = sorted(set(left_specs.keys()) & set(right_specs.keys()))

    for key in shared_keys:
        left_value = str(left_specs.get(key, "")).strip().lower()
        right_value = str(right_specs.get(key, "")).strip().lower()
        if not left_value or not right_value:
            continue
        if left_value == right_value:
            shared_exact += 1
            continue

        left_num, left_unit = _parse_numeric_spec(left_value)
        right_num, right_unit = _parse_numeric_spec(right_value)
        if left_num is not None and right_num is not None and left_unit == right_unit and left_unit:
            relative_diff = abs(left_num - right_num) / max(left_num, right_num)
            if relative_diff > 0.10:
                conflicts.append(f"spec_conflict:{key}:{left_value}!={right_value}")
            continue

        conflicts.append(f"spec_conflict:{key}:{left_value}!={right_value}")

    return conflicts, shared_exact


def evaluate_pair(
    left: dict[str, Any],
    right: dict[str, Any],
    threshold_confident: int,
    threshold_review: int,
) -> dict[str, Any]:
    blocked_by: list[str] = []
    reasons: list[str] = []

    if left.get("store") == right.get("store"):
        blocked_by.append("BLOCK_STORE_SAME")

    left_name = left.get("name_normalized") or ""
    right_name = right.get("name_normalized") or ""
    if not left_name or not right_name:
        blocked_by.append("BLOCK_EMPTY_NAME")

    left_unit = left.get("unidad_medida")
    right_unit = right.get("unidad_medida")
    if left_unit and right_unit and left_unit != right_unit:
        blocked_by.append("BLOCK_UNIT_MISMATCH")

    left_specs = left.get("numeric_specs") or {}
    right_specs = right.get("numeric_specs") or {}
    spec_conflicts, shared_specs_exact = _spec_conflicts(left_specs, right_specs)
    if spec_conflicts:
        blocked_by.append("BLOCK_NUMERIC_CONFLICT")
        reasons.extend(spec_conflicts)

    left_brand = left.get("brand_normalized") or "SIN MARCA"
    right_brand = right.get("brand_normalized") or "SIN MARCA"
    brand_score, brand_reason = _score_brand(left_brand, right_brand)
    reasons.append(brand_reason)
    if brand_score == 0:
        blocked_by.append("BLOCK_BRAND_MISMATCH")

    name_score, raw_name_score, lev_distance, lev_penalty = _score_name(left_name, right_name)
    reasons.append(f"name_score={name_score}")
    reasons.append(f"name_score_raw={raw_name_score}")
    reasons.append(f"levenshtein_distance={lev_distance}")
    if lev_penalty > 0:
        reasons.append(f"levenshtein_penalty={lev_penalty}")

    if shared_specs_exact > 0:
        numeric_score = 100
    elif left_specs or right_specs:
        numeric_score = 55
    else:
        numeric_score = 70

    if left_unit and right_unit and left_unit == right_unit:
        unit_score = 100
    elif left_unit or right_unit:
        unit_score = 60
    else:
        unit_score = 70

    base_score = round(name_score * 0.65 + brand_score * 0.20 + numeric_score * 0.10 + unit_score * 0.05)
    quality_penalty = _quality_penalty(left) + _quality_penalty(right)
    outlier_penalty = 15 if _price_outlier(left, right) else 0
    final_score = max(0, base_score - quality_penalty - outlier_penalty)

    if outlier_penalty:
        reasons.append("price_outlier_penalty")
    if quality_penalty:
        reasons.append(f"quality_penalty={quality_penalty}")

    tier = "rejected"
    if not blocked_by:
        if (
            final_score >= threshold_confident
            and name_score >= 90
            and brand_score == 100
            and (shared_specs_exact == 0 or numeric_score == 100)
        ):
            tier = "confident"
        elif final_score >= threshold_review:
            tier = "review"

    return {
        "left_row_id": left.get("silver_row_id"),
        "right_row_id": right.get("silver_row_id"),
        "left_store": left.get("store"),
        "right_store": right.get("store"),
        "left_name": left.get("name_original"),
        "right_name": right.get("name_original"),
        "left_brand": left_brand,
        "right_brand": right_brand,
        "left_product_url": left.get("product_url"),
        "right_product_url": right.get("product_url"),
        "left_sku_store": left.get("sku_store"),
        "right_sku_store": right.get("sku_store"),
        "score": final_score,
        "tier": tier,
        "blocked_by": blocked_by,
        "reasons": reasons,
        "matching_signals": {
            "name_score": name_score,
            "brand_score": brand_score,
            "numeric_score": numeric_score,
            "unit_score": unit_score,
            "base_score": base_score,
            "quality_penalty": quality_penalty,
            "outlier_penalty": outlier_penalty,
            "shared_specs_exact": shared_specs_exact,
        },
    }


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def _load_silver_rows(
    data_dir: Path,
    input_file: str,
    strict_silver_coverage: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_path = data_dir / input_file
    if not input_path.exists():
        raise FileNotFoundError(f"Silver dataset not found: {input_path}")

    payload = read_json_file(input_path)
    rows_raw = payload.get("rows") or []
    if not isinstance(rows_raw, list):
        raise ValueError("Silver payload has invalid rows field")

    validation_errors: list[str] = []
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows_raw):
        validation_error = _validate_silver_row(row, row_index)
        if validation_error:
            validation_errors.append(validation_error)
            continue
        rows.append(row)

    if validation_errors:
        examples = "; ".join(validation_errors[:3])
        raise ValueError(
            f"Silver payload validation failed with {len(validation_errors)} invalid rows. Examples: {examples}"
        )

    if strict_silver_coverage:
        if payload.get("coverage_complete") is False:
            raise ValueError("Silver coverage is incomplete (coverage_complete=false)")
        present_stores = sorted({str(row.get("store")) for row in rows if row.get("store")})
        missing = [store for store in EXPECTED_STORES if store not in present_stores]
        if missing:
            raise ValueError(f"Silver rows missing expected stores: {', '.join(missing)}")

    rows_sorted = sorted(rows, key=lambda row: str(row.get("silver_row_id", "")))
    return rows_sorted, payload


def _evaluate_all_pairs(
    rows: list[dict[str, Any]],
    threshold_confident: int,
    threshold_review: int,
    max_review_pairs: int,
    max_diagnostic_pairs: int,
) -> dict[str, Any]:
    confident_pairs: list[dict[str, Any]] = []
    review_pairs: list[dict[str, Any]] = []
    diagnostic_pairs: list[dict[str, Any]] = []
    rejected_count = 0
    evaluated_pairs = 0
    total_pairs = 0
    last_percent = -1

    block_counts = {
        "BLOCK_STORE_SAME": 0,
        "BLOCK_EMPTY_NAME": 0,
        "BLOCK_UNIT_MISMATCH": 0,
        "BLOCK_NUMERIC_CONFLICT": 0,
        "BLOCK_BRAND_MISMATCH": 0,
    }

    filtered_out = {"count": 0}

    def _candidate_filter(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_brand = left.get("brand_normalized") or "SIN MARCA"
        right_brand = right.get("brand_normalized") or "SIN MARCA"
        if left_brand != "SIN MARCA" and right_brand != "SIN MARCA" and left_brand != right_brand:
            return False

        left_unit = left.get("unidad_medida")
        right_unit = right.get("unidad_medida")
        if left_unit and right_unit and left_unit != right_unit:
            return False

        return True

    def _candidate_filter_counted(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_brand = left.get("brand_normalized") or "SIN MARCA"
        right_brand = right.get("brand_normalized") or "SIN MARCA"
        if left_brand != "SIN MARCA" and right_brand != "SIN MARCA" and left_brand != right_brand:
            block_counts["BLOCK_BRAND_MISMATCH"] += 1
            filtered_out["count"] += 1
            return False

        left_unit = left.get("unidad_medida")
        right_unit = right.get("unidad_medida")
        if left_unit and right_unit and left_unit != right_unit:
            block_counts["BLOCK_UNIT_MISMATCH"] += 1
            filtered_out["count"] += 1
            return False

        return True

    plans, token_cache = build_candidate_plans(rows)
    total_pairs = estimate_total_candidate_pairs(plans, token_cache, candidate_filter=_candidate_filter)

    if total_pairs == 0:
        _print_progress_bar("GOLD MATCH", 0, 0, -1)
        return {
            "evaluated_pairs": 0,
            "confident_pairs": confident_pairs,
            "review_pairs": review_pairs,
            "diagnostic_pairs": diagnostic_pairs,
            "rejected_pairs": 0,
            "blocking_rules_triggered": block_counts,
        }

    for left, right in iter_candidate_pairs(plans, token_cache, candidate_filter=_candidate_filter_counted):
        evaluated_pairs += 1
        last_percent = _print_progress_bar("GOLD MATCH", evaluated_pairs, total_pairs, last_percent)

        pair = evaluate_pair(left, right, threshold_confident=threshold_confident, threshold_review=threshold_review)

        for blocked in pair["blocked_by"]:
            if blocked in block_counts:
                block_counts[blocked] += 1

        if pair["tier"] == "confident":
            confident_pairs.append(pair)
            continue

        if pair["tier"] == "review":
            review_pairs.append(pair)
            continue

        rejected_count += 1
        if not pair["blocked_by"]:
            diagnostic_pairs.append(pair)

    rejected_count += filtered_out["count"]

    confident_pairs.sort(key=lambda item: item["score"], reverse=True)
    review_pairs.sort(key=lambda item: item["score"], reverse=True)
    diagnostic_pairs.sort(key=lambda item: item["score"], reverse=True)

    review_pairs_total = len(review_pairs)
    review_pairs_persisted = review_pairs if max_review_pairs <= 0 else review_pairs[:max_review_pairs]

    diagnostic_pairs_persisted = (
        diagnostic_pairs if max_diagnostic_pairs <= 0 else diagnostic_pairs[:max_diagnostic_pairs]
    )

    return {
        "evaluated_pairs": evaluated_pairs,
        "confident_pairs": confident_pairs,
        "review_pairs": review_pairs_persisted,
        "review_pairs_total": review_pairs_total,
        "review_pairs_persisted": len(review_pairs_persisted),
        "diagnostic_pairs": diagnostic_pairs_persisted,
        "rejected_pairs": rejected_count,
        "blocking_rules_triggered": block_counts,
    }


def _build_gold_entities(
    rows: list[dict[str, Any]],
    confident_pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_id = {str(row.get("silver_row_id")): row for row in rows if row.get("silver_row_id")}
    uf = UnionFind()

    for pair in confident_pairs:
        uf.union(pair["left_row_id"], pair["right_row_id"])

    components: dict[str, set[str]] = {}
    for pair in confident_pairs:
        for row_id in [pair["left_row_id"], pair["right_row_id"]]:
            root = uf.find(row_id)
            components.setdefault(root, set()).add(row_id)

    gold_entities: list[dict[str, Any]] = []
    for component_ids in components.values():
        if len(component_ids) < 2:
            continue

        component_rows = [rows_by_id[row_id] for row_id in sorted(component_ids) if row_id in rows_by_id]
        stores = sorted({str(row.get("store")) for row in component_rows})
        if len(stores) < 2:
            continue

        base_row = sorted(
            component_rows,
            key=lambda row: (
                len(row.get("quality_flags") or []),
                -len(str(row.get("name_normalized") or "")),
                str(row.get("silver_row_id")),
            ),
        )[0]

        component_pairs = [
            pair
            for pair in confident_pairs
            if pair["left_row_id"] in component_ids and pair["right_row_id"] in component_ids
        ]

        pair_scores = [pair["score"] for pair in component_pairs] or [0]
        confidence_score = min(pair_scores)
        gold_product_id = _hash_short("|".join(sorted(component_ids)))

        price_values = [
            int(row["effective_price"])
            for row in component_rows
            if isinstance(row.get("effective_price"), int) and int(row["effective_price"]) > 0
        ]

        store_variants = []
        for row in component_rows:
            store_variants.append(
                {
                    "store": row.get("store"),
                    "silver_row_id": row.get("silver_row_id"),
                    "name_original": row.get("name_original"),
                    "name_normalized": row.get("name_normalized"),
                    "brand_original": row.get("brand_original"),
                    "brand_normalized": row.get("brand_normalized"),
                    "sku_store": row.get("sku_store"),
                    "product_url": row.get("product_url"),
                    "effective_price": row.get("effective_price"),
                    "unidad_medida": row.get("unidad_medida"),
                    "numeric_specs": row.get("numeric_specs") or {},
                    "image_url": row.get("image_url"),
                    "quality_flags": row.get("quality_flags") or [],
                }
            )

        # Select canonical image (first available)
        canonical_image = next((v.get("image_url") for v in store_variants if v.get("image_url")), None)

        rationale: list[str] = []
        for pair in component_pairs[:5]:
            rationale.extend(pair.get("reasons") or [])
        rationale = list(dict.fromkeys(rationale))[:12]

        gold_entities.append(
            {
                "gold_product_id": gold_product_id,
                "confidence_score": confidence_score,
                "confidence_tier": "GOLD_CONFIDENT",
                "created_at_utc": _utc_now(),
                "canonical_product": {
                    "name_canonical": base_row.get("name_normalized") or base_row.get("name_original"),
                    "brand_canonical": base_row.get("brand_normalized"),
                    "numeric_specs": base_row.get("numeric_specs") or {},
                    "unidad_medida": base_row.get("unidad_medida"),
                    "image_url": canonical_image,
                    "category_normalized": base_row.get("category_normalized"),
                    "price_reference": min(price_values) if price_values else None,
                },
                "store_variants": store_variants,
                "matching_signals": {
                    "component_pair_count": len(component_pairs),
                    "min_pair_score": min(pair_scores),
                    "max_pair_score": max(pair_scores),
                    "avg_pair_score": round(mean(pair_scores), 2),
                },
                "matching_rationale": rationale,
            }
        )

    gold_entities.sort(key=lambda item: item["confidence_score"], reverse=True)
    return gold_entities


def _build_review_payload(review_pairs: list[dict[str, Any]], total_pending_total: int | None = None) -> dict[str, Any]:
    review_candidates = []

    for pair in review_pairs:
        review_id = _hash_short(f"{pair['left_row_id']}|{pair['right_row_id']}|{pair['score']}")
        review_candidates.append(
            {
                "review_item_id": review_id,
                "confidence_score": pair["score"],
                "left_product": {
                    "store": pair["left_store"],
                    "silver_row_id": pair["left_row_id"],
                    "name_original": pair["left_name"],
                    "brand_normalized": pair["left_brand"],
                    "sku_store": pair.get("left_sku_store"),
                    "product_url": pair.get("left_product_url"),
                },
                "right_product": {
                    "store": pair["right_store"],
                    "silver_row_id": pair["right_row_id"],
                    "name_original": pair["right_name"],
                    "brand_normalized": pair["right_brand"],
                    "sku_store": pair.get("right_sku_store"),
                    "product_url": pair.get("right_product_url"),
                },
                "matching_signals": pair.get("matching_signals", {}),
                "decision_reasons": pair.get("reasons", []),
            }
        )

    return {
        "generated_at_utc": _utc_now(),
        "review_tier": "GOLD_REVIEW",
        "total_pending": len(review_candidates),
        "total_pending_total": total_pending_total if total_pending_total is not None else len(review_candidates),
        "review_candidates": review_candidates,
    }


def write_gold_datasets(
    data_dir: Path,
    silver_input_file: str = "silver/silver_products.json",
    gold_output_file: str = "gold/gold_products.json",
    review_output_file: str = "gold/gold_review_queue.json",
    metrics_output_file: str = "gold/gold_metrics.json",
    diagnostics_output_file: str = "gold/gold_diagnostics.json",
    threshold_confident: int = 90,
    threshold_review: int = 78,
    strict_silver_coverage: bool = True,
    max_review_pairs: int = 0,
    max_diagnostic_pairs: int = 500,
    write_diagnostics: bool = False,
) -> dict[str, Any]:
    rows, silver_payload = _load_silver_rows(
        data_dir,
        input_file=silver_input_file,
        strict_silver_coverage=strict_silver_coverage,
    )

    pair_result = _evaluate_all_pairs(
        rows,
        threshold_confident=threshold_confident,
        threshold_review=threshold_review,
        max_review_pairs=max_review_pairs,
        max_diagnostic_pairs=max_diagnostic_pairs,
    )

    gold_products = _build_gold_entities(rows, pair_result["confident_pairs"])
    review_payload = _build_review_payload(
        pair_result["review_pairs"],
        total_pending_total=pair_result.get("review_pairs_total"),
    )

    gold_payload = {
        "generated_at_utc": _utc_now(),
        "gold_version": "1.0",
        "matching_strategy": "precision_first_ultra_strict",
        "threshold_confident": threshold_confident,
        "threshold_review": threshold_review,
        "silver_input": {
            "file": silver_input_file,
            "total_rows": silver_payload.get("total_rows", len(rows)),
            "coverage_complete": silver_payload.get("coverage_complete", None),
            "missing_stores": silver_payload.get("missing_stores", []),
        },
        "total_gold_products": len(gold_products),
        "gold_products": gold_products,
    }

    metrics_payload = {
        "generated_at_utc": _utc_now(),
        "matching_strategy": "precision_first_ultra_strict",
        "threshold_confident": threshold_confident,
        "threshold_review": threshold_review,
        "pairs_evaluated": pair_result["evaluated_pairs"],
        "confident_pairs": len(pair_result["confident_pairs"]),
        "review_pairs": len(pair_result["review_pairs"]),
        "review_pairs_total": pair_result.get("review_pairs_total", len(pair_result["review_pairs"])),
        "review_pairs_persisted": pair_result.get("review_pairs_persisted", len(pair_result["review_pairs"])),
        "rejected_pairs": pair_result["rejected_pairs"],
        "gold_products": len(gold_products),
        "blocking_rules_triggered": pair_result["blocking_rules_triggered"],
    }

    data_dir.mkdir(parents=True, exist_ok=True)
    gold_output_path = data_dir / gold_output_file
    review_output_path = data_dir / review_output_file
    metrics_output_path = data_dir / metrics_output_file
    gold_output_path.parent.mkdir(parents=True, exist_ok=True)
    review_output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_output_path.parent.mkdir(parents=True, exist_ok=True)

    write_json_atomic(gold_output_path, gold_payload)
    write_json_atomic(review_output_path, review_payload)
    write_json_atomic(metrics_output_path, metrics_payload)

    if write_diagnostics:
        diagnostics_payload = {
            "generated_at_utc": _utc_now(),
            "total_diagnostic_pairs": len(pair_result["diagnostic_pairs"]),
            "diagnostic_pairs": pair_result["diagnostic_pairs"],
        }
        diagnostics_output_path = data_dir / diagnostics_output_file
        diagnostics_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(diagnostics_output_path, diagnostics_payload)

    return {
        "gold": gold_payload,
        "review": review_payload,
        "metrics": metrics_payload,
        "diagnostics_count": len(pair_result["diagnostic_pairs"]),
    }
