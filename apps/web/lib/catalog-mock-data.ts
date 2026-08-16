import type {
  DataMarketListing,
  DatasetVersionQualityReport,
  MarketplaceListing,
} from "./catalog-api";

export type CatalogScene = "ppe" | "fire" | "traffic" | "defect" | "parcel" | "shelf";

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
    preview: { scene: input.scene, alt: `${input.title}标注样例`, boxes: input.boxes },
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
