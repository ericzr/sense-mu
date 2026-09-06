# SenseMu 演示素材清单

数据市场和算法市场的道路工程、城市治理 mock 卡片使用仓库内的真实公开数据集样本。每张图片的来源、样本标识和许可证均记录在本文件；图片只用于产品预览，页面上的框线和中文标签仍由 mock 数据生成，不能解释为原始标注或真实模型推理结果。

## 使用边界

- 这些文件不是可交付的数据商品，也不代表 SenseMu 对原始数据集享有所有权。
- Open Images 样本按其图像元数据中记录的 `CC BY 2.0` 使用，发布时保留作者、原始落地页和许可证链接。
- RTK 与 TACO 样本的原始数据集为 `CC BY 4.0`；页面展示没有改变原始图片内容。
- 正式商品发布需要供应方授权、采集和去标识化证据；不能将这里的预览图或 mock 框作为训练、评测或生产结果。

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

新增或替换演示图片时，必须同时更新本文件，且至少记录数据集、样本 ID、原始落地页、作者和许可证。无法确认单张图片授权或与能力场景没有实质关联的素材，不得作为市场卡片预览图。
