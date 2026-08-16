from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base
from sensemu_api.db.models import (
    CapabilitySpec,
    Deployment,
    MarketplaceLedgerEntry,
    MarketplaceListing,
    MarketplaceListingReview,
    Model,
    ModelVersion,
    Project,
    UsageReservation,
    Workspace,
)
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app


def test_marketplace_listing_subscription_and_atomic_quota() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    owner_key = "smu_live_owner-test-key"
    with testing_session() as session:
        provider = Workspace(slug="provider", name="算法供应方")
        buyer = Workspace(slug="buyer", name="应用开发方")
        session.add_all([provider, buyer])
        session.flush()
        project = Project(
            workspace_id=provider.id,
            slug="helmet",
            name="安全帽检测",
            task_type="object-detection",
        )
        session.add(project)
        session.flush()
        model = Model(project_id=project.id, name="安全帽检测模型", task_type="object-detection")
        session.add(model)
        session.flush()
        model_version = ModelVersion(
            model_id=model.id,
            run_id=uuid4(),
            version_number=1,
            status="approved",
            artifact_uri="s3://sensemu-test/models/helmet.pt",
            metrics={"map50": 0.9},
        )
        session.add(model_version)
        session.flush()
        deployment = Deployment(
            workspace_id=provider.id,
            model_version_id=model_version.id,
            name="安全帽检测服务",
            endpoint_slug="helmet-detector",
            environment="production",
            status="published",
            api_key_prefix=owner_key[:16],
            api_key_hash=sha256(owner_key.encode()).hexdigest(),
            published_at=datetime.now(UTC),
        )
        session.add(deployment)
        session.flush()
        capability = CapabilitySpec(
            workspace_id=provider.id,
            deployment_id=deployment.id,
            capability_slug="ppe-compliance",
            version_number=1,
            display_name="PPE 合规检测",
            problem_definition="识别固定监控视角中的人员安全帽佩戴情况。",
            input_spec={
                "media_types": ["image/jpeg", "image/png"],
                "max_payload_bytes": 8_388_608,
                "capture_constraints": "固定监控视角，人员高度不低于 80 像素。",
            },
            output_spec={
                "contract": "detections.v1",
                "classes": ["person", "hardhat"],
                "business_events": ["missing_hardhat"],
            },
            applicability={
                "verified_scenes": ["construction-site"],
                "unsupported_conditions": ["严重逆光", "严重遮挡"],
            },
            delivery={
                "profiles": ["shared-api"],
                "data_retention_default": "none",
            },
            evidence={"evaluation_id": str(uuid4())},
            status="published",
            content_hash="b" * 64,
            spec_uri="s3://sensemu-test/capabilities/ppe-compliance/v1.json",
            published_at=datetime.now(UTC),
        )
        session.add(capability)
        session.commit()
        provider_id = str(provider.id)
        buyer_id = str(buyer.id)
        deployment_id = str(deployment.id)
        capability_id = str(capability.id)

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
    client = TestClient(application)

    missing_capability = client.post(
        f"/api/v1/capability-specs/{uuid4()}/marketplace-listing",
        headers={"X-Workspace-ID": provider_id},
        json={
            "title": "无效商品",
            "summary": "不得绕过能力契约直接提交在线服务。",
            "price_per_1000_cents": 3900,
            "monthly_quota_units": 10,
        },
    )
    assert missing_capability.status_code == 404

    listing_response = client.post(
        f"/api/v1/capability-specs/{capability_id}/marketplace-listing",
        headers={"X-Workspace-ID": provider_id},
        json={
            "title": "工地安全帽检测",
            "summary": "识别施工现场人员是否正确佩戴安全帽。",
            "price_per_1000_cents": 3900,
            "monthly_quota_units": 10,
        },
    )
    assert listing_response.status_code == 201
    listing = listing_response.json()
    assert listing["provider_name"] == "算法供应方"
    assert listing["capability_spec_id"] == capability_id
    assert listing["capability_slug"] == "ppe-compliance"
    assert listing["capability_version_number"] == 1
    assert listing["capability_display_name"] == "PPE 合规检测"
    assert listing["capability_output_contract"] == "detections.v1"
    assert listing["capability_verified_scenes"] == ["construction-site"]
    assert listing["capability_unsupported_conditions"] == ["严重逆光", "严重遮挡"]
    assert listing["endpoint_url"].endswith("/helmet-detector:predict")
    assert listing["status"] == "pending_review"
    assert listing["published_at"] is None

    hidden_listing = client.get(
        "/api/v1/marketplace/listings",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert hidden_listing.status_code == 200
    assert hidden_listing.json() == []
    hidden_checkout = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert hidden_checkout.status_code == 404
    pending_submissions = client.get(
        "/api/v1/marketplace/submissions",
        headers={"X-Workspace-ID": provider_id},
    )
    assert pending_submissions.status_code == 200
    assert pending_submissions.json()[0]["status"] == "pending_review"
    assert pending_submissions.json()[0]["review_note"] is None

    rejected_reviewer = client.post(
        f"/api/v1/internal/marketplace/listings/{listing['id']}:review",
        headers={"X-SenseMu-Platform-Review-Token": "invalid-review-token"},
        json={
            "decision": "approved",
            "reviewer_identity": "平台审核员",
            "note": "生产服务与验收报告已核验。",
        },
    )
    assert rejected_reviewer.status_code == 403
    rejected_review = client.post(
        f"/api/v1/internal/marketplace/listings/{listing['id']}:review",
        headers={
            "X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"
        },
        json={
            "decision": "rejected",
            "reviewer_identity": "平台审核员",
            "note": "请补充算法适用边界说明后重新提交。",
        },
    )
    assert rejected_review.status_code == 200
    assert rejected_review.json()["status"] == "rejected"
    assert client.get(
        "/api/v1/marketplace/listings",
        headers={"X-Workspace-ID": buyer_id},
    ).json() == []
    rejected_submissions = client.get(
        "/api/v1/marketplace/submissions",
        headers={"X-Workspace-ID": provider_id},
    ).json()
    assert rejected_submissions[0]["status"] == "rejected"
    assert (
        rejected_submissions[0]["review_note"]
        == "请补充算法适用边界说明后重新提交。"
    )
    assert rejected_submissions[0]["reviewed_at"] is not None

    resubmitted_response = client.post(
        f"/api/v1/capability-specs/{capability_id}/marketplace-listing",
        headers={"X-Workspace-ID": provider_id},
        json={
            "title": "工地安全帽检测",
            "summary": "识别施工现场人员是否正确佩戴安全帽，并明确仅适用于固定监控视角。",
            "price_per_1000_cents": 3900,
            "monthly_quota_units": 10,
        },
    )
    assert resubmitted_response.status_code == 201
    assert resubmitted_response.json()["id"] == listing["id"]
    assert resubmitted_response.json()["status"] == "pending_review"

    with testing_session() as session:
        stored_deployment = session.get(Deployment, UUID(deployment_id))
        assert stored_deployment is not None
        stored_deployment.status = "disabled"
        session.commit()
    unavailable_capability_review = client.post(
        f"/api/v1/internal/marketplace/listings/{listing['id']}:review",
        headers={
            "X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"
        },
        json={
            "decision": "approved",
            "reviewer_identity": "平台审核员",
            "note": "服务已停用时不得批准。",
        },
    )
    assert unavailable_capability_review.status_code == 409
    with testing_session() as session:
        stored_deployment = session.get(Deployment, UUID(deployment_id))
        assert stored_deployment is not None
        stored_deployment.status = "published"
        session.commit()

    review = client.post(
        f"/api/v1/internal/marketplace/listings/{listing['id']}:review",
        headers={
            "X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"
        },
        json={
            "decision": "approved",
            "reviewer_identity": "平台审核员",
            "note": "生产服务与验收报告已核验。",
        },
    )
    assert review.status_code == 200
    assert review.json()["status"] == "published"
    assert review.json()["reviewer_identity"] == "平台审核员"
    public_listings = client.get(
        "/api/v1/marketplace/listings",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert public_listings.status_code == 200
    assert [item["id"] for item in public_listings.json()] == [listing["id"]]
    own_checkout = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": provider_id},
    )
    assert own_checkout.status_code == 409
    with testing_session() as session:
        review_history = session.scalars(
            select(MarketplaceListingReview).where(
                MarketplaceListingReview.listing_id == UUID(listing["id"])
            ).order_by(MarketplaceListingReview.reviewed_at)
        ).all()
        assert [item.decision for item in review_history] == ["rejected", "approved"]
    repeated_review = client.post(
        f"/api/v1/internal/marketplace/listings/{listing['id']}:review",
        headers={
            "X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"
        },
        json={
            "decision": "approved",
            "reviewer_identity": "平台审核员",
        },
    )
    assert repeated_review.status_code == 409

    subscribed_response = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert subscribed_response.status_code == 201
    subscription = subscribed_response.json()
    assert subscription["status"] == "pending_payment"
    assert subscription["api_key_prefix"] is None
    assert subscription["started_at"] is None
    assert subscription["remaining_units"] == 10
    assert subscription["order_number"].startswith("smu_ord_")
    assert subscription["payment_status"] == "not_collected"
    assert subscription["payment_intent_status"] == "requires_provider"
    assert subscription["expected_amount_yuan"] == 0.39
    assert subscription["checkout_available"] is False
    payment_intent_id = subscription["payment_intent_id"]

    repeated_checkout = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert repeated_checkout.status_code == 201
    assert repeated_checkout.json()["order_number"] == subscription["order_number"]
    assert repeated_checkout.json()["reused"] is True

    premature_claim = client.post(
        f"/api/v1/marketplace/subscriptions/{subscription['id']}:claim-key",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert premature_claim.status_code == 409

    payment_headers = {
        "X-SenseMu-Payment-Adapter-Token": "sensemu-payment-adapter-local-only"
    }

    def send_payment_event(
        external_event_id: str,
        event_type: str,
        amount_micros: int,
        payload_sha256: str,
        *,
        provider_refund_id: str | None = None,
    ):
        return client.post(
            "/api/v1/internal/payments/normalized-events",
            headers=payment_headers,
            json={
                "payment_intent_id": payment_intent_id,
                "provider": "testpay",
                "external_event_id": external_event_id,
                "provider_payment_id": "pay_market_001",
                "event_type": event_type,
                "amount_micros": amount_micros,
                "currency": "CNY",
                "payload_sha256": payload_sha256,
                "occurred_at": datetime.now(UTC).isoformat(),
                "provider_refund_id": provider_refund_id,
            },
        )

    rejected_adapter = client.post(
        "/api/v1/internal/payments/normalized-events",
        headers={"X-SenseMu-Payment-Adapter-Token": "invalid-adapter-token"},
        json={
            "payment_intent_id": payment_intent_id,
            "provider": "testpay",
            "external_event_id": "evt_rejected_adapter_001",
            "provider_payment_id": "pay_market_001",
            "event_type": "payment.succeeded",
            "amount_micros": 390000,
            "currency": "CNY",
            "payload_sha256": "0" * 64,
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert rejected_adapter.status_code == 403

    wrong_amount = send_payment_event(
        "evt_wrong_amount_001",
        "payment.succeeded",
        390001,
        "1" * 64,
    )
    assert wrong_amount.status_code == 409

    paid = send_payment_event(
        "evt_payment_success_001",
        "payment.succeeded",
        390000,
        "2" * 64,
    )
    assert paid.status_code == 200
    assert paid.json()["payment_intent_status"] == "succeeded"
    assert paid.json()["order_payment_status"] == "paid"
    assert paid.json()["order_status"] == "entitlement_issued"
    assert paid.json()["subscription_status"] == "active"
    assert paid.json()["paid_amount_yuan"] == 0.39
    paid_retry = send_payment_event(
        "evt_payment_success_001",
        "payment.succeeded",
        390000,
        "2" * 64,
    )
    assert paid_retry.status_code == 200
    assert paid_retry.json()["reused"] is True

    stale_failure = send_payment_event(
        "evt_payment_failure_late_001",
        "payment.failed",
        390000,
        "3" * 64,
    )
    assert stale_failure.status_code == 200
    assert stale_failure.json()["processing_status"] == "ignored_stale"
    assert stale_failure.json()["order_payment_status"] == "paid"

    claimed_response = client.post(
        f"/api/v1/marketplace/subscriptions/{subscription['id']}:claim-key",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert claimed_response.status_code == 200
    market_key = claimed_response.json()["api_key"]
    assert market_key.startswith("smu_market_")
    assert claimed_response.json()["credential_claimed_at"]
    repeated_claim = client.post(
        f"/api/v1/marketplace/subscriptions/{subscription['id']}:claim-key",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert repeated_claim.status_code == 409

    active_checkout = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert active_checkout.status_code == 409

    rotated_response = client.post(
        f"/api/v1/marketplace/subscriptions/{subscription['id']}:rotate-key",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert rotated_response.status_code == 200
    rotated_key = rotated_response.json()["api_key"]
    assert rotated_key != market_key
    rejected_old_key = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers={
            "X-SenseMu-Gateway-Token": "sensemu-gateway-local-only",
            "X-API-Key": market_key,
        },
        json={
            "request_id": "request-old-key-001",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert rejected_old_key.status_code == 401
    market_key = rotated_key

    gateway_headers = {
        "X-SenseMu-Gateway-Token": "sensemu-gateway-local-only",
        "X-API-Key": market_key,
    }
    released_authorization = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers=gateway_headers,
        json={
            "request_id": "request-market-release",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert released_authorization.status_code == 200
    released = client.post(
        (
            "/api/v1/internal/inference/usage-reservations/"
            f"{released_authorization.json()['reservation_id']}:release"
        ),
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json={"request_id": "request-market-release"},
    )
    assert released.status_code == 200
    assert released.json()["status"] == "released"

    stale_authorization = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers=gateway_headers,
        json={
            "request_id": "request-market-stale",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert stale_authorization.status_code == 200
    with testing_session() as session:
        stale_reservation = session.scalar(
            select(UsageReservation).where(
                UsageReservation.id
                == UUID(stale_authorization.json()["reservation_id"])
            )
        )
        assert stale_reservation is not None
        stale_reservation.created_at = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
    recovered = client.post(
        "/api/v1/internal/inference/usage-reservations:recover-stale",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovered"][0]["request_id"] == "request-market-stale"
    assert recovered.json()["recovered"][0]["released_units"] == 1

    for index, units in enumerate((2, 4, 4), start=1):
        request_id = f"request-market-00{index}"
        authorization = client.post(
            "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
            headers=gateway_headers,
            json={
                "request_id": request_id,
                "billable_units": units,
                "unit": "image",
            },
        )
        assert authorization.status_code == 200
        usage_payload = {
            "deployment_id": deployment_id,
            "reservation_id": authorization.json()["reservation_id"],
            "request_id": request_id,
            "capability_id": "vision.predict",
            "billable_units": units,
            "unit": "image",
            "dimensions": {"input_count": units},
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        usage = client.post(
            "/api/v1/internal/inference/usage-records",
            headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
            json=usage_payload,
        )
        assert usage.status_code == 200
        assert usage.json()["subscription_id"] == subscription["id"]
        if index == 1:
            reused = client.post(
                "/api/v1/internal/inference/usage-records",
                headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
                json=usage_payload,
            )
            assert reused.json()["reused"] is True

    exhausted = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers=gateway_headers,
        json={
            "request_id": "request-market-004",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert exhausted.status_code == 402

    subscriptions = client.get(
        "/api/v1/marketplace/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    ).json()
    assert subscriptions[0]["status"] == "exhausted"
    assert subscriptions[0]["consumed_units"] == 10
    assert subscriptions[0]["remaining_units"] == 0

    usage_audit = client.get(
        "/api/v1/marketplace/usage-records?limit=10",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert usage_audit.status_code == 200
    assert len(usage_audit.json()) == 3
    assert usage_audit.json()[0]["listing_title"] == "工地安全帽检测"
    assert usage_audit.json()[0]["estimated_cost_yuan"] == 0.156

    buyer_billing = client.get(
        "/api/v1/marketplace/billing?limit=10",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert buyer_billing.status_code == 200
    assert buyer_billing.json()["authorization_ceiling_yuan"] == 0.39
    assert buyer_billing.json()["unsettled_earnings_yuan"] == 0
    assert len(buyer_billing.json()["orders"]) == 1
    assert buyer_billing.json()["orders"][0]["order_number"] == subscription["order_number"]
    assert buyer_billing.json()["orders"][0]["payment_status"] == "paid"
    assert (
        buyer_billing.json()["orders"][0]["payment_intent_status"]
        == "succeeded"
    )

    provider_billing = client.get(
        "/api/v1/marketplace/billing?limit=10",
        headers={"X-Workspace-ID": provider_id},
    )
    assert provider_billing.status_code == 200
    assert provider_billing.json()["authorization_ceiling_yuan"] == 0
    assert provider_billing.json()["unsettled_earnings_yuan"] == 0.39
    assert len(provider_billing.json()["earnings"]) == 3
    assert {
        earning["request_id"] for earning in provider_billing.json()["earnings"]
    } == {"request-market-001", "request-market-002", "request-market-003"}
    assert provider_billing.json()["earnings"][0]["settlement_status"] == "unsettled"

    provider_profile = client.patch(
        "/api/v1/provider/profile",
        headers={"X-Workspace-ID": provider_id},
        json={
            "public_name": "SenseMu 安全算法实验室",
            "summary": "提供经过质量门禁的工业安全视觉算法与生产推理支持。",
            "provider_type": "organization",
            "support_email": "support@provider.example",
            "website_url": "https://provider.example",
            "service_regions": ["中国大陆", "亚太"],
            "support_commitment": "工作日内响应集成问题，生产故障进入人工排查流程。",
        },
    )
    assert provider_profile.status_code == 200
    assert provider_profile.json()["onboarding_status"] == "profile_complete"
    assert provider_profile.json()["identity_verification_status"] == "not_started"
    assert provider_profile.json()["payout_onboarding_status"] == "not_started"

    provider_dashboard = client.get(
        "/api/v1/provider/dashboard?limit=10",
        headers={"X-Workspace-ID": provider_id},
    )
    assert provider_dashboard.status_code == 200
    dashboard = provider_dashboard.json()
    assert dashboard["profile"]["public_name"] == "SenseMu 安全算法实验室"
    assert dashboard["algorithm_listing_count"] == 1
    assert dashboard["data_listing_count"] == 0
    assert dashboard["active_customer_grants"] == 0
    assert dashboard["successful_units"] == 10
    assert dashboard["authorized_sales_yuan"] == 0.39
    assert dashboard["paid_sales_yuan"] == 0.39
    assert dashboard["unsettled_earnings_yuan"] == 0.39
    assert dashboard["sales"][0]["buyer_name"] == "应用开发方"
    assert len(dashboard["earnings"]) == 3

    partial_refund = send_payment_event(
        "evt_refund_success_001",
        "refund.succeeded",
        100000,
        "4" * 64,
        provider_refund_id="refund_market_001",
    )
    assert partial_refund.status_code == 200
    assert partial_refund.json()["order_payment_status"] == "partially_refunded"
    assert partial_refund.json()["refunded_amount_yuan"] == 0.1
    duplicate_refund = send_payment_event(
        "evt_refund_duplicate_001",
        "refund.succeeded",
        100000,
        "5" * 64,
        provider_refund_id="refund_market_001",
    )
    assert duplicate_refund.status_code == 200
    assert duplicate_refund.json()["processing_status"] == "ignored_duplicate_refund"
    assert duplicate_refund.json()["refunded_amount_yuan"] == 0.1

    final_refund = send_payment_event(
        "evt_refund_success_002",
        "refund.succeeded",
        290000,
        "6" * 64,
        provider_refund_id="refund_market_002",
    )
    assert final_refund.status_code == 200
    assert final_refund.json()["payment_intent_status"] == "refunded"
    assert final_refund.json()["order_payment_status"] == "refunded"
    assert final_refund.json()["order_status"] == "entitlement_revoked"
    assert final_refund.json()["subscription_status"] == "refunded"
    assert final_refund.json()["refunded_amount_yuan"] == 0.39

    revoked_authorization = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers=gateway_headers,
        json={
            "request_id": "request-market-after-refund",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert revoked_authorization.status_code == 401
    revoked_subscription = client.get(
        "/api/v1/marketplace/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    ).json()[0]
    assert revoked_subscription["status"] == "refunded"
    assert revoked_subscription["api_key_prefix"] is None
    assert revoked_subscription["credential_claimed_at"] is None

    billing_after_refund = client.get(
        "/api/v1/marketplace/billing?limit=10",
        headers={"X-Workspace-ID": buyer_id},
    ).json()
    assert billing_after_refund["orders"][0]["payment_status"] == "refunded"
    assert billing_after_refund["orders"][0]["refunded_amount_yuan"] == 0.39

    dashboard_after_refund = client.get(
        "/api/v1/provider/dashboard?limit=10",
        headers={"X-Workspace-ID": provider_id},
    ).json()
    assert dashboard_after_refund["paid_sales_yuan"] == 0.39
    assert dashboard_after_refund["refunded_sales_yuan"] == 0.39
    assert dashboard_after_refund["sales"][0]["payment_status"] == "refunded"

    reconciliation = client.get(
        "/api/v1/internal/marketplace/reconciliation/daily",
        params={"date": datetime.now(UTC).date().isoformat()},
        headers={"X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"},
    )
    assert reconciliation.status_code == 200
    report = reconciliation.json()
    assert report["successful_usage_requests"] >= 1
    assert report["marketplace_usage_requests"] == report["ledger_entries"]
    assert report["marketplace_usage_units"] > 0
    assert report["provider_earnings_yuan"] > 0
    assert report["is_reconciled"] is True
    assert report["issues"] == []

    with testing_session() as session:
        ledger_entry = session.scalar(select(MarketplaceLedgerEntry))
        assert ledger_entry is not None
        session.delete(ledger_entry)
        session.commit()
    mismatch = client.get(
        "/api/v1/internal/marketplace/reconciliation/daily",
        params={"date": datetime.now(UTC).date().isoformat()},
        headers={"X-SenseMu-Platform-Review-Token": "sensemu-platform-review-local-only"},
    )
    assert mismatch.status_code == 200
    assert mismatch.json()["is_reconciled"] is False
    assert mismatch.json()["issues"][0]["code"] == "marketplace_usage_without_ledger"

    with testing_session() as session:
        free_listing = session.get(MarketplaceListing, UUID(listing["id"]))
        assert free_listing is not None
        free_listing.price_per_1000_cents = 0
        session.commit()
    free_checkout = client.post(
        f"/api/v1/marketplace/listings/{listing['id']}/subscriptions",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert free_checkout.status_code == 201
    assert free_checkout.json()["status"] == "active"
    assert free_checkout.json()["payment_status"] == "waived"
    assert free_checkout.json()["payment_intent_status"] == "not_required"
    assert free_checkout.json()["expected_amount_yuan"] == 0
    free_claim = client.post(
        f"/api/v1/marketplace/subscriptions/{subscription['id']}:claim-key",
        headers={"X-Workspace-ID": buyer_id},
    )
    assert free_claim.status_code == 200
    free_market_key = free_claim.json()["api_key"]
    free_authorization = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers={
            "X-SenseMu-Gateway-Token": "sensemu-gateway-local-only",
            "X-API-Key": free_market_key,
        },
        json={
            "request_id": "request-market-free-001",
            "billable_units": 1,
            "unit": "image",
        },
    )
    assert free_authorization.status_code == 200

    owner_authorization = client.post(
        "/api/v1/internal/inference/workspaces/provider/endpoints/helmet-detector:authorize",
        headers={
            "X-SenseMu-Gateway-Token": "sensemu-gateway-local-only",
            "X-API-Key": owner_key,
        },
        json={
            "request_id": "request-owner-001",
            "billable_units": 4,
            "unit": "image",
        },
    )
    assert owner_authorization.status_code == 200
    assert owner_authorization.json()["reservation_id"] is None
