# SenseMu contracts

该目录存放跨运行时的稳定协议，而不是业务实体的镜像。

- `capability-manifest.schema.json`：算法市场与推理网关共用的轻量能力声明
- `capability-spec.schema.json`：在线服务固化为可审核、可复现能力版本时的完整契约
- `job-event.schema.json`：API、Worker 和可观测系统间的任务事件信封

任何破坏性变更必须升级 `schema_version`。
