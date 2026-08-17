"use client";

import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  LoaderCircle,
  MousePointer2,
  Pentagon,
  Redo2,
  Save,
  Send,
  Sparkles,
  Square,
  Trash2,
  Undo2,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { catalogApi, type AnnotationTask, type Asset } from "../../../../lib/catalog-api";
import { DynamicAssetImage } from "../../../components/dynamic-asset-image";

type Tool = "select" | "box" | "polygon" | "smart";
type Label = string;
type AnnotationBox = {
  id: string;
  classId: number;
  label: Label;
  x: number;
  y: number;
  width: number;
  height: number;
};

const fallbackClasses = ["人员", "安全帽", "反光衣"];

function parseYolo(text: string, classNames: string[]): AnnotationBox[] {
  return text.split(/\r?\n/).flatMap((line, index) => {
    const fields = line.trim().split(/\s+/);
    if (fields.length !== 5) return [];
    const [classId, x, y, width, height] = fields.map(Number);
    if (![classId, x, y, width, height].every(Number.isFinite)) return [];
    return [{
      id: `annotation-${index}`,
      classId,
      label: classNames[classId] ?? `类别 ${classId}`,
      x: (x - width / 2) * 100,
      y: (y - height / 2) * 100,
      width: width * 100,
      height: height * 100,
    }];
  });
}

function serializeYolo(boxes: AnnotationBox[]): string {
  return boxes.map((box) => {
    const x = (box.x + box.width / 2) / 100;
    const y = (box.y + box.height / 2) / 100;
    return `${box.classId} ${x.toFixed(6)} ${y.toFixed(6)} ${(box.width / 100).toFixed(6)} ${(box.height / 100).toFixed(6)}`;
  }).join("\n") + (boxes.length ? "\n" : "");
}

