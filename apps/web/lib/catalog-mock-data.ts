import type {
  DataMarketListing,
  DatasetVersionQualityReport,
  MarketplaceListing,
} from "./catalog-api";

export type CatalogScene =
  | "ppe"
  | "fire"
  | "traffic"
  | "defect"
  | "parcel"
  | "shelf"
  | "forest"
  | "crop"
  | "orchard"
  | "apiary";

export type CatalogMetric = {
  label: string;
  value: string;
};

export type PreviewBox = {
  label: string;
  confidence?: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CatalogPreview = {
  scene: CatalogScene;
  alt: string;
  boxes: PreviewBox[];
  image_url?: string;
  aspect_ratio?: number;
};

export type AlgorithmCatalogItem = MarketplaceListing & {
  is_mock: boolean;
  preview: CatalogPreview;
  metrics: CatalogMetric[];
  classes: string[];
  model_architecture: string;
  input_size: string;
  latency_p95: string;
  evaluation_basis: string;
  updated_label: string;
};

export type DataCatalogItem = DataMarketListing & {
  is_mock: boolean;
  preview: CatalogPreview;
  scene_category: string;
  price_label: string;
  annotation_type: string;
  image_size_summary: string;
  updated_label: string;
};

const mockProvider = {
  provider_workspace_id: "mock-sensemu-verified",
  provider_name: "SenseMu 精选",
};

const algorithmDefaults = {
  deployment_id: "mock-deployment",
  capability_spec_id: "mock-capability",
  capability_version_number: 1,
  pricing_unit: "request",
  status: "published",
  published_at: "2026-08-01T08:00:00Z",
  subscription_id: null,
  subscription_status: null,
  remaining_units: null,
};

export const MOCK_ALGORITHM_LISTINGS: AlgorithmCatalogItem[] = [
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-ppe",
    deployment_id: "mock-deployment-ppe",
    capability_spec_id: "mock-capability-ppe",
    capability_slug: "ppe-compliance",
    capability_display_name: "安全穿戴检测",
    capability_problem_definition: "识别作业人员是否正确佩戴安全帽与反光衣。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["固定监控视角", "白天工地", "单人或多人作业区"],
    capability_unsupported_conditions: ["人员小于画面高度 4%", "严重逆光或夜间无补光"],
    endpoint_url: "/v1/marketplace/mock-alg-ppe/infer",
    model_name: "YOLO26s",
    model_version_number: 3,
    task_type: "object-detection",
    title: "工地安全穿戴检测",
    summary: "识别人员、安全帽与反光衣，并返回未规范穿戴的位置。",
    category: "安全生产",
    price_per_1000_cents: 1680,
    monthly_quota_units: 20000,
    is_mock: true,
    preview: {
      scene: "ppe",
      alt: "工地作业人员安全穿戴检测效果样例",
      boxes: [
        { label: "人员", confidence: "0.97", x: 12, y: 8, width: 52, height: 84 },
        { label: "安全帽", confidence: "0.95", x: 22, y: 6, width: 28, height: 22 },
        { label: "反光衣", confidence: "0.93", x: 12, y: 32, width: 51, height: 43 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "92.4%" },
      { label: "精确率", value: "90.8%" },
      { label: "召回率", value: "88.6%" },
    ],
    classes: ["人员", "安全帽", "未戴安全帽", "反光衣", "未穿反光衣"],
    model_architecture: "YOLO26s",
    input_size: "640 × 640",
    latency_p95: "48 ms",
    evaluation_basis: "独立测试集 1,280 张工地监控图像",
    updated_label: "2026-07-28",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-fire",
    deployment_id: "mock-deployment-fire",
    capability_spec_id: "mock-capability-fire",
    capability_slug: "smoke-fire-alert",
    capability_display_name: "烟火早期识别",
    capability_problem_definition: "发现仓储与生产区域中的烟雾和明火。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["仓库固定监控", "室内厂房", "可见光画面"],
    capability_unsupported_conditions: ["蒸汽密集区域", "强光直射镜头"],
    endpoint_url: "/v1/marketplace/mock-alg-fire/infer",
    model_name: "YOLO26m",
    model_version_number: 2,
    task_type: "object-detection",
    title: "仓储烟火早期识别",
    summary: "检测烟雾与明火，适合接入仓库监控做早期风险提示。",
    category: "安全生产",
    price_per_1000_cents: 2280,
    monthly_quota_units: 15000,
    is_mock: true,
    preview: {
      scene: "fire",
      alt: "仓库烟雾与明火检测效果样例",
      boxes: [
        { label: "烟雾", confidence: "0.91", x: 29, y: 2, width: 38, height: 58 },
        { label: "明火", confidence: "0.96", x: 35, y: 47, width: 25, height: 29 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "90.1%" },
      { label: "精确率", value: "91.7%" },
      { label: "召回率", value: "86.2%" },
    ],
    classes: ["烟雾", "明火"],
    model_architecture: "YOLO26m",
    input_size: "768 × 768",
    latency_p95: "72 ms",
    evaluation_basis: "独立测试集 860 段仓储与厂房画面",
    updated_label: "2026-07-22",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-traffic",
    deployment_id: "mock-deployment-traffic",
    capability_spec_id: "mock-capability-traffic",
    capability_slug: "road-vehicle-counting",
    capability_display_name: "道路车辆统计",
    capability_problem_definition: "检测并区分道路中的常见车辆，输出逐帧数量。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["城市路口", "高位固定相机", "白天与路灯夜景"],
    capability_unsupported_conditions: ["超密集拥堵遮挡", "鱼眼畸变未校正"],
    endpoint_url: "/v1/marketplace/mock-alg-traffic/infer",
    model_name: "RT-DETR-L",
    model_version_number: 5,
    task_type: "object-detection",
    title: "道路车辆检测与计数",
    summary: "区分小客车、货车、公交车与两轮车，返回位置和数量。",
    category: "智慧交通",
    price_per_1000_cents: 1980,
    monthly_quota_units: 30000,
    is_mock: true,
    preview: {
      scene: "traffic",
      alt: "城市路口车辆检测效果样例",
      boxes: [
        { label: "货车", confidence: "0.98", x: 36, y: 34, width: 48, height: 29 },
        { label: "小客车", confidence: "0.94", x: 18, y: 62, width: 30, height: 19 },
        { label: "小客车", confidence: "0.90", x: 72, y: 60, width: 24, height: 18 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "94.0%" },
      { label: "精确率", value: "92.1%" },
      { label: "召回率", value: "91.5%" },
    ],
    classes: ["小客车", "货车", "公交车", "摩托车", "自行车"],
    model_architecture: "RT-DETR-L",
    input_size: "960 × 544",
    latency_p95: "83 ms",
    evaluation_basis: "独立测试集 2,100 张城市道路图像",
    updated_label: "2026-07-30",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-defect",
    deployment_id: "mock-deployment-defect",
    capability_spec_id: "mock-capability-defect",
    capability_slug: "metal-surface-defect",
    capability_display_name: "金属表面缺陷分割",
    capability_problem_definition: "定位金属板材表面的划痕、凹坑与氧化区域。",
    capability_output_contract: "segments.v1",
    capability_verified_scenes: ["均匀产线光源", "金属板材近景", "单件通过"],
    capability_unsupported_conditions: ["镜面强反射", "相机焦距偏离标定范围"],
    endpoint_url: "/v1/marketplace/mock-alg-defect/infer",
    model_name: "YOLO26s-seg",
    model_version_number: 4,
    task_type: "segmentation",
    title: "金属表面缺陷分割",
    summary: "定位划痕、凹坑和氧化区域，输出缺陷轮廓与面积。",
    category: "工业质检",
    price_per_1000_cents: 2880,
    monthly_quota_units: 12000,
    is_mock: true,
    preview: {
      scene: "defect",
      alt: "金属板材划痕分割效果样例",
      boxes: [{ label: "划痕", confidence: "0.89", x: 22, y: 48, width: 62, height: 17 }],
    },
    metrics: [
      { label: "mAP50", value: "88.7%" },
      { label: "精确率", value: "91.2%" },
      { label: "召回率", value: "84.9%" },
    ],
    classes: ["划痕", "凹坑", "氧化"],
    model_architecture: "YOLO26s-seg",
    input_size: "1024 × 1024",
    latency_p95: "96 ms",
    evaluation_basis: "独立测试集 740 张产线质检图像",
    updated_label: "2026-07-19",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-parcel",
    deployment_id: "mock-deployment-parcel",
    capability_spec_id: "mock-capability-parcel",
    capability_slug: "parcel-counting",
    capability_display_name: "包裹检测与计数",
    capability_problem_definition: "检测传送带上的包裹并输出当前数量。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["俯拍传送带", "纸箱与软包", "稳定室内光照"],
    capability_unsupported_conditions: ["包裹完全重叠", "高速运动拖影"],
    endpoint_url: "/v1/marketplace/mock-alg-parcel/infer",
    model_name: "YOLO26n",
    model_version_number: 2,
    task_type: "object-detection",
    title: "快递包裹检测与计数",
    summary: "识别纸箱与软包，适合分拣线计数和漏件提示。",
    category: "仓储物流",
    price_per_1000_cents: 1380,
    monthly_quota_units: 50000,
    is_mock: true,
    preview: {
      scene: "parcel",
      alt: "物流传送带包裹检测效果样例",
      boxes: [
        { label: "纸箱", confidence: "0.96", x: 15, y: 14, width: 22, height: 18 },
        { label: "软包", confidence: "0.92", x: 34, y: 57, width: 24, height: 15 },
        { label: "纸箱", confidence: "0.98", x: 49, y: 70, width: 35, height: 25 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "95.6%" },
      { label: "精确率", value: "96.0%" },
      { label: "召回率", value: "93.8%" },
    ],
    classes: ["纸箱", "软包", "编织袋"],
    model_architecture: "YOLO26n",
    input_size: "640 × 640",
    latency_p95: "34 ms",
    evaluation_basis: "独立测试集 1,520 张分拣线图像",
    updated_label: "2026-07-26",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-shelf",
    deployment_id: "mock-deployment-shelf",
    capability_spec_id: "mock-capability-shelf",
    capability_slug: "retail-shelf-gap",
    capability_display_name: "货架缺货识别",
    capability_problem_definition: "识别零售货架中的连续空位和低库存区域。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["正面货架图像", "便利店与商超", "标准陈列区"],
    capability_unsupported_conditions: ["玻璃柜强反光", "大面积促销牌遮挡"],
    endpoint_url: "/v1/marketplace/mock-alg-shelf/infer",
    model_name: "YOLO26s",
    model_version_number: 1,
    task_type: "object-detection",
    title: "零售货架缺货识别",
    summary: "发现连续空位和低库存区域，返回货架层级与位置。",
    category: "智慧零售",
    price_per_1000_cents: 1880,
    monthly_quota_units: 20000,
    is_mock: true,
    preview: {
      scene: "shelf",
      alt: "零售货架缺货检测效果样例",
      boxes: [{ label: "缺货区域", confidence: "0.93", x: 24, y: 24, width: 51, height: 31 }],
    },
    metrics: [
      { label: "mAP50", value: "89.5%" },
      { label: "精确率", value: "90.4%" },
      { label: "召回率", value: "87.1%" },
    ],
    classes: ["缺货区域", "低库存区域"],
    model_architecture: "YOLO26s",
    input_size: "768 × 768",
    latency_p95: "61 ms",
    evaluation_basis: "独立测试集 980 张商超货架图像",
    updated_label: "2026-07-18",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-forest-health",
    deployment_id: "mock-deployment-forest-health",
    capability_spec_id: "mock-capability-forest-health",
    capability_slug: "forest-tree-health",
    capability_display_name: "林木健康巡检",
    capability_problem_definition: "从林区航拍或固定机位图像中发现枯死、倒伏和明显病害树木。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["林区航拍", "林道固定机位", "自然光可见光图像"],
    capability_unsupported_conditions: ["浓雾遮挡树冠", "单棵树小于画面高度 2%"],
    endpoint_url: "/v1/marketplace/mock-alg-forest-health/infer",
    model_name: "YOLO26m",
    model_version_number: 1,
    task_type: "object-detection",
    title: "林木健康巡检",
    summary: "发现枯死、倒伏与明显病害树木，适合林区巡检和复核调度。",
    category: "林业",
    price_per_1000_cents: 2480,
    monthly_quota_units: 18000,
    is_mock: true,
    preview: {
      scene: "forest",
      alt: "林区林木健康巡检效果样例",
      image_url: "/catalog-forest.jpg",
      aspect_ratio: 1600 / 1067,
      boxes: [
        { label: "疑似枯死树", confidence: "0.91", x: 4, y: 20, width: 18, height: 63 },
        { label: "倒伏树木", confidence: "0.88", x: 67, y: 54, width: 25, height: 18 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "87.9%" },
      { label: "精确率", value: "89.1%" },
      { label: "召回率", value: "84.7%" },
    ],
    classes: ["健康树木", "疑似枯死树", "倒伏树木", "病害斑块"],
    model_architecture: "YOLO26m",
    input_size: "1280 × 720",
    latency_p95: "76 ms",
    evaluation_basis: "独立测试集 1,460 张林区航拍与巡检图像",
    updated_label: "2026-08-02",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-forest-fire",
    deployment_id: "mock-deployment-forest-fire",
    capability_spec_id: "mock-capability-forest-fire",
    capability_slug: "forest-fire-smoke",
    capability_display_name: "森林烟火早期识别",
    capability_problem_definition: "在林区监控画面中发现早期烟雾和火点，减少人工巡屏范围。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["林区高点监控", "山地防火瞭望", "白天可见光视频"],
    capability_unsupported_conditions: ["厚云层与低云雾", "红外热成像之外的夜间画面"],
    endpoint_url: "/v1/marketplace/mock-alg-forest-fire/infer",
    model_name: "YOLO26s",
    model_version_number: 2,
    task_type: "object-detection",
    title: "森林烟火早期识别",
    summary: "识别林区早期烟雾和火点，输出告警位置与置信度。",
    category: "林业",
    price_per_1000_cents: 2980,
    monthly_quota_units: 12000,
    is_mock: true,
    preview: {
      scene: "forest",
      alt: "森林烟火早期识别效果样例",
      image_url: "/catalog-forest.jpg",
      aspect_ratio: 1600 / 1067,
      boxes: [{ label: "烟雾", confidence: "0.93", x: 49, y: 4, width: 38, height: 30 }],
    },
    metrics: [
      { label: "mAP50", value: "91.2%" },
      { label: "精确率", value: "92.4%" },
      { label: "召回率", value: "88.9%" },
    ],
    classes: ["烟雾", "火点", "高亮反光"],
    model_architecture: "YOLO26s",
    input_size: "1280 × 720",
    latency_p95: "54 ms",
    evaluation_basis: "独立测试集 920 段林区监控视频帧",
    updated_label: "2026-08-01",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-produce-sort",
    deployment_id: "mock-deployment-produce-sort",
    capability_spec_id: "mock-capability-produce-sort",
    capability_slug: "produce-sorting",
    capability_display_name: "农产品分选识别",
    capability_problem_definition: "识别常见蔬果品类和明显外观缺陷，辅助收购与分选台抽检。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["收购分选台", "农产品近景", "室内均匀光照"],
    capability_unsupported_conditions: ["目标堆叠超过 60%", "透明塑料袋强反光"],
    endpoint_url: "/v1/marketplace/mock-alg-produce-sort/infer",
    model_name: "YOLO26s",
    model_version_number: 3,
    task_type: "object-detection",
    title: "农产品分选识别",
    summary: "识别常见蔬果品类和明显外观缺陷，适合收购、分选与质检抽查。",
    category: "农业",
    price_per_1000_cents: 1680,
    monthly_quota_units: 24000,
    is_mock: true,
    preview: {
      scene: "crop",
      alt: "农产品分选识别效果样例",
      image_url: "/catalog-crop.jpg",
      aspect_ratio: 1600 / 1067,
      boxes: [
        { label: "苦瓜", confidence: "0.96", x: 8, y: 14, width: 41, height: 37 },
        { label: "黄瓜", confidence: "0.94", x: 56, y: 8, width: 37, height: 43 },
        { label: "胡萝卜", confidence: "0.92", x: 45, y: 48, width: 31, height: 39 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "94.6%" },
      { label: "精确率", value: "93.8%" },
      { label: "召回率", value: "91.7%" },
    ],
    classes: ["苦瓜", "黄瓜", "胡萝卜", "辣椒", "疑似外观缺陷"],
    model_architecture: "YOLO26s",
    input_size: "512 × 512",
    latency_p95: "41 ms",
    evaluation_basis: "独立测试集 3,200 张农产品分选图像",
    updated_label: "2026-07-31",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-orchard-count",
    deployment_id: "mock-deployment-orchard-count",
    capability_spec_id: "mock-capability-orchard-count",
    capability_slug: "orchard-fruit-counting",
    capability_display_name: "果园果实计数",
    capability_problem_definition: "检测果树上的果实并按区域统计数量，辅助产量预估。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["果园行间", "自然光树冠", "单果与小簇果实"],
    capability_unsupported_conditions: ["果实完全被叶片遮挡", "强风造成连续运动模糊"],
    endpoint_url: "/v1/marketplace/mock-alg-orchard-count/infer",
    model_name: "YOLO26n",
    model_version_number: 2,
    task_type: "object-detection",
    title: "果园果实计数",
    summary: "检测果实位置并按树行统计，适合采收前产量预估。",
    category: "农业",
    price_per_1000_cents: 2180,
    monthly_quota_units: 20000,
    is_mock: true,
    preview: {
      scene: "orchard",
      alt: "果园果实计数效果样例",
      image_url: "/catalog-orchard.jpg",
      aspect_ratio: 1600 / 1065,
      boxes: [
        { label: "果实", confidence: "0.94", x: 43, y: 20, width: 12, height: 17 },
        { label: "果实", confidence: "0.91", x: 58, y: 34, width: 14, height: 18 },
        { label: "果实", confidence: "0.89", x: 22, y: 44, width: 13, height: 17 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "90.8%" },
      { label: "精确率", value: "92.0%" },
      { label: "召回率", value: "87.6%" },
    ],
    classes: ["果实", "未成熟果", "病果"],
    model_architecture: "YOLO26n",
    input_size: "960 × 544",
    latency_p95: "39 ms",
    evaluation_basis: "独立测试集 2,480 张果园图像",
    updated_label: "2026-07-29",
  },
  {
    ...mockProvider,
    ...algorithmDefaults,
    id: "mock-alg-apiary",
    deployment_id: "mock-deployment-apiary",
    capability_spec_id: "mock-capability-apiary",
    capability_slug: "apiary-inspection",
    capability_display_name: "蜂箱巡检与计数",
    capability_problem_definition: "识别养蜂场蜂箱与巡检人员，辅助蜂场资产盘点和作业记录。",
    capability_output_contract: "detections.v1",
    capability_verified_scenes: ["蜂场固定机位", "蜂箱近景", "白天自然光视频"],
    capability_unsupported_conditions: ["蜂箱被植被大面积遮挡", "夜间无补光"],
    endpoint_url: "/v1/marketplace/mock-alg-apiary/infer",
    model_name: "YOLO26s",
    model_version_number: 1,
    task_type: "object-detection",
    title: "蜂箱巡检与计数",
    summary: "识别蜂箱和巡检人员，支持蜂场资产盘点与作业记录。",
    category: "农业",
    price_per_1000_cents: 1880,
    monthly_quota_units: 16000,
    is_mock: true,
    preview: {
      scene: "apiary",
      alt: "蜂箱巡检与计数效果样例",
      image_url: "/catalog-apiary.jpg",
      aspect_ratio: 1600 / 1063,
      boxes: [
        { label: "巡检人员", confidence: "0.97", x: 16, y: 10, width: 38, height: 77 },
        { label: "蜂箱", confidence: "0.94", x: 54, y: 23, width: 31, height: 49 },
      ],
    },
    metrics: [
      { label: "mAP50", value: "93.1%" },
      { label: "精确率", value: "94.0%" },
      { label: "召回率", value: "90.2%" },
    ],
    classes: ["蜂箱", "巡检人员", "疑似空箱"],
    model_architecture: "YOLO26s",
    input_size: "1280 × 720",
    latency_p95: "52 ms",
    evaluation_basis: "独立测试集 1,760 张蜂场巡检图像",
    updated_label: "2026-07-27",
  },
];

function qualityReport(
  id: string,
  assetCount: number,
  classes: string[],
  coverage: number,
  advisories: string[],
): DatasetVersionQualityReport {
  const valid = Math.round(assetCount * 0.15);
  const test = Math.round(assetCount * 0.1);
  const train = assetCount - valid - test;
  return {
    dataset_version_id: id,
    schema_version: "1.0",
    asset_count: assetCount,
    split_counts: { train, valid, test },
    annotated_asset_count: Math.round(assetCount * coverage / 100),
    unannotated_asset_count: assetCount - Math.round(assetCount * coverage / 100),
    annotation_coverage_percent: coverage,
    class_distribution: classes.map((className, index) => ({
      class_id: index,
      class_name: className,
      annotation_count: Math.max(120, Math.round(assetCount * (1.25 - index * 0.12))),
      asset_count: Math.max(90, Math.round(assetCount * (0.72 - index * 0.07))),
    })),
    image_dimensions: {
      known_asset_count: assetCount,
      unknown_asset_count: 0,
      min_width: 640,
      max_width: 3840,
      min_height: 480,
      max_height: 2160,
    },
    advisories,
  };
}

const dataDefaults = {
  ...mockProvider,
  project_name: "SenseMu 数据精选",
  review_basis: "provider_attestation" as const,
  status: "published" as const,
  delivery_mode: "workspace_copy_after_authorization" as const,
  delivery_status: "prepared_not_open" as const,
  delivery_spec_hash: null,
  published_at: "2026-08-01T08:00:00Z",
  allow_derivative_models: true,
  allow_redistribution: false,
  contains_personal_data: false,
  privacy_treatment: "不包含可识别个人身份的信息；人像已做脱敏或只用于目标框标注。",
  custom_license_terms: null,
};

const dataSceneCategories: Record<CatalogScene, string> = {
  ppe: "安全生产",
  fire: "安全生产",
  traffic: "智慧交通",
  defect: "工业质检",
  parcel: "仓储物流",
  shelf: "智慧零售",
  forest: "林业",
  crop: "农业",
  orchard: "农业",
  apiary: "农业",
};

function dataListing(input: {
  id: string;
  scene: CatalogScene;
  title: string;
  summary: string;
  taskType: string;
  assetCount: number;
  classes: string[];
  source: string;
  method: string;
  coverage: string;
  limitations: string;
  license: DataMarketListing["license_code"];
  commercial: boolean;
  price: string;
  annotationType: string;
  imageSize: string;
  imageUrl?: string;
  aspectRatio?: number;
  boxes: PreviewBox[];
  coveragePercent: number;
  advisories: string[];
}): DataCatalogItem {
  const versionId = `${input.id}-v2`;
  return {
    ...dataDefaults,
    id: input.id,
    dataset_version_id: versionId,
    dataset_id: `${input.id}-dataset`,
    dataset_name: input.title,
    dataset_version_number: 2,
    task_type: input.taskType,
    asset_count: input.assetCount,
    class_map: Object.fromEntries(input.classes.map((name, index) => [String(index), name])),
    quality_report: qualityReport(versionId, input.assetCount, input.classes, input.coveragePercent, input.advisories),
    title: input.title,
    summary: input.summary,
    source_summary: input.source,
    collection_method: input.method,
    coverage_summary: input.coverage,
    known_limitations: input.limitations,
    license_code: input.license,
    allow_commercial_use: input.commercial,
    allow_model_training: true,
    preview: {
      scene: input.scene,
      alt: `${input.title}标注样例`,
      image_url: input.imageUrl,
      aspect_ratio: input.aspectRatio,
      boxes: input.boxes,
    },
    scene_category: dataSceneCategories[input.scene],
    price_label: input.price,
    annotation_type: input.annotationType,
    image_size_summary: input.imageSize,
    updated_label: "2026-07",
    is_mock: true,
  };
}

export const MOCK_DATA_LISTINGS: DataCatalogItem[] = [
  dataListing({
    id: "mock-data-ppe",
    scene: "ppe",
    title: "工地安全穿戴数据集",
    summary: "覆盖安全帽、反光衣和人员目标，适合训练工地安全检测模型。",
    taskType: "object-detection",
    assetCount: 18420,
    classes: ["人员", "安全帽", "未戴安全帽", "反光衣", "未穿反光衣"],
    source: "华东与华南 12 个真实工地的固定监控画面，经项目方授权整理。",
    method: "按工地、天气与时段分层抽样；两轮人工框选并交叉复核。",
    coverage: "包含室内外、晴雨天、日间与傍晚，以及 1–20 人不同密度。",
    limitations: "夜间无补光与极远距离人员样本较少；不建议直接用于人脸识别。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥6,800 / 版本",
    annotationType: "目标框",
    imageSize: "640p–4K",
    boxes: MOCK_ALGORITHM_LISTINGS[0].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 99.2,
    advisories: ["夜间样本占比 8.4%，部署到夜间场景前建议补充采样。"],
  }),
  dataListing({
    id: "mock-data-fire",
    scene: "fire",
    title: "仓储烟火异常数据集",
    summary: "烟雾、明火与正常蒸汽对照数据，用于仓储风险识别。",
    taskType: "object-detection",
    assetCount: 8630,
    classes: ["烟雾", "明火", "蒸汽"],
    source: "模拟实验、授权仓储监控与公开消防演练素材混合构成。",
    method: "以事件为单位切帧并去重，按事件来源隔离训练与测试划分。",
    coverage: "覆盖低照度、远距离、小火点、浅色烟雾与蒸汽干扰。",
    limitations: "户外森林火灾比例低；不包含红外热成像。",
    license: "CC-BY-4.0",
    commercial: true,
    price: "¥4,200 / 版本",
    annotationType: "目标框",
    imageSize: "720p–1080p",
    boxes: MOCK_ALGORITHM_LISTINGS[1].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 98.7,
    advisories: ["蒸汽对照样本集中于室内环境。"],
  }),
  dataListing({
    id: "mock-data-traffic",
    scene: "traffic",
    title: "城市路口车辆数据集",
    summary: "多城市固定高位相机采集的车辆检测与分类数据。",
    taskType: "object-detection",
    assetCount: 32680,
    classes: ["小客车", "货车", "公交车", "摩托车", "自行车"],
    source: "6 座城市、24 个路口的授权交通视频抽帧。",
    method: "按相机点位隔离划分，剔除连续重复帧后完成人工框选。",
    coverage: "覆盖晴雨、白天、夜间路灯与轻中度拥堵。",
    limitations: "极端暴雨和严重拥堵样本不足；车牌已模糊处理。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥9,600 / 版本",
    annotationType: "目标框",
    imageSize: "1080p–4K",
    boxes: MOCK_ALGORITHM_LISTINGS[2].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 99.6,
    advisories: ["夜间摩托车样本量低于其他类别。"],
  }),
  dataListing({
    id: "mock-data-defect",
    scene: "defect",
    title: "金属表面缺陷数据集",
    summary: "钢板与铝板表面的划痕、凹坑和氧化区域精细标注。",
    taskType: "segmentation",
    assetCount: 12940,
    classes: ["划痕", "凹坑", "氧化"],
    source: "3 条真实质检线与标准缺陷样片采集。",
    method: "固定光源与相机参数采集，使用像素级多边形标注并抽检。",
    coverage: "覆盖拉丝、磨砂和哑光材质，以及轻微到明显缺陷。",
    limitations: "不覆盖高反射镜面金属；跨产线使用前需验证光源差异。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥12,800 / 版本",
    annotationType: "多边形分割",
    imageSize: "2048 × 2048",
    boxes: MOCK_ALGORITHM_LISTINGS[3].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 100,
    advisories: ["凹坑类别占比为 12.6%，存在轻度不均衡。"],
  }),
  dataListing({
    id: "mock-data-parcel",
    scene: "parcel",
    title: "物流包裹传送带数据集",
    summary: "纸箱、软包和编织袋在分拣线上的检测标注数据。",
    taskType: "object-detection",
    assetCount: 22160,
    classes: ["纸箱", "软包", "编织袋"],
    source: "8 条快递分拣线的授权视频抽帧。",
    method: "按班次和相机点位去重，遮挡超过 70% 的目标不标注。",
    coverage: "覆盖不同传送带颜色、俯拍角度、包裹尺寸与堆叠程度。",
    limitations: "高速运动模糊样本偏少；不包含快递面单文字转录。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥7,200 / 版本",
    annotationType: "目标框",
    imageSize: "720p–2K",
    boxes: MOCK_ALGORITHM_LISTINGS[4].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 99.8,
    advisories: [],
  }),
  dataListing({
    id: "mock-data-shelf",
    scene: "shelf",
    title: "零售货架缺货数据集",
    summary: "商超货架空位、低库存与正常陈列的区域标注数据。",
    taskType: "object-detection",
    assetCount: 15780,
    classes: ["缺货区域", "低库存区域", "正常陈列"],
    source: "42 家便利店与商超的授权巡检图像。",
    method: "按门店隔离划分，区域框标注后由零售运营人员复核。",
    coverage: "覆盖饮料、粮油、零食与日化货架，以及不同照明和角度。",
    limitations: "冷柜反光与促销堆头样本较少；不包含 SKU 级商品识别。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥5,600 / 版本",
    annotationType: "区域框",
    imageSize: "1080p–4K",
    boxes: MOCK_ALGORITHM_LISTINGS[5].preview.boxes.map(({ label, x, y, width, height }) => ({ label, x, y, width, height })),
    coveragePercent: 98.9,
    advisories: ["正常陈列类别数量较多，训练时建议使用类别权重。"],
  }),
  dataListing({
    id: "mock-data-forest-health",
    scene: "forest",
    title: "林区树木健康数据集",
    summary: "林区航拍与固定机位图像，标注健康、枯死和倒伏树木。",
    taskType: "object-detection",
    assetCount: 14680,
    classes: ["健康树木", "疑似枯死树", "倒伏树木", "病害斑块"],
    source: "3 个林场的授权巡检航拍与林道监控图像。",
    method: "按林场与季节隔离划分，目标框标注后由林业巡检人员复核。",
    coverage: "覆盖针叶林、阔叶林、林缘与林道，以及晴天和阴天光照。",
    limitations: "浓雾和冬季落叶林样本较少；不用于树种级鉴定。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥8,400 / 版本",
    annotationType: "目标框",
    imageSize: "1080p–4K",
    imageUrl: "/catalog-forest.jpg",
    aspectRatio: 1600 / 1067,
    boxes: [
      { label: "疑似枯死树", x: 4, y: 20, width: 18, height: 63 },
      { label: "倒伏树木", x: 67, y: 54, width: 25, height: 18 },
    ],
    coveragePercent: 96.4,
    advisories: ["冬季落叶林样本占比 11.2%，跨季节部署前建议补充验证。"],
  }),
  dataListing({
    id: "mock-data-forest-fire",
    scene: "forest",
    title: "森林烟火监控数据集",
    summary: "林区烟雾、火点与云雾反光对照数据，用于早期火情识别。",
    taskType: "object-detection",
    assetCount: 9240,
    classes: ["烟雾", "火点", "云雾", "高亮反光"],
    source: "山地防火瞭望点与林区监控设备的授权视频抽帧。",
    method: "以事件为单位去重，按林区和天气隔离训练、验证与测试划分。",
    coverage: "覆盖远距离小烟柱、林缘火点、低云雾和日照反光干扰。",
    limitations: "夜间红外数据未包含在本版本；不覆盖地下火。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥5,900 / 版本",
    annotationType: "目标框",
    imageSize: "720p–4K",
    imageUrl: "/catalog-forest.jpg",
    aspectRatio: 1600 / 1067,
    boxes: [{ label: "烟雾", x: 49, y: 4, width: 38, height: 30 }],
    coveragePercent: 98.1,
    advisories: ["云雾与烟雾对照样本已分层，但仍建议结合现场阈值复核。"],
  }),
  dataListing({
    id: "mock-data-produce",
    scene: "crop",
    title: "农产品分选数据集",
    summary: "蔬果品类与明显外观缺陷标注，适合收购与分选台训练。",
    taskType: "object-detection",
    assetCount: 32100,
    classes: ["苦瓜", "黄瓜", "胡萝卜", "辣椒", "疑似外观缺陷"],
    source: "4 个农产品收购点的分选台图像，经供应方授权整理。",
    method: "按收购点和日期隔离划分，密集堆叠目标由两名标注员交叉复核。",
    coverage: "覆盖不同品类、尺寸、成熟度和室内均匀光照。",
    limitations: "透明包装与严重堆叠样本较少；不包含重量估计标签。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥7,600 / 版本",
    annotationType: "目标框",
    imageSize: "1080p–4K",
    imageUrl: "/catalog-crop.jpg",
    aspectRatio: 1600 / 1067,
    boxes: [
      { label: "苦瓜", x: 8, y: 14, width: 41, height: 37 },
      { label: "黄瓜", x: 56, y: 8, width: 37, height: 43 },
      { label: "胡萝卜", x: 45, y: 48, width: 31, height: 39 },
    ],
    coveragePercent: 99.1,
    advisories: ["疑似外观缺陷类别已单独标注，适合先做人工复核再用于自动分选。"],
  }),
  dataListing({
    id: "mock-data-orchard",
    scene: "orchard",
    title: "果园果实计数数据集",
    summary: "果园行间与树冠近景的果实、未成熟果和病果标注数据。",
    taskType: "object-detection",
    assetCount: 24800,
    classes: ["果实", "未成熟果", "病果"],
    source: "5 个果园的授权采收前巡检图像。",
    method: "按果园和树行隔离划分，遮挡目标保留可见部分并记录复核状态。",
    coverage: "覆盖苹果、梨等树冠近景，以及不同成熟度和自然光照。",
    limitations: "强风运动模糊和完全遮挡果实样本偏少；不含产量真值。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥8,900 / 版本",
    annotationType: "目标框",
    imageSize: "1080p–4K",
    imageUrl: "/catalog-orchard.jpg",
    aspectRatio: 1600 / 1065,
    boxes: [
      { label: "果实", x: 43, y: 20, width: 12, height: 17 },
      { label: "果实", x: 58, y: 34, width: 14, height: 18 },
      { label: "病果", x: 22, y: 44, width: 13, height: 17 },
    ],
    coveragePercent: 97.8,
    advisories: ["病果类别占比 8.6%，训练时建议使用类别权重。"],
  }),
  dataListing({
    id: "mock-data-apiary",
    scene: "apiary",
    title: "蜂场巡检数据集",
    summary: "蜂箱、巡检人员与疑似空箱标注数据，适合蜂场资产盘点。",
    taskType: "object-detection",
    assetCount: 11760,
    classes: ["蜂箱", "巡检人员", "疑似空箱"],
    source: "2 个养蜂场的授权巡检与固定机位图像。",
    method: "按蜂场隔离划分，蜂箱区域框标注后由养蜂人员复核。",
    coverage: "覆盖蜂箱排列、植被背景、作业人员进入和白天自然光。",
    limitations: "蜂箱被高草完全遮挡和夜间样本较少；不替代人工蜂群健康判断。",
    license: "CUSTOM-COMMERCIAL",
    commercial: true,
    price: "¥4,800 / 版本",
    annotationType: "目标框",
    imageSize: "1080p–2K",
    imageUrl: "/catalog-apiary.jpg",
    aspectRatio: 1600 / 1063,
    boxes: [
      { label: "巡检人员", x: 16, y: 10, width: 38, height: 77 },
      { label: "蜂箱", x: 54, y: 23, width: 31, height: 49 },
    ],
    coveragePercent: 98.5,
    advisories: ["疑似空箱标签来自巡检记录，部署后建议与蜂场台账联动复核。"],
  }),
];

const previewFallbacks: CatalogPreview[] = MOCK_ALGORITHM_LISTINGS.map((item) => item.preview);

export function decorateAlgorithmListing(listing: MarketplaceListing, index = 0): AlgorithmCatalogItem {
  const preview = previewFallbacks[index % previewFallbacks.length];
  return {
    ...listing,
    is_mock: false,
    preview,
    metrics: [
      { label: "调用状态", value: "可用" },
      { label: "模型版本", value: `v${listing.model_version_number}` },
      { label: "月度额度", value: listing.monthly_quota_units.toLocaleString("zh-CN") },
    ],
    classes: [],
    model_architecture: listing.model_name,
    input_size: "按接口说明",
    latency_p95: "待供应商公布",
    evaluation_basis: "以供应商发布的验收材料为准",
    updated_label: listing.published_at ? listing.published_at.slice(0, 10) : "近期发布",
  };
}

export function decorateDataListing(listing: DataMarketListing, index = 0): DataCatalogItem {
  const preview = previewFallbacks[index % previewFallbacks.length];
  return {
    ...listing,
    is_mock: false,
    preview,
    scene_category: dataSceneCategories[preview.scene],
    price_label: "联系供应方",
    annotation_type: listing.task_type === "segmentation" ? "多边形分割" : "目标框",
    image_size_summary: listing.quality_report?.image_dimensions.max_width
      ? `最长边 ${listing.quality_report.image_dimensions.max_width}px`
      : "尺寸待确认",
    updated_label: listing.published_at.slice(0, 10),
  };
}

export function mergeAlgorithmListings(listings: MarketplaceListing[]): AlgorithmCatalogItem[] {
  const real = listings.map(decorateAlgorithmListing);
  return [...real, ...MOCK_ALGORITHM_LISTINGS.filter((mock) => !real.some((item) => item.title === mock.title))];
}

export function mergeDataListings(listings: DataMarketListing[]): DataCatalogItem[] {
  const real = listings.map(decorateDataListing);
  return [...real, ...MOCK_DATA_LISTINGS.filter((mock) => !real.some((item) => item.title === mock.title))];
}

export function findMockAlgorithm(id: string): AlgorithmCatalogItem | null {
  return MOCK_ALGORITHM_LISTINGS.find((item) => item.id === id) ?? null;
}

export function findMockData(id: string): DataCatalogItem | null {
  return MOCK_DATA_LISTINGS.find((item) => item.id === id) ?? null;
}
