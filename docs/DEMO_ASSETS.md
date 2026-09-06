# SenseMu 演示素材清单

数据市场和算法市场的 mock 卡片使用可追溯的公开数据集原始样本，或在无法取得单张原图时使用数据集官方项目预览图。每张图片的来源、样本标识和许可证均记录在本文件；图片只用于产品预览，页面上的框线和中文标签仍由 mock 数据生成，不能解释为原始标注或真实模型推理结果。

页面所用的可读结构化元数据维护在 `apps/web/lib/catalog-preview-assets.ts`。它是预览图片地址、比例、来源、样本 ID、许可证和原始链接的运行时单一来源；本文件保留完整归因与审核说明。

## 使用边界

- 这些文件不是可交付的数据商品，也不代表 SenseMu 对原始数据集享有所有权。
- Open Images 样本按其图像元数据中记录的 `CC BY 2.0` 使用，发布时保留作者、原始落地页和许可证链接。
- RTK 与 TACO 样本的原始数据集为 `CC BY 4.0`；页面展示没有改变原始图片内容。
- 正式商品发布需要供应方授权、采集和去标识化证据；不能将这里的预览图或 mock 框作为训练、评测或生产结果。
- 页面标记“真实公开样本”表示仓库内保存的是可追溯的单张来源图片；标记“数据集官方预览图”表示来源是官方 README/项目页的样本拼图或结果预览，不能当作原始训练单图。

## 通用视觉能力

