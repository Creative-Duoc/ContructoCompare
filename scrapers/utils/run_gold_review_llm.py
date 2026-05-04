from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from core.ledger import append_llm_decision_batch
from core.persistence import read_json_file, write_json_atomic


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LLM-assisted auto-review and auto-integrate accepted matches into Gold products."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing Gold files (default: data)",
    )
    parser.add_argument(
        "--review-input",
        default="gold/gold_review_queue.json",
        help="Gold review queue filename inside data-dir (default: gold/gold_review_queue.json)",
    )
    parser.add_argument(
        "--decisions-output",
        default="gold/gold_review_llm_decisions.json",
        help="Decisions output filename inside data-dir (default: gold/gold_review_llm_decisions.json)",
    )
    parser.add_argument(
        "--remaining-output",
        default="gold/gold_review_queue_remaining.json",
        help="Remaining queue filename inside data-dir (default: gold/gold_review_queue_remaining.json)",
    )
    parser.add_argument(
        "--model",
        default="gemma3:27b",
        help="Local Ollama model name (default: gemma3:27b)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434/api/generate",
        help="Ollama generate endpoint URL (default: http://localhost:11434/api/generate)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=500,
        help="Maximum review candidates to send to LLM in this run (default: 500)",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start index in review_candidates for batch processing (default: 0)",
    )
    parser.add_argument(
        "--min-llm-confidence-accept",
        type=int,
        default=90,
        help="Minimum LLM confidence to auto-accept MATCH (default: 90)",
    )
    parser.add_argument(
        "--min-llm-confidence-reject",
        type=int,
        default=92,
        help="Minimum LLM confidence to auto-reject NO_MATCH (default: 92)",
    )
    parser.add_argument(
        "--min-gold-score-accept",
        type=int,
        default=90,
        help="Minimum Gold confidence_score to auto-accept (default: 90)",
    )
    parser.add_argument(
        "--min-gold-score-review",
        type=int,
        default=85,
        help="Minimum Gold confidence_score required to send candidate to LLM review (default: 85)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Ollama temperature (default: 0.0)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="HTTP timeout per LLM call in seconds (default: 180)",
    )
    parser.add_argument(
        "--silver-input",
        default="silver/silver_products.json",
        help="Silver input filename inside data-dir for integration (default: silver/silver_products.json)",
    )
    parser.add_argument(
        "--gold-input",
        default="gold/gold_products.json",
        help="Gold input filename inside data-dir for integration (default: gold/gold_products.json)",
    )
    parser.add_argument(
        "--gold-output",
        default="gold/gold_products.json",
        help="Gold output filename inside data-dir after integration (default: gold/gold_products.json)",
    )
    parser.add_argument(
        "--ledger-file",
        default="gold/gold_llm_decision_ledger.json",
        help="Ledger filename inside data-dir for immutable LLM decision history.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute decisions but do not write output files.",
    )
    return parser.parse_args()


def _build_prompt(candidate: dict[str, Any]) -> str:
    left = candidate.get("left_product") or {}
    right = candidate.get("right_product") or {}
    signals = candidate.get("matching_signals") or {}
    reasons = candidate.get("decision_reasons") or []

    return (
        "Eres un validador estricto de matching de productos retail en Chile.\\n"
        "Tu trabajo es decidir si dos productos representan el MISMO producto comercial.\\n"
        "Responde SOLO un JSON valido sin markdown ni texto extra.\\n"
        "\\n"
        "Formato de respuesta requerido:\\n"
        '{"decision":"MATCH|NO_MATCH|UNSURE","confidence":0-100,"reason":"motivo breve"}\\n'
        "\\n"
        "Criterios:\\n"
        "1) Marca distinta explicita => NO_MATCH.\\n"
        "2) Especificaciones incompatibles (kg, lt, mm, dimensiones) => NO_MATCH.\\n"
        "3) Si nombre+marca+specs son claramente equivalentes => MATCH.\\n"
        "4) Si hay ambiguedad por presentacion/pack/capacidad => UNSURE.\\n"
        "5) Prioriza precision (evitar falsos positivos).\\n"
        "\\n"
        f"Gold confidence_score: {candidate.get('confidence_score')}\\n"
        f"Left product: {json.dumps(left, ensure_ascii=False)}\\n"
        f"Right product: {json.dumps(right, ensure_ascii=False)}\\n"
        f"Matching signals: {json.dumps(signals, ensure_ascii=False)}\\n"
        f"Decision reasons: {json.dumps(reasons, ensure_ascii=False)}\\n"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty LLM response")

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON is not an object")
    return parsed


def _normalize_decision(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"MATCH", "NO_MATCH", "UNSURE"}:
        return token
    if "NO" in token and "MATCH" in token:
        return "NO_MATCH"
    if "MATCH" in token:
        return "MATCH"
    return "UNSURE"


def _ask_ollama(
    candidate: dict[str, Any],
    model: str,
    ollama_url: str,
    temperature: float,
    timeout_seconds: int,
) -> dict[str, Any]:
    prompt = _build_prompt(candidate)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }

    request = Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama connection error: {exc.reason}") from exc

    body = json.loads(response_text)
    raw = str(body.get("response") or "")
    parsed = _extract_json_object(raw)

    decision = _normalize_decision(parsed.get("decision"))
    confidence = _clamp(_safe_int(parsed.get("confidence"), default=50))
    reason = str(parsed.get("reason") or "").strip()

    return {
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
    }


