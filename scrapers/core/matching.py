from __future__ import annotations

from difflib import SequenceMatcher

try:
    from thefuzz import fuzz
except Exception:
    fuzz = None


def token_similarity(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if fuzz is not None:
        return int(fuzz.token_set_ratio(left, right))
    return int(SequenceMatcher(None, left, right).ratio() * 100)


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous_row = list(range(len(right) + 1))
    for i, l_char in enumerate(left, start=1):
        current_row = [i]
        for j, r_char in enumerate(right, start=1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (l_char != r_char)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def are_similar(left: str, right: str, threshold: int = 90) -> bool:
    return token_similarity(left, right) >= threshold
