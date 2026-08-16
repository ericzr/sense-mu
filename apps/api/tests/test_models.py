from sqlalchemy import create_engine, inspect, text

from sensemu_api.db import (
    Base,
    models,  # noqa: F401
)


def test_core_traceability_tables_can_be_created() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    assert {
        "assets",
        "capability_specs",
        "dataset_items",
        "dataset_versions",
        "data_marketplace_listings",
        "data_delivery_specs",
        "deployments",
        "models",
        "model_versions",
        "marketplace_listings",
        "marketplace_ledger_entries",
        "marketplace_orders",
        "marketplace_payment_events",
        "marketplace_payment_intents",
        "marketplace_listing_reviews",
        "marketplace_refunds",
        "marketplace_subscriptions",
        "projects",
        "provider_profiles",
        "run_events",
        "runs",
        "usage_records",
        "usage_reservations",
        "user_accounts",
        "video_extraction_outputs",
        "workspace_memberships",
        "workspace_invitations",
        "workspace_access_events",
        "workspaces",
        "workflow_specs",
        "vision_events",
        "webhook_deliveries",
    } <= tables

    reservation_indexes = {
        item["name"] for item in inspect(engine).get_indexes("usage_reservations")
    }
    usage_indexes = {item["name"] for item in inspect(engine).get_indexes("usage_records")}
    order_indexes = {
        item["name"] for item in inspect(engine).get_indexes("marketplace_orders")
    }
    ledger_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("marketplace_ledger_entries")
    }
    membership_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("workspace_memberships")
    }
    invitation_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("workspace_invitations")
    }
    access_event_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("workspace_access_events")
    }
    data_listing_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("data_marketplace_listings")
    }
    data_delivery_spec_indexes = {
        item["name"] for item in inspect(engine).get_indexes("data_delivery_specs")
    }
    capability_indexes = {
        item["name"] for item in inspect(engine).get_indexes("capability_specs")
    }
    workflow_indexes = {
        item["name"] for item in inspect(engine).get_indexes("workflow_specs")
    }
    vision_event_indexes = {
        item["name"] for item in inspect(engine).get_indexes("vision_events")
    }
    webhook_delivery_indexes = {
        item["name"] for item in inspect(engine).get_indexes("webhook_deliveries")
    }
    listing_review_indexes = {
        item["name"]
        for item in inspect(engine).get_indexes("marketplace_listing_reviews")
    }
    listing_unique_constraints = {
        tuple(item["column_names"])
        for item in inspect(engine).get_unique_constraints("marketplace_listings")
    }
    assert "ix_usage_reservations_status_created_at" in reservation_indexes
    assert "ix_usage_records_subscription_occurred_at" in usage_indexes
    assert "ix_marketplace_orders_buyer_created_at" in order_indexes
    assert "ix_marketplace_orders_provider_created_at" in order_indexes
    assert "ix_marketplace_ledger_provider_status_occurred_at" in ledger_indexes
    assert "ix_workspace_memberships_user_status" in membership_indexes
    assert (
        "ix_workspace_invitations_workspace_status_created_at"
        in invitation_indexes
    )
    assert (
        "ix_workspace_access_events_workspace_occurred_at"
        in access_event_indexes
    )
    assert (
        "ix_data_marketplace_listings_status_published_at"
        in data_listing_indexes
    )
    assert "ix_data_delivery_specs_status_created_at" in data_delivery_spec_indexes
    assert (
        "ix_marketplace_listing_reviews_listing_reviewed_at"
        in listing_review_indexes
    )
    assert "ix_capability_specs_workspace_slug_version" in capability_indexes
    assert ("capability_spec_id",) in listing_unique_constraints
    assert "ix_workflow_specs_workspace_slug_version" in workflow_indexes
    assert "ix_vision_events_workspace_occurred_at" in vision_event_indexes
    assert (
        "ix_vision_events_workflow_event_dedupe_occurred_at" in vision_event_indexes
    )
    assert (
        "ix_webhook_deliveries_status_next_attempt_at"
        in webhook_delivery_indexes
    )

    with engine.connect() as connection:
        plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM usage_reservations "
                "WHERE status = 'pending' AND created_at < '2026-08-09'"
            )
        ).all()
    assert any(
        "ix_usage_reservations_status_created_at" in str(row) for row in plan
    )

    with engine.connect() as connection:
        order_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_orders "
                "WHERE buyer_workspace_id = 'buyer' ORDER BY created_at DESC"
            )
        ).all()
        provider_order_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_orders "
                "WHERE provider_workspace_id = 'provider' ORDER BY created_at DESC"
            )
        ).all()
        ledger_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_ledger_entries "
                "WHERE provider_workspace_id = 'provider' "
                "AND settlement_status = 'unsettled' ORDER BY occurred_at DESC"
            )
        ).all()
    assert any("ix_marketplace_orders_buyer_created_at" in str(row) for row in order_plan)
    assert any(
        "ix_marketplace_orders_provider_created_at" in str(row)
        for row in provider_order_plan
    )
    assert any(
        "ix_marketplace_ledger_provider_status_occurred_at" in str(row)
        for row in ledger_plan
    )

    with engine.connect() as connection:
        payment_event_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_payment_events "
                "WHERE provider = 'testpay' AND external_event_id = 'evt_1'"
            )
        ).all()
        refund_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_refunds "
                "WHERE provider = 'testpay' AND provider_refund_id = 'refund_1'"
            )
        ).all()
    assert any("USING INDEX" in str(row) for row in payment_event_plan)
    assert any("USING INDEX" in str(row) for row in refund_plan)

    with engine.connect() as connection:
        membership_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT workspace_id FROM workspace_memberships "
                "WHERE user_id = 'user' AND status = 'active'"
            )
        ).all()
    assert any("ix_workspace_memberships_user_status" in str(row) for row in membership_plan)

    with engine.connect() as connection:
        access_event_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM workspace_access_events "
                "WHERE workspace_id = 'workspace' ORDER BY occurred_at DESC"
            )
        ).all()
    assert any(
        "ix_workspace_access_events_workspace_occurred_at" in str(row)
        for row in access_event_plan
    )

    with engine.connect() as connection:
        listing_review_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM marketplace_listing_reviews "
                "WHERE listing_id = 'listing' ORDER BY reviewed_at DESC"
            )
        ).all()
    assert any(
        "ix_marketplace_listing_reviews_listing_reviewed_at" in str(row)
        for row in listing_review_plan
    )

    with engine.connect() as connection:
        capability_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM capability_specs "
                "WHERE workspace_id = 'workspace' AND capability_slug = 'ppe' "
                "ORDER BY version_number DESC"
            )
        ).all()
    assert any(
        "ix_capability_specs_workspace_slug_version" in str(row)
        for row in capability_plan
    )

    with engine.connect() as connection:
        workflow_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM workflow_specs "
                "WHERE workspace_id = 'workspace' AND workflow_slug = 'ppe' "
                "ORDER BY version_number DESC"
            )
        ).all()
    assert any(
        "ix_workflow_specs_workspace_slug_version" in str(row)
        for row in workflow_plan
    )

    with engine.connect() as connection:
        vision_event_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM vision_events "
                "WHERE workspace_id = 'workspace' ORDER BY occurred_at DESC"
            )
        ).all()
        webhook_delivery_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM webhook_deliveries "
                "WHERE status = 'retrying' AND next_attempt_at < '2026-08-10'"
            )
        ).all()
    assert any(
        "ix_vision_events_workspace_occurred_at" in str(row)
        for row in vision_event_plan
    )
    with engine.connect() as connection:
        vision_event_deduplication_plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM vision_events "
                "WHERE workflow_spec_id = 'workflow' AND event_type = 'missing_hardhat' "
                "AND deduplication_key = 'camera.0' "
                "AND occurred_at >= '2026-08-10' ORDER BY occurred_at DESC"
            )
        ).all()
    assert any(
        "ix_vision_events_workflow_event_dedupe_occurred_at" in str(row)
        for row in vision_event_deduplication_plan
    )
    assert any(
        "ix_webhook_deliveries_status_next_attempt_at" in str(row)
        for row in webhook_delivery_plan
    )
