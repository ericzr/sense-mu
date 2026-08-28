from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base
from sensemu_api.db.models import (
    Dataset,
    DatasetVersion,
    Project,
    WorkspaceMembership,
)
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app
from sensemu_api.storage import get_storage


class _MemoryStorage:
    def put_json(self, key: str, payload: dict[str, object]) -> str:
        del payload
        return f"memory://{key}"

    def get_json(self, uri: str) -> dict[str, object]:
        raise KeyError(uri)


def _client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with testing_session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_storage] = _MemoryStorage
    return TestClient(application), testing_session


def _payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "工地安全帽目标检测数据",
        "summary": "覆盖室内外工地常见视角的安全帽与人员目标检测冻结数据版本。",
        "source_summary": "由数据供应方在自有且已获授权的工地摄像头中采集。",
        "collection_method": "固定摄像头按时段抽帧，经人工去重和标注后形成。",
        "coverage_summary": "包含晴天、阴天、室内与夜间补光场景，覆盖多个拍摄高度。",
        "known_limitations": "远距离小目标和强逆光样本数量仍然有限，不适合直接用于人脸识别。",
        "license_code": "CUSTOM-COMMERCIAL",
        "custom_license_terms": "允许购买方内部训练和商用衍生模型，禁止再分发原始数据。",
        "allow_commercial_use": True,
        "allow_model_training": True,
        "allow_derivative_models": True,
        "allow_redistribution": False,
        "contains_personal_data": False,
        "privacy_treatment": "采集前已排除人脸可辨识画面，并删除设备与位置元数据。",
        "rights_confirmed": True,
    }
    payload.update(updates)
    return payload


def _seed_version(
    testing_session: sessionmaker[Session],
    workspace_id: str,
    *,
    version_number: int,
) -> DatasetVersion:
    with testing_session() as session:
        project = session.scalar(
            select(Project).where(Project.workspace_id == UUID(workspace_id))
        )
        if project is None:
            project = Project(
                workspace_id=UUID(workspace_id),
                slug="data-market-project",
                name="数据市场项目",
                task_type="object-detection",
            )
            session.add(project)
            session.flush()
        dataset = session.scalar(
            select(Dataset).where(Dataset.project_id == project.id)
        )
        if dataset is None:
            dataset = Dataset(project_id=project.id, name="工地安全数据")
            session.add(dataset)
            session.flush()
        version = DatasetVersion(
            dataset_id=dataset.id,
            version_number=version_number,
            status="frozen",
            manifest_uri=f"local://versions/{version_number}/manifest.json",
            asset_count=42680,
            class_map={"0": "person", "1": "helmet"},
            frozen_at=datetime.now(UTC),
        )
        session.add(version)
        session.commit()
        return version


def test_publish_and_discover_trusted_data_card() -> None:
    client, testing_session = _client()
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "data-provider", "name": "数据供应方"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    version = _seed_version(testing_session, workspace["id"], version_number=1)

    published = client.post(
        f"/api/v1/dataset-versions/{version.id}/data-listing",
        headers=headers,
        json=_payload(),
    )
    assert published.status_code == 201
    card = published.json()
    assert card["asset_count"] == 42680
    assert card["class_map"] == {"0": "person", "1": "helmet"}
    assert card["provider_name"] == "数据供应方"
    assert card["quality_report"] is None
    assert "manifest_uri" not in card
    assert card["review_basis"] == "provider_attestation"
    assert card["delivery_mode"] == "workspace_copy_after_authorization"
    assert card["delivery_status"] == "prepared_not_open"
    assert len(card["delivery_spec_hash"]) == 64
    assert "local://" not in str(card)

    delivery_spec = client.get(
        f"/api/v1/data-market/listings/{card['id']}/delivery-spec",
        headers=headers,
    )
    assert delivery_spec.status_code == 200
    spec = delivery_spec.json()
    assert spec["content_hash"] == card["delivery_spec_hash"]
    assert spec["delivery_mode"] == "workspace_copy_after_authorization"
    assert "对象地址" in spec["access_boundary"][0]
    assert "spec_uri" not in spec

    listed = client.get("/api/v1/data-market/listings", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["dataset_version_id"] == str(version.id)
    public_listed = client.get("/api/v1/data-market/listings/public")
    assert public_listed.status_code == 200
    assert public_listed.json()[0]["dataset_version_id"] == str(version.id)
    provider_dashboard = client.get(
        "/api/v1/provider/dashboard", headers=headers
    )
    assert provider_dashboard.status_code == 200
    assert provider_dashboard.json()["data_listing_count"] == 1
    assert provider_dashboard.json()["data_listings"][0]["asset_count"] == 42680
    assert client.post(
        f"/api/v1/dataset-versions/{version.id}/data-listing",
        headers=headers,
        json=_payload(),
    ).status_code == 409


def test_data_market_publication_gates_rights_privacy_and_role() -> None:
    client, testing_session = _client()
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "gated-provider", "name": "受控数据供应方"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    personal_version = _seed_version(testing_session, workspace["id"], version_number=1)
    personal = client.post(
        f"/api/v1/dataset-versions/{personal_version.id}/data-listing",
        headers=headers,
        json=_payload(contains_personal_data=True),
    )
    assert personal.status_code == 409
    rights_missing = client.post(
        f"/api/v1/dataset-versions/{personal_version.id}/data-listing",
        headers=headers,
        json=_payload(rights_confirmed=False),
    )
    assert rights_missing.status_code == 422

    with testing_session() as session:
        membership = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == UUID(workspace["id"]),
                WorkspaceMembership.status == "active",
            )
        )
        assert membership is not None
        membership.role = "member"
        session.commit()
    member_attempt = client.post(
        f"/api/v1/dataset-versions/{personal_version.id}/data-listing",
        headers=headers,
        json=_payload(),
    )
    assert member_attempt.status_code == 403
    assert client.get("/api/v1/provider/dashboard", headers=headers).status_code == 403