def _auto_action(
    candidate: dict[str, Any],
    gold_score: int,
    llm_decision: str,
    llm_confidence: int,
    min_llm_confidence_accept: int,
    min_llm_confidence_reject: int,
    min_gold_score_accept: int,

) -> tuple[str, dict[str, Any]]:
    left = candidate.get("left_product") or {}
    right = candidate.get("right_product") or {}
    signals = candidate.get("matching_signals") or {}
    decision_reasons = [str(reason) for reason in (candidate.get("decision_reasons") or [])]

    left_store = str(left.get("store") or "").strip().lower()
    right_store = str(right.get("store") or "").strip().lower()
    left_row_id = str(left.get("silver_row_id") or "").strip()
    right_row_id = str(right.get("silver_row_id") or "").strip()
    left_brand = str(left.get("brand_normalized") or "").strip().upper()
    right_brand = str(right.get("brand_normalized") or "").strip().upper()

    blocking_keywords = ["BLOCK_", "mismatch", "conflict"]
    reasons_text = "|".join(decision_reasons).lower()

    checks = {
        "llm_decision_match": llm_decision == "MATCH",
        "llm_confidence_min": llm_confidence >= min_llm_confidence_accept,
        "gold_score_min": gold_score >= min_gold_score_accept,
        "different_store": bool(left_store and right_store and left_store != right_store),
        "distinct_rows": bool(left_row_id and right_row_id and left_row_id != right_row_id),
        "brand_not_conflicting": (
            not left_brand
            or not right_brand
            or left_brand == "SIN MARCA"
            or right_brand == "SIN MARCA"
            or left_brand == right_brand
        ),
        "brand_score_exact": _safe_int(signals.get("brand_score"), default=0) >= 100,
        "numeric_score_strict": _safe_int(signals.get("numeric_score"), default=0) >= 95,
        "unit_score_strict": _safe_int(signals.get("unit_score"), default=0) >= 90,
        "shared_specs_exact": _safe_int(signals.get("shared_specs_exact"), default=0) >= 1,
        "name_score_floor": _safe_int(signals.get("name_score"), default=0) >= 84,
        "no_blocking_reason_tokens": not any(token.lower() in reasons_text for token in blocking_keywords),
    }

    if llm_decision == "NO_MATCH" and llm_confidence >= min_llm_confidence_reject:
        return "reject", {"mode": "reject_rule", "checks": checks, "passed": False}

    checks_passed = all(checks.values())
    if checks_passed:
        return "accept", {"mode": "accept_rule", "checks": checks, "passed": True}

    return "escalate", {"mode": "escalate_rule", "checks": checks, "passed": False}


def _canonicalize_lookup_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    path = parsed.path or ""
    while path.lower().endswith("/p/p"):
        path = path[:-2]
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip("/"), "", "", ""))


def _to_store_variant(row: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "quality_flags": row.get("quality_flags") or [],
    }


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        len(row.get("quality_flags") or []),
        -len(str(row.get("name_normalized") or "")),
        str(row.get("silver_row_id") or ""),
    )


def _safe_positive_int(value: Any) -> int | None:
    parsed = _safe_int(value, default=0)
    return parsed if parsed > 0 else None


