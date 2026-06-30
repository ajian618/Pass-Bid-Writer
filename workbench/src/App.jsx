import { useEffect, useState } from "react";
import {
  Archive,
  ArrowClockwise,
  BookOpenText,
  Buildings,
  CheckCircle,
  ClipboardText,
  Database,
  FileDoc,
  FilePdf,
  FileText,
  FolderOpen,
  Gauge,
  Gear,
  ImageSquare,
  ListChecks,
  MagnifyingGlass,
  PlayCircle,
  Plus,
  ShieldCheck,
  SquaresFour,
  UploadSimple,
  Warning,
  X,
} from "@phosphor-icons/react";

const STAGES = [
  "资料导入", "角色确认", "证据提取", "规范获取", "蓝图匹配", "任务书确认",
  "章节生成", "图表生成", "文字复核", "视觉复核", "文档装配", "输出交付",
];

const NAV_ITEMS = [
  { id: "overview", label: "项目总览", icon: Gauge },
  { id: "sources", label: "资料与依据", icon: Database },
  { id: "drawings", label: "图纸中心", icon: ImageSquare },
  { id: "blueprint", label: "成品蓝图", icon: SquaresFour },
  { id: "task", label: "编制任务书", icon: ClipboardText },
  { id: "chapters", label: "章节生产", icon: FileText },
  { id: "review", label: "复核中心", icon: ShieldCheck },
  { id: "delivery", label: "交付中心", icon: Archive },
];

const ROLE_LABELS = {
  tender: "招标文件",
  design_report: "初设/批复",
  budget: "预算/清单",
  drawing: "设计图纸",
  standard: "规范标准",
  accepted_bid: "已通过技术标",
  attachment: "其他附件",
};

const STATUS = {
  ready: ["可生成", "success"],
  generated: ["已确认", "success"],
  awaiting_approval: ["待本章确认", "warning"],
  needs_input: ["待补资料", "warning"],
  available: ["已取得", "success"],
  pending_download: ["待下载", "warning"],
  needs_confirmation: ["待核验", "danger"],
  not_applicable: ["不适用", "neutral"],
  resolved: ["已解决", "success"],
  dismissed: ["已忽略", "neutral"],
  open: ["待处理", "warning"],
  confirmed: ["已确认", "success"],
  rejected: ["已拒绝", "neutral"],
  pending_analysis: ["待识别", "warning"],
  pending_confirmation: ["待确认", "warning"],
  missing_pdf: ["缺少PDF", "danger"],
  awaiting_confirmation: ["待确认任务书", "warning"],
  awaiting_role_confirmation: ["待确认文件角色", "warning"],
  ready_for_generation: ["可逐章生成", "success"],
  ready_for_assembly: ["可装配", "success"],
  visual_analysis_pending: ["待视觉分析", "warning"],
  generating: ["逐章生产中", "warning"],
  draft_generated: ["初稿已生成", "success"],
  reviewed: ["复核完成", "success"],
  partial_draft: ["部分章节完成", "warning"],
  generation_failed: ["生成失败", "danger"],
  analyzing_visuals: ["视觉分析中", "warning"],
  visual_analysis_failed: ["视觉分析失败", "danger"],
  empty: ["未导入", "neutral"],
  not_started: ["未开始", "neutral"],
  duplicate: ["重复文件", "neutral"],
};

async function api(path, options = {}) {
  const headers = options.body instanceof FormData
    ? (options.headers || {})
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, { ...options, headers });
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text();
  if (!response.ok) throw new Error(payload?.detail || payload || "操作失败");
  return payload;
}

function StatusPill({ value }) {
  const [label, tone] = STATUS[value] || [value || "未开始", "neutral"];
  return <span className={`status-pill ${tone}`}>{label}</span>;
}

function fileUrl(path) {
  return path ? `/api/files?path=${encodeURIComponent(path)}` : "#";
}

function FolderInput({ onFiles, label = "选择整个文件夹", disabled = false }) {
  return (
    <label className={`button secondary folder-button ${disabled ? "disabled" : ""}`}>
      <FolderOpen size={18} />
      {label}
      <input
        type="file"
        multiple
        webkitdirectory=""
        directory=""
        disabled={disabled}
        onChange={(event) => onFiles(Array.from(event.target.files || []))}
      />
    </label>
  );
}

