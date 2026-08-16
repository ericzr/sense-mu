# ADR-0002: 训练执行合同与事实状态

- 状态：Accepted
- 日期：2026-08-08

## 决策

API 是训练任务、事件和模型版本的唯一事实源。Worker 不直连业务数据库，只通过内部接口领取任务、回传事件并登记产物。

每次队列投递产生唯一 `attempt_id`。API 使用行锁和 `execution_token` 只允许一个尝试领取 `queued` 任务，防止重复投递导致双重训练。Worker 事件带唯一 `event_id`，API 按 `(run_id, event_id)` 幂等处理。

领取成功后 Worker 定期向 API 续期租约，心跳只更新 `Run.heartbeat_at`，不产生高频事件。定时回收任务查找超过租约期限的执行：普通执行重新排队并废止旧 `attempt_id`；处于 `cancel_requested` 的执行直接收敛为 `cancelled`；达到最大执行次数的任务转为 `failed`。旧 Worker 一旦发现心跳被拒绝，必须停止容器和产物回传。

首个引擎适配器是 Ultralytics YOLO，首个执行器是 Docker。Worker 从冻结 manifest 准备一次性 YOLO 数据目录，通过 Docker API 将数据打包写入隔离容器，完成后只取回 `best.pt` 和真实指标文件。训练容器不获取数据库凭据或 Worker 凭据。

## 状态规则

`queued → preparing → running → succeeded | failed | cancelled`。

- 只有 Worker 的真实日志才能推进训练进度。
- 进度不得回退，完成前最高为 99。
- `ModelVersion` 只能在模型文件已上传后由完成事件原子创建。
- 排队中的任务可直接取消；已领取任务使用 `cancel_requested` 等待执行器停止容器。

## 当前边界

Docker Socket 只作为本地和单机执行器。生产多租户上线前，应将同一执行合同替换为受限的远程 GPU 执行器，不向通用 Worker 暴露主机 Docker Socket。生产环境的定时调度器必须保持单实例，多个训练 Worker 可以水平扩展。
