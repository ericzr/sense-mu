from typing import Any

import httpx

from sensemu_worker.config import WorkerSettings


class BatchRuntimeError(RuntimeError):
    pass


class BatchRuntimeUnavailable(BatchRuntimeError):
    pass


class BatchRuntimeClient:
    def __init__(self, settings: WorkerSettings) -> None:
        self.url = settings.runtime_url
        self.token = settings.runtime_token

    def predict(
        self,
        *,
        request_id: str,
        model: dict[str, Any],
        contract: str,
        inputs: list[str],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.url}/v1/predict",
                headers={"X-SenseMu-Runtime-Token": self.token},
                json={
                    "request_id": request_id,
                    "contract": contract,
                    "model": model,
                    "inputs": inputs,
                    "parameters": parameters,
                },
                timeout=120,
            )
        except httpx.HTTPError as error:
            raise BatchRuntimeUnavailable("无法连接受限推理运行时") from error
        if response.status_code >= 500:
            raise BatchRuntimeUnavailable(
                f"受限推理运行时暂时不可用 ({response.status_code})"
            )
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise BatchRuntimeError(str(detail))
        try:
            return response.json()
        except ValueError as error:
            raise BatchRuntimeError("推理运行时返回了无效结果") from error
