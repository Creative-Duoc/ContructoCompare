from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.persistence import read_json_file, write_json_atomic


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_pair_key_from_sides(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_id = str(left.get("silver_row_id") or "")
    right_id = str(right.get("silver_row_id") or "")

    if left_id and right_id:
        a, b = sorted([left_id, right_id])
        return f"row:{a}|{b}"

    left_store = str(left.get("store") or "").strip().lower()
    right_store = str(right.get("store") or "").strip().lower()
    left_sku = str(left.get("sku_store") or "").strip()
    right_sku = str(right.get("sku_store") or "").strip()

    a, b = sorted([f"{left_store}:{left_sku}", f"{right_store}:{right_sku}"])
    return f"sku:{a}|{b}"


def _canonical_pair_key_from_decision(decision: dict[str, Any]) -> str:
    left = decision.get("left_product") or {}
    right = decision.get("right_product") or {}
    return _canonical_pair_key_from_sides(left, right)


def _canonical_pair_key_from_review_candidate(candidate: dict[str, Any]) -> str:
    left = candidate.get("left_product") or {}
    right = candidate.get("right_product") or {}
    return _canonical_pair_key_from_sides(left, right)


def load_llm_ledger(ledger_path: Path) -> dict[str, Any]:
    if not ledger_path.exists():
        return {
            "version": "1.0",
            "updated_at_utc": _utc_now(),
            "transactions": [],
        }

    payload = read_json_file(ledger_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid ledger format: {ledger_path}")

    payload.setdefault("version", "1.0")
    payload.setdefault("transactions", [])
    return payload


def append_llm_decision_batch(
    *,
    data_dir: Path,
    ledger_file: str,
    source_review_queue: str,
    model: str,
    batch: dict[str, Any],
    thresholds: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    ledger_path = data_dir / ledger_file
    ledger = load_llm_ledger(ledger_path)

    fingerprint = f"{source_review_queue}|{model}|{batch.get('start_index')}|{batch.get('max_items')}|{len(decisions)}|{_utc_now()}"
    transaction_id = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]

    transaction = {
        "transaction_id": transaction_id,
        "created_at_utc": _utc_now(),
        "source_review_queue": source_review_queue,
        "model": model,
        "batch": batch,
        "thresholds": thresholds,
        "decisions": decisions,
    }

    transactions = ledger.get("transactions")
    if not isinstance(transactions, list):
        raise ValueError(f"Invalid ledger transactions list: {ledger_path}")

    transactions.append(transaction)
    ledger["updated_at_utc"] = _utc_now()

    write_json_atomic(ledger_path, ledger)
    return transaction


def replay_accept_decisions(ledger_payload: dict[str, Any]) -> list[dict[str, Any]]:
    transactions = ledger_payload.get("transactions") or []
    latest_by_pair: dict[str, dict[str, Any]] = {}

    for tx in transactions:
        decisions = (tx or {}).get("decisions") or []
        for decision in decisions:
            key = _canonical_pair_key_from_decision(decision)
            latest_by_pair[key] = decision

    accepted = [decision for decision in latest_by_pair.values() if decision.get("auto_action") == "accept"]
    accepted.sort(key=lambda item: str(item.get("review_item_id") or ""))
    return accepted


def filter_review_candidates_by_decisions(
    review_payload: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    candidates = review_payload.get("review_candidates") or []
    if not isinstance(candidates, list):
        return review_payload, 0

    accepted_keys = {
        _canonical_pair_key_from_decision(decision)
        for decision in decisions
        if decision.get("auto_action") == "accept"
    }

    if not accepted_keys:
        return review_payload, 0

    filtered = [
        candidate
        for candidate in candidates
        if _canonical_pair_key_from_review_candidate(candidate) not in accepted_keys
    ]
    removed = len(candidates) - len(filtered)

    review_payload["review_candidates"] = filtered
    review_payload["total_pending"] = len(filtered)
    total_pending_total = review_payload.get("total_pending_total")
    if isinstance(total_pending_total, int):
        review_payload["total_pending_total"] = max(0, total_pending_total - removed)
    return review_payload, removed
