"""Export the checked-in Core API OpenAPI contract from the FastAPI application."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sensemu_api.main import create_app


def openapi_body() -> bytes:
    schema = create_app().openapi()
    return (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    body = openapi_body()
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != body:
            print(
                f"{args.output} is out of date. Run `make api-openapi`.",
                file=sys.stderr,
            )
            return 1
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