function ImportModal({ open, kind = "project", onClose, onSubmitted }) {
  const [name, setName] = useState("");
  const [projectType, setProjectType] = useState("水利工程通用");
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  if (!open) return null;
  const isCase = kind === "case";

  const submit = async (event) => {
    event.preventDefault();
    if (!files.length) return setError("请先选择整个资料文件夹");
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append(isCase ? "case_name" : "project_name", name.trim());
      form.append("project_type", projectType);
      files.forEach((file) => {
        form.append("files", file, file.name);
        form.append("relative_paths", file.webkitRelativePath || file.name);
      });
      const result = await api(isCase ? "/api/cases/import" : "/api/projects/import", {
        method: "POST",
        body: form,
      });
      onSubmitted(result);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h2>{isCase ? "导入已通过案例" : "创建施工组织设计项目"}</h2>
            <p>{isCase ? "文件夹内需同时包含招标文件和已通过技术标。" : "浏览器会保留相对目录并复制到应用数据区，原资料不改动。"}</p>
          </div>
          <button className="icon-button" onClick={onClose}><X size={20} /></button>
        </header>
        <form onSubmit={submit}>
          <label>
            {isCase ? "案例名称" : "项目名称"}
            <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          </label>
          <label>
            工程类型
            <select value={projectType} onChange={(e) => setProjectType(e.target.value)}>
              <option>水利工程通用</option><option>河道治理工程</option>
              <option>堤防工程</option><option>泵站工程</option>
              <option>水闸工程</option><option>水库除险加固工程</option>
            </select>
          </label>
          <div className="folder-picker">
            <FolderInput onFiles={setFiles} label={files.length ? "重新选择文件夹" : "选择整个资料文件夹"} />
            <div>
              <strong>{files.length ? `已选择 ${files.length} 个文件` : "尚未选择文件夹"}</strong>
              <span>{files[0]?.webkitRelativePath?.split("/")[0] || "支持嵌套目录、压缩包和图纸文件"}</span>
            </div>
          </div>
          <div className="modal-note"><ShieldCheck size={20} />旧数据不会迁移；本次导入建立全新的证据链。</div>
          {error && <div className="form-error">{error}</div>}
          <footer>
            <button type="button" className="button secondary" onClick={onClose}>取消</button>
            <button className="button primary" disabled={loading || !files.length}>
              {loading ? <ArrowClockwise className="spin" size={18} /> : <UploadSimple size={18} />}
              {loading ? "正在复制…" : isCase ? "导入并学习" : "导入并分析"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function ConfigModal({ open, onClose, onSaved }) {
  const [form, setForm] = useState({});
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) api("/api/config").then(setInfo).catch((e) => setError(e.message));
  }, [open]);
  if (!open) return null;
  const save = async (event) => {
    event.preventDefault();
    try {
      await api("/api/config", { method: "PATCH", body: JSON.stringify(form) });
      onSaved();
      onClose();
    } catch (e) { setError(e.message); }
  };
  const field = (key, label, placeholder, secret = false) => (
    <label>{label}<input type={secret ? "password" : "text"} placeholder={placeholder}
      value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>
  );
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal config-modal" onMouseDown={(e) => e.stopPropagation()}>
        <header><div><h2>模型配置</h2><p>密钥仅保存在本机应用数据目录，不写入项目仓库。</p></div>
          <button className="icon-button" onClick={onClose}><X size={20} /></button></header>
        <form onSubmit={save}>
          <div className="config-grid">
            {field("deepseek_api_key", "DeepSeek API Key", info?.configured_keys?.DEEPSEEK_API_KEY ? "已配置；留空保持不变" : "输入密钥", true)}
            {field("deepseek_model", "DeepSeek 文字模型", "deepseek-v4-pro")}
            {field("dashscope_api_key", "阿里云百炼 API Key", info?.configured_keys?.DASHSCOPE_API_KEY ? "已配置；留空保持不变" : "输入密钥", true)}
            {field("qwen_plus_model", "千问视觉模型", "qwen3.7-plus-2026-05-26")}
            {field("qwen_flash_model", "千问批处理模型", "qwen3.6-flash-2026-04-16")}
            {field("bigmodel_api_key", "智谱 API Key", info?.configured_keys?.ZHIPU_API_KEY ? "已配置；留空保持不变" : "输入密钥", true)}
            {field("glm_vision_model", "智谱复核模型", "glm-5v-turbo")}
          </div>
          {error && <div className="form-error">{error}</div>}
          <footer><button type="button" className="button secondary" onClick={onClose}>取消</button>
            <button className="button primary">保存配置</button></footer>
        </form>
      </section>
    </div>
  );
}

function Sidebar({ active, onChange, data }) {
  return (
    <aside className="sidebar">
      <div className="brand"><Buildings weight="fill" size={30} /><div><strong>施工组织设计</strong><span>多模型生产台 V1</span></div></div>
      <nav>{NAV_ITEMS.map(({ id, label, icon: Icon }) => (
        <button key={id} className={active === id ? "active" : ""} onClick={() => onChange(id)}>
          <Icon size={21} /><span>{label}</span>
          {id === "review" && data?.metrics?.open_confirmations > 0 && <b>{data.metrics.open_confirmations}</b>}
          {id === "drawings" && data?.drawings?.some((d) => !["confirmed", "rejected"].includes(d.status)) && <i />}
        </button>
      ))}</nav>
      <div className="sidebar-bottom"><BookOpenText size={20} /><div><strong>正式水利模板</strong><span>证据约束 · 人工闸门</span></div></div>
    </aside>
  );
}

