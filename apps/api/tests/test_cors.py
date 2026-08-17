import pytest
from fastapi.testclient import TestClient

from sensemu_api.main import create_app


@pytest.mark.parametrize("method", ["DELETE", "PUT"])
def test_browser_preflight_allows_supported_write_methods(method: str) -> None:
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": (
                    "X-Workspace-ID, Content-Type, X-Amz-Meta-Sha256"
                ),
            },
        )

    assert response.status_code == 200
    allowed_methods = response.headers["access-control-allow-methods"]
    assert method in {value.strip() for value in allowed_methods.split(",")}
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-amz-meta-sha256" in {
        value.strip() for value in allowed_headers.split(",")
    }