def _refresh_gold_entity(entity: dict[str, Any]) -> None:
    variants = entity.get("store_variants") or []
    if not isinstance(variants, list):
        variants = []

    dedup: dict[str, dict[str, Any]] = {}
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        row_id = str(variant.get("silver_row_id") or "")
        if not row_id:
            continue
        dedup[row_id] = variant

    variants_sorted = sorted(dedup.values(), key=lambda row: (str(row.get("store") or ""), str(row.get("silver_row_id") or "")))
    entity["store_variants"] = variants_sorted

    if not variants_sorted:
        entity["canonical_product"] = {
            "name_canonical": "",
            "brand_canonical": "SIN MARCA",
            "numeric_specs": {},
            "unidad_medida": None,
            "category_normalized": "",
            "price_reference": None,
        }
        return

    base_row = sorted(variants_sorted, key=_row_sort_key)[0]
    price_values = [
        price
        for price in (_safe_positive_int(row.get("effective_price")) for row in variants_sorted)
        if price is not None
    ]

    canonical = entity.get("canonical_product") or {}
    entity["canonical_product"] = {
        "name_canonical": base_row.get("name_normalized") or base_row.get("name_original") or canonical.get("name_canonical"),
        "brand_canonical": base_row.get("brand_normalized") or canonical.get("brand_canonical") or "SIN MARCA",
        "numeric_specs": base_row.get("numeric_specs") or canonical.get("numeric_specs") or {},
        "unidad_medida": base_row.get("unidad_medida") or canonical.get("unidad_medida"),
        "category_normalized": base_row.get("category_normalized") or canonical.get("category_normalized"),
        "price_reference": min(price_values) if price_values else canonical.get("price_reference"),
    }

    if "created_at_utc" not in entity:
        entity["created_at_utc"] = _utc_now()
    if "confidence_tier" not in entity:
        entity["confidence_tier"] = "GOLD_CONFIDENT"

    row_ids = sorted(str(row.get("silver_row_id") or "") for row in variants_sorted if row.get("silver_row_id"))
    if row_ids:
        entity["gold_product_id"] = hashlib.sha1("|".join(row_ids).encode("utf-8")).hexdigest()[:16]


def _build_silver_indexes(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], list[str]], dict[tuple[str, str], str], dict[str, str]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    by_store_sku: dict[tuple[str, str], list[str]] = {}
    by_store_url: dict[tuple[str, str], str] = {}
    row_url_by_id: dict[str, str] = {}

    for row in rows:
        row_id = str(row.get("silver_row_id") or "")
        if not row_id:
            continue

        store = str(row.get("store") or "").strip().lower()
        sku = str(row.get("sku_store") or "").strip()
        canonical_url = _canonicalize_lookup_url(str(row.get("product_url") or ""))

        rows_by_id[row_id] = row
        row_url_by_id[row_id] = canonical_url

        if store and sku:
            key = (store, sku)
            by_store_sku.setdefault(key, []).append(row_id)
        if store and canonical_url:
            by_store_url[(store, canonical_url)] = row_id

    return rows_by_id, by_store_sku, by_store_url, row_url_by_id


def _resolve_row_id(
    side: dict[str, Any],
    rows_by_id: dict[str, dict[str, Any]],
    by_store_sku: dict[tuple[str, str], list[str]],
    by_store_url: dict[tuple[str, str], str],
    row_url_by_id: dict[str, str],
) -> str | None:
    direct_id = str(side.get("silver_row_id") or "")
    if direct_id and direct_id in rows_by_id:
        return direct_id

    store = str(side.get("store") or "").strip().lower()
    sku = str(side.get("sku_store") or "").strip()
    target_url = _canonicalize_lookup_url(str(side.get("product_url") or ""))

    if store and sku:
        candidates = by_store_sku.get((store, sku), [])
        if target_url:
            for candidate in candidates:
                if row_url_by_id.get(candidate) == target_url:
                    return candidate
        if len(candidates) == 1:
            return candidates[0]

    if store and target_url:
        resolved = by_store_url.get((store, target_url))
        if resolved:
            return resolved

    return None


def _set_entity_confidence(entity: dict[str, Any], incoming_score: int) -> None:
    current = _safe_positive_int(entity.get("confidence_score"))
    if current is None:
        entity["confidence_score"] = incoming_score
        return
    entity["confidence_score"] = min(current, incoming_score)