function Header({ data, projects, onImport, onConfig, onRefresh, onSelect }) {
  return (
    <header className="topbar">
      <div className="project-title"><h1>{data.project?.name || "施工组织设计生成台"}</h1><StatusPill value={data.status} /></div>
      <select className="project-switcher" value={data.run_id || ""} onChange={(e) => onSelect(e.target.value)}>
        <option value="">选择历史项目</option>
        {projects.map((p) => <option key={p.run_id} value={p.run_id}>{p.name} · {p.stage}</option>)}
      </select>
      <div className="model-strip">{(data.models || []).map((m) => <span key={m.role} className={m.configured ? "configured" : ""}>{m.model} · {m.configured ? "已连接" : "未配置"}</span>)}</div>
      <div className="top-actions">
        <button className="icon-button" onClick={onConfig} title="模型配置"><Gear size={19} /></button>
        <button className="icon-button" onClick={onRefresh} title="刷新"><ArrowClockwise size={19} /></button>
        <button className="button primary compact" onClick={onImport}><Plus size={18} />新建项目</button>
      </div>
    </header>
  );
}

function WorkflowBar({ data }) {
  const workflow = data.workflow || {};
  const active = ["queued", "running"].includes(workflow.status);
  return (
    <div className={`workflow-bar ${workflow.status || "idle"}`}>
      <div className="workflow-identity"><span><PlayCircle size={20} /></span><div><strong>受控生产引擎</strong><small>Python 工作流 · 状态持久化</small></div></div>
      <div className="workflow-activity">
        {active && <ArrowClockwise className="spin" size={18} />}
        {!active && workflow.status === "failed" && <Warning size={18} />}
        {!active && workflow.status !== "failed" && <CheckCircle size={18} />}
        <div><strong>{workflow.message || "等待下一步操作"}</strong><small>{workflow.error || "每一步由工作台显式触发，不存在后台自主循环"}</small></div>
      </div>
      <span className={`agent-state ${workflow.status || "idle"}`}>{active ? "执行中" : workflow.status === "failed" ? "失败，可重试" : "就绪"}</span>
    </div>
  );
}

function StageRail({ current = 1 }) {
  return <div className="stage-rail">{STAGES.map((name, i) => {
    const n = i + 1;
    return <div key={name} className={`stage ${n < current ? "done" : n === current ? "active" : ""}`}>
      <div className="stage-node">{n < current ? "✓" : n}</div><strong>{name}</strong><span>{n < current ? "已完成" : n === current ? "当前" : "待执行"}</span>
    </div>;
  })}</div>;
}

function Metric({ value, displayValue, label, detail, tone = "blue" }) {
  return <div className="progress-stat"><div className={`ring ${tone}`} style={{ "--progress": `${Math.max(0, Math.min(100, value || 0)) * 3.6}deg` }}><span>{displayValue ?? `${value || 0}%`}</span></div>
    <div><strong>{label}</strong><small>{detail}</small></div></div>;
}

function Overview({ data, onNavigate, action }) {
  const m = data.metrics || {};
  const open = (data.confirmations || []).filter((x) => x.status === "open").slice(0, 5);
  return (
    <>
      <div className="main-grid">
        <section className="panel">
          <div className="panel-heading"><div><h2>生产状态</h2><span>{data.project?.project_type} · {data.project?.file_count || 0} 份源文件</span></div><StatusPill value={data.status} /></div>
          <div className="metric-row">
            <Metric value={m.requirement_coverage} label="要求覆盖" detail={`${m.requirement_count || 0} 项招标要求`} />
            <Metric value={m.standards_readiness} label="规范就绪" detail={`${m.standards_ready || 0}/${m.standards_count || 0} 份`} tone="teal" />
            <Metric value={m.chapter_completion} label="章节完成" detail={`${m.section_count || 0} 个章节`} tone="amber" />
            <Metric value={m.fact_count ? Math.min(100, m.fact_count * 4) : 0} displayValue={m.fact_count || 0} label="事实证据" detail="条可追溯事实" tone="green" />
          </div>
          <div className="action-row">
            <button className="button primary" disabled={!data.run_id} onClick={() => onNavigate(nextView(data))}><PlayCircle size={18} />继续当前流程</button>
            {data.run_id && <button className="button secondary" onClick={() => action("export-reports")}><Archive size={18} />更新控制报告</button>}
          </div>
        </section>
        <section className="panel risk-panel">
          <div className="panel-heading"><div><h2>需要你处理</h2><span>{m.open_confirmations || 0} 项未关闭，{m.high_risks || 0} 项高风险</span></div></div>
          <div className="risk-list">{open.length ? open.map((x, i) => <button className="risk-item" key={`${x.title}-${i}`} onClick={() => onNavigate("review")}><Warning size={20} /><div><strong>{x.title}</strong><span>{x.detail}</span></div></button>) : <div className="empty-state"><CheckCircle size={28} /><p>当前没有待处理项</p></div>}</div>
        </section>
      </div>
      <div className="lower-grid">
        <section className="panel recent-panel"><div className="panel-heading"><div><h2>证据链摘要</h2><span>项目事实和编制依据分开管理</span></div></div>
          <dl><div><dt>项目事实</dt><dd>{data.facts?.length || 0}</dd></div><div><dt>招标要求</dt><dd>{data.requirements?.requirement_count || 0}</dd></div><div><dt>规范文件</dt><dd>{data.standards?.length || 0}</dd></div><div><dt>已确认图纸</dt><dd>{data.drawings?.filter((d) => d.status === "confirmed").length || 0}</dd></div></dl>
        </section>
        <section className="panel recent-panel"><div className="panel-heading"><div><h2>运行目录</h2><span>所有运行数据位于本机 LOCALAPPDATA</span></div></div>
          <div className="path-box">{data.project?.project_dir || "新建项目后显示"}</div>
        </section>
      </div>
    </>
  );
}

