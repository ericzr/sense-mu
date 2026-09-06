# 数据集来源清单（算法市场 / 数据市场 Mock 卡片）

本清单记录 `apps/web/lib/catalog-mock-data.ts` 中各演示数据卡引用的**真实公开数据集**，
每条来源均核实过公开规模与当前可见授权状态（2026-09 核查）；授权待核验的社区来源不会被标成可商用。许可代码含义见
`data-market-workbench.tsx` 的 `licenseLabels`：

- `CC-BY-4.0`：署名使用，允许商业
- `CC-BY-SA-4.0`：署名-相同方式共享，允许商业（衍生数据须同许可）
- `CUSTOM-RESEARCH`：研究用途授权，**默认不允许商业**，商用前需联系原作者

## 有真实公开数据集支撑的卡片

| 卡片 | 数据集 | 规模 | 许可 |
|---|---|---|---|
| 工地安全穿戴 | SH17 — github.com/ahmadmughees/sh17dataset（arXiv:2407.04590） | 8,099 图 / 75,994 实例 / 17 类 | CC BY-NC-SA 4.0（非商业） |
| 仓储烟火 / 森林烟火 / 城市火情 / 生态烟雾 | D-Fire — github.com/gaiasd/DFireDataset | 21,527 图（明火 14,692 框、烟雾 11,865 框） | 研究授权（Venâncio et al. 2022） |
| 森林烟火（补充） | FLAME — IEEE Dataport | 航拍林火视频帧 | 注册获取 |
| 道路车辆 / 交通停车 | BDD100K — bdd-data.berkeley.edu | 100,000 图 | 非商业研究 |
| 道路车辆（补充） | UA-DETRAC | 100,000+ 帧 | 研究授权 |
| 金属表面缺陷 | NEU-DET（1,800 张 6 类）+ GC10-DET（约 2,300 张 10 类） | — | 学术研究 |
| 零售货架 | SKU-110K — github.com/eg4000/SKU110K_CVPR19 | 11,762 图 / 170 万+ 框 | 研究授权 |
| 农产品分选 | Fruits-360 — github.com/Horea94/Fruit-Images-Dataset | 约 90,483 图 / 130+ 类 | MIT（仓库；仍需核对数据分发条款） |
| 果园果实计数 | MinneApple — arXiv:1905.11451；页面样本来自 Orchard Apple Detection Dataset | 1,349 图 / 7 万+ 实例（MinneApple） | 学术研究；社区样本授权待核验 |
| 路面病害 / 市政坑槽 | RDD2022 — figshare.com/21431547（arXiv:2209.08538） | 47,420 图 / 55,000+ 实例 / 6 国 | CC BY-SA 4.0（美国子集 Google 街景，非商业） |
| 交安设施（标志类） | TTPLA（约 940 张航拍标志牌）+ GTSDB/CCTSDB | — | 逐集核验 |
| 路基边坡 | Landslide4Sense — IEEE DataPort | 3,799 个 Sentinel-2 切片 | 研究用途 |
| 桥梁病害 | CODEBRIM（1,569 图 6 类多标签）+ SDNET2018（5.6 万+ 图） | — | 研究用途 |
| 路域环境 / 市容垃圾 | TACO — tacodataset.org | 约 1,500 图 / 28 类 | CC BY 4.0 |
| 人员聚集 | JHU-CROWD++（4,372 图）+ ShanghaiTech A/B（1,914 图） | — | 学术研究 |

## 当前没有已核验原始单图、明确标注为演示样例的卡片

隧道设施、违法建设、建筑垃圾渣土、户外广告招牌、
河道水域污染、园林绿化、交安设施（护栏类）、市政设施（井盖/路灯类）、
工地扬尘/围挡类、违停/应急车道类。

包裹、货架、蜂箱卡片目前使用公开仓库 README/项目页中的官方预览图，已在页面标为
「数据集官方预览图」，不承诺这些文件就是可下载的原始训练单图；果园卡片使用公开社区仓库的一张真实标注样本，但授权仍需单独核验。
其余卡片已在 `source` / `method` / `limitations` 字段中如实标注
「当前为演示数据，不承诺样本出处」，正式版本需自建采集并标注。

## 引用规范

任何基于上述公开数据集的训练或二次发布，均需在文档与页面中保留原始论文引用，
详见各数据集官方仓库的 Citation 说明。
