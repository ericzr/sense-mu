export type AnnotationTaskStatus = "annotating" | "review" | "done";

export type AnnotationTask = {
  id: string;
  name: string;
  source: string;
  method: "manual" | "smart";
  assetCount: number;
  completedCount: number;
  status: AnnotationTaskStatus;
  assignee: string;
};

export const annotationTasks: AnnotationTask[] = [
  {
    id: "ppe-video-gate-a",
    name: "工地入口第一批",
    source: "视频抽帧 · gate-a.mp4",
    method: "smart",
    assetCount: 320,
    completedCount: 218,
    status: "review",
    assignee: "我",
  },
  {
    id: "ppe-night-shift",
    name: "夜间作业样本",
    source: "图片批次 · 2026-08-10",
    method: "manual",
    assetCount: 128,
    completedCount: 46,
    status: "annotating",
    assignee: "我",
  },
  {
    id: "ppe-review-finished",
    name: "安全帽补充样本",
    source: "图片批次 · 2026-08-06",
    method: "smart",
    assetCount: 96,
    completedCount: 96,
    status: "done",
    assignee: "已完成",
  },
];

export const annotationStatusLabels: Record<AnnotationTaskStatus, string> = {
  annotating: "标注中",
  review: "待检查",
  done: "已完成",
};