function Sources({ data, setData, action, busy, notify }) {
  const [tab, setTab] = useState("files");
  const uploadSources = async (files) => {
    if (!files.length) return;
    const form = new FormData();
    files.forEach((f) => { form.append("files", f, f.name); form.append("relative_paths", f.webkitRelativePath || f.name); });
    const result = await api(`/api/runs/${data.run_id}/sources`, { method: "POST", body: form });
    action(null, null, result.job);
  };
  const roleChange = async (item, role) => {
    try {
      const next = await api(`/api/runs/${data.run_id}/files/role`, { method: "PATCH", body: JSON.stringify({ path: item.path, role }) });
      setData(next); notify("文件角色已更新，已生成新的分析任务");
    } catch (e) { notify(e.message, true); }
  };
  return (
    <div className="workspace-view">
      <div className="view-heading"><div><h2>资料与依据</h2><p>确认资料角色后，视觉模型才会读取扫描件、复杂表格和图纸 PDF。</p></div>
        <div className="heading-actions"><FolderInput disabled={busy} onFiles={uploadSources} label="补充资料文件夹" />
          <button className="button primary" disabled={!data.run_id || busy} onClick={() => action("confirm-file-roles")}>确认文件角色</button></div></div>
      <div className="tabs"><button className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>项目文件</button><button className={tab === "standards" ? "active" : ""} onClick={() => setTab("standards")}>规范清单</button><button className={tab === "facts" ? "active" : ""} onClick={() => setTab("facts")}>事实证据</button></div>
      <section className="panel">
        {tab === "files" && <div className="table-wrap"><table><thead><tr><th>文件</th><th>角色</th><th>状态</th><th>来源</th></tr></thead><tbody>{(data.files || []).map((f) => <tr key={f.path}><td><strong>{f.name}</strong><small>{f.suffix?.toUpperCase()} · {f.size ? `${Math.round(f.size / 1024)} KB` : ""}</small></td><td><select className="role-select" value={f.role} onChange={(e) => roleChange(f, e.target.value)}>{Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td><td><StatusPill value={f.is_duplicate ? "duplicate" : "ready"} /></td><td><a href={fileUrl(f.path)} target="_blank">查看原件</a></td></tr>)}</tbody></table></div>}
        {tab === "standards" && <div className="table-wrap"><table><thead><tr><th>编号</th><th>标准名称</th><th>招标引用</th><th>状态</th></tr></thead><tbody>{(data.standards || []).map((s) => <tr key={`${s.code}-${s.title}`}><td>{s.code || "待核对"}</td><td><strong>{s.title}</strong><small>{s.version || "版本待确认"}</small></td><td>{s.source_page ? `第 ${s.source_page} 页` : "未定位页码"}</td><td><StatusPill value={s.status} /></td></tr>)}</tbody></table></div>}
        {tab === "facts" && <div className="table-wrap"><table><thead><tr><th>事实</th><th>取值</th><th>来源</th><th>置信度</th></tr></thead><tbody>{(data.facts || []).map((f, i) => <tr key={`${f.key}-${i}`}><td>{f.key}</td><td><strong>{f.value} {f.unit}</strong></td><td>{f.source_path === "人工确认" ? "人工确认" : `${f.source_path?.split(/[\\/]/).pop() || ""}${f.source_page ? ` · 第${f.source_page}页` : ""}`}</td><td>{Math.round((f.confidence || 0) * 100)}%</td></tr>)}</tbody></table></div>}
      </section>
      <div className="footer-actions"><button className="button primary" disabled={busy || !data.run_id} onClick={() => action("analyze-visuals")}><ImageSquare size={18} />运行千问视觉分析</button><span>DWG 只保存，不会送入模型；必须先提供对应 PDF。</span></div>
    </div>
  );
}

function Drawings({ data, setData, notify }) {
  const [selected, setSelected] = useState(null);
  const drawing = (data.drawings || []).find((d) => d.drawing_id === selected) || data.drawings?.[0];
  useEffect(() => { if (!selected && data.drawings?.[0]) setSelected(data.drawings[0].drawing_id); }, [data.drawings, selected]);
  const [draft, setDraft] = useState({});
  useEffect(() => { if (drawing) setDraft({ ...drawing, crop: drawing.crop || {} }); }, [drawing?.drawing_id]);
  const save = async (status) => {
    try {
      const payload = {
        drawing_no: draft.drawing_no || "", title: draft.title || "", caption: draft.caption || "",
        placement: draft.placement || "inline", applicable_sections: draft.applicable_sections || [],
        crop: draft.crop || {}, status,
      };
      const next = await api(`/api/runs/${data.run_id}/drawings/${drawing.drawing_id}`, { method: "PATCH", body: JSON.stringify(payload) });
      setData(next); notify(status === "confirmed" ? "图纸使用方案已确认" : "图纸已拒绝");
    } catch (e) { notify(e.message, true); }
  };
  if (!data.drawings?.length) return <div className="empty-page"><ImageSquare size={42} /><h2>还没有图纸资产</h2><p>确认文件角色并运行视觉分析后，图纸 PDF 会出现在这里。</p></div>;
  return (
    <div className="drawing-layout">
      <section className="panel drawing-list"><div className="panel-heading"><div><h2>图纸资产</h2><span>{data.drawings.length} 项</span></div></div>
        {data.drawings.map((d) => <button key={d.drawing_id} className={drawing?.drawing_id === d.drawing_id ? "active" : ""} onClick={() => setSelected(d.drawing_id)}><ImageSquare size={20} /><div><strong>{d.drawing_no || d.title || "未命名图纸"}</strong><small>{d.source_pdf_name || d.source_dwg_name}</small></div><StatusPill value={d.status} /></button>)}</section>
      <section className="panel drawing-canvas"><div className="panel-heading"><div><h2>{drawing?.title}</h2><span>{drawing?.source_pdf_name || "尚无图纸PDF"}</span></div>{drawing?.source_pdf_path && <a href={fileUrl(drawing.source_pdf_path)} target="_blank">查看整张 PDF</a>}</div>
        {drawing?.preview_path ? <div className="drawing-preview"><img src={fileUrl(drawing.preview_path)} alt={drawing.title} /></div> : <div className="empty-state"><Warning size={28} /><p>{drawing?.source_pdf_path ? "尚未生成图纸预览，请先运行视觉分析" : "仅有 DWG，V1 不会假装已经识别"}</p></div>}
      </section>
      <section className="panel drawing-form"><div className="panel-heading"><div><h2>插图设置</h2><span>确认后才会进入正文</span></div></div>
        <label>图号<input value={draft.drawing_no || ""} onChange={(e) => setDraft({ ...draft, drawing_no: e.target.value })} /></label>
        <label>图名<input value={draft.title || ""} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
        <label>图注<textarea value={draft.caption || ""} onChange={(e) => setDraft({ ...draft, caption: e.target.value })} /></label>
        <label>插入方式<select value={draft.placement || "inline"} onChange={(e) => setDraft({ ...draft, placement: e.target.value })}><option value="inline">章节局部图</option><option value="landscape_page">横向整页图</option></select></label>
        <label>插入章节<select multiple value={draft.applicable_sections || []} onChange={(e) => setDraft({ ...draft, applicable_sections: Array.from(e.target.selectedOptions, (o) => o.value) })}>{(data.sections || []).map((s) => <option key={s.code} value={s.code}>{s.code} {s.title}</option>)}</select></label>
        <fieldset><legend>裁剪范围（0–1，相对坐标）</legend><div className="crop-grid">{["x", "y", "width", "height"].map((k) => <label key={k}>{k}<input type="number" min="0" max="1" step="0.01" value={draft.crop?.[k] ?? (k === "width" || k === "height" ? 1 : 0)} onChange={(e) => setDraft({ ...draft, crop: { ...draft.crop, [k]: Number(e.target.value) } })} /></label>)}</div></fieldset>
        <div className="drawing-actions"><button className="button secondary" onClick={() => save("rejected")}>拒绝使用</button><button className="button primary" disabled={!drawing?.source_pdf_path} onClick={() => save("confirmed")}><CheckCircle size={18} />确认图纸</button></div>
      </section>
    </div>
  );
}

function Blueprint({ data, onCase, cases }) {
  return <div className="workspace-view"><div className="view-heading"><div><h2>{data.blueprint?.title || "水利工程施工组织设计标准蓝图"}</h2><p>蓝图定义成品应该包含什么；历史案例只复用结构、表达和版式。</p></div><button className="button secondary" onClick={onCase}><UploadSimple size={18} />导入已通过案例</button></div>
    {!!cases.length && <section className="panel case-strip"><strong>案例库</strong>{cases.slice(0, 5).map((c) => <span key={c.id}>{c.title}</span>)}</section>}
    <div className="blueprint-grid">{(data.sections || []).map((s) => <article className="blueprint-section" key={s.code}><span>{s.code}</span><div><h3>{s.title}</h3><p>{s.purpose}</p><small>交付项：{s.components?.join("、")}</small></div></article>)}</div></div>;
}

function TaskSpec({ data, action, busy }) {
  return <div className="workspace-view"><div className="view-heading"><div><h2>施组编制任务书</h2><p>确认目录、交付项、项目依据、编制依据和缺口后，才能进入正文生产。</p></div>
    <button className="button primary" disabled={busy || !["awaiting_confirmation", "visual_analysis_failed"].includes(data.status)} onClick={() => action("confirm-task-spec")}><CheckCircle size={18} />确认任务书</button></div>
    <section className="panel task-table"><table><thead><tr><th>章节</th><th>完成标准</th><th>项目依据</th><th>编制依据</th><th>缺失输入</th></tr></thead><tbody>{(data.sections || []).map((s) => <tr key={s.code}><td><strong>{s.code} {s.title}</strong><small>{s.purpose}</small></td><td>{s.acceptance?.join("；")}</td><td>{s.project_basis?.length ? s.project_basis.join("；") : "尚无"}</td><td>{s.reference_basis?.join("；")}</td><td className={s.missing_inputs?.length ? "warning-text" : ""}>{s.missing_inputs?.length ? s.missing_inputs.join("；") : "完整"}</td></tr>)}</tbody></table></section></div>;
}

function Chapters({ data, action, busy }) {
  const firstOpen = data.sections?.find((s) => s.status !== "generated");
  const [code, setCode] = useState(firstOpen?.code || data.sections?.[0]?.code);
  const [instruction, setInstruction] = useState("");
  const section = data.sections?.find((s) => s.code === code) || data.sections?.[0];
  useEffect(() => { if (!data.sections?.some((s) => s.code === code)) setCode(firstOpen?.code || data.sections?.[0]?.code); }, [data.sections, code, firstOpen?.code]);
  if (!section) return null;
  const isNext = firstOpen?.code === section.code;
  return <div className="chapter-view">
    <section className="panel chapter-list">{data.sections.map((s) => <button key={s.code} className={s.code === section.code ? "active" : ""} onClick={() => setCode(s.code)}><span>{s.code}</span><div><strong>{s.title}</strong><small>{s.completion || 0}% · {STATUS[s.status]?.[0] || s.status}</small></div></button>)}</section>
    <section className="panel chapter-detail"><div className="panel-heading"><div><h2>{section.code} {section.title}</h2><span>{section.purpose}</span></div><StatusPill value={section.status} /></div>
      <h3>本章交付组件</h3><div className="component-list">{section.components?.map((x) => <div key={x}><CheckCircle size={17} /><span>{x}</span></div>)}</div>
      <h3>正文预览</h3><div className="content-preview">{section.content || "尚未生成。本章只有在前一章确认后才能生成。"}</div>
      {section.status === "awaiting_approval" && <div className="revision-box"><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="输入具体修改要求，例如：补充围堰拆除顺序，并引用已确认图纸。" /><div><button className="button secondary" disabled={busy || instruction.trim().length < 2} onClick={() => action("revise", { section_code: section.code, instruction })}>按要求重写</button><button className="button primary" disabled={busy} onClick={() => action("approve", { section_code: section.code })}><CheckCircle size={18} />接受本章</button></div></div>}
      {!section.content && <button className="button primary wide" disabled={busy || !isNext || !["generating", "generation_failed"].includes(data.status)} onClick={() => action("generate", { section_code: section.code })}><PlayCircle size={18} />生成本章</button>}
    </section>
    <section className="panel basis-panel"><div className="panel-heading"><div><h2>章节依据</h2><span>生成时只发送此证据包</span></div></div><h3>项目依据</h3>{section.project_basis?.map((x) => <p key={x}>{x}</p>)}{!section.project_basis?.length && <p className="missing">尚无项目依据</p>}<h3>编制依据</h3>{section.reference_basis?.map((x) => <p key={x}>{x}</p>)}<h3>待确认输入</h3>{section.missing_inputs?.map((x) => <p className="missing" key={x}>{x}</p>)}</section>
  </div>;
}

function ReviewModal({ item, index, onClose, onSaved, runId }) {
  const [form, setForm] = useState({ status: "resolved", resolution: "", fact_key: "", value: "", unit: "" });
  if (!item) return null;
  const save = async (event) => {
    event.preventDefault();
    const state = await api(`/api/runs/${runId}/review-items/${index}`, { method: "PATCH", body: JSON.stringify(form) });
    onSaved(state); onClose();
  };
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="modal" onMouseDown={(e) => e.stopPropagation()}><header><div><h2>{item.title}</h2><p>{item.detail}</p></div><button className="icon-button" onClick={onClose}><X /></button></header><form onSubmit={save}>
    <label>处理结论<textarea value={form.resolution} onChange={(e) => setForm({ ...form, resolution: e.target.value })} required /></label>
    <div className="form-row"><label>状态<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="resolved">已解决</option><option value="dismissed">不适用/忽略</option><option value="open">仍待处理</option></select></label><label>事实名称（可选）<input value={form.fact_key} onChange={(e) => setForm({ ...form, fact_key: e.target.value })} /></label></div>
    <div className="form-row"><label>人工确认值<input value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} /></label><label>单位<input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></label></div>
    <footer><button type="button" className="button secondary" onClick={onClose}>取消</button><button className="button primary">保存复核结果</button></footer></form></section></div>;
}

