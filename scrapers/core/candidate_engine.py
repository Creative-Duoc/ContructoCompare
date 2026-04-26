from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class CandidatePlan:
    left_store: str
    right_store: str
    left_rows: list[dict[str, Any]]
    right_index: dict[str, list[dict[str, Any]]]


def name_tokens(name: str, min_token_len: int = 3) -> set[str]:
    raw_tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {token for token in raw_tokens if len(token) >= min_token_len}


def build_candidate_plans(
    rows: list[dict[str, Any]],
    *,
    row_id_field: str = "silver_row_id",
    name_field: str = "name_normalized",
    min_token_len: int = 3,
) -> tuple[list[CandidatePlan], dict[str, set[str]]]:
    rows_by_store: dict[str, list[dict[str, Any]]] = {}
    token_cache: dict[str, set[str]] = {}

    for row in rows:
        store = str(row.get("store") or "")
        if not store:
            continue

        rows_by_store.setdefault(store, []).append(row)
        row_id = str(row.get(row_id_field) or "")
        token_cache[row_id] = name_tokens(str(row.get(name_field) or ""), min_token_len=min_token_len)

    plans: list[CandidatePlan] = []
    stores = sorted(rows_by_store.keys())
    for left_store, right_store in combinations(stores, 2):
        left_rows = rows_by_store.get(left_store, [])
        right_rows = rows_by_store.get(right_store, [])
        if not left_rows or not right_rows:
            continue

        right_index: dict[str, list[dict[str, Any]]] = {}
        for right in right_rows:
            right_id = str(right.get(row_id_field) or "")
            for token in token_cache.get(right_id, set()):
                right_index.setdefault(token, []).append(right)

        plans.append(
            CandidatePlan(
                left_store=left_store,
                right_store=right_store,
                left_rows=left_rows,
                right_index=right_index,
            )
        )

    return plans, token_cache


def collect_row_candidates(
    left: dict[str, Any],
    right_index: dict[str, list[dict[str, Any]]],
    token_cache: dict[str, set[str]],
    *,
    row_id_field: str = "silver_row_id",
    candidate_filter: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    left_id = str(left.get(row_id_field) or "")
    left_tokens = token_cache.get(left_id, set())
    if not left_tokens:
        return []

    candidates: list[dict[str, Any]] = []
    seen_right_ids: set[str] = set()
    for token in left_tokens:
        for right in right_index.get(token, []):
            right_id = str(right.get(row_id_field) or "")
            if right_id and right_id not in seen_right_ids:
                seen_right_ids.add(right_id)
                if candidate_filter and not candidate_filter(left, right):
                    continue
                candidates.append(right)

    return candidates


def estimate_total_candidate_pairs(
    plans: list[CandidatePlan],
    token_cache: dict[str, set[str]],
    *,
    row_id_field: str = "silver_row_id",
    candidate_filter: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> int:
    total = 0
    for plan in plans:
        for left in plan.left_rows:
            total += len(
                collect_row_candidates(
                    left,
                    plan.right_index,
                    token_cache,
                    row_id_field=row_id_field,
                    candidate_filter=candidate_filter,
                )
            )
    return total


def iter_candidate_pairs(
    plans: list[CandidatePlan],
    token_cache: dict[str, set[str]],
    *,
    row_id_field: str = "silver_row_id",
    candidate_filter: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    for plan in plans:
        for left in plan.left_rows:
            for right in collect_row_candidates(
                left,
                plan.right_index,
                token_cache,
                row_id_field=row_id_field,
                candidate_filter=candidate_filter,
            ):
                yield left, right
