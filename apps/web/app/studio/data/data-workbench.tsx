"use client";

import {
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  Box,
  Cloud,
  Check,
  ChevronRight,
  Cpu,
  Database,
  FileCheck2,
  FileImage,
  Film,
  Grid2X2,
  Globe2,
  HardDrive,
  Link2,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  List,
  ListChecks,
  Mountain,
  PersonStanding,
  Plus,
  RefreshCw,
  RotateCw,
  ScanText,
  Search,
  Settings2,
  Sparkles,
  Tag,
  Trash2,
  Video,
  UploadCloud,
  X,
} from "lucide-react";
import { type ChangeEvent, type DragEvent, type FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { DynamicAssetImage } from "../../components/dynamic-asset-image";
import {
  type AnnotationTask,
  type Asset,
  catalogApi,
  type Dataset,
  type DatasetVersion,
  type DatasetVersionQualityReport,
  type ModelVersion,
  type Project,
  type VideoExtractionJob,
  type Workspace,
} from "../../../lib/catalog-api";

type ConnectionState = "loading" | "online" | "offline";
type DataView = "assets" | "annotation" | "classes" | "models" | "versions";
type DatasetSourceMode = "upload" | "url" | "cloud" | "on-premise";

const taskTypeLabels: Record<string, string> = {
  "object-detection": "目标检测",
  classification: "图像分类",
  segmentation: "实例分割",
  "instance-segmentation": "实例分割",
  "semantic-segmentation": "语义分割",
  pose: "姿态估计",
  "oriented-bounding-box": "旋转框检测",
  "depth-estimation": "深度估计",
  ocr: "文字识别",
};

const datasetTaskTypes = [
  { id: "object-detection", label: "目标检测", description: "用矩形框定位对象", support: "内置标注" },
  { id: "instance-segmentation", label: "实例分割", description: "逐个对象绘制掩码", support: "可导入" },
  { id: "semantic-segmentation", label: "语义分割", description: "按类别标记每个像素", support: "可导入" },
  { id: "classification", label: "图像分类", description: "为整张图像分配类别", support: "可导入" },
  { id: "pose", label: "姿态估计", description: "标注对象关键点", support: "可导入" },
  { id: "oriented-bounding-box", label: "旋转框检测", description: "用带方向的框定位对象", support: "可导入" },
  { id: "depth-estimation", label: "深度估计", description: "逐像素估计距离", support: "可导入" },
  { id: "ocr", label: "文字识别", description: "定位并转写图像文字", support: "可导入" },
] as const;

const projectTaskTypes = [
  { id: "object-detection", label: "目标检测" },
  { id: "classification", label: "图像分类" },
  { id: "segmentation", label: "实例分割" },
  { id: "pose", label: "姿态估计" },
  { id: "ocr", label: "文字识别" },
] as const;

function taskUsesClasses(taskType: string): boolean {
  return taskType !== "depth-estimation";
}

function datasetTaskTypeForProject(taskType: string): string {
  return taskType === "segmentation" ? "instance-segmentation" : taskType;
}

function TaskTypeIcon({ taskType, size = 18 }: { taskType: string; size?: number }) {
  if (taskType === "object-detection") return <Box size={size} />;
  if (taskType === "segmentation" || taskType === "instance-segmentation" || taskType === "semantic-segmentation") return <Layers3 size={size} />;
  if (taskType === "classification") return <Tag size={size} />;
  if (taskType === "pose") return <PersonStanding size={size} />;
  if (taskType === "oriented-bounding-box") return <RotateCw size={size} />;
  if (taskType === "depth-estimation") return <Mountain size={size} />;
  return <ScanText size={size} />;
}

function TaskTypePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="dataset-task-type-grid">
      {datasetTaskTypes.map((taskType) => (
        <button
          type="button"
          key={taskType.id}
          className={value === taskType.id ? "is-active" : ""}
          aria-pressed={value === taskType.id}
          disabled={disabled}
          onClick={() => onChange(taskType.id)}
        >
          <span className="dataset-task-type-icon"><TaskTypeIcon taskType={taskType.id} /></span>
          <span><strong>{taskType.label}</strong><small>{taskType.description}</small></span>
          <em>{taskType.support}</em>
        </button>
      ))}
    </div>
  );
}

const splitLabels: Record<string, string> = {
  train: "训练集",
  valid: "验证集",
  test: "测试集",
  draft: "未划分",
};

const annotationStatusLabels: Record<AnnotationTask["status"], string> = {
  annotating: "标注中",
  review: "待检查",
  done: "已完成",
};