function Review({ data, setData, action, busy }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const items = (data.confirmations || []).map((item, index) => ({ item, index })).filter(({ item }) => !query || `${item.title}${item.detail}`.includes(query));
  return <div className="workspace-view"><div className="view-heading"><div><h2>人工复核中心</h2><p>复核项可以录入结论和确认事实，不只是展示告警。</p></div><button className="button primary" disabled={busy || !(data.outputs?.docx_path || data.docx?.docx_path)} onClick={() => action("review-draft")}><ShieldCheck size={18} />运行成品复核</button></div>
    <section className="panel"><div className="review-toolbar"><div className="search"><MagnifyingGlass size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索复核项" /></div><span>{items.length} 项</span></div>
      {items.map(({ item, index }) => <div className={`finding ${item.severity || ""}`} key={`${item.title}-${index}`}><Warning size={20} /><div><strong>{item.title}</strong><p>{item.detail}</p><small>{item.category} · {item.affected_sections?.join("、")}</small></div><div className="finding-actions"><StatusPill value={item.status} /><button className="text-button compact-link" onClick={() => setSelected({ item, index })}>编辑处理</button></div></div>)}
      {!items.length && <div className="empty-state"><CheckCircle size={28} /><p>没有匹配的复核项</p></div>}
    </section>
    <ReviewModal item={selected?.item} index={selected?.index} runId={data.run_id} onClose={() => setSelected(null)} onSaved={setData} />
  </div>;
}