def _integrate_accepted_into_gold(
    decisions_payload: dict[str, Any],
    silver_payload: dict[str, Any],
    gold_payload: dict[str, Any],
) -> dict[str, Any]:
    decisions = decisions_payload.get("decisions") or []
    accepted = [decision for decision in decisions if decision.get("auto_action") == "accept"]

    silver_rows = silver_payload.get("rows") or []
    rows_by_id, by_store_sku, by_store_url, row_url_by_id = _build_silver_indexes(silver_rows)

    gold_products = gold_payload.get("gold_products") or []
    if not isinstance(gold_products, list):
        raise ValueError("Invalid gold payload: gold_products must be a list")

    row_to_entity: dict[str, int] = {}
    for index, entity in enumerate(gold_products):
        for variant in entity.get("store_variants") or []:
            row_id = str((variant or {}).get("silver_row_id") or "")
            if row_id:
                row_to_entity[row_id] = index

    merged_entities = 0
    expanded_entities = 0
    created_entities = 0
    already_connected = 0
    skipped_missing_rows = 0

    removed_indices: set[int] = set()

    for decision in accepted:
        left = decision.get("left_product") or {}
        right = decision.get("right_product") or {}

        left_id = _resolve_row_id(left, rows_by_id, by_store_sku, by_store_url, row_url_by_id)
        right_id = _resolve_row_id(right, rows_by_id, by_store_sku, by_store_url, row_url_by_id)

        if not left_id or not right_id:
            skipped_missing_rows += 1
            continue

        if left_id == right_id:
            already_connected += 1
            continue

        left_row = rows_by_id.get(left_id)
        right_row = rows_by_id.get(right_id)
        if left_row is None or right_row is None:
            skipped_missing_rows += 1
            continue

        score = _clamp(_safe_int(decision.get("gold_confidence_score"), default=0))

        left_entity_index = row_to_entity.get(left_id)
        right_entity_index = row_to_entity.get(right_id)

        if left_entity_index is None and right_entity_index is None:
            new_entity = {
                "gold_product_id": "",
                "confidence_score": score,
                "confidence_tier": "GOLD_CONFIDENT",
                "created_at_utc": _utc_now(),
                "canonical_product": {},
                "store_variants": [_to_store_variant(left_row), _to_store_variant(right_row)],
                "matching_signals": {
                    "llm_accept_links": 1,
                },
                "matching_rationale": [
                    "llm_accept_integration",
                ],
            }
            _refresh_gold_entity(new_entity)
            gold_products.append(new_entity)
            new_index = len(gold_products) - 1
            row_to_entity[left_id] = new_index
            row_to_entity[right_id] = new_index
            created_entities += 1
            continue

        if left_entity_index is not None and right_entity_index is None:
            target = gold_products[left_entity_index]
            target.setdefault("store_variants", []).append(_to_store_variant(right_row))
            _set_entity_confidence(target, score)
            target.setdefault("matching_rationale", []).append("llm_accept_expand")
            _refresh_gold_entity(target)
            row_to_entity[right_id] = left_entity_index
            expanded_entities += 1
            continue

        if left_entity_index is None and right_entity_index is not None:
            target = gold_products[right_entity_index]
            target.setdefault("store_variants", []).append(_to_store_variant(left_row))
            _set_entity_confidence(target, score)
            target.setdefault("matching_rationale", []).append("llm_accept_expand")
            _refresh_gold_entity(target)
            row_to_entity[left_id] = right_entity_index
            expanded_entities += 1
            continue

        assert left_entity_index is not None
        assert right_entity_index is not None

        if left_entity_index == right_entity_index:
            already_connected += 1
            target = gold_products[left_entity_index]
            _set_entity_confidence(target, score)
            continue

        target_index = min(left_entity_index, right_entity_index)
        source_index = max(left_entity_index, right_entity_index)

        target_entity = gold_products[target_index]
        source_entity = gold_products[source_index]

        target_variants = target_entity.get("store_variants") or []
        source_variants = source_entity.get("store_variants") or []
        target_entity["store_variants"] = [*target_variants, *source_variants]

        _set_entity_confidence(target_entity, _clamp(_safe_int(source_entity.get("confidence_score"), default=score)))
        _set_entity_confidence(target_entity, score)

        target_entity.setdefault("matching_rationale", []).append("llm_accept_merge")
        _refresh_gold_entity(target_entity)

        for variant in target_entity.get("store_variants") or []:
            row_id = str((variant or {}).get("silver_row_id") or "")
            if row_id:
                row_to_entity[row_id] = target_index

        removed_indices.add(source_index)
        merged_entities += 1

    if removed_indices:
        gold_products = [entity for index, entity in enumerate(gold_products) if index not in removed_indices]

    for entity in gold_products:
        _refresh_gold_entity(entity)

    gold_products.sort(key=lambda item: _safe_int(item.get("confidence_score"), default=0), reverse=True)

    gold_payload["gold_products"] = gold_products
    gold_payload["total_gold_products"] = len(gold_products)
    gold_payload["generated_at_utc"] = _utc_now()
    gold_payload["llm_integration"] = {
        "integrated_at_utc": _utc_now(),
        "accepted_decisions_seen": len(accepted),
        "created_entities": created_entities,
        "expanded_entities": expanded_entities,
        "merged_entities": merged_entities,
        "already_connected": already_connected,
        "skipped_missing_rows": skipped_missing_rows,
    }

    return gold_payload["llm_integration"]