async function checksumText(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function checksumFile(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function AnnotationEditor() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");
  const datasetId = searchParams.get("dataset");
  const taskId = searchParams.get("task");
  const returnParams = new URLSearchParams({ view: "annotation" });
  if (projectId) returnParams.set("project", projectId);
  if (datasetId) returnParams.set("dataset", datasetId);

  const [workspace, setWorkspace] = useState<{ id: string } | null>(null);
  const [task, setTask] = useState<AnnotationTask | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [boxes, setBoxes] = useState<AnnotationBox[]>([]);
  const [classNames, setClassNames] = useState(fallbackClasses);
  const [activeTool, setActiveTool] = useState<Tool>("select");
  const [selectedClass, setSelectedClass] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState("正在读取任务");
  const [busy, setBusy] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [history, setHistory] = useState<AnnotationBox[][]>([]);
  const [future, setFuture] = useState<AnnotationBox[][]>([]);
  const [draftBox, setDraftBox] = useState<AnnotationBox | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const boxesRef = useRef<AnnotationBox[]>([]);
  const historyRef = useRef<AnnotationBox[][]>([]);
  const futureRef = useRef<AnnotationBox[][]>([]);
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number } | null>(null);

  const asset = assets[currentIndex] ?? null;
  const assetId = asset?.id ?? null;
  const workspaceId = workspace?.id ?? null;
  const currentLabelCounts = useMemo(() => classNames.map((label) => boxes.filter((box) => box.label === label).length), [boxes, classNames]);

  useEffect(() => {
    if (!taskId || !datasetId) return;
    void catalogApi.listWorkspaces()
      .then(async (workspaces) => {
        const nextWorkspace = workspaces[0];
        if (!nextWorkspace) return;
        setWorkspace(nextWorkspace);
        const [nextTask, nextAssets] = await Promise.all([
          catalogApi.getAnnotationTask(nextWorkspace.id, datasetId, taskId),
          catalogApi.listAnnotationTaskAssets(nextWorkspace.id, datasetId, taskId),
        ]);
        setTask(nextTask);
        const taskClasses = Object.entries(nextTask.class_map)
          .sort(([left], [right]) => Number(left) - Number(right))
          .map(([, name]) => name);
        if (taskClasses.length) setClassNames(taskClasses);
        setAssets(nextAssets);
        setNotice("已读取任务");
      })
      .catch((reason) => setNotice(reason instanceof Error ? reason.message : "任务读取失败"));
  }, [datasetId, taskId]);

  useEffect(() => {
    if (!workspaceId || !datasetId || !assetId) {
      setImageUrl(null);
      return;
    }
    const controller = new AbortController();
    let objectUrl: string | null = null;
    void catalogApi.getAssetContent(workspaceId, datasetId, assetId, controller.signal)
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setImageUrl(objectUrl); })
      .catch(() => setNotice("素材预览读取失败"));
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [assetId, datasetId, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !datasetId || !assetId) return;
    const controller = new AbortController();
    void catalogApi.getAnnotationContent(workspaceId, datasetId, assetId, controller.signal)
      .then((text) => {
        const nextBoxes = parseYolo(text, classNames);
        boxesRef.current = nextBoxes;
        setBoxes(nextBoxes);
        historyRef.current = [];
        futureRef.current = [];
        setHistory([]);
        setFuture([]);
        setDraftBox(null);
        setSelectedId(null);
      })
      .catch(() => {
        boxesRef.current = [];
        setBoxes([]);
        historyRef.current = [];
        futureRef.current = [];
        setHistory([]);
        setFuture([]);
        setDraftBox(null);
        setSelectedId(null);
      });
    return () => controller.abort();
  }, [assetId, classNames, datasetId, workspaceId]);

  function getImageFrame() {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image?.naturalWidth || !image.naturalHeight) return null;
    const bounds = canvas.getBoundingClientRect();
    const imageRatio = image.naturalWidth / image.naturalHeight;
    const canvasRatio = bounds.width / bounds.height;
    const width = imageRatio >= canvasRatio ? bounds.width : bounds.height * imageRatio;
    const height = imageRatio >= canvasRatio ? bounds.width / imageRatio : bounds.height;
    return {
      left: bounds.left + (bounds.width - width) / 2,
      top: bounds.top + (bounds.height - height) / 2,
      width,
      height,
    };
  }

  function getImagePoint(clientX: number, clientY: number) {
    const frame = getImageFrame();
    if (!frame || frame.width <= 0 || frame.height <= 0) return null;
    return {
      x: Math.max(0, Math.min(100, ((clientX - frame.left) / frame.width) * 100)),
      y: Math.max(0, Math.min(100, ((clientY - frame.top) / frame.height) * 100)),
    };
  }

  function applyBoxes(nextBoxes: AnnotationBox[], message: string) {
    historyRef.current = [...historyRef.current, boxesRef.current];
    futureRef.current = [];
    setHistory(historyRef.current);
    setFuture(futureRef.current);
    boxesRef.current = nextBoxes;
    setBoxes(nextBoxes);
    setNotice(message);
  }

  function undo() {
    const previous = historyRef.current[historyRef.current.length - 1];
    if (!previous) return;
    futureRef.current = [boxesRef.current, ...futureRef.current];
    historyRef.current = historyRef.current.slice(0, -1);
    setFuture(futureRef.current);
    setHistory(historyRef.current);
    boxesRef.current = previous;
    setBoxes(previous);
    setSelectedId(null);
    setNotice("已撤销上一步操作");
  }

  function redo() {
    const next = futureRef.current[0];
    if (!next) return;
    historyRef.current = [...historyRef.current, boxesRef.current];
    futureRef.current = futureRef.current.slice(1);
    setHistory(historyRef.current);
    setFuture(futureRef.current);
    boxesRef.current = next;
    setBoxes(next);
    setSelectedId(null);
    setNotice("已重做上一步操作");
  }

  function beginBox(event: React.PointerEvent<HTMLDivElement>) {
    if (activeTool !== "box" || dragRef.current) return;
    const point = getImagePoint(event.clientX, event.clientY);
    if (!point) {
      setNotice("图片尚未加载完成");
      return;
    }
    dragRef.current = { pointerId: event.pointerId, startX: point.x, startY: point.y };
    setDraftBox({
      id: "draft",
      classId: selectedClass,
      label: classNames[selectedClass] ?? `类别 ${selectedClass}`,
      x: point.x,
      y: point.y,
      width: 0,
      height: 0,
    });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function updateBox(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const point = getImagePoint(event.clientX, event.clientY);
    if (!point) return;
    setDraftBox((current) => current ? {
      ...current,
      x: Math.min(drag.startX, point.x),
      y: Math.min(drag.startY, point.y),
      width: Math.abs(point.x - drag.startX),
      height: Math.abs(point.y - drag.startY),
    } : null);
  }

  function completeBox(clientX: number, clientY: number, cancelled = false) {
    const drag = dragRef.current;
    if (!drag) return;
    const point = getImagePoint(clientX, clientY);
    const draft = point ? {
      x: Math.min(drag.startX, point.x),
      y: Math.min(drag.startY, point.y),
      width: Math.abs(point.x - drag.startX),
      height: Math.abs(point.y - drag.startY),
    } : null;
    dragRef.current = null;
    setDraftBox(null);
    if (cancelled || !draft || draft.width < 1 || draft.height < 1) {
      if (!cancelled) setNotice("框选范围太小，请重新拖拽");
      return;
    }
    const id = `box-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const nextBox = { id, classId: selectedClass, label: classNames[selectedClass] ?? `类别 ${selectedClass}`, ...draft };
    applyBoxes([...boxesRef.current, nextBox], "已添加标注，保存后写入数据集");
    setSelectedId(id);
  }

  function finishBox(event: React.PointerEvent<HTMLDivElement>, cancelled = false) {
    completeBox(event.clientX, event.clientY, cancelled);
    if (typeof event.pointerId === "number" && event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "z") return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      if (event.shiftKey) redo(); else undo();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  useEffect(() => {
    function handleWindowPointerUp(event: MouseEvent) {
      if (dragRef.current) completeBox(event.clientX, event.clientY);
    }
    window.addEventListener("pointerup", handleWindowPointerUp);
    window.addEventListener("mouseup", handleWindowPointerUp);
    return () => {
      window.removeEventListener("pointerup", handleWindowPointerUp);
      window.removeEventListener("mouseup", handleWindowPointerUp);
    };
  });

  async function saveAnnotations(): Promise<boolean> {
    if (!workspace || !datasetId || !asset) return false;
    setBusy(true);
    try {
      const text = serializeYolo(boxes);
      const checksum = await checksumText(text);
      const intent = await catalogApi.createAnnotationUploadIntent(workspace.id, datasetId, asset.id, {
        filename: `${asset.id}.txt`, byte_size: new TextEncoder().encode(text).byteLength, checksum_sha256: checksum,
      });
      const upload = await fetch(intent.upload_url, { method: intent.method, headers: intent.headers, body: text });
      if (!upload.ok) throw new Error(`标注上传失败 (${upload.status})`);
      await catalogApi.registerAnnotation(workspace.id, datasetId, asset.id, { object_key: intent.object_key, byte_size: new TextEncoder().encode(text).byteLength, checksum_sha256: checksum });
      setNotice("已保存当前标注");
      return true;
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "标注保存失败");
      return false;
    } finally { setBusy(false); }
  }

  async function submitForReview() {
    const saved = await saveAnnotations();
    if (!saved || !workspace || !datasetId || !task) return;
    try { setTask(await catalogApi.updateAnnotationTaskStatus(workspace.id, datasetId, task.id, "review")); setNotice("任务已提交检查"); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "提交失败"); }
  }

  async function completeReview() {
    const saved = await saveAnnotations();
    if (!saved || !workspace || !datasetId || !task) return;
    setBusy(true);
    try {
      setTask(await catalogApi.updateAnnotationTaskStatus(workspace.id, datasetId, task.id, "done"));
      setNotice("检查已完成，可以冻结数据版本");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "完成检查失败");
    } finally {
      setBusy(false);
    }
  }

  async function downloadTaskPackage() {
    if (!workspace || !datasetId || !task) return;
    setBusy(true);
    try {
      await catalogApi.downloadAnnotationTaskPackage(workspace.id, datasetId, task.id);
      setNotice("任务包已开始下载");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "任务包导出失败");
    } finally {
      setBusy(false);
    }
  }

  async function importTaskPackage(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!workspace || !datasetId || !task || !file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) {
      input.value = "";
      setNotice("请选择从此任务导出的 ZIP 任务包");
      return;
    }
    setBusy(true);
    try {
      const checksum = await checksumFile(file);
      const intent = await catalogApi.createAnnotationTaskYoloImportUploadIntent(
        workspace.id,
        datasetId,
        task.id,
        { filename: file.name, byte_size: file.size, checksum_sha256: checksum },
      );
      const upload = await fetch(intent.upload_url, {
        method: intent.method,
        headers: intent.headers,
        body: file,
      });
      if (!upload.ok) throw new Error(`任务包上传失败 (${upload.status})`);
      const imported = await catalogApi.importAnnotationTaskYoloPackage(
        workspace.id,
        datasetId,
        task.id,
        { object_key: intent.object_key, byte_size: file.size, checksum_sha256: checksum },
      );
      const refreshedAssets = await catalogApi.listAnnotationTaskAssets(workspace.id, datasetId, task.id);
      setTask(imported.task);
      setAssets(refreshedAssets);
      setNotice(`已导入 ${imported.imported_asset_count} 张图片的外部标注`);
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "任务包导入失败");
    } finally {
      input.value = "";
      setBusy(false);
    }
  }

  function moveAsset(direction: -1 | 1) {
    setCurrentIndex((current) => Math.max(0, Math.min(Math.max(assets.length - 1, 0), current + direction)));
    setSelectedId(null);
  }

  if (!task) return (
    <main className="annotation-editor-page">
      <Link href={`/studio/data?${returnParams.toString()}`} className="sr-only">返回标注任务</Link>
      <div className="annotation-editor-empty"><LoaderCircle className="spinner" size={20} />{notice}</div>
    </main>
  );

  return (
    <main className="annotation-editor-page">
      <header className="annotation-editor-header">
        <div className="editor-title-group"><Link href={`/studio/data?${returnParams.toString()}`} className="editor-back-link"><ChevronLeft size={15} />返回标注任务</Link><span className="editor-title-divider" /><div><strong>{task.name}</strong><small>{currentIndex + 1} / {assets.length}</small></div></div>
        <div className="editor-history-actions"><button type="button" aria-label="撤销" title="撤销" disabled={!history.length} onClick={undo}><Undo2 size={15} /></button><button type="button" aria-label="重做" title="重做" disabled={!future.length} onClick={redo}><Redo2 size={15} /></button><span>{notice}</span></div>
        <div className="editor-primary-actions">
          <input ref={importInputRef} className="sr-only" type="file" accept=".zip,application/zip" onChange={(event) => void importTaskPackage(event)} />
          <button className="editor-package-button" type="button" disabled={busy} title="导出兼容 YOLO 与 COCO 的标注任务包" onClick={() => void downloadTaskPackage()}><Download size={14} />导出</button>
          <button className="editor-package-button" type="button" disabled={busy} title="导入外部完成的 YOLO 或 COCO 标注任务包" onClick={() => importInputRef.current?.click()}><Upload size={14} />导入</button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void saveAnnotations()}><Save size={14} />保存</button>
          {task.status === "annotating" ? <button className="primary-button" type="button" disabled={busy} onClick={() => void submitForReview()}><Send size={14} />提交检查</button> : task.status === "review" ? <button className="primary-button" type="button" disabled={busy} onClick={() => void completeReview()}><Check size={14} />完成检查</button> : <button className="secondary-button" type="button" disabled><Check size={14} />已完成</button>}
        </div>
        <p className="annotation-editor-notice" role="status" aria-live="polite">{notice}</p>
      </header>
      <div className="annotation-editor-workspace">
        <aside className="annotation-tool-rail" aria-label="标注工具"><EditorTool active={activeTool === "select"} label="选择" onClick={() => setActiveTool("select")}><MousePointer2 size={18} /></EditorTool><EditorTool active={activeTool === "box"} label="矩形框" onClick={() => setActiveTool("box")}><Square size={18} /></EditorTool><EditorTool active={activeTool === "polygon"} label="多边形" onClick={() => setNotice("多边形工具将在专业标注工具接入后开放")}><Pentagon size={18} /></EditorTool><span className="tool-rail-divider" /><EditorTool active={false} label="智能预标注" onClick={() => setNotice("智能预标注尚未接入真实模型")}><Sparkles size={18} /></EditorTool></aside>
        <section className="annotation-canvas-column"><div className={`annotation-canvas tool-${activeTool}`} ref={canvasRef} aria-label="标注画布">{imageUrl ? <DynamicAssetImage ref={imageRef} className="annotation-source-image" src={imageUrl} alt="当前素材" /> : <LoaderCircle className="spinner" size={24} />}{activeTool === "box" ? <div className="canvas-drag-layer" role="presentation" aria-label={`添加「${classNames[selectedClass] ?? "类别"}」矩形框`} onPointerDown={beginBox} onPointerMove={updateBox} onPointerUp={finishBox} onPointerCancel={(event) => finishBox(event, true)} onLostPointerCapture={finishBox} onMouseUp={(event) => completeBox(event.clientX, event.clientY)} /> : null}{boxes.map((box) => <button type="button" key={box.id} className={`canvas-box label-${box.classId % 3}${selectedId === box.id ? " is-selected" : ""}`} style={{ left: `${box.x}%`, top: `${box.y}%`, width: `${box.width}%`, height: `${box.height}%` }} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); setSelectedId(box.id); setActiveTool("select"); }} aria-label={`${box.label}标注`}><span>{box.label}</span></button>)}{draftBox ? <div className={`canvas-box is-draft label-${draftBox.classId % 3}`} style={{ left: `${draftBox.x}%`, top: `${draftBox.y}%`, width: `${draftBox.width}%`, height: `${draftBox.height}%` }} aria-hidden="true"><span>{draftBox.label}</span></div> : null}{activeTool === "box" ? <span className="canvas-help">在图片上按住并拖拽，框选「{classNames[selectedClass] ?? "类别"}」</span> : null}</div><footer className="annotation-filmstrip"><button type="button" onClick={() => moveAsset(-1)} aria-label="上一张"><ChevronLeft size={17} /></button><div className="filmstrip-items">{assets.slice(Math.max(0, currentIndex - 2), currentIndex + 3).map((item, index) => <button type="button" key={item.id} className={item.id === asset.id ? "is-active" : ""} onClick={() => setCurrentIndex(Math.max(0, currentIndex - 2 + index))}><span className="filmstrip-scene" /><small>{Math.max(0, currentIndex - 2 + index) + 1}</small></button>)}</div><button type="button" onClick={() => moveAsset(1)} aria-label="下一张"><ChevronRight size={17} /></button></footer></section>
        <aside className="annotation-inspector"><section><div className="inspector-heading"><div><strong>类别</strong><small>拖拽画布时使用</small></div><span>{classNames.length}</span></div><div className="annotation-class-list">{classNames.map((name, index) => <button type="button" className={selectedClass === index ? "is-active" : ""} key={`${name}-${index}`} onClick={() => setSelectedClass(index)}><i className={`class-color color-${index % 3}`} /><span>{name}</span><small>{currentLabelCounts[index] ?? 0}</small></button>)}</div></section><section className="smart-label-panel"><div className="inspector-heading"><div><strong>智能预标注</strong><small>尚未接入真实模型</small></div><Sparkles size={15} /></div><p>接入模型并完成权限、成本和审核配置后开放。</p><button className="secondary-button smart-trial-button" type="button" onClick={() => setNotice("智能预标注尚未接入真实模型")}><Sparkles size={14} />暂未开放</button></section><section><div className="inspector-heading"><div><strong>本张标注</strong><small>{boxes.length} 个已确认</small></div></div><div className="instance-list">{boxes.map((box, index) => <button type="button" className={selectedId === box.id ? "is-active" : ""} key={box.id} onClick={() => setSelectedId(box.id)}><i className={`class-color color-${box.classId % 3}`} /><span>{box.label} {index + 1}</span></button>)}</div><button className="delete-annotation-button" type="button" disabled={!selectedId} onClick={() => { if (!selectedId) return; applyBoxes(boxesRef.current.filter((box) => box.id !== selectedId), "已删除标注，可撤销恢复"); setSelectedId(null); }}><Trash2 size={14} />删除选中标注</button></section></aside>
      </div>
    </main>
  );
}

function EditorTool({ active, label, onClick, children }: { active: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" className={active ? "is-active" : ""} aria-label={label} title={label} onClick={onClick}>{children}<span>{label}</span></button>;
}