function Delivery({ data, action, busy }) {
  const outputs = { docx_path: data.docx?.docx_path, pdf_path: data.pdf?.pdf_path, ...(data.outputs || {}) };
  const reports = data.reports || {};
  const entries = [
    ["施工组织设计_初稿.docx", outputs.docx_path, FileDoc],
    ["施工组织设计_初稿.pdf", outputs.pdf_path, FilePdf],
    ...Object.entries(reports).filter(([, path]) => typeof path === "string").map(([name, path]) => [name, path, ListChecks]),
  ];
  return <div className="workspace-view"><div className="view-heading"><div><h2>交付中心</h2><p>全部章节确认后装配 Word，优先用 Word COM 导出 PDF。</p></div><div className="heading-actions"><button className="button primary" disabled={busy || data.status !== "ready_for_assembly"} onClick={() => action("assemble")}><FileDoc size={18} />装配 DOCX / PDF</button><button className="button secondary" disabled={busy || !data.run_id} onClick={() => action("export-reports")}><Archive size={18} />更新报告</button></div></div>
    <div className="delivery-grid">{entries.filter(([, path]) => path).map(([name, path, Icon]) => <article className="delivery-card" key={`${name}-${path}`}><Icon size={30} /><div><strong>{name}</strong><span>{path}</span></div><a href={fileUrl(path)} target="_blank">打开</a></article>)}</div>
    {!entries.some(([, p]) => p) && <div className="empty-page"><Archive size={42} /><h2>尚未生成交付文件</h2><p>请先完成任务书确认和全部章节审批。</p></div>}
  </div>;
}

