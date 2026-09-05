"use client";

import {
  Activity,
  ArrowRight,
  CircleGauge,
  Cpu,
  Database,
  FolderKanban,
  Image as ImageIcon,
  Plus,
  Rocket,
} from "lucide-react";
import Link from "next/link";
import { MorphIcon } from "./components/morph-icon";
import { Pause as PauseData, Play as PlayData } from "lucide";
import { useState } from "react";
import type { OverviewResponse } from "../lib/api";
import { catalogApi } from "../lib/catalog-api";

const taskTypeLabels: Record<string, string> = {
  "object-detection": "目标检测",
  classification: "图像分类",
  segmentation: "图像分割",
  pose: "姿态估计",
  ocr: "文字识别",
};

export function WorkbenchOverview({
  initialOverview,
}: {
  initialOverview: OverviewResponse;
}) {
  const [projects, setProjects] = useState(initialOverview.projects);
  const [changingProjectId, setChangingProjectId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function changeProjectStatus(projectId: string, nextStatus: "active" | "paused") {
    if (!initialOverview.workspace_id || changingProjectId) return;
    setChangingProjectId(projectId);
    setNotice(null);
    try {
      if (nextStatus === "paused") {
        await catalogApi.pauseProject(initialOverview.workspace_id, projectId);
      } else {
        await catalogApi.resumeProject(initialOverview.workspace_id, projectId);
      }
      setProjects((current) => current.map((project) => (
        project.id === projectId ? { ...project, status: nextStatus } : project
      )));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "项目状态更新失败");
    } finally {
      setChangingProjectId(null);
    }
  }

  const metrics = [
    { label: "数据集", value: initialOverview.metrics.datasets, icon: Database },
    { label: "素材", value: initialOverview.metrics.assets, icon: ImageIcon },
    { label: "训练项目", value: projects.length, icon: FolderKanban },
    { label: "可用模型", value: initialOverview.metrics.model_versions_ready, icon: Cpu },
    { label: "训练中", value: initialOverview.metrics.training_jobs_running, icon: CircleGauge },
    { label: "在线服务", value: projects.reduce((sum, project) => sum + project.published_service_count, 0), icon: Rocket },
  ];

  const recentActivity = [
    ...initialOverview.datasets.map((dataset) => ({
      id: `dataset-${dataset.id}`,
      name: dataset.name,
      type: "数据集",
      detail: `${dataset.asset_count} 个素材 · ${dataset.version_count} 个版本`,
      status: dataset.version_count ? "已就绪" : "草稿",
      updatedAt: dataset.created_at,
      href: `/studio/data?project=${dataset.project_id}&dataset=${dataset.id}`,
    })),
    ...initialOverview.recent_runs.map((run) => {
      const relatedProject = projects.find((project) => project.name === run.project_name);
      return {
        id: `run-${run.run_id}`,
        name: run.model,
        type: "训练任务",
        detail: `${run.project_name} · 数据版本 ${run.dataset_version_number}`,
        status: run.status === "succeeded" ? "已完成" : run.status === "running" ? `${run.progress}%` : run.status,
        updatedAt: run.created_at,
        href: `/studio/training/runs/${run.run_id}${relatedProject ? `?project=${relatedProject.id}` : ""}`,
      };
    }),
  ]
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
    .slice(0, 8);

  const formatDate = (value: string) => new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
  }).format(new Date(value));

  return (
    <>
      <header className="workbench-home-header">
        <div>
          <h1>工作台</h1>
          <p>继续最近的数据和训练工作。</p>
        </div>
        <div className="workbench-home-actions">
          <Link className="secondary-button" href="/studio/data"><Database size={14} />新建数据集</Link>
          <Link className="primary-button" href="/studio/data?createProject=1"><Plus size={14} />新建项目</Link>
        </div>
      </header>

      {initialOverview.availability === "not_configured" ? (
        <p className="inline-notice is-error" role="status">
          {initialOverview.availability_message ?? "Core API 尚未配置，当前页面仅显示空状态。"}
        </p>
      ) : null}

      <section className="workbench-metrics" aria-label="概览">
        {metrics.map(({ label, value, icon: Icon }) => (
          <article className="workbench-metric" key={label}>
            <Icon size={17} strokeWidth={1.7} aria-hidden="true" />
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      {notice ? <p className="inline-notice is-error" role="alert">{notice}</p> : null}

      <section className="workbench-section">
        <div className="workbench-section-heading">
          <div><h2>数据集</h2></div>
          <Link href="/studio/data">查看全部</Link>
        </div>
        {initialOverview.datasets.length ? (
          <div className="workbench-resource-grid">
            {initialOverview.datasets.slice(0, 6).map((dataset) => (
              <Link className="workbench-resource-card" href={`/studio/data?project=${dataset.project_id}&dataset=${dataset.id}`} key={dataset.id}>
                <span className="workbench-resource-card-icon"><Database size={18} /></span>
                <div><strong>{dataset.name}</strong><small>{dataset.project_name}</small></div>
                <p><span>{dataset.asset_count} 个素材</span><span>{dataset.version_count} 个版本</span></p>
              </Link>
            ))}
          </div>
        ) : (
          <div className="workbench-empty">
            <Database size={20} /><span>还没有数据集</span>
          </div>
        )}
      </section>

      <section className="workbench-section">
        <div className="workbench-section-heading">
          <div><h2>训练项目</h2></div>
          <span>{projects.length} 个</span>
        </div>
        {projects.length ? (
          <div className="workbench-list">
            {projects.map((project) => {
              const paused = project.status === "paused";
              return (
                <article className="workbench-row" key={project.id}>
                  <span className="workbench-row-icon"><FolderKanban size={18} /></span>
                  <div className="workbench-row-copy">
                    <div className="workbench-row-title"><strong>{project.name}</strong><span className={`plain-status${paused ? " is-paused" : ""}`}>{paused ? "已暂停" : "进行中"}</span></div>
                    <small>{taskTypeLabels[project.task_type] ?? project.task_type} · {project.dataset_version_count} 个数据版本 · {project.active_run_count} 个运行中任务 · {project.published_service_count} 个在线服务</small>
                  </div>
                  <div className="workbench-row-actions">
                    <button className="text-button compact" type="button" disabled={changingProjectId === project.id || !initialOverview.workspace_id} onClick={() => void changeProjectStatus(project.id, paused ? "active" : "paused")}>
                      <MorphIcon icon={paused ? PlayData : PauseData} size={13} aria-hidden="true" />{paused ? "继续" : "暂停"}
                    </button>
                    <Link className="secondary-button compact" href={`/studio?project=${project.id}`}>打开 <ArrowRight size={14} /></Link>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="workbench-empty"><FolderKanban size={20} /><span>还没有训练项目</span></div>
        )}
      </section>

      <section className="workbench-section">
        <div className="workbench-section-heading"><div><h2>最近活动</h2></div><Activity size={17} aria-hidden="true" /></div>
        {recentActivity.length ? (
          <div className="workbench-activity-table">
            <div className="workbench-activity-row is-heading"><span>名称</span><span>类型</span><span>内容</span><span>状态</span><span>更新</span></div>
            {recentActivity.map((item) => (
              <Link className="workbench-activity-row" href={item.href} key={item.id}>
                <strong>{item.name}</strong><span>{item.type}</span><span>{item.detail}</span><span className="plain-status">{item.status}</span><time dateTime={item.updatedAt}>{formatDate(item.updatedAt)}</time>
              </Link>
            ))}
          </div>
        ) : <div className="workbench-empty"><Activity size={20} /><span>还没有活动记录</span></div>}
      </section>
    </>
  );
}
