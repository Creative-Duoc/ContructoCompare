from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.persistence import read_json_file
from core.transformer import write_matching_preview, write_silver_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sprint 2 Silver: unify Bronze data from 3 retail stores")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent / "data"))
    parser.add_argument("--silver-output", default="silver/silver_products.json")
    parser.add_argument("--preview-matching", action="store_true")
    parser.add_argument("--only-preview-matching", action="store_true")
    parser.add_argument("--preview-output", default="silver/silver_matching_preview.json")
    parser.add_argument("--preview-threshold", type=int, default=60)
    parser.add_argument("--preview-max-pairs", type=int, default=400)
    parser.add_argument("--strict-missing-stores", action="store_true")
    return parser.parse_args()


def run_silver_stage(args: argparse.Namespace) -> dict:
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    run_transform = not args.only_preview_matching
    run_preview = args.preview_matching or args.only_preview_matching

    silver_payload: dict | None = None

    if run_transform:
        silver_payload = write_silver_dataset(
            data_dir,
            output_file=args.silver_output,
            strict_missing_stores=args.strict_missing_stores,
        )
        print("=" * 60)
        print("Silver dataset generated")
        print(
            json.dumps(
                {
                    "output": str(data_dir / args.silver_output),
                    "total_rows": silver_payload.get("total_rows", 0),
                    "per_store_counts": silver_payload.get("per_store_counts", {}),
                    "missing_stores": silver_payload.get("missing_stores", []),
                    "coverage_complete": silver_payload.get("coverage_complete", False),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif not run_preview:
        raise ValueError("Nothing to run. Use transform or --preview-matching.")

    if run_preview:
        if silver_payload is not None:
            rows = silver_payload.get("rows", [])
        else:
            silver_path = data_dir / args.silver_output
            if not silver_path.exists():
                raise FileNotFoundError(
                    f"Silver dataset not found for preview: {silver_path}. Run Silver first."
                )
            existing_payload = read_json_file(silver_path)
            rows = existing_payload.get("rows", [])

        preview_payload = write_matching_preview(
            data_dir,
            rows=rows,
            threshold=min(100, max(0, args.preview_threshold)),
            max_pairs=max(1, args.preview_max_pairs),
            output_file=args.preview_output,
        )

        print("=" * 60)
        print("Diagnostic matching preview generated")
        print(
            json.dumps(
                {
                    "output": str(data_dir / args.preview_output),
                    "total_pairs": preview_payload.get("total_pairs", 0),
                    "pairs_by_store_combo": preview_payload.get("pairs_by_store_combo", {}),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return silver_payload or {}


def main() -> None:
    args = parse_args()
    run_silver_stage(args)


if __name__ == "__main__":
    main()