| 场景 | 文件 | 数据集样本 | 原始来源与许可证 |
|---|---|---|---|
| 工地安全穿戴 | `catalog-real-ppe.jpg` | SH17 清单中的 Pexels photo 159306 | [SH17](https://github.com/ahmadmughees/SH17dataset)，数据集 CC BY-NC-SA 4.0；原图遵循 Pexels License |
| 烟火 / 森林烟火 | `catalog-real-forest-fire.jpg` | Open Images `2afab7192939c56d` | Glenn Batuyong，[原图](https://www.flickr.com/photos/glennbatuyong/4729261348)，CC BY 2.0；不是 D-Fire 原始文件 |
| 道路车辆 | `catalog-real-traffic.jpg` | Open Images `1ab5db67d31e2038` | Andy Chan，[原图](https://www.flickr.com/photos/24810925@N04/2648287727)，CC BY 2.0；不是 BDD100K 原始文件 |
| 金属表面缺陷 | `catalog-real-defect.jpg` | NEU-DET `test_images/scratches_39.jpg` | [NEU-DET 仓库](https://github.com/songzhiweiknight/NEU-DET-Datasets)，来源仓库未声明 OSI 许可，按学术研究用途处理 |
| 林木 / 绿地 | `catalog-real-forest.jpg` | Open Images `2e49ef1ef93f6fd6` | Bruno Cordioli，[原图](https://www.flickr.com/photos/br1dotcom/2914696201)，CC BY 2.0；林木健康标签仍需二次标注 |
| 农产品 | `catalog-real-crop.jpg` | Fruits-360 `Test/Apple Braeburn/321_100.jpg` | [Fruits-360](https://github.com/Horea94/Fruit-Images-Dataset)，MIT（仓库）；页面已将示例框调整为苹果 |

## 仅有官方项目预览图的能力

以下素材已替换掉旧的通用拼贴图，但当前仍不是可下载的原始训练单图，页面会明确标记“数据集官方预览图”：

| 场景 | 文件 | 来源与限制 |
|---|---|---|
| 包裹损伤 | `catalog-real-parcel.jpg` | [Wisdom Logistics Express Parcel Damage](https://github.com/lonlonago/Wisdom-Logistics-Express-Parcel-Damage-Detection-Dataset-VOC-YOLO-Format-with-1340-Images) README 预览图；完整数据需向作者申请，授权待核验 |
| 货架密集商品 | `catalog-real-shelf.jpg` | [SKU-110K](https://github.com/eg4000/SKU110K_CVPR19) 官方 `qualitative.jpg`；研究用途，商用需联系作者 |
| 果园果实 | `catalog-real-orchard.jpg` | [Orchard Apple Detection Dataset](https://github.com/lonlonago/orchard-apple-detection-dataset) `img_00.png` 原始样本；社区仓库授权待核验 |
| 蜂场巡检 | `catalog-real-apiary.jpg` | [Picking honey Scene Bawah Bee Detection](https://github.com/lonlonago/Picking-honey-Scene-Bawah-Bee-Detection-Dataset-6640-imagesVOC-YOLO-format) README 预览图；完整数据与授权待核验 |

## 道路工程

| 场景 | 文件 | 数据集样本 | 原始来源与许可证 |
|---|---|---|---|
| 路面病害识别 | `catalog-real-road-surface.png` | RTK `image/000000112.png`，含路面、标线、修补和裂缝类像素标注 | [Road Traversing Knowledge](https://doi.org/10.17632/hssswvmjwf.1)，CC BY 4.0 |
| 交安设施异常识别 | `catalog-real-road-safety.jpg` | Open Images `9c7e9f0b7713352b`，交通信号灯与标志标注 | Michael Kumm，[原图](https://www.flickr.com/photos/mkumm/2840891484)，CC BY 2.0 |
| 路基边坡异常识别 | `catalog-real-road-slope.jpg` | Open Images `0376af43cb012d3f`，山地道路边坡 / landslide 标签 | JOHN LLOYD，[原图](https://www.flickr.com/photos/hugo90/2771912825)，CC BY 2.0 |
| 路域环境异常识别 | `catalog-real-road-environment.png` | RTK `image/000000526.png`，含路面与裂缝类像素标注 | [Road Traversing Knowledge](https://doi.org/10.17632/hssswvmjwf.1)，CC BY 4.0 |
| 隧道设施异常识别 | `catalog-real-tunnel.jpg` | Open Images `0fa91664f038fbc8`，tunnel 标签 | Larry Koester，[原图](https://www.flickr.com/photos/larrywkoester/15452965777)，CC BY 2.0 |
| 桥梁设施病害识别 | `catalog-real-bridge.jpg` | Open Images `00a159a661a2f5aa`，bridge 标签 | Fran Babcock，[原图](https://www.flickr.com/photos/feelingdoing/13645764903)，CC BY 2.0 |

## 城市治理

| 场景 | 文件 | 数据集样本 | 原始来源与许可证 |
|---|---|---|---|
| 违法建设识别 | `catalog-real-urban-illegal.jpg` | Open Images `00794645d77184eb`，街区建筑附属结构样本 | Steven Pisano，[原图](https://www.flickr.com/photos/stevenpisano/15256561208)，CC BY 2.0 |
| 市容环境问题识别 | `catalog-real-urban-sanitation.jpg` | TACO `1321`，街面散落垃圾实例标注 | [TACO](https://github.com/pedropro/TACO)，CC BY 4.0 |
| 建筑垃圾与渣土识别 | `catalog-real-urban-construction-waste.jpg` | Open Images `03edd1fdd321dd39`，construction / rubble 标签 | Anna Oakley，[原图](https://www.flickr.com/photos/annaoakley/3022479439)，CC BY 2.0 |
| 工地施工违规识别 | `catalog-real-urban-site.jpg` | Open Images `496a5b694439b447`，construction 标签 | JaxStrong，[原图](https://www.flickr.com/photos/jaxstrong/10311778426)，CC BY 2.0 |
| 户外广告与招牌识别 | `catalog-real-urban-advertising.jpg` | Open Images `03c35bdfffbea53f`，billboard 标签 | bizmac，[原图](https://www.flickr.com/photos/bizmac/16332584327)，CC BY 2.0 |
| 市政设施损坏识别 | `catalog-real-urban-municipal.jpg` | Open Images `97293a439963c5f2`，street light 与交通标志标签 | Leopoldstadt，[原图](https://www.flickr.com/photos/leopoldstadt/5624935537)，CC BY 2.0 |
| 河道与水域污染识别 | `catalog-real-urban-water.jpg` | TACO `1107`，水边垃圾实例标注 | [TACO](https://github.com/pedropro/TACO)，CC BY 4.0 |
| 生态环境问题识别 | `catalog-real-urban-ecology.jpg` | Open Images `9ff070bff835a3b9`，fire / smoke 场景标签 | frankieleon，[原图](https://www.flickr.com/photos/armydre2008/10810196273)，CC BY 2.0 |
| 火情与安全隐患识别 | `catalog-real-urban-fire.jpg` | Open Images `2afab7192939c56d`，fire 标签 | Glenn Batuyong，[原图](https://www.flickr.com/photos/glennbatuyong/4729261348)，CC BY 2.0 |
| 人员聚集与公共安全识别 | `catalog-real-urban-crowd.jpg` | Open Images `0162246ca3c39e68`，crowd 标签 | Magharebia，[原图](https://www.flickr.com/photos/magharebia/6431185703)，CC BY 2.0 |
| 交通与停车秩序识别 | `catalog-real-urban-traffic.jpg` | Open Images `1ab5db67d31e2038`，traffic congestion 标签 | Andy Chan，[原图](https://www.flickr.com/photos/24810925@N04/2648287727)，CC BY 2.0 |
| 园林绿化问题识别 | `catalog-real-urban-greening.jpg` | Open Images `2e49ef1ef93f6fd6`，街区树木与绿地标签 | Bruno Cordioli，[原图](https://www.flickr.com/photos/br1dotcom/2914696201)，CC BY 2.0 |

## 维护规则

新增或替换演示图片时，必须同时更新 `apps/web/lib/catalog-preview-assets.ts` 和本文件，且至少记录数据集、样本 ID、原始落地页、作者和许可证。无法确认单张图片授权或与能力场景没有实质关联的素材，不得作为市场卡片预览图。
