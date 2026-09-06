"""Build an auditable catalog of public vision-dataset candidates.

The catalog is deliberately discovery-only. It never follows dataset download links,
writes to object storage, or asserts commercial training rights from a directory tag.
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CATALOG_SCHEMA_VERSION = "1.0"
DEFAULT_HUGGING_FACE_QUERIES = ("yolo", "coco", "instance segmentation", "semantic segmentation", "sam")
VALID_YOLO_READINESS = {
    "native_yolo",
    "coco_convertible",
    "conversion_required",
    "review_required",
    "not_suitable",
}
VALID_SAM3_READINESS = {
    "mask_ready",
    "box_prompt_convertible",
    "review_required",
    "not_suitable",
}
VALID_COMMERCIAL_USE = {"allowed", "conditional", "research_only", "unknown"}
VALID_ACCESS = {"direct_public", "registration_required", "terms_acceptance_required", "manual_request"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


@dataclass(frozen=True)
class DatasetCandidate:
    source_id: str
    title: str
    provider: str
    catalog_url: str
    tasks: list[str]
    annotation_types: list[str]
    modalities: list[str]
    yolo_readiness: str
    sam3_readiness: str
    license: str
    commercial_use: str
    access: str
    estimated_size: str
    priority: str
    summary: str
    risk_notes: str
    discovery_origin: str
    last_seen_at: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return value


def candidate_from_mapping(raw: dict[str, object], *, discovered_at: str | None = None) -> DatasetCandidate:
    required = (
        "source_id",
        "title",
        "provider",
        "catalog_url",
        "license",
        "access",
        "estimated_size",
        "priority",
        "summary",
        "risk_notes",
    )
    for field_name in required:
        if not isinstance(raw.get(field_name), str) or not str(raw[field_name]).strip():
            raise ValueError(f"{field_name} must be a non-empty string")

    yolo_readiness = str(raw.get("yolo_readiness", "review_required"))
    sam3_readiness = str(raw.get("sam3_readiness", "review_required"))
    commercial_use = str(raw.get("commercial_use", "unknown"))
    access = str(raw["access"])
    priority = str(raw["priority"])
    if yolo_readiness not in VALID_YOLO_READINESS:
        raise ValueError(f"unsupported yolo_readiness: {yolo_readiness}")
    if sam3_readiness not in VALID_SAM3_READINESS:
        raise ValueError(f"unsupported sam3_readiness: {sam3_readiness}")
    if commercial_use not in VALID_COMMERCIAL_USE:
        raise ValueError(f"unsupported commercial_use: {commercial_use}")
    if access not in VALID_ACCESS:
        raise ValueError(f"unsupported access: {access}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"unsupported priority: {priority}")

    return DatasetCandidate(
        source_id=str(raw["source_id"]),
        title=str(raw["title"]),
        provider=str(raw["provider"]),
        catalog_url=str(raw["catalog_url"]),
        tasks=_string_list(raw.get("tasks"), "tasks"),
        annotation_types=_string_list(raw.get("annotation_types"), "annotation_types"),
        modalities=_string_list(raw.get("modalities"), "modalities"),
        yolo_readiness=yolo_readiness,
        sam3_readiness=sam3_readiness,
        license=str(raw["license"]),
        commercial_use=commercial_use,
        access=access,
        estimated_size=str(raw["estimated_size"]),
        priority=priority,
        summary=str(raw["summary"]),
        risk_notes=str(raw["risk_notes"]),
        discovery_origin=str(raw.get("discovery_origin", "curated")),
        last_seen_at=str(raw.get("last_seen_at") or discovered_at or _now()),
    )


def load_curated_candidates(path: Path) -> list[DatasetCandidate]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("curated dataset manifest must be a JSON array")
    candidates = [candidate_from_mapping(item) for item in raw if isinstance(item, dict)]
    if len(candidates) != len(raw):
        raise ValueError("curated dataset manifest entries must be JSON objects")
    return candidates


def _tags(value: object) -> set[str]:
    return {item.lower() for item in value if isinstance(item, str)} if isinstance(value, list) else set()


def hugging_face_candidate(record: dict[str, Any], *, query: str, discovered_at: str) -> DatasetCandidate | None:
    dataset_id = record.get("id")
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        return None
    tags = _tags(record.get("tags"))
    card_data = record.get("cardData") if isinstance(record.get("cardData"), dict) else {}
    card_license = card_data.get("license") if isinstance(card_data.get("license"), str) else None
    has_yolo = any("yolo" in tag for tag in tags)
    has_coco = any("coco" in tag for tag in tags)
    has_segmentation = any("segmentation" in tag or "segmentation" in tag.replace("_", "-") for tag in tags)
    has_detection = any("object-detection" in tag or "detection" == tag for tag in tags)
    if has_yolo:
        yolo_readiness = "native_yolo"
    elif has_coco:
        yolo_readiness = "coco_convertible"
    elif has_detection:
        yolo_readiness = "conversion_required"
    else:
        yolo_readiness = "review_required"
    if has_segmentation:
        sam3_readiness = "mask_ready"
    elif has_detection or has_coco:
        sam3_readiness = "box_prompt_convertible"
    else:
        sam3_readiness = "review_required"
    task_tags = sorted(tag.removeprefix("task_categories:") for tag in tags if tag.startswith("task_categories:"))
    if not task_tags:
        task_tags = ["unknown"]
    annotation_types: list[str] = []
    if has_yolo:
        annotation_types.append("YOLO (directory tag)")
    if has_coco:
        annotation_types.append("COCO (directory tag)")
    if has_segmentation:
        annotation_types.append("segmentation (directory tag)")
    if not annotation_types:
        annotation_types.append("unknown")
    return DatasetCandidate(
        source_id=f"huggingface:{dataset_id}",
        title=dataset_id,
        provider="Hugging Face Hub",
        catalog_url=f"https://huggingface.co/datasets/{dataset_id}",
        tasks=task_tags,
        annotation_types=annotation_types,
        modalities=["image or multimodal; inspect dataset card"],
        yolo_readiness=yolo_readiness,
        sam3_readiness=sam3_readiness,
        license=card_license or "not declared in API response",
        commercial_use="unknown",
        access="terms_acceptance_required",
        estimated_size="inspect dataset card and repository files",
        priority="P3",
        summary=f'Hugging Face public-directory candidate discovered by query "{query}".',
        risk_notes="Directory tags and license fields are unverified metadata. Review the dataset card, files, upstream rights and personal-data risk before any download.",
        discovery_origin=f"huggingface-api:{query}",
        last_seen_at=discovered_at,
    )


def fetch_hugging_face_candidates(
    *,
    queries: tuple[str, ...] = DEFAULT_HUGGING_FACE_QUERIES,
    limit_per_query: int = 40,
    timeout_seconds: float = 15,
    request_delay_seconds: float = 1,
) -> tuple[list[DatasetCandidate], list[str]]:
    """Read public Hugging Face directory metadata without downloading dataset files."""
    if limit_per_query < 1 or limit_per_query > 100:
        raise ValueError("limit_per_query must be between 1 and 100")
    discovered_at = _now()
    candidates: list[DatasetCandidate] = []
    errors: list[str] = []
    for index, query in enumerate(queries):
        if index:
            time.sleep(max(0, request_delay_seconds))
        url = "https://huggingface.co/api/datasets?" + urlencode(
            {"search": query, "limit": str(limit_per_query), "full": "true"}
        )
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "SenseMuDatasetCatalog/1.0"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise TypeError("unexpected Hugging Face API response")
            candidates.extend(
                candidate
                for item in payload
                if isinstance(item, dict)
                for candidate in [hugging_face_candidate(item, query=query, discovered_at=discovered_at)]
                if candidate is not None
            )
        except (OSError, TimeoutError, TypeError, json.JSONDecodeError) as error:
            errors.append(f"Hugging Face query {query!r}: {error}")
    return candidates, errors


def merge_candidates(*groups: list[DatasetCandidate]) -> list[DatasetCandidate]:
    """Keep the most actionable entry for a source ID and return a stable queue order."""
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    merged: dict[str, DatasetCandidate] = {}
    for candidate in (candidate for group in groups for candidate in group):
        current = merged.get(candidate.source_id)
        if current is None or rank[candidate.priority] < rank[current.priority]:
            merged[candidate.source_id] = candidate
    return sorted(merged.values(), key=lambda item: (rank[item.priority], item.provider.lower(), item.title.lower()))


def build_catalog_document(candidates: list[DatasetCandidate], *, errors: list[str]) -> dict[str, object]:
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "generated_at": _now(),
        "discovery_only": True,
        "ingestion_rule": "No row may be downloaded or imported until an owner reviews license, upstream terms, personal-data exposure, checksum and target task fit.",
        "errors": errors,
        "items": [candidate.as_dict() for candidate in candidates],
    }


def _pipe(values: list[str]) -> str:
    return " | ".join(values)


def write_catalog_outputs(catalog: dict[str, object], output_dir: Path, *, markdown_rows: int = 80) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    items = catalog.get("items")
    if not isinstance(items, list):
        raise TypeError("catalog items must be a list")
    candidates = [candidate_from_mapping(item) for item in items if isinstance(item, dict)]
    if len(candidates) != len(items):
        raise ValueError("catalog items must be objects")
    json_path = output_dir / "open-vision-datasets.json"
    csv_path = output_dir / "open-vision-datasets.csv"
    markdown_path = output_dir / "open-vision-datasets.md"
    queue_path = output_dir / "storage-intake-queue.csv"
    json_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = list(DatasetCandidate.__dataclass_fields__)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            row = candidate.as_dict()
            row["tasks"] = _pipe(candidate.tasks)
            row["annotation_types"] = _pipe(candidate.annotation_types)
            row["modalities"] = _pipe(candidate.modalities)
            writer.writerow(row)

    with queue_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "batch", "source_id", "title", "catalog_url", "priority", "commercial_use", "yolo_readiness",
            "sam3_readiness", "intake_status", "required_review",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            batch = "batch-1" if candidate.priority == "P0" else "batch-2" if candidate.priority == "P1" else "backlog"
            writer.writerow(
                {
                    "batch": batch,
                    "source_id": candidate.source_id,
                    "title": candidate.title,
                    "catalog_url": candidate.catalog_url,
                    "priority": candidate.priority,
                    "commercial_use": candidate.commercial_use,
                    "yolo_readiness": candidate.yolo_readiness,
                    "sam3_readiness": candidate.sam3_readiness,
                    "intake_status": "catalogued_not_downloaded",
                    "required_review": "license, upstream terms, personal data, task fit, checksum, storage budget",
                }
            )

    priority_counts = Counter(candidate.priority for candidate in candidates)
    lines = [
        "# Open Vision Dataset Catalog",
        "",
        f"Generated: {catalog.get('generated_at', 'unknown')}",
        "",
        "This is a discovery catalog, not a download list. Every row remains `catalogued_not_downloaded` until a named reviewer confirms the upstream license, commercial rights, personal-data boundary, task fit, checksum and storage budget.",
        "",
        f"Candidates: {len(candidates)}. Priority split: " + ", ".join(f"{key}={priority_counts[key]}" for key in sorted(priority_counts)),
        "",
        "YOLO readiness describes annotation conversion effort. SAM3 readiness only describes whether the cataloged annotation modality appears usable for a promptable segmentation evaluation; it does not imply a SAM3 training or model-license grant.",
        "",
        "| Priority | Dataset | YOLO | SAM3 | Commercial use | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates[:markdown_rows]:
        lines.append(
            f"| {candidate.priority} | {candidate.title} | {candidate.yolo_readiness} | {candidate.sam3_readiness} | {candidate.commercial_use} | [{candidate.provider}]({candidate.catalog_url}) |"
        )
    if len(candidates) > markdown_rows:
        lines.extend(["", f"Only the first {markdown_rows} rows are shown here. The complete table is in `open-vision-datasets.csv` and `open-vision-datasets.json`."])
    errors = catalog.get("errors")
    if isinstance(errors, list) and errors:
        lines.extend(["", "## Discovery Errors", ""] + [f"- {error}" for error in errors if isinstance(error, str)])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path, "queue": queue_path}