def run_gold_review_llm(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = Path(args.data_dir)
    review_input_path = data_dir / args.review_input
    decisions_output_path = data_dir / args.decisions_output
    remaining_output_path = data_dir / args.remaining_output
    silver_input_path = data_dir / args.silver_input
    gold_input_path = data_dir / args.gold_input
    gold_output_path = data_dir / args.gold_output
    ledger_path = data_dir / args.ledger_file

    if not review_input_path.exists():
        raise FileNotFoundError(f"Review queue file not found: {review_input_path}")

    payload = read_json_file(review_input_path)
    all_candidates = payload.get("review_candidates") or []
    if not isinstance(all_candidates, list):
        raise ValueError("Invalid review queue format: review_candidates must be a list")

    min_gold_score_review = _clamp(args.min_gold_score_review)

    eligible_candidates = [
        candidate
        for candidate in all_candidates
        if _clamp(_safe_int(candidate.get("confidence_score"), default=0)) >= min_gold_score_review
    ]

    start_index = max(0, args.start_index)
    max_items = max(1, args.max_items)
    selected_candidates = eligible_candidates[start_index : start_index + max_items]

    min_llm_confidence_accept = _clamp(args.min_llm_confidence_accept)
    min_llm_confidence_reject = _clamp(args.min_llm_confidence_reject)
    min_gold_score_accept = _clamp(args.min_gold_score_accept)

    decisions: list[dict[str, Any]] = []
    action_by_id: dict[str, str] = {}
    interrupted = False

    for index, candidate in enumerate(selected_candidates, start=start_index):
        review_item_id = str(candidate.get("review_item_id") or "")
        gold_score = _clamp(_safe_int(candidate.get("confidence_score"), default=0))

        print(
            f"LLM REVIEW [{index + 1}/{len(eligible_candidates)}] id={review_item_id} gold_score={gold_score}",
            flush=True,
        )

        try:
            llm_result = _ask_ollama(
                candidate=candidate,
                model=args.model,
                ollama_url=args.ollama_url,
                temperature=args.temperature,
                timeout_seconds=max(1, args.timeout_seconds),
            )
            action, guardrail_trace = _auto_action(
                candidate=candidate,
                gold_score=gold_score,
                llm_decision=llm_result["decision"],
                llm_confidence=llm_result["confidence"],
                min_llm_confidence_accept=min_llm_confidence_accept,
                min_llm_confidence_reject=min_llm_confidence_reject,
                min_gold_score_accept=min_gold_score_accept,
            )
            error: str | None = None
        except KeyboardInterrupt:
            interrupted = True
            print("LLM REVIEW interrupted by user. Flushing processed items...", flush=True)
            break
        except Exception as exc:  # noqa: BLE001
            llm_result = {
                "decision": "UNSURE",
                "confidence": 0,
                "reason": "",
            }
            action = "escalate"
            guardrail_trace = {
                "mode": "error",
                "checks": {},
                "passed": False,
            }
            error = str(exc)

        action_by_id[review_item_id] = action
        left = candidate.get("left_product") or {}
        right = candidate.get("right_product") or {}

        decisions.append(
            {
                "review_item_id": review_item_id,
                "gold_confidence_score": gold_score,
                "left_product": {
                    "store": left.get("store"),
                    "silver_row_id": left.get("silver_row_id"),
                    "name_original": left.get("name_original"),
                    "brand_normalized": left.get("brand_normalized"),
                    "sku_store": left.get("sku_store"),
                    "product_url": left.get("product_url"),
                },
                "right_product": {
                    "store": right.get("store"),
                    "silver_row_id": right.get("silver_row_id"),
                    "name_original": right.get("name_original"),
                    "brand_normalized": right.get("brand_normalized"),
                    "sku_store": right.get("sku_store"),
                    "product_url": right.get("product_url"),
                },
                "llm_decision": llm_result["decision"],
                "llm_confidence": llm_result["confidence"],
                "llm_reason": llm_result["reason"],
                "auto_action": action,
                "guardrail_trace": guardrail_trace,
                "error": error,
            }
        )

    reviewed_ids = {str(item.get("review_item_id") or "") for item in decisions}

    remaining_candidates = []
    for candidate in all_candidates:
        review_item_id = str(candidate.get("review_item_id") or "")

        if review_item_id in reviewed_ids:
            if action_by_id.get(review_item_id) == "escalate":
                remaining_candidates.append(candidate)
            continue

        remaining_candidates.append(candidate)

    accept_count = sum(1 for item in decisions if item["auto_action"] == "accept")
    reject_count = sum(1 for item in decisions if item["auto_action"] == "reject")
    escalate_count = sum(1 for item in decisions if item["auto_action"] == "escalate")
    error_count = sum(1 for item in decisions if item.get("error"))

    decisions_payload = {
        "generated_at_utc": _utc_now(),
        "source_review_queue": args.review_input,
        "model": args.model,
        "ollama_url": args.ollama_url,
        "batch": {
            "start_index": start_index,
            "max_items": max_items,
            "requested_items": len(selected_candidates),
            "processed_items": len(decisions),
            "interrupted": interrupted,
            "total_review_items": len(all_candidates),
            "eligible_review_items": len(eligible_candidates),
            "filtered_out_by_gold_score": max(0, len(all_candidates) - len(eligible_candidates)),
        },
        "thresholds": {
            "min_llm_confidence_accept": min_llm_confidence_accept,
            "min_llm_confidence_reject": min_llm_confidence_reject,
            "min_gold_score_accept": min_gold_score_accept,
            "min_gold_score_review": min_gold_score_review,
        },
        "summary": {
            "accepted": accept_count,
            "rejected": reject_count,
            "escalated": escalate_count,
            "errors": error_count,
        },
        "decisions": decisions,
    }

    remaining_payload = {
        "generated_at_utc": _utc_now(),
        "review_tier": "GOLD_REVIEW_REMAINING",
        "source_review_queue": args.review_input,
        "llm_model": args.model,
        "interrupted": interrupted,
        "total_pending": len(remaining_candidates),
        "review_candidates": remaining_candidates,
    }

    integration_summary: dict[str, Any] | None = None
    if not silver_input_path.exists():
        raise FileNotFoundError(f"Silver dataset not found for integration: {silver_input_path}")
    if not gold_input_path.exists():
        raise FileNotFoundError(f"Gold dataset not found for integration: {gold_input_path}")

    silver_payload = read_json_file(silver_input_path)
    gold_payload = read_json_file(gold_input_path)
    integration_summary = _integrate_accepted_into_gold(
        decisions_payload=decisions_payload,
        silver_payload=silver_payload,
        gold_payload=gold_payload,
    )

    if not args.dry_run:
        decisions_output_path.parent.mkdir(parents=True, exist_ok=True)
        remaining_output_path.parent.mkdir(parents=True, exist_ok=True)
        gold_output_path.parent.mkdir(parents=True, exist_ok=True)

        write_json_atomic(gold_output_path, gold_payload)
        write_json_atomic(decisions_output_path, decisions_payload)
        write_json_atomic(remaining_output_path, remaining_payload)
        append_llm_decision_batch(
            data_dir=data_dir,
            ledger_file=args.ledger_file,
            source_review_queue=args.review_input,
            model=args.model,
            batch=decisions_payload["batch"],
            thresholds=decisions_payload["thresholds"],
            decisions=decisions,
        )

    print("=" * 60)
    print("Gold LLM review completed")
    summary = {
        "review_input": str(review_input_path),
        "decisions_output": str(decisions_output_path),
        "remaining_output": str(remaining_output_path),
        "model": args.model,
        "min_gold_score_review": min_gold_score_review,
        "eligible_items": len(eligible_candidates),
        "filtered_out_by_gold_score": max(0, len(all_candidates) - len(eligible_candidates)),
        "requested_items": len(selected_candidates),
        "processed_items": len(decisions),
        "interrupted": interrupted,
        "accepted": accept_count,
        "rejected": reject_count,
        "escalated": escalate_count,
        "errors": error_count,
        "integrated_into_gold": True,
        "gold_input": str(gold_input_path),
        "gold_output": str(gold_output_path),
        "ledger_file": str(ledger_path),
        "integration_summary": integration_summary,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return summary


def main() -> None:
    args = parse_args()
    run_gold_review_llm(args)


if __name__ == "__main__":
    main()