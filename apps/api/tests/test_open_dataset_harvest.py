from pathlib import Path

import pytest

from sensemu_api.open_dataset_harvest import (
    build_catalog_document,
    candidate_from_mapping,
    fetch_hugging_face_candidates,
    hugging_face_candidate,
    load_curated_candidates,
    merge_candidates,
    write_catalog_outputs,
)


def sample_candidate(source_id: str = "test:sample") -> dict[str, object]:
    return {
        "source_id": source_id,
        "title": "Sample Vision Dataset",
        "provider": "Test Provider",
        "catalog_url": "https://example.test/dataset",
        "tasks": ["object detection"],
        "annotation_types": ["bounding boxes"],
        "modalities": ["images"],
        "yolo_readiness": "conversion_required",
        "sam3_readiness": "box_prompt_convertible",
        "license": "CC BY 4.0",
        "commercial_use": "allowed",
        "access": "direct_public",
        "estimated_size": "small",
        "priority": "P0",
        "summary": "Candidate for a fully reviewed test flow.",
        "risk_notes": "Review before download.",
    }


def test_curated_manifest_is_parseable_and_discovery_only():
    manifest = Path(__file__).resolve().parents[3] / "docs/open-data-catalog/curated-open-vision-datasets.json"
    candidates = load_curated_candidates(manifest)

    assert len(candidates) >= 20
    assert {candidate.source_id for candidate in candidates} >= {"coco:2017", "taco:2020", "sa1b:1.0"}
    assert all(candidate.access for candidate in candidates)
    assert all(candidate.risk_notes for candidate in candidates)


def test_hugging_face_candidate_is_never_auto_approved_for_commercial_intake():
    candidate = hugging_face_candidate(
        {
            "id": "example/public-yolo-segmentation",
            "tags": ["yolo", "coco", "instance-segmentation", "task_categories:object-detection"],
            "cardData": {"license": "mit"},
        },
        query="yolo",
        discovered_at="2026-09-06T00:00:00+00:00",
    )

    assert candidate is not None
    assert candidate.yolo_readiness == "native_yolo"
    assert candidate.sam3_readiness == "mask_ready"
    assert candidate.commercial_use == "unknown"
    assert candidate.priority == "P3"
    assert candidate.access == "terms_acceptance_required"


def test_catalog_outputs_preserve_review_gate(tmp_path: Path):
    reviewed = candidate_from_mapping(sample_candidate())
    catalog = build_catalog_document(merge_candidates([reviewed]), errors=[])
    outputs = write_catalog_outputs(catalog, tmp_path)

    assert "catalogued_not_downloaded" in outputs["queue"].read_text(encoding="utf-8")
    assert "No row may be downloaded" in outputs["json"].read_text(encoding="utf-8")
    assert "Sample Vision Dataset" in outputs["markdown"].read_text(encoding="utf-8")


def test_rejects_invalid_readiness_value():
    raw = sample_candidate()
    raw["yolo_readiness"] = "ready"

    with pytest.raises(ValueError, match="unsupported yolo_readiness"):
        candidate_from_mapping(raw)


def test_remote_fetch_limits_are_bounded_without_making_network_calls():
    with pytest.raises(ValueError, match="limit_per_query"):
        fetch_hugging_face_candidates(queries=("yolo",), limit_per_query=101)