const extractionStatusLabels: Record<VideoExtractionJob["status"], string> = {
  queued: "等待处理",
  preparing: "正在准备",
  running: "正在抽帧",
  succeeded: "已完成",
  failed: "处理失败",
  cancel_requested: "正在取消",
  cancelled: "已取消",
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function assetDisplayName(asset: Asset): string {
  const fallback = asset.checksum_sha256.slice(0, 12);
  try {
    const lastPart = decodeURIComponent(asset.uri.split("/").pop() || fallback);
    return lastPart.replace(/^[a-f0-9]{16}-/, "") || fallback;
  } catch {
    return fallback;
  }
}

function classMapsEqual(left: Record<string, string>, right: Record<string, string>): boolean {
  const normalize = (value: Record<string, string>) =>
    Object.entries(value).sort(([a], [b]) => Number(a) - Number(b));
  return JSON.stringify(normalize(left)) === JSON.stringify(normalize(right));
}

function AssetThumbnail({
  workspaceId,
  datasetId,
  asset,
}: {
  workspaceId: string;
  datasetId: string;
  asset: Asset;
}) {
  const [source, setSource] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setSource(null);
    setFailed(false);
    void catalogApi
      .getAssetContent(workspaceId, datasetId, asset.id, controller.signal)
      .then((blob) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [workspaceId, datasetId, asset.id]);

  if (failed) return <FileImage size={20} aria-hidden="true" />;
  if (!source) return <LoaderCircle className="spinner" size={17} aria-label="正在加载素材预览" />;
  return <DynamicAssetImage src={source} alt={assetDisplayName(asset)} />;
}

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function imageDimensions(file: File): Promise<{ width: number; height: number }> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = objectUrl;
    await image.decode();
    return { width: image.naturalWidth, height: image.naturalHeight };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function DataWorkbench() {
  const searchParams = useSearchParams();
  const requestedProjectId = searchParams.get("project");
  const requestedDatasetId = searchParams.get("dataset");
  const requestedVersionId = searchParams.get("version");
  const requestedProjectCreation = searchParams.get("createProject") === "1";
  const requestedDatasetCreation = searchParams.get("createDataset") === "1";
  const requestedView = searchParams.get("view");
  const initialView: DataView = requestedView === "annotation"
    || requestedView === "classes"
    || requestedView === "models"
    || requestedView === "versions"
    ? requestedView
    : "assets";
  const [connection, setConnection] = useState<ConnectionState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [versions, setVersions] = useState<DatasetVersion[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [qualityReport, setQualityReport] = useState<DatasetVersionQualityReport | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("SenseMu 实验室");
  const [projectName, setProjectName] = useState("PPE 安全检测");
  const [projectSlug, setProjectSlug] = useState("ppe-safety-detection");
  const [projectSlugTouched, setProjectSlugTouched] = useState(false);
  const [projectDescription, setProjectDescription] = useState("");
  const [projectTaskType, setProjectTaskType] = useState("object-detection");
  const [projectModelFile, setProjectModelFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("ppe_site_a");
  const [datasetDescription, setDatasetDescription] = useState("");
  const [newDatasetTaskType, setNewDatasetTaskType] = useState("object-detection");
  const [datasetSourceMode, setDatasetSourceMode] = useState<DatasetSourceMode>("upload");
  const [datasetSourceFiles, setDatasetSourceFiles] = useState<File[]>([]);
  const [datasetSourceUrl, setDatasetSourceUrl] = useState("");
  const [pendingTaskType, setPendingTaskType] = useState("object-detection");
  const [taskTypeDialogOpen, setTaskTypeDialogOpen] = useState(false);
  const [classRows, setClassRows] = useState<Array<{ id: string; name: string }>>([]);
  const [projectCreationOpen, setProjectCreationOpen] = useState(requestedProjectCreation);
  const [datasetCreationOpen, setDatasetCreationOpen] = useState(requestedDatasetCreation);
  const [activeView, setActiveView] = useState<DataView>(initialView);
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [pendingVideo, setPendingVideo] = useState<File | null>(null);
  const [pendingVideos, setPendingVideos] = useState<File[]>([]);
  const [frameInterval, setFrameInterval] = useState(1);
  const [sourceVideos, setSourceVideos] = useState<Asset[]>([]);
  const [extractionJobs, setExtractionJobs] = useState<VideoExtractionJob[]>([]);
  const [cancellingExtractionId, setCancellingExtractionId] = useState<string | null>(null);
  const [creatingAnnotationFromJobId, setCreatingAnnotationFromJobId] = useState<string | null>(null);
  const [deduplicateFrames, setDeduplicateFrames] = useState(true);
  const [annotationTasks, setAnnotationTasks] = useState<AnnotationTask[]>([]);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [taskName, setTaskName] = useState("新一批安全穿戴样本");
  const [taskMethod, setTaskMethod] = useState<"manual" | "smart">("manual");
  const [taskAssetScope, setTaskAssetScope] = useState<"unlabeled" | "all">("unlabeled");
  const [assetSearch, setAssetSearch] = useState("");
  const [assetSplitFilter, setAssetSplitFilter] = useState<"all" | "train" | "valid" | "test" | "draft">("all");
  const [assetLayout, setAssetLayout] = useState<"grid" | "list">("grid");
  const workspaceId = workspace?.id ?? null;
  const datasetId = dataset?.id ?? null;
  const datasetClassMap = dataset?.class_map;

  async function loadWorkspaces() {
    setConnection("loading");
    setError(null);
    try {
      const result = await catalogApi.listWorkspaces();
      setWorkspace((current) => result.find((item) => item.id === current?.id) ?? result[0] ?? null);
      setConnection("online");
    } catch (reason) {
      setConnection("offline");
      setError(reason instanceof Error ? reason.message : "无法连接数据服务");
    }
  }

  useEffect(() => {
    void loadWorkspaces();
  }, []);

  useEffect(() => {
    setProjectCreationOpen(requestedProjectCreation);
  }, [requestedProjectCreation]);

  useEffect(() => {
    setDatasetCreationOpen(requestedDatasetCreation);
  }, [requestedDatasetCreation]);

  useEffect(() => {
    if (!workspace) {
      setProjects([]);
      setProject(null);
      return;
    }
    void catalogApi
      .listProjects(workspace.id)
      .then((result) => {
        setProjects(result);
        setProject((current) =>
          result.find((item) => item.id === requestedProjectId)
          ?? result.find((item) => item.id === current?.id)
          ?? result[0]
          ?? null,
        );
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "项目加载失败"));
  }, [workspace, requestedProjectId]);

  useEffect(() => {
    if (!workspace || !project) {
      setDatasets([]);
      setDataset(null);
      setModelVersions([]);
      return;
    }
    void Promise.all([
      catalogApi.listDatasets(workspace.id, project.id),
      catalogApi.listModelVersions(workspace.id, project.id),
    ])
      .then(([result, nextModels]) => {
        setDatasets(result);
        setModelVersions(nextModels);
        setDataset((current) =>
          requestedDatasetCreation
            ? null
            : result.find((item) => item.id === requestedDatasetId)
              ?? result.find((item) => item.id === current?.id)
              ?? result[0]
              ?? null,
        );
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "数据集加载失败"));
  }, [workspace, project, requestedDatasetCreation, requestedDatasetId]);

  async function refreshDataset(selected = dataset) {
    if (!workspace || !project || !selected) return;
    const [nextAssets, nextVersions, nextDatasets, nextSourceVideos, nextExtractions] = await Promise.all([
      catalogApi.listAssets(workspace.id, selected.id),
      catalogApi.listVersions(workspace.id, selected.id),
      catalogApi.listDatasets(workspace.id, project.id),
      catalogApi.listSourceVideos(workspace.id, selected.id),
      catalogApi.listVideoExtractions(workspace.id, selected.id),
    ]);
    setAssets(nextAssets);
    setVersions(nextVersions);
    setDatasets(nextDatasets);
    const refreshedDataset = nextDatasets.find((item) => item.id === selected.id) ?? selected;
    setDataset(refreshedDataset);
    setClassRows(
      Object.entries(refreshedDataset.class_map ?? {})
        .sort(([left], [right]) => Number(left) - Number(right))
        .map(([id, name]) => ({ id, name })),
    );
    setPendingTaskType(refreshedDataset.task_type);
    setSourceVideos(nextSourceVideos);
    setExtractionJobs(nextExtractions);
  }

  useEffect(() => {
    if (!datasetId || !workspaceId) {
      setAssets([]);
      setVersions([]);
      return;
    }
    void Promise.all([
      catalogApi.listAssets(workspaceId, datasetId),
      catalogApi.listVersions(workspaceId, datasetId),
      catalogApi.listSourceVideos(workspaceId, datasetId),
      catalogApi.listVideoExtractions(workspaceId, datasetId),
    ])
      .then(([nextAssets, nextVersions, nextSourceVideos, nextExtractions]) => {
        setAssets(nextAssets);
        setVersions(nextVersions);
        setSelectedVersionId((current) => {
          if (requestedVersionId && nextVersions.some((version) => version.id === requestedVersionId)) {
            return requestedVersionId;
          }
          return current && nextVersions.some((version) => version.id === current) ? current : null;
        });
        setSourceVideos(nextSourceVideos);
        setExtractionJobs(nextExtractions);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "数据加载失败"));
  }, [datasetId, requestedVersionId, workspaceId]);

  useEffect(() => {
    setClassRows(
      Object.entries(datasetClassMap ?? {})
        .sort(([left], [right]) => Number(left) - Number(right))
        .map(([id, name]) => ({ id, name })),
    );
  }, [datasetClassMap]);

  useEffect(() => {
    if (dataset?.task_type) setPendingTaskType(dataset.task_type);
  }, [dataset?.task_type]);

  useEffect(() => {
    if (project?.task_type) setNewDatasetTaskType(datasetTaskTypeForProject(project.task_type));
  }, [project?.id, project?.task_type]);

  useEffect(() => {
    if (!workspaceId || !datasetId) return;
    const hasActiveExtraction = extractionJobs.some((job) =>
      ["queued", "preparing", "running", "cancel_requested"].includes(job.status),
    );
    if (!hasActiveExtraction) return;
    const timer = window.setInterval(() => {
      void Promise.all([
        catalogApi.listVideoExtractions(workspaceId, datasetId),
        catalogApi.listAssets(workspaceId, datasetId),
      ])
        .then(([jobs, nextAssets]) => {
          setExtractionJobs(jobs);
          setAssets(nextAssets);
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [datasetId, extractionJobs, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !datasetId) {
      setAnnotationTasks([]);
      return;
    }
    void catalogApi
      .listAnnotationTasks(workspaceId, datasetId)
      .then(setAnnotationTasks)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "标注任务加载失败"));
  }, [datasetId, workspaceId]);

  const selectedVersion = versions.find((item) => item.id === selectedVersionId) ?? versions[0] ?? null;
  const resolvedVersionId = selectedVersion?.id ?? null;

  useEffect(() => {
    if (!workspaceId || !resolvedVersionId) {
      setQualityReport(null);
      return;
    }
    setQualityLoading(true);
    void catalogApi
      .getDatasetVersionQualityReport(workspaceId, resolvedVersionId)
      .then(setQualityReport)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "质量报告加载失败"))
      .finally(() => setQualityLoading(false));
  }, [resolvedVersionId, workspaceId]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await catalogApi.createWorkspace({
        name: workspaceName,
        slug: slugify(workspaceName) || "sensemu-lab",
      });
      setWorkspace(created);
      setNotice("工作区已创建");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "工作区创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    if (!workspace) return;
    setBusy(true);
    setError(null);
    try {
      const created = await catalogApi.createProject(workspace.id, {
        name: projectName,
        slug: projectSlug || slugify(projectName) || "vision-project",
        task_type: projectTaskType,
        description: projectDescription.trim() || undefined,
      });
      setProjects([created, ...projects]);
      setProject(created);
      setProjectCreationOpen(false);
      setProjectModelFile(null);
      setNotice("项目已创建");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function createDataset(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !project) return;
    if (datasetSourceMode !== "upload") {
      setError("当前数据源尚未接入，请先选择上传素材");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await catalogApi.createDataset(workspace.id, project.id, {
        name: datasetName,
        task_type: newDatasetTaskType,
        description: datasetDescription.trim() || undefined,
      });
      setDatasets([created, ...datasets]);
      setDataset(created);
      setDatasetCreationOpen(false);
      const imageFiles = datasetSourceFiles.filter((file) => file.type.startsWith("image/"));
      const videoFiles = datasetSourceFiles.filter((file) => file.type.startsWith("video/"));
      setDatasetSourceFiles([]);
      setDatasetDescription("");
      setNotice(imageFiles.length ? "数据集已创建，正在导入素材" : "数据集已创建");
      if (imageFiles.length) await uploadImageFiles(imageFiles, created);
      if (videoFiles.length) {
        setPendingVideos(videoFiles);
        setPendingVideo(videoFiles[0]);
        setVideoDialogOpen(true);
        setNotice(`数据集已创建，请配置第 1 / ${videoFiles.length} 个视频的抽帧`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "数据集创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadImageFiles(files: File[], targetDataset: Dataset | null = dataset) {
    if (!workspace || !targetDataset || files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      for (const [index, file] of files.entries()) {
        setNotice(`正在上传 ${index + 1} / ${files.length}：${file.name}`);
        const checksum = await sha256(file);
        const dimensions = await imageDimensions(file);
        const intent = await catalogApi.createUploadIntent(workspace.id, targetDataset.id, {
          filename: file.name,
          content_type: file.type,
          byte_size: file.size,
          checksum_sha256: checksum,
        });
        const upload = await fetch(intent.upload_url, {
          method: intent.method,
          headers: intent.headers,
          body: file,
        });
        if (!upload.ok) throw new Error(`对象存储上传失败 (${upload.status})`);
        await catalogApi.registerAsset(workspace.id, targetDataset.id, {
          object_key: intent.object_key,
          media_type: file.type,
          checksum_sha256: checksum,
          byte_size: file.size,
          width: dimensions.width,
          height: dimensions.height,
        });
      }
      await refreshDataset(targetDataset);
      setNotice(`${files.length} 个资产已导入`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  function selectMedia(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const videoFile = files.find((file) => file.type.startsWith("video/"));
    const imageFiles = files.filter((file) => file.type.startsWith("image/"));

    if (videoFile) {
      setPendingVideo(videoFile);
      setVideoDialogOpen(true);
    }
    if (imageFiles.length) void uploadImageFiles(imageFiles);
    event.target.value = "";
  }

  function stageDatasetSourceFiles(files: File[]) {
    const supportedFiles = files.filter(
      (file) => file.type.startsWith("image/") || file.type.startsWith("video/"),
    );
    if (!supportedFiles.length) {
      setError("请选择图片或视频文件");
      return;
    }
    setDatasetSourceFiles((current) => [...current, ...supportedFiles].slice(0, 100));
    setError(null);
  }

  function selectDatasetSourceFiles(event: ChangeEvent<HTMLInputElement>) {
    stageDatasetSourceFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  async function createExtractionJob(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !dataset || !pendingVideo) return;
    setBusy(true);
    setError(null);
    try {
      const checksum = await sha256(pendingVideo);
      const intent = await catalogApi.createUploadIntent(workspace.id, dataset.id, {
        filename: pendingVideo.name,
        content_type: pendingVideo.type,
        byte_size: pendingVideo.size,
        checksum_sha256: checksum,
      });
      const upload = await fetch(intent.upload_url, {
        method: intent.method,
        headers: intent.headers,
        body: pendingVideo,
      });
      if (!upload.ok) throw new Error(`视频上传失败 (${upload.status})`);
      const sourceAsset = await catalogApi.registerAsset(workspace.id, dataset.id, {
        object_key: intent.object_key,
        media_type: pendingVideo.type,
        checksum_sha256: checksum,
        byte_size: pendingVideo.size,
        width: null,
        height: null,
      });
      const job = await catalogApi.createVideoExtraction(
        workspace.id,
        dataset.id,
        `video-${checksum.slice(0, 20)}-${Math.round(frameInterval * 1000)}-${deduplicateFrames}`,
        {
          source_asset_id: sourceAsset.id,
          frame_interval_ms: Math.round(frameInterval * 1000),
          deduplicate: deduplicateFrames,
        },
      );
      setSourceVideos((current) => [sourceAsset, ...current.filter((item) => item.id !== sourceAsset.id)]);
      setExtractionJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      const remainingVideos = pendingVideos.slice(1);
      if (remainingVideos.length) {
        setPendingVideos(remainingVideos);
        setPendingVideo(remainingVideos[0]);
        setNotice(`抽帧任务已创建：${pendingVideo.name}，请配置下一个视频`);
      } else {
        setPendingVideos([]);
        setPendingVideo(null);
        setVideoDialogOpen(false);
        setActiveView("assets");
        setNotice(`抽帧任务已创建：${pendingVideo.name}`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "抽帧任务创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function createAnnotationTask(event: FormEvent) {
    event.preventDefault();
    if (!workspace || !dataset) return;
    if (usesClasses && (classMapChanged || hasInvalidClassName)) {
      setError("请先保存类别定义，再创建标注任务");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await catalogApi.createAnnotationTask(workspace.id, dataset.id, {
        name: taskName.trim() || "未命名标注任务",
        method: taskMethod,
        asset_scope: taskAssetScope,
        class_map: dataset.class_map,
      });
      setAnnotationTasks((current) => [created, ...current]);
      setTaskDialogOpen(false);
      setNotice("手动标注任务已创建");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "标注任务创建失败");
    } finally {
      setBusy(false);
    }
  }

  function openAnnotationTaskDialog() {
    setTaskAssetScope("unlabeled");
    setTaskDialogOpen(true);
  }

  async function cancelExtractionJob(job: VideoExtractionJob) {
    if (!workspace || ["succeeded", "failed", "cancelled", "cancel_requested"].includes(job.status)) return;
    setCancellingExtractionId(job.id);
    setError(null);
    try {
      const updated = await catalogApi.cancelVideoExtraction(workspace.id, job.id);
      setExtractionJobs((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(updated.status === "cancelled" ? "抽帧任务已取消" : "已请求取消抽帧任务");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "抽帧任务取消失败");
    } finally {
      setCancellingExtractionId(null);
    }
  }

  async function createAnnotationTaskFromExtraction(job: VideoExtractionJob) {
    if (!workspace || !dataset || job.status !== "succeeded") return;
    if (usesClasses && (classMapChanged || hasInvalidClassName)) {
      setError("请先保存类别定义，再创建标注任务");
      return;
    }
    setCreatingAnnotationFromJobId(job.id);
    setError(null);
    try {
      const source = sourceVideos.find((item) => item.id === job.source_asset_id);
      const created = await catalogApi.createAnnotationTaskFromVideoExtraction(
        workspace.id,
        dataset.id,
        job.id,
        `${source ? assetDisplayName(source) : "视频抽帧"} 标注`,
        dataset.class_map,
      );
      setAnnotationTasks((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setActiveView("annotation");
      setNotice(`标注任务已就绪：${created.asset_count} 个素材`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "标注任务创建失败");
    } finally {
      setCreatingAnnotationFromJobId(null);
    }
  }

  async function freezeVersion() {
    if (!workspace || !dataset) return;
    if (usesClasses && (classMapChanged || hasInvalidClassName)) {
      setError("请先保存类别定义，再生成数据版本");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const version = await catalogApi.freezeDataset(workspace.id, dataset.id, dataset.class_map);
      await refreshDataset(dataset);
      setSelectedVersionId(version.id);
      setNotice(`ds_v${version.version_number} 已冻结`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "版本冻结失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveClassMap() {
    if (!workspace || !dataset || !classMapChanged || hasInvalidClassName) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await catalogApi.updateDatasetClassMap(workspace.id, dataset.id, classMap);
      setDataset(updated);
      setDatasets((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setNotice("类别定义已保存");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "类别定义保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveDatasetTaskType() {
    if (!workspace || !dataset || pendingTaskType === dataset.task_type) {
      setTaskTypeDialogOpen(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await catalogApi.updateDatasetDefinition(
        workspace.id,
        dataset.id,
        pendingTaskType,
      );
      const merged = {
        ...dataset,
        ...updated,
        asset_count: dataset.asset_count,
        version_count: dataset.version_count,
      };
      setDataset(merged);
      setDatasets((current) => current.map((item) => (item.id === merged.id ? merged : item)));
      if (!taskUsesClasses(merged.task_type)) setClassRows([]);
      setTaskTypeDialogOpen(false);
      setNotice(`任务类型已更新为${taskTypeLabels[merged.task_type] ?? merged.task_type}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "任务类型更新失败");
    } finally {
      setBusy(false);
    }
  }

  function addClassRow() {
    setClassRows((current) => [...current, { id: String(current.length), name: "" }]);
  }

  function updateClassRow(index: number, name: string) {
    setClassRows((current) => current.map((item, rowIndex) => rowIndex === index ? { ...item, name } : item));
  }

  function removeClassRow(index: number) {
    setClassRows((current) => current
      .filter((_, rowIndex) => rowIndex !== index)
      .map((item, rowIndex) => ({ ...item, id: String(rowIndex) })));
  }

  async function updateSplit(asset: Asset, split: "train" | "valid" | "test") {
    if (!workspace || !dataset) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await catalogApi.updateDatasetItem(
        workspace.id,
        dataset.id,
        asset.id,
        split,
      );
      setAssets((current) => current.map((item) => (item.id === asset.id ? updated : item)));
      setNotice(`已设为${splitLabels[split]}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "数据划分更新失败");
    } finally {
      setBusy(false);
    }
  }

  async function uploadAnnotation(asset: Asset, event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!workspace || !dataset || !file) return;
    setBusy(true);
    setError(null);
    try {
      const checksum = await sha256(file);
      const intent = await catalogApi.createAnnotationUploadIntent(
        workspace.id,
        dataset.id,
        asset.id,
        {
          filename: file.name,
          byte_size: file.size,
          checksum_sha256: checksum,
        },
      );
      const upload = await fetch(intent.upload_url, {
        method: intent.method,
        headers: intent.headers,
        body: file,
      });
      if (!upload.ok) throw new Error(`标注上传失败 (${upload.status})`);
      const updated = await catalogApi.registerAnnotation(
        workspace.id,
        dataset.id,
        asset.id,
        {
          object_key: intent.object_key,
          byte_size: file.size,
          checksum_sha256: checksum,
        },
      );
      setAssets((current) => current.map((item) => (item.id === asset.id ? updated : item)));
      setNotice("YOLO 标注已校验并登记");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "标注导入失败");
    } finally {
      input.value = "";
      setBusy(false);
    }
  }

  const parsedClassNames = classRows.map((item) => item.name.trim()).filter(Boolean);
  const hasInvalidClassName = classRows.some((item) => !item.name.trim());
  const classMap = Object.fromEntries(classRows.map((item, index) => [String(index), item.name.trim()]));
  const classMapChanged = !classMapsEqual(classMap, dataset?.class_map ?? {});
  const annotatedCount = assets.filter((item) => item.annotation_uri).length;
  const totalBytes = assets.reduce((sum, item) => sum + item.byte_size, 0);
  const visibleQualityReport = qualityReport?.dataset_version_id === selectedVersion?.id
    ? qualityReport
    : null;
  const annotationCount = visibleQualityReport?.class_distribution.reduce(
    (sum, item) => sum + item.annotation_count,
    0,
  );
  const splitCounts = assets.reduce(
    (counts, item) => {
      const split = item.split === "train" || item.split === "valid" || item.split === "test"
        ? item.split
        : "draft";
      counts[split] += 1;
      return counts;
    },
    { train: 0, valid: 0, test: 0, draft: 0 },
  );
  const normalizedAssetSearch = assetSearch.trim().toLowerCase();
  const visibleAssets = assets.filter((item) => {
    const matchesSplit = assetSplitFilter === "all"
      || (assetSplitFilter === "draft" ? !item.split : item.split === assetSplitFilter);
    const matchesSearch = !normalizedAssetSearch
      || assetDisplayName(item).toLowerCase().includes(normalizedAssetSearch)
      || item.checksum_sha256.includes(normalizedAssetSearch);
    return matchesSplit && matchesSearch;
  });
  const assignedCount = assets.filter((item) => item.split).length;
  const hasTrain = assets.some((item) => item.split === "train");
  const hasValid = assets.some((item) => item.split === "valid");
  const activeTaskType = dataset?.task_type ?? project?.task_type ?? "object-detection";
  const requiresYolo = activeTaskType === "object-detection";
  const supportsBuiltInAnnotation = activeTaskType === "object-detection";
  const usesClasses = taskUsesClasses(activeTaskType);
  const datasetDefinitionLocked = annotatedCount > 0 || annotationTasks.length > 0 || versions.length > 0;
  const pendingAnnotationTasks = annotationTasks.filter((item) => item.status !== "done");
  const trainingHref = project
    ? selectedVersion
      ? `/studio/training?project=${project.id}&datasetVersion=${selectedVersion.id}`
      : `/studio/training?project=${project.id}`
    : "/studio/training";
  const freezeBlockers = [
    assets.length === 0 ? "请先导入图片" : null,
    usesClasses && parsedClassNames.length === 0 ? "请定义类别" : null,
    usesClasses && (classMapChanged || hasInvalidClassName) ? "请先保存类别" : null,
    requiresYolo && assignedCount !== assets.length ? "仍有图片未划分" : null,
    requiresYolo && !hasTrain ? "缺少训练集" : null,
    requiresYolo && !hasValid ? "缺少验证集" : null,
    requiresYolo && annotatedCount !== assets.length ? "仍有图片未标注" : null,
    pendingAnnotationTasks.length
      ? `标注任务「${pendingAnnotationTasks[0].name}」尚未完成检查`
      : null,
  ].filter((item): item is string => Boolean(item));
  const activeExtractionJobs = extractionJobs.filter((job) =>
    ["queued", "preparing", "running", "cancel_requested"].includes(job.status),
  );
  const annotationSummary = annotationTasks.reduce(
    (summary, item) => {
      summary[item.status] += item.asset_count - (item.status === "done" ? 0 : item.completed_count);
      return summary;
    },
    { annotating: 0, review: 0, done: 0 },
  );

  return (
    <section className="data-workbench" id="new-project">
      <div className="data-content">
        {error ? (
          <div className="workbench-message error-message" role="alert">
            <AlertCircle size={15} aria-hidden="true" />
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)}>
              关闭
            </button>
          </div>
        ) : null}
        {notice ? (
          <div className="workbench-message notice-message" role="status">
            <Check size={14} aria-hidden="true" />
            <span>{notice}</span>
          </div>
        ) : null}

        {connection === "offline" ? (
          <article className="panel workbench-empty-state">
            <span className="empty-state-icon">
              <AlertCircle size={20} />
            </span>
            <span className="eyebrow">本地数据服务</span>
            <h2>数据服务尚未连接</h2>
            <p>启动 SenseMu 数据服务后，这里会显示真实项目与数据版本。</p>
            <button className="primary-button" type="button" onClick={() => void loadWorkspaces()}>
              <RefreshCw size={14} />
              重新连接
            </button>
          </article>
        ) : connection === "loading" ? (
          <article className="panel workbench-loading" aria-live="polite">
            <LoaderCircle size={20} className="spinner" />
            <span>正在读取工作区…</span>
          </article>
        ) : !workspace ? (
          <SetupForm
            eyebrow="首次配置"
            title="创建第一个工作区"
            description="工作区是项目、数据和计费的隔离边界。"
            label="工作区名称"
            value={workspaceName}
            onChange={setWorkspaceName}
            onSubmit={createWorkspace}
            busy={busy}
          />
        ) : !project || projectCreationOpen ? (
          <ProjectSetupForm
            name={projectName}
            onNameChange={(value) => {
              setProjectName(value);
              if (!projectSlugTouched) setProjectSlug(slugify(value) || "vision-project");
            }}
            slug={projectSlug}
            onSlugChange={(value) => {
              setProjectSlugTouched(true);
              setProjectSlug(slugify(value));
            }}
            description={projectDescription}
            onDescriptionChange={setProjectDescription}
            taskType={projectTaskType}
            onTaskTypeChange={setProjectTaskType}
            modelFile={projectModelFile}
            onModelFileChange={setProjectModelFile}
            onSubmit={createProject}
            busy={busy}
          />
        ) : !dataset || datasetCreationOpen ? (
          <DatasetSetupForm
            name={datasetName}
            onNameChange={setDatasetName}
            description={datasetDescription}
            onDescriptionChange={setDatasetDescription}
            taskType={newDatasetTaskType}
            onTaskTypeChange={setNewDatasetTaskType}
            sourceMode={datasetSourceMode}
            onSourceModeChange={setDatasetSourceMode}
            sourceFiles={datasetSourceFiles}
            onFilesSelected={selectDatasetSourceFiles}
            onFilesDropped={stageDatasetSourceFiles}
            sourceUrl={datasetSourceUrl}
            onSourceUrlChange={setDatasetSourceUrl}
            onSubmit={createDataset}
            onCancel={() => setDatasetCreationOpen(false)}
            canCancel={Boolean(dataset)}
            busy={busy}
          />
        ) : (
          <>
            <div className="dataset-object-breadcrumbs">
              <Link href="/">工作台</Link>
              <ChevronRight size={12} aria-hidden="true" />
              <span>数据与标注</span>
              <ChevronRight size={12} aria-hidden="true" />
              <strong>{dataset.name}</strong>
            </div>

            <header className="dataset-object-header">
              <span className="dataset-object-mark"><Database size={20} strokeWidth={1.6} aria-hidden="true" /></span>
              <div className="dataset-object-copy">
                <div className="dataset-object-title-row">
                  <h1>{dataset.name}</h1>
                  <button
                    type="button"
                    className="dataset-task-type dataset-task-type-button"
                    onClick={() => {
                      setPendingTaskType(activeTaskType);
                      setTaskTypeDialogOpen(true);
                    }}
                  >
                    <TaskTypeIcon taskType={activeTaskType} size={13} />
                    {taskTypeLabels[activeTaskType] ?? activeTaskType}
                    <Settings2 size={12} aria-hidden="true" />
                  </button>
                  <span className={`dataset-object-state${versions.length ? " is-ready" : ""}`}><i />{versions.length ? "已就绪" : "草稿"}</span>
                </div>
                <p>{dataset.description || `${project.name} 的${taskTypeLabels[activeTaskType] ?? activeTaskType}数据集`}</p>
                <div className="dataset-object-meta" aria-label="数据集统计">
                  <span><FileImage size={13} />{assets.length.toLocaleString("zh-CN")} 个素材</span>
                  <span><FileCheck2 size={13} />{annotatedCount.toLocaleString("zh-CN")} 个已标注</span>
                  {annotationCount !== undefined ? <span><ListChecks size={13} />{annotationCount.toLocaleString("zh-CN")} 个标注实例</span> : null}
                  <span>{formatBytes(totalBytes)}</span>
                  <span>更新于 {new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(dataset.created_at))}</span>
                </div>
              </div>
              <div className="dataset-object-actions">
                <button
                  className="secondary-button freeze-button"
                  type="button"
                  disabled={busy || freezeBlockers.length > 0}
                  onClick={() => void freezeVersion()}
                  title={freezeBlockers.join("；")}
                >
                  <LockKeyhole size={14} aria-hidden="true" />
                  冻结新版本
                </button>
                <Link className="primary-button" href={trainingHref}>
                  开始训练<ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              </div>
            </header>

            <nav className="dataset-view-tabs" aria-label="数据集视图">
              <button type="button" className={activeView === "assets" ? "is-active" : ""} onClick={() => setActiveView("assets")}>素材 <span>{assets.length}</span></button>
              <button type="button" className={activeView === "annotation" ? "is-active" : ""} onClick={() => setActiveView("annotation")}>标注任务 <span>{annotationTasks.length}</span></button>
              <button type="button" className={activeView === "classes" ? "is-active" : ""} onClick={() => setActiveView("classes")}>类别 <span>{parsedClassNames.length}</span></button>
              <button type="button" className={activeView === "models" ? "is-active" : ""} onClick={() => setActiveView("models")}>模型 <span>{modelVersions.length}</span></button>
              <button type="button" className={activeView === "versions" ? "is-active" : ""} onClick={() => setActiveView("versions")}>版本 <span>{versions.length}</span></button>
            </nav>

            {activeView === "assets" ? (
              <>
                <div className="dataset-ingest-bar">
                  <div>
                    <strong>导入素材</strong>
                    <span>支持图片、视频文件和固定视频流</span>
                  </div>
                  <label className={`secondary-button compact dataset-upload-button ${busy ? "is-busy" : ""}`}>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                      multiple
                      disabled={busy}
                      onChange={selectMedia}
                    />
                    {busy ? <LoaderCircle size={14} className="spinner" /> : <UploadCloud size={14} />}
                    {busy ? "正在处理" : "选择文件"}
                  </label>
                  <button className="secondary-button compact" type="button" disabled title="待建立加密凭据和 Worker 访问边界"><Video size={14} />视频流待接入</button>
                  {activeExtractionJobs.length ? <span className="dataset-extraction-state"><LoaderCircle size={13} className="spinner" />{activeExtractionJobs.length} 个抽帧任务处理中</span> : null}
                </div>

                <article className="panel asset-table-card">
                  <div className="asset-table-heading">
                    <div><h3>素材</h3><p>{visibleAssets.length} / {assets.length} 项</p></div>
                  </div>
                  <div className="asset-browser-toolbar">
                    <div className="asset-split-tabs" role="tablist" aria-label="数据划分">
                      {([
                        ["all", "全部", assets.length],
                        ["train", "训练集", splitCounts.train],
                        ["valid", "验证集", splitCounts.valid],
                        ["test", "测试集", splitCounts.test],
                        ["draft", "未划分", splitCounts.draft],
                      ] as const).map(([value, label, count]) => (
                        <button type="button" role="tab" aria-selected={assetSplitFilter === value} className={assetSplitFilter === value ? "is-active" : ""} onClick={() => setAssetSplitFilter(value)} key={value}>{label}<span>{count}</span></button>
                      ))}
                    </div>
                    <div className="asset-browser-controls">
                      <label className="asset-search"><Search size={14} /><span className="sr-only">搜索素材</span><input value={assetSearch} onChange={(event) => setAssetSearch(event.target.value)} placeholder="搜索素材" /></label>
                      <div className="asset-layout-switch" aria-label="素材视图">
                        <button type="button" className={assetLayout === "grid" ? "is-active" : ""} aria-label="网格视图" aria-pressed={assetLayout === "grid"} onClick={() => setAssetLayout("grid")}><Grid2X2 size={14} /></button>
                        <button type="button" className={assetLayout === "list" ? "is-active" : ""} aria-label="列表视图" aria-pressed={assetLayout === "list"} onClick={() => setAssetLayout("list")}><List size={14} /></button>
                      </div>
                    </div>
                  </div>
                  {extractionJobs.map((job) => {
                    const source = sourceVideos.find((item) => item.id === job.source_asset_id);
                    const canCancel = ["queued", "preparing", "running"].includes(job.status);
                    const existingTask = annotationTasks.find((item) => item.source_video_extraction_job_id === job.id);
                    return (
                      <div className="asset-batch-row" key={job.id}>
                        <span className="asset-preview"><Film size={16} /></span>
                        <span><strong>{source ? assetDisplayName(source) : "视频文件"}</strong><small>每 {(job.frame_interval_ms / 1000).toLocaleString("zh-CN")} 秒抽取 1 帧{job.deduplicate ? " · 去除重复帧" : ""}</small></span>
                        <span className={`batch-state ${job.status}`}>{extractionStatusLabels[job.status]}{job.status === "running" ? ` ${job.progress}%` : job.status === "succeeded" ? ` · ${job.frames_created} 张` : ""}</span>
                        {canCancel ? <button className="batch-cancel-button" type="button" onClick={() => void cancelExtractionJob(job)} disabled={cancellingExtractionId === job.id} aria-label="取消抽帧任务" title="取消抽帧任务">{cancellingExtractionId === job.id ? <LoaderCircle size={13} className="spinner" /> : <X size={13} />}</button> : null}
                        {job.status === "succeeded" ? <button className="batch-annotation-button" type="button" onClick={() => void createAnnotationTaskFromExtraction(job)} disabled={creatingAnnotationFromJobId === job.id}>{creatingAnnotationFromJobId === job.id ? <LoaderCircle size={13} className="spinner" /> : <FileCheck2 size={13} />}{existingTask ? "查看标注" : "标注"}</button> : null}
                      </div>
                    );
                  })}
                  {visibleAssets.length ? assetLayout === "grid" ? (
                    <div className="asset-grid">
                      {visibleAssets.map((asset) => (
                        <article className="asset-grid-card" key={asset.id}>
                          <div className="asset-grid-preview">
                            {workspace && dataset ? <AssetThumbnail workspaceId={workspace.id} datasetId={dataset.id} asset={asset} /> : <FileImage size={20} />}
                            <span className={asset.annotation_uri ? "is-ready" : ""}>{asset.annotation_uri ? "已标注" : "未标注"}</span>
                          </div>
                          <div className="asset-grid-copy"><strong title={assetDisplayName(asset)}>{assetDisplayName(asset)}</strong><small>{asset.width && asset.height ? `${asset.width} × ${asset.height}` : formatBytes(asset.byte_size)}</small></div>
                          <div className="asset-grid-actions">
                            <select className={`split-select ${asset.split ?? "draft"}`} value={asset.split ?? ""} disabled={busy} aria-label="数据划分" onChange={(event) => { const split = event.target.value as "train" | "valid" | "test"; if (split) void updateSplit(asset, split); }}>
                              <option value="" disabled>未划分</option><option value="train">训练集</option><option value="valid">验证集</option><option value="test">测试集</option>
                            </select>
                            <label className={`annotation-upload ${asset.annotation_uri ? "is-ready" : ""}`}><input type="file" accept=".txt,text/plain" disabled={busy} onChange={(event) => void uploadAnnotation(asset, event)} />{asset.annotation_uri ? <FileCheck2 size={13} /> : <UploadCloud size={13} />}<span>{asset.annotation_uri ? "替换标注" : "导入标注"}</span></label>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="asset-table">
                      {visibleAssets.map((asset) => (
                        <div className="asset-row" key={asset.id}>
                          <span className="asset-preview">{workspace && dataset ? <AssetThumbnail workspaceId={workspace.id} datasetId={dataset.id} asset={asset} /> : <FileImage size={16} />}</span>
                          <span className="asset-identity"><strong>{assetDisplayName(asset)}</strong><small>{asset.media_type}</small></span>
                          <span>{asset.width && asset.height ? `${asset.width} × ${asset.height}` : "—"}</span>
                          <span>{formatBytes(asset.byte_size)}</span>
                          <select
                            className={`split-select ${asset.split ?? "draft"}`}
                            value={asset.split ?? ""}
                            disabled={busy}
                            aria-label="数据划分"
                            onChange={(event) => {
                              const split = event.target.value as "train" | "valid" | "test";
                              if (split) void updateSplit(asset, split);
                            }}
                          >
                            <option value="" disabled>选择划分</option>
                            <option value="train">训练集</option>
                            <option value="valid">验证集</option>
                            <option value="test">测试集</option>
                          </select>
                          <label className={`annotation-upload ${asset.annotation_uri ? "is-ready" : ""}`}>
                            <input type="file" accept=".txt,text/plain" disabled={busy} onChange={(event) => void uploadAnnotation(asset, event)} />
                            {asset.annotation_uri ? <FileCheck2 size={13} /> : <UploadCloud size={13} />}
                            <span>{asset.annotation_uri ? "已标注" : "导入标注"}</span>
                          </label>
                          <button type="button" title="复制素材地址" onClick={() => void navigator.clipboard.writeText(asset.uri)}><ArrowUpRight size={14} /></button>
                        </div>
                      ))}
                    </div>
                  ) : !activeExtractionJobs.length && !assets.length ? (
                    <div className="asset-empty"><FileImage size={19} /><p>还没有素材，请先导入图片、视频或视频流。</p></div>
                  ) : assets.length ? (
                    <div className="asset-empty"><Search size={19} /><p>没有符合当前筛选的素材。</p></div>
                  ) : null}
                </article>
              </>
            ) : null}

            {activeView === "annotation" ? (
              <article className="panel annotation-tasks-card">
                <div className="annotation-tasks-heading">
                  <div><h3>标注任务</h3><p>任务沿用数据集的任务类型和类别定义，创建后保持固定。</p></div>
                  <button className="primary-button" type="button" disabled={!supportsBuiltInAnnotation} title={supportsBuiltInAnnotation ? undefined : "当前内置标注器仅支持目标检测"} onClick={openAnnotationTaskDialog}><Plus size={14} />新建任务</button>
                </div>
                {!supportsBuiltInAnnotation ? (
                  <div className="annotation-compatibility-note">
                    <AlertCircle size={15} />
                    <span><strong>{taskTypeLabels[activeTaskType] ?? activeTaskType}暂未接入内置编辑器</strong><small>当前先维护数据契约和类别；标注格式适配完成后开放创建任务。</small></span>
                  </div>
                ) : null}
                <div className="annotation-summary-strip">
                  <div><span>标注中</span><strong>{annotationSummary.annotating}</strong></div>
                  <div><span>待检查</span><strong>{annotationSummary.review}</strong></div>
                  <div><span>已完成</span><strong>{annotationTasks.filter((item) => item.status === "done").reduce((sum, item) => sum + item.asset_count, 0)}</strong></div>
                </div>
                <div className="annotation-task-list">
                  {annotationTasks.map((item) => {
                    const progress = item.asset_count ? Math.round((item.completed_count / item.asset_count) * 100) : 0;
                    return (
                      <div className="annotation-task-row" key={item.id}>
                        <span className="task-method-icon manual" aria-hidden="true"><FileCheck2 size={16} /></span>
                        <span className="task-main"><strong>{item.name}</strong><small>{item.asset_scope === "all" ? "全部素材" : item.asset_scope === "video_extraction" ? "视频抽帧素材" : "未标注素材"} · 手动标注</small></span>
                        <span className="task-progress"><i><b style={{ width: `${progress}%` }} /></i><small>{item.completed_count} / {item.asset_count}</small></span>
                        <span className={`task-status ${item.status}`}>{annotationStatusLabels[item.status]}</span>
                        <Link href={`/studio/data/annotate?task=${item.id}&project=${project.id}&dataset=${dataset.id}`} className="task-open-link">{item.status === "done" ? "查看" : item.status === "review" ? "检查" : "继续"}<ChevronRight size={14} /></Link>
                      </div>
                    );
                  })}
                </div>
              </article>
            ) : null}

            {activeView === "classes" ? (
              <article className="panel dataset-insights-card">
                <div className="dataset-insights-heading">
                  <div><span className="dataset-insights-icon"><BarChart3 size={17} /></span><span><h3>类别与标注统计</h3><p>快速判断类别分布和标注覆盖是否适合训练。</p></span></div>
                  {selectedVersion ? <span className="immutable-chip"><LockKeyhole size={12} />版本 {selectedVersion.version_number}</span> : <span className="immutable-chip">当前草稿</span>}
                </div>
                {usesClasses ? (
                  <div className="dataset-class-editor is-structured">
                    <div className="dataset-class-editor-heading">
                      <span className="readiness-icon"><ListChecks size={15} /></span>
                      <span><strong>类别定义</strong><small>类别编号写入标注文件，创建任务后不再改变。</small></span>
                      <span className={classMapChanged ? "class-state is-dirty" : "class-state"}>{classMapChanged ? "未保存" : "已同步"}</span>
                    </div>
                    {datasetDefinitionLocked ? (
                      <div className="dataset-definition-lock-note"><LockKeyhole size={14} /><span><strong>类别已锁定</strong><small>已有标注任务、标注内容或固定版本。新类别请在新数据集中定义，避免历史编号错位。</small></span></div>
                    ) : null}
                    <div className="dataset-class-editor-list">
                      {classRows.map((item, index) => (
                        <div className="dataset-class-editor-row" key={item.id}>
                          <span className={`class-color color-${index % 3}`} aria-hidden="true" />
                          <span className="class-id">{index}</span>
                          <input
                            value={item.name}
                            aria-label={`类别 ${index} 名称`}
                            placeholder={index === 0 ? "例如：安全帽" : "类别名称"}
                            disabled={busy || datasetDefinitionLocked}
                            onChange={(event) => updateClassRow(index, event.target.value)}
                          />
                          <button type="button" aria-label={`删除类别 ${index}`} disabled={busy || datasetDefinitionLocked} onClick={() => removeClassRow(index)}><Trash2 size={14} /></button>
                        </div>
                      ))}
                      {!classRows.length ? <div className="dataset-class-editor-empty"><Tag size={16} /><span>还没有类别。先添加业务中需要识别的对象。</span></div> : null}
                    </div>
                    <div className="dataset-class-editor-actions">
                      <button className="secondary-button" type="button" disabled={busy || datasetDefinitionLocked} onClick={addClassRow}><Plus size={13} />添加类别</button>
                      <button className="primary-button" type="button" disabled={busy || datasetDefinitionLocked || !classMapChanged || hasInvalidClassName} onClick={() => void saveClassMap()}><Check size={13} />保存类别</button>
                    </div>
                  </div>
                ) : (
                  <div className="dataset-classless-note"><Mountain size={17} /><span><strong>深度估计不使用类别</strong><small>该任务输出每个像素的深度值，数据版本只固定深度标注规范。</small></span></div>
                )}
                <div className="dataset-insight-summary">
                  <div><span>标注覆盖</span><strong>{visibleQualityReport ? `${visibleQualityReport.annotation_coverage_percent}%` : assets.length ? `${Math.round((annotatedCount / assets.length) * 100)}%` : "—"}</strong></div>
                  <div><span>类别</span><strong>{visibleQualityReport?.class_distribution.length ?? parsedClassNames.length}</strong></div>
                  <div><span>标注实例</span><strong>{visibleQualityReport ? visibleQualityReport.class_distribution.reduce((sum, item) => sum + item.annotation_count, 0).toLocaleString("zh-CN") : "—"}</strong></div>
                  <div><span>已知尺寸</span><strong>{visibleQualityReport?.image_dimensions.known_asset_count ?? assets.filter((asset) => asset.width && asset.height).length}</strong></div>
                </div>
                {visibleQualityReport?.class_distribution.length ? (
                  <div className="dataset-class-table">
                    <div className="dataset-class-row is-heading"><span>类别</span><span>涉及素材</span><span>标注实例</span><span>占比</span></div>
                    {visibleQualityReport.class_distribution.map((item) => {
                      const total = visibleQualityReport.class_distribution.reduce((sum, entry) => sum + entry.annotation_count, 0);
                      const percentage = total ? Math.round((item.annotation_count / total) * 100) : 0;
                      return (
                        <div className="dataset-class-row" key={item.class_id}>
                          <span><i aria-hidden="true" />{item.class_name}</span>
                          <strong>{item.asset_count.toLocaleString("zh-CN")}</strong>
                          <strong>{item.annotation_count.toLocaleString("zh-CN")}</strong>
                          <span>{percentage}%</span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="dataset-insights-empty"><ListChecks size={18} /><p>生成数据版本后，这里会显示真实的类别分布与标注数量。</p></div>
                )}
              </article>
            ) : null}

            {activeView === "models" ? (
              <article className="panel dataset-models-card">
                <div className="dataset-models-heading">
                  <div><span className="dataset-insights-icon"><Cpu size={17} /></span><span><h3>使用此数据集的模型</h3><p>模型详情保留训练参数、指标、测试和发布入口。</p></span></div>
                  <Link className="primary-button" href={trainingHref}><Plus size={13} />新建训练</Link>
                </div>
                {modelVersions.length ? (
                  <div className="dataset-model-list">
                    {modelVersions.map((model) => (
                      <Link className="dataset-model-row" href={`/studio/training/models/${model.id}?project=${project.id}`} key={model.id}>
                        <span className="dataset-model-mark"><Cpu size={15} /></span>
                        <span><strong>{model.model_name} · v{model.version_number}</strong><small>来自训练任务 {model.run_id.slice(0, 8)}</small></span>
                        <span>{model.status === "approved" ? "可发布" : model.status === "rejected" ? "未通过" : "已登记"}</span>
                        <ArrowUpRight size={14} aria-hidden="true" />
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="dataset-insights-empty"><Cpu size={18} /><p>尚无模型，生成一个固定数据版本后即可开始训练。</p><Link href={trainingHref}>前往训练</Link></div>
                )}
              </article>
            ) : null}

            {activeView === "versions" ? (
              <>
                {usesClasses ? (
                  <div className="dataset-readiness-grid version-readiness-grid">
                    <div className="class-map-saved-state"><span className="readiness-icon"><ListChecks size={15} /></span><span><strong>类别</strong><small>{dataset?.class_map && Object.keys(dataset.class_map).length ? `${Object.keys(dataset.class_map).length} 个类别已保存` : "尚未定义类别"}</small></span></div>
                    <div className={`freeze-readiness ${freezeBlockers.length ? "is-blocked" : "is-ready"}`}>
                      <span className="readiness-icon">{freezeBlockers.length ? <AlertCircle size={15} /> : <Check size={15} />}</span>
                      <span><strong>{freezeBlockers.length ? "还不能生成版本" : "可以生成训练版本"}</strong><small>{freezeBlockers.length ? freezeBlockers.join(" · ") : `${parsedClassNames.length} 个类别，素材均已就绪`}</small></span>
                    </div>
                  </div>
                ) : null}

                <aside className="panel versions-card versions-full-card">
                  <div className="versions-heading"><div><h3>数据版本</h3><p>生成后内容固定，可直接用于训练。</p></div><span>{versions.length}</span></div>
                  {versions.length ? (
                    <div className="version-list">
                      {versions.map((version) => (
                        <button className={`version-row${selectedVersion?.id === version.id ? " is-active" : ""}`} type="button" key={version.id} aria-pressed={selectedVersion?.id === version.id} onClick={() => setSelectedVersionId(version.id)}>
                          <span className="version-lock"><LockKeyhole size={12} /></span>
                          <span><strong>ds_v{version.version_number}</strong><small>{version.asset_count} 个素材</small></span>
                          <Check size={13} aria-label="已生成" />
                        </button>
                      ))}
                    </div>
                  ) : <div className="versions-empty"><LockKeyhole size={17} /><p>素材标注、检查并完成划分后，再生成第一个版本。</p></div>}
                </aside>

                {selectedVersion ? (
                  <DatasetQualityCard version={selectedVersion} report={visibleQualityReport} loading={qualityLoading} />
                ) : null}
              </>
            ) : null}
          </>
        )}
      </div>

      {videoDialogOpen ? (
        <div className="workbench-dialog-backdrop" role="presentation">
          <form className="workbench-dialog video-import-dialog" role="dialog" aria-modal="true" aria-labelledby="video-dialog-title" onSubmit={createExtractionJob}>
            <div className="dialog-heading"><div><span className="dialog-icon"><Film size={18} /></span><span><h2 id="video-dialog-title">从视频生成素材</h2><p>抽取的画面会进入当前数据集。{pendingVideos.length > 1 ? `还剩 ${pendingVideos.length - 1} 个视频待配置。` : ""}</p></span></div><button type="button" onClick={() => { setVideoDialogOpen(false); setPendingVideos([]); setPendingVideo(null); }} aria-label="关闭">×</button></div>
            <div className="selected-video-file"><Film size={17} /><span><strong>{pendingVideo?.name ?? "尚未选择视频"}</strong><small>{pendingVideo ? formatBytes(pendingVideo.size) : "请返回素材页选择 MP4、MOV 或 WebM"}</small></span></div>
            <section className="video-purpose-panel"><div><strong>抽取图片用于训练</strong><small>按固定间隔生成独立图片，适合检测、分类和分割。</small></div><span>当前阶段</span></section>
            <div className="frame-interval-field"><span><strong>抽帧间隔</strong><small>间隔越小，生成的连续画面越多。</small></span><span className="number-input-wrap"><input aria-label="抽帧间隔" type="number" min="0.1" step="0.1" value={frameInterval} onChange={(event) => setFrameInterval(Number(event.target.value) || 1)} /><b>秒 / 帧</b></span></div>
            <div className="extraction-options"><label><input type="checkbox" checked={deduplicateFrames} onChange={(event) => setDeduplicateFrames(event.target.checked)} />去除重复帧</label></div>
            <div className="dialog-callout"><span>处理方式</span><strong>后台生成图片</strong><small>完成后自动写入当前数据集，可直接创建标注任务。</small></div>
            <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => { setVideoDialogOpen(false); setPendingVideos([]); setPendingVideo(null); }}>取消</button><button className="primary-button" type="submit" disabled={!pendingVideo || busy}>{busy ? "正在上传" : pendingVideos.length > 1 ? "保存并配置下一个" : "创建抽帧任务"}</button></div>
          </form>
        </div>
      ) : null}

      {taskTypeDialogOpen && dataset ? (
        <div className="workbench-dialog-backdrop" role="presentation">
          <div className="workbench-dialog dataset-task-type-dialog" role="dialog" aria-modal="true" aria-labelledby="dataset-task-type-title">
            <div className="dialog-heading"><div><span className="dialog-icon"><Settings2 size={18} /></span><span><h2 id="dataset-task-type-title">数据集任务类型</h2><p>任务类型决定标注结构、质量检查和可用训练引擎。</p></span></div><button type="button" onClick={() => setTaskTypeDialogOpen(false)} aria-label="关闭">×</button></div>
            {datasetDefinitionLocked ? (
              <div className="dataset-task-type-warning"><AlertCircle size={16} /><span><strong>当前任务类型已锁定</strong><small>已有标注任务、标注内容或固定版本。为保护历史数据，请新建数据集后选择其他类型。</small></span></div>
            ) : (
              <div className="dataset-task-type-warning is-neutral"><AlertCircle size={16} /><span><strong>修改前请确认标注格式</strong><small>不同任务类型的标注互不兼容；保存后会以数据集定义为准。</small></span></div>
            )}
            <TaskTypePicker value={pendingTaskType} onChange={setPendingTaskType} disabled={datasetDefinitionLocked || busy} />
            <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setTaskTypeDialogOpen(false)}>取消</button><button className="primary-button" type="button" disabled={busy || datasetDefinitionLocked || pendingTaskType === dataset.task_type} onClick={() => void saveDatasetTaskType()}>保存任务类型</button></div>
          </div>
        </div>
      ) : null}

      {taskDialogOpen ? (
        <div className="workbench-dialog-backdrop" role="presentation">
          <form className="workbench-dialog annotation-task-dialog" role="dialog" aria-modal="true" aria-labelledby="task-dialog-title" onSubmit={createAnnotationTask}>
            <div className="dialog-heading"><div><span className="dialog-icon"><FileCheck2 size={18} /></span><span><h2 id="task-dialog-title">新建标注任务</h2><p>创建后，素材会固定在任务中。</p></span></div><button type="button" onClick={() => setTaskDialogOpen(false)} aria-label="关闭">×</button></div>
            <div className="annotation-task-definition">
              <span className="dataset-task-type-icon"><TaskTypeIcon taskType={activeTaskType} /></span>
              <span><strong>{taskTypeLabels[activeTaskType] ?? activeTaskType}</strong><small>{parsedClassNames.length ? `${parsedClassNames.length} 个类别：${parsedClassNames.slice(0, 3).join("、")}${parsedClassNames.length > 3 ? "…" : ""}` : "尚未定义类别"}</small></span>
              <button type="button" onClick={() => { setTaskDialogOpen(false); setActiveView("classes"); }}>管理类别</button>
            </div>
            <div className="dialog-fields">
              <label><span>任务名称</span><input value={taskName} onChange={(event) => setTaskName(event.target.value)} required /></label>
              <label><span>素材范围</span><select value={taskAssetScope} onChange={(event) => setTaskAssetScope(event.target.value as "unlabeled" | "all")}><option value="unlabeled">全部未标注素材</option><option value="all">全部素材</option></select></label>
            </div>
            <fieldset className="annotation-method-picker"><legend>标注方式</legend><button type="button" className="is-active" onClick={() => setTaskMethod("manual")}><FileCheck2 size={17} /><span><strong>手动标注</strong><small>逐张绘制并确认标注</small></span></button><button type="button" className="is-disabled" disabled><Sparkles size={17} /><span><strong>智能预标注</strong><small>尚未接入真实模型</small></span></button></fieldset>
            <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setTaskDialogOpen(false)}>取消</button><button className="primary-button" type="submit" disabled={!parsedClassNames.length || classMapChanged}>创建任务</button></div>
          </form>
        </div>
      ) : null}
    </section>
  );
}

function DatasetQualityCard({
  version,
  report,
  loading,
}: {
  version: DatasetVersion;
  report: DatasetVersionQualityReport | null;
  loading: boolean;
}) {
  return (
    <article className="panel dataset-quality-card">
      <div className="dataset-quality-heading">
        <div><h3>ds_v{version.version_number} 数据质量</h3><p>这份检查结果会随版本固定。</p></div>
        <span className="quality-version-state">{version.asset_count} 个素材</span>
      </div>
      {loading || !report ? (
        <div className="quality-loading" aria-live="polite"><LoaderCircle size={16} className="spinner" />正在读取质量检查</div>
      ) : (
        <div className="dataset-quality-body">
          <div className="quality-summary-grid">
            <div><span>标注覆盖</span><strong>{report.annotation_coverage_percent}%</strong><small>{report.annotated_asset_count} / {report.asset_count} 个素材</small></div>
            <div><span>类别</span><strong>{report.class_distribution.length}</strong><small>已定义训练类别</small></div>
            <div><span>已知尺寸</span><strong>{report.image_dimensions.known_asset_count}</strong><small>{report.image_dimensions.unknown_asset_count ? `${report.image_dimensions.unknown_asset_count} 个待补齐` : "全部已登记"}</small></div>
          </div>
          <div className="quality-detail-grid">
            <section className="quality-detail-section">
              <div className="quality-section-heading"><FileCheck2 size={14} /><strong>数据划分</strong></div>
              <div className="quality-split-list">
                {(["train", "valid", "test"] as const).map((split) => {
                  const count = report.split_counts[split] ?? 0;
                  const percentage = report.asset_count ? Math.round((count / report.asset_count) * 100) : 0;
                  return <div key={split}><span>{splitLabels[split]}</span><strong>{count}</strong><small>{percentage}%</small><i aria-hidden="true"><b style={{ width: `${percentage}%` }} /></i></div>;
                })}
              </div>
            </section>
            <section className="quality-detail-section">
              <div className="quality-section-heading"><ListChecks size={14} /><strong>类别分布</strong></div>
              {report.class_distribution.length ? (
                <div className="quality-class-list">{report.class_distribution.map((item) => <div key={item.class_id}><span>{item.class_name}</span><small>{item.asset_count} 个素材</small><strong>{item.annotation_count} 个标注</strong></div>)}</div>
              ) : <p className="quality-empty">当前版本尚无类别分布。</p>}
            </section>
            <section className="quality-detail-section">
              <div className="quality-section-heading"><FileImage size={14} /><strong>图像尺寸</strong></div>
              <div className="quality-dimension-copy"><strong>{report.image_dimensions.min_width && report.image_dimensions.min_height ? `${report.image_dimensions.min_width} × ${report.image_dimensions.min_height} 至 ${report.image_dimensions.max_width} × ${report.image_dimensions.max_height}` : "暂无尺寸范围"}</strong><small>按已登记的原始图片尺寸计算。</small></div>
            </section>
          </div>
          {report.advisories.length ? <div className="quality-advisories"><AlertCircle size={15} aria-hidden="true" /><div>{report.advisories.map((advisory) => <p key={advisory}>{advisory}</p>)}</div></div> : null}
        </div>
      )}
    </article>
  );
}

function DatasetSetupForm({
  name,
  onNameChange,
  description,
  onDescriptionChange,
  taskType,
  onTaskTypeChange,
  sourceMode,
  onSourceModeChange,
  sourceFiles,
  onFilesSelected,
  onFilesDropped,
  sourceUrl,
  onSourceUrlChange,
  onSubmit,
  onCancel,
  canCancel,
  busy,
}: {
  name: string;
  onNameChange: (value: string) => void;
  description: string;
  onDescriptionChange: (value: string) => void;
  taskType: string;
  onTaskTypeChange: (value: string) => void;
  sourceMode: DatasetSourceMode;
  onSourceModeChange: (value: DatasetSourceMode) => void;
  sourceFiles: File[];
  onFilesSelected: (event: ChangeEvent<HTMLInputElement>) => void;
  onFilesDropped: (files: File[]) => void;
  sourceUrl: string;
  onSourceUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent) => Promise<void>;
  onCancel: () => void;
  canCancel: boolean;
  busy: boolean;
}) {
  const sourceOptions: Array<{ id: DatasetSourceMode; label: string; icon: typeof UploadCloud }> = [
    { id: "upload", label: "上传", icon: UploadCloud },
    { id: "url", label: "URL", icon: Link2 },
    { id: "cloud", label: "云端存储", icon: Cloud },
    { id: "on-premise", label: "本地服务器", icon: HardDrive },
  ];
  const unavailableCopy: Record<Exclude<DatasetSourceMode, "upload">, { title: string; description: string }> = {
    url: { title: "URL 导入待接入", description: "后端连接器上线后，可以从公开地址导入图像、视频和标注包。" },
    cloud: { title: "云端存储连接待接入", description: "首期先使用本地上传；对象存储连接器会沿用同一套导入校验。" },
    "on-premise": { title: "本地服务器连接待接入", description: "算力与存储服务器上线后，可在这里绑定内部数据源。" },
  };

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    if (sourceMode !== "upload" || busy) return;
    onFilesDropped(Array.from(event.dataTransfer.files));
  }

  return (
    <article className="panel setup-card dataset-create-surface">
      <div className="dataset-create-header">
        <span className="setup-icon"><Database size={19} /></span>
        <div>
          <span className="eyebrow">数据与标注</span>
          <h2>新建数据集</h2>
          <p>创建用于训练的图像、视频和标注数据集。</p>
        </div>
        {canCancel ? <button className="dataset-create-close" type="button" onClick={onCancel} aria-label="关闭新建数据集"><X size={16} /></button> : null}
      </div>

      <form onSubmit={(event) => void onSubmit(event)}>
        <fieldset className="dataset-source-section">
          <legend>数据源</legend>
          <div className="dataset-source-tabs" role="tablist" aria-label="数据源类型">
            {sourceOptions.map(({ id, label, icon: Icon }) => (
              <button
                type="button"
                key={id}
                className={`dataset-source-tab${sourceMode === id ? " is-active" : ""}`}
                role="tab"
                aria-selected={sourceMode === id}
                onClick={() => onSourceModeChange(id)}
                disabled={busy}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          {sourceMode === "upload" ? (
            <>
              <label
                className={`dataset-source-dropzone${sourceFiles.length ? " has-files" : ""}`}
                htmlFor="dataset-source-file-input"
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
              >
                <input
                  id="dataset-source-file-input"
                  type="file"
                  accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                  multiple
                  onChange={onFilesSelected}
                  disabled={busy}
                />
                <span className="dataset-source-dropzone-icon"><UploadCloud size={21} /></span>
                <strong>{sourceFiles.length ? "继续添加素材" : "拖放图像或视频到这里"}</strong>
                <small>或点击选择文件，支持 JPG、PNG、WebP、MP4、MOV 和 WebM；图片自动导入，视频会逐个配置抽帧</small>
              </label>
              {sourceFiles.length ? (
                <div className="dataset-source-file-list" aria-live="polite">
                  <div className="dataset-source-file-summary"><strong>已选择 {sourceFiles.length} 个文件</strong><span>创建后自动导入</span></div>
                  {sourceFiles.slice(0, 4).map((file, index) => (
                    <div className="dataset-source-file" key={`${file.name}-${file.lastModified}-${index}`}>
                      {file.type.startsWith("video/") ? <Film size={14} /> : <FileImage size={14} />}
                      <span>{file.name}</span>
                      <small>{formatBytes(file.size)}</small>
                    </div>
                  ))}
                  {sourceFiles.length > 4 ? <small className="dataset-source-more">还有 {sourceFiles.length - 4} 个文件将在创建后导入</small> : null}
                </div>
              ) : <p className="dataset-source-hint">也可以先创建空数据集，稍后在素材页继续导入。</p>}
            </>
          ) : (
            <div className="dataset-source-unavailable">
              <span className="dataset-source-unavailable-icon">{sourceMode === "url" ? <Globe2 size={18} /> : sourceMode === "cloud" ? <Cloud size={18} /> : <HardDrive size={18} />}</span>
              <div><strong>{unavailableCopy[sourceMode].title}</strong><p>{unavailableCopy[sourceMode].description}</p></div>
              {sourceMode === "url" ? <input value={sourceUrl} onChange={(event) => onSourceUrlChange(event.target.value)} placeholder="https://example.com/dataset.zip" disabled={busy} aria-label="数据集 URL" /> : null}
            </div>
          )}
        </fieldset>

        <div className="dataset-create-fields">
          <label className="dataset-create-field">
            <span>数据集名称</span>
            <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder="例如：道路病害巡检" required />
            <small>名称用于工作区内识别数据集。</small>
          </label>
          <div className="dataset-create-field">
            <span>标识预览</span>
            <div className="dataset-create-slug"><Link2 size={13} /><code>{slugify(name) || "dataset"}</code></div>
            <small>由名称生成，当前仅作为可读预览。</small>
          </div>
        </div>
        <label className="dataset-create-field">
          <span>描述 <em>可选</em></span>
          <textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder="补充数据来源、采集范围或使用限制" rows={3} maxLength={500} />
        </label>

        <fieldset className="dataset-setup-task-types">
          <legend>任务类型与标注结构</legend>
          <p className="dataset-create-section-hint">创建后仍可调整；一旦开始标注或生成版本，任务类型将被锁定。</p>
          <TaskTypePicker value={taskType} onChange={onTaskTypeChange} disabled={busy} />
        </fieldset>

        <div className="dataset-create-footer">
          {canCancel ? <button className="secondary-button" type="button" onClick={onCancel}>取消</button> : <span />}
          <button className="primary-button" type="submit" disabled={busy || sourceMode !== "upload"}>
            {busy ? <LoaderCircle size={14} className="spinner" /> : <Plus size={14} />}
            {busy ? "正在创建" : "创建数据集"}
          </button>
        </div>
        {sourceMode !== "upload" ? <p className="dataset-create-footer-note">切换回“上传”后即可创建；其他数据源会在连接器上线后开放。</p> : null}
      </form>
    </article>
  );
}

function ProjectSetupForm({
  name,
  onNameChange,
  slug,
  onSlugChange,
  description,
  onDescriptionChange,
  taskType,
  onTaskTypeChange,
  modelFile,
  onModelFileChange,
  onSubmit,
  busy,
}: {
  name: string;
  onNameChange: (value: string) => void;
  slug: string;
  onSlugChange: (value: string) => void;
  description: string;
  onDescriptionChange: (value: string) => void;
  taskType: string;
  onTaskTypeChange: (value: string) => void;
  modelFile: File | null;
  onModelFileChange: (file: File | null) => void;
  onSubmit: (event: FormEvent) => Promise<void>;
  busy: boolean;
}) {
  return (
    <article className="panel setup-card project-create-surface">
      <div className="project-create-header">
        <div>
          <span className="eyebrow">工作台项目</span>
          <h2>创建视觉项目</h2>
          <p>项目用于组织数据集、训练实验和已发布的视觉能力。</p>
        </div>
      </div>

      <form onSubmit={(event) => void onSubmit(event)}>
        <label
          className="project-model-dropzone"
          htmlFor="project-model-input"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            onModelFileChange(event.dataTransfer.files?.[0] ?? null);
          }}
        >
          <input
            id="project-model-input"
            type="file"
            accept=".pt,.onnx,application/octet-stream"
            onChange={(event) => onModelFileChange(event.target.files?.[0] ?? null)}
            disabled={busy}
          />
          <span className="project-model-dropzone-icon"><UploadCloud size={22} /></span>
          <strong>{modelFile ? modelFile.name : "拖放模型文件到这里"}</strong>
          <small>{modelFile ? "模型文件已选择；模型上传接口接入后可继续导入" : "可选，支持 .pt 和 .onnx；也可以先创建空项目"}</small>
        </label>

        <div className="project-create-fields">
          <label className="dataset-create-field">
            <span>项目名称</span>
            <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder="例如：道路病害识别" required />
          </label>
          <label className="dataset-create-field">
            <span>项目 URL</span>
            <div className="project-slug-input"><span>/</span><input value={slug} onChange={(event) => onSlugChange(event.target.value)} placeholder="road-defects" required /></div>
            <small>仅支持小写字母、数字和连字符。</small>
          </label>
        </div>

        <label className="dataset-create-field">
          <span>项目描述 <em>可选</em></span>
          <textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder="说明项目目标、数据范围或协作边界" rows={3} maxLength={2_000} />
        </label>

        <fieldset className="project-task-types">
          <legend>默认任务类型</legend>
          <p className="dataset-create-section-hint">创建数据集时仍可选择更具体的标注结构。</p>
          <div className="project-task-type-grid">
            {projectTaskTypes.map((item) => (
              <button
                type="button"
                key={item.id}
                className={taskType === item.id ? "is-active" : ""}
                aria-pressed={taskType === item.id}
                onClick={() => onTaskTypeChange(item.id)}
                disabled={busy}
              >
                <TaskTypeIcon taskType={item.id} size={15} />
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <div className="project-create-footer">
          <span>项目创建后可继续添加数据集和协作者。</span>
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? <LoaderCircle size={14} className="spinner" /> : <Plus size={14} />}
            {busy ? "正在创建" : "创建项目"}
          </button>
        </div>
      </form>
    </article>
  );
}

function SetupForm({
  eyebrow,
  title,
  description,
  label,
  value,
  onChange,
  onSubmit,
  busy,
}: {
  eyebrow: string;
  title: string;
  description: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => Promise<void>;
  busy: boolean;
}) {
  return (
    <article className="panel setup-card">
      <span className="setup-icon"><Database size={19} /></span>
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <form onSubmit={(event) => void onSubmit(event)}>
        <label>
          <span>{label}</span>
          <input value={value} onChange={(event) => onChange(event.target.value)} required />
        </label>
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? <LoaderCircle size={14} className="spinner" /> : <Plus size={14} />}
          创建并继续
        </button>
      </form>
    </article>
  );
}
