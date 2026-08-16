from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class EngineDescriptor(BaseModel):
    key: str
    label: str
    task_types: list[str]
    models: list[str]
    defaults: dict[str, Any]


class EngineAdapter(Protocol):
    descriptor: EngineDescriptor

    def validate_recipe(self, recipe: dict[str, Any]) -> dict[str, Any]: ...


class UltralyticsRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: Literal["yolo26n.pt", "yolo26s.pt", "yolo26m.pt"] = "yolo26s.pt"
    task: Literal["detect"] = "detect"
    epochs: int = Field(default=100, ge=1, le=500)
    image_size: int = Field(default=640, ge=320, le=1536)
    batch_size: int = Field(default=16, ge=1, le=256)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @field_validator("image_size")
    @classmethod
    def image_size_is_stride_aligned(cls, value: int) -> int:
        if value % 32:
            raise ValueError("图像尺寸必须能被 32 整除")
        return value


class UltralyticsEngineAdapter:
    descriptor = EngineDescriptor(
        key="ultralytics",
        label="Ultralytics YOLO",
        task_types=["object-detection"],
        models=["yolo26n.pt", "yolo26s.pt", "yolo26m.pt"],
        defaults=UltralyticsRecipe().model_dump(),
    )

    def validate_recipe(self, recipe: dict[str, Any]) -> dict[str, Any]:
        try:
            return UltralyticsRecipe.model_validate(recipe).model_dump()
        except ValidationError as error:
            field_labels = {
                "model": "基础模型",
                "task": "任务类型",
                "epochs": "训练轮次",
                "image_size": "图像尺寸",
                "batch_size": "批量大小",
                "seed": "随机种子",
            }

            def describe(item: dict[str, Any]) -> str:
                field = str(item["loc"][0]) if item["loc"] else "训练配置"
                label = field_labels.get(field, field)
                error_type = item["type"]
                context = item.get("ctx") or {}
                if error_type == "greater_than_equal":
                    return f"{label}不得小于 {context.get('ge')}"
                if error_type == "less_than_equal":
                    return f"{label}不得大于 {context.get('le')}"
                if error_type == "literal_error":
                    return f"{label}不支持该值"
                if error_type == "extra_forbidden":
                    return f"不允许额外字段 {field}"
                return f"{label}格式不正确"

            messages = "; ".join(
                describe(item) for item in error.errors()
            )
            raise ValueError(messages) from error


ENGINE_ADAPTERS: dict[str, EngineAdapter] = {
    "ultralytics": UltralyticsEngineAdapter(),
}


def get_engine_adapter(key: str) -> EngineAdapter:
    try:
        return ENGINE_ADAPTERS[key]
    except KeyError as error:
        raise ValueError(f"不支持的训练引擎：{key}") from error


def list_engine_descriptors() -> list[EngineDescriptor]:
    return [adapter.descriptor for adapter in ENGINE_ADAPTERS.values()]