function nextView(data) {
  if (!data.run_id) return "sources";
  if (data.status === "awaiting_role_confirmation") return "sources";
  if (["visual_analysis_pending", "analyzing_visuals"].includes(data.status)) return "sources";
  if (["awaiting_confirmation", "visual_analysis_failed"].includes(data.status)) return "task";
  if (["generating", "generation_failed"].includes(data.status)) return "chapters";
  if (data.status === "ready_for_assembly") return "delivery";
  if (["draft_generated", "reviewed"].includes(data.status)) return "delivery";
  return "overview";
}

export default function App() {
  const [data, setData] = useState(null);
  const [projects, setProjects] = useState([]);
  const [cases, setCases] = useState([]);
  const [active, setActive] = useState("overview");
  const [modal, setModal] = useState("");
  const [trackedJob, setTrackedJob] = useState(null);
  const [toast, setToast] = useState(null);

  const notify = (message, error = false) => { setToast({ message, error }); setTimeout(() => setToast(null), 4500); };
  const refreshLists = () => Promise.all([api("/api/projects").then(setProjects), api("/api/cases").then(setCases).catch(() => setCases([]))]);
  const refresh = async (runId = data?.run_id) => {
    const state = await api(`/api/dashboard${runId ? `?run_id=${runId}` : ""}`);
    setData(state); refreshLists();
  };
  useEffect(() => { refresh().catch((e) => notify(e.message, true)); }, []);
  useEffect(() => {
    if (!trackedJob) return undefined;
    const timer = setInterval(async () => {
      try {
        const result = await api(`/api/jobs/${trackedJob}`);
        if (result.state) setData(result.state);
        if (["succeeded", "failed"].includes(result.job.status)) {
          clearInterval(timer); setTrackedJob(null); refreshLists();
          if (result.job.status === "failed") notify(result.job.error_text || "任务失败", true);
          else notify("后台任务已完成");
        }
      } catch (e) { clearInterval(timer); setTrackedJob(null); notify(e.message, true); }
    }, 1200);
    return () => clearInterval(timer);
  }, [trackedJob]);

  const busy = !!trackedJob || ["queued", "running"].includes(data?.workflow?.status);
  const runAction = async (name, payload = {}, suppliedJob = null) => {
    try {
      if (suppliedJob) return setTrackedJob(suppliedJob.id);
      const runId = data.run_id;
      if (name === "approve") {
        const state = await api(`/api/runs/${runId}/chapters/${payload.section_code}/approve`, { method: "POST" });
        setData(state); return notify("本章已确认");
      }
      const routes = {
        "confirm-file-roles": [`/api/runs/${runId}/confirm-file-roles`, {}],
        "analyze-visuals": [`/api/runs/${runId}/analyze-visuals`, {}],
        "confirm-task-spec": [`/api/runs/${runId}/confirm-task-spec`, { confirmed: true }],
        generate: [`/api/runs/${runId}/chapters/${payload.section_code}/generate`, {}],
        revise: [`/api/runs/${runId}/chapters/${payload.section_code}/revise`, { instruction: payload.instruction }],
        assemble: [`/api/runs/${runId}/assemble`, {}],
        "review-draft": [`/api/runs/${runId}/review-draft`, {}],
        "export-reports": [`/api/runs/${runId}/export-reports`, {}],
      };
      const [path, body] = routes[name];
      const result = await api(path, { method: "POST", body: JSON.stringify(body) });
      setData(result);
      const job = result.workflow_jobs?.find((j) => ["queued", "running"].includes(j.status));
      if (job) setTrackedJob(job.id);
    } catch (e) { notify(e.message, true); }
  };

  const onSubmitted = (result) => {
    if (result.job) setTrackedJob(result.job.id);
    notify("资料已复制，开始受控分析");
  };
  if (!data) return <div className="loading-screen"><ArrowClockwise className="spin" />正在启动生产台…</div>;

  let view;
  if (active === "overview") view = <Overview data={data} onNavigate={setActive} action={runAction} />;
  if (active === "sources") view = <Sources data={data} setData={setData} action={runAction} busy={busy} notify={notify} />;
  if (active === "drawings") view = <Drawings data={data} setData={setData} notify={notify} />;
  if (active === "blueprint") view = <Blueprint data={data} onCase={() => setModal("case")} cases={cases} />;
  if (active === "task") view = <TaskSpec data={data} action={runAction} busy={busy} />;
  if (active === "chapters") view = <Chapters data={data} action={runAction} busy={busy} />;
  if (active === "review") view = <Review data={data} setData={setData} action={runAction} busy={busy} />;
  if (active === "delivery") view = <Delivery data={data} action={runAction} busy={busy} />;

  return (
    <div className="app-shell">
      <Sidebar active={active} onChange={setActive} data={data} />
      <main className="app-main">
        <Header data={data} projects={projects} onImport={() => setModal("project")} onConfig={() => setModal("config")} onRefresh={() => refresh()} onSelect={(id) => id && refresh(id)} />
        <div className="content"><WorkflowBar data={data} /><StageRail current={data.stage_index || 1} />{view}</div>
      </main>
      <ImportModal open={modal === "project"} kind="project" onClose={() => setModal("")} onSubmitted={onSubmitted} />
      <ImportModal open={modal === "case"} kind="case" onClose={() => setModal("")} onSubmitted={onSubmitted} />
      <ConfigModal open={modal === "config"} onClose={() => setModal("")} onSaved={() => refresh()} />
      {toast && <div className={`toast ${toast.error ? "error" : ""}`}>{toast.error ? <Warning size={18} /> : <CheckCircle size={18} />}{toast.message}</div>}
    </div>
  );
}
