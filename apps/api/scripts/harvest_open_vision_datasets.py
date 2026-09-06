"""Generate SenseMu's reviewable catalog of public YOLO and SAM3 dataset candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

from sensemu_api.open_dataset_harvest import (
    DEFAULT_HUGGING_FACE_QUERIES,
    build_catalog_document,
    fetch_hugging_face_candidates,
    load_curated_candidates,
    merge_candidates,
    write_catalog_outputs,
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--curated-manifest",
        type=Path,
        default=repo_root / "docs/open-data-catalog/curated-open-vision-datasets.json",
        help="Reviewed source manifest. This is always loaded.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "docs/open-data-catalog/generated",
        help="Directory for JSON, CSV, Markdown and the later storage intake queue.",
    )
    parser.add_argument(
        "--refresh-huggingface",
        action="store_true",
        help="Query only Hugging Face's public directory API. Never downloads dataset files.",
    )
    parser.add_argument("--huggingface-query", action="append", dest="queries", help="Additional or replacement Hugging Face search query.")
    parser.add_argument("--limit-per-query", type=int, default=40, help="Maximum public directory records per query (1-100).")
    parser.add_argument("--request-delay", type=float, default=1.0, help="Delay between public directory requests in seconds.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds.")
    parser.add_argument("--markdown-rows", type=int, default=80, help="Maximum table rows written to Markdown.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    curated = load_curated_candidates(args.curated_manifest)
    discovered = []
    errors: list[str] = []
    if args.refresh_huggingface:
        queries = tuple(args.queries) if args.queries else DEFAULT_HUGGING_FACE_QUERIES
        discovered, errors = fetch_hugging_face_candidates(
            queries=queries,
            limit_per_query=args.limit_per_query,
            timeout_seconds=args.timeout,
            request_delay_seconds=args.request_delay,
        )
    catalog = build_catalog_document(merge_candidates(curated, discovered), errors=errors)
    outputs = write_catalog_outputs(catalog, args.output_dir, markdown_rows=args.markdown_rows)
    print(f"Cataloged {len(catalog['items'])} candidates; no files were downloaded.")
    for name, path in outputs.items():
        print(f"{name}: {path}")
    if errors:
        print(f"Completed with {len(errors)} directory-query errors; see JSON and Markdown output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
