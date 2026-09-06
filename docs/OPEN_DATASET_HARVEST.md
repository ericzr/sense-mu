# 公开视觉数据集采集与接入队列

## 目的和边界

这个工具建立可审计的候选目录，供对象存储和算力服务器上线后分批评审与接入。它不是通用网页爬虫，也不是自动下载器：不绕过登录、验证码、robots 规则或数据集条款；不抓取受限内容；不下载图片、视频或标注；不把发现记录写入 SenseMu 对象存储、训练数据集或数据市场。

“全网”不可能被一次扫描完整覆盖，也不适合直接作为生产数据源。本阶段以可复核来源为边界：维护人工审核过的来源清单，并可选读取 Hugging Face 的公共目录 API。Kaggle、Roboflow Universe、论文附件和需要账号、邀请或单独许可的目录只记录链接，后续由人工完成许可和下载路径审核。

## 产物

输入清单：`docs/open-data-catalog/curated-open-vision-datasets.json`

离线生成的完整目录：

- `docs/open-data-catalog/generated/open-vision-datasets.csv`：供产品、数据和法务筛选的表格。
- `docs/open-data-catalog/generated/open-vision-datasets.json`：含采集时间、来源和错误信息的机器可读快照。
- `docs/open-data-catalog/generated/open-vision-datasets.md`：便于在仓库中浏览的摘要表。
- `docs/open-data-catalog/generated/storage-intake-queue.csv`：服务器上线后的分批接入队列，所有行初始均为 `catalogued_not_downloaded`。

每条记录均包含来源、任务、标注类型、YOLO 转换就绪度、SAM3 评估就绪度、许可、商用状态、访问方式、优先级和风险说明。

`sam3_readiness` 只表示该数据集声称具有的标注模态是否适合未来进行提示分割评估：`mask_ready`、`box_prompt_convertible`、`review_required` 或 `not_suitable`。它不表示数据集可用于训练任何 SAM3 版本，也不表示已获得模型许可。

## 运行

只生成受版本控制的人工清单，不访问网络：

```bash
make harvest-open-datasets
```

刷新 Hugging Face 的公共目录候选。此动作只请求目录 JSON 元数据，单个查询最多 40 条，查询间隔默认 1 秒：

```bash
make refresh-open-datasets
```

可用参数：

```bash
PYTHONPATH='apps/api/src' .venv/bin/python apps/api/scripts/harvest_open_vision_datasets.py \
  --refresh-huggingface \
  --huggingface-query yolo \
  --huggingface-query 'instance segmentation' \
  --limit-per-query 25 \
  --request-delay 1.5
```

网络错误不会丢掉人工清单；脚本会继续生成文件，并在 JSON 和 Markdown 中登记错误。Hugging Face 标签、卡片许可字段和下载量是未核验目录元数据，因此它们始终是 `P3`、`commercial_use=unknown`、`catalogued_not_downloaded`。

## 存储上线后的接入门禁

任何队列行进入对象存储前，数据负责人必须对该版本创建一份审查记录，并逐项完成：

1. 固化数据集版本、上游页面和许可文本的 URL 与抓取时间。
2. 确认商业训练、衍生模型、再分发和地域限制；图片级许可不允许按数据集整体放宽。
3. 样本抽查个人信息、车牌、人脸、位置和敏感场景，定义脱敏或排除规则。
4. 将上游格式转换到 SenseMu 的 YOLO/COCO 交换契约，校验类别表、图像尺寸、标注范围、数量和 SHA-256。
5. 预估原始文件、转换产物、版本副本和备份后的实际存储预算。
6. 对每次下载记录来源、checksum、操作者、许可证快照、转换器版本和导入清单。
7. 只有冻结后的 `DatasetVersion` 才能进入训练或数据市场；公开目录绝不展示对象路径或下载链接。

P0 只表示优先完成审查，并不等于可自动下载或可上架。研究授权、按图片授权、未知许可和需要登录的数据集应留在 P2/P3，直到法律和业务负责人书面批准。
