import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowClockwise,
  BookOpenText,
  Buildings,
  CaretRight,
  CheckCircle,
  ClipboardText,
  CloudArrowDown,
  Database,
  FileDoc,
  FileText,
  FolderOpen,
  Gauge,
  ListChecks,
  MagnifyingGlass,
  PlayCircle,
  ShieldCheck,
  SquaresFour,
  UploadSimple,
  Warning,
  X,
} from "@phosphor-icons/react";

const STAGES = [
  "资料导入",
  "角色确认",
  "证据提取",
  "规范获取",
  "蓝图匹配",
  "任务书确认",
  "章节生成",
  "图表生成",
  "文字复核",
  "视觉复核",
  "文档装配",
  "输出交付",
];

const NAV_ITEMS = [
  { id: "overview", label: "项目总览", icon: Gauge },
  { id: "sources", label: "资料与依据", icon: Database },
  { id: "blueprint", label: "成品蓝图", icon: SquaresFour },
  { id: "task", label: "编制任务书", icon: ClipboardText },
  { id: "chapters", label: "章节生产", icon: FileText },
  { id: "review", label: "复核中心", icon: ShieldCheck },
  { id: "delivery", label: "交付中心", icon: Archive },
];

const API = "";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "操作失败");
  return payload;
}

function StatusPill({ value }) {
  const map = {
    ready: ["可生成", "success"],
    generated: ["已生成", "success"],
    needs_input: ["待补资料", "warning"],
    blocked: ["已阻断", "danger"],
    available: ["已取得", "success"],
    pending_download: ["待下载", "warning"],
    needs_confirmation: ["待核验版本", "danger"],
    not_applicable: ["不适用", "neutral"],
    resolved: ["已解决", "success"],
    open: ["待处理", "warning"],
    awaiting_confirmation: ["待确认任务书", "warning"],
    awaiting_role_confirmation: ["待确认文件角色", "warning"],
    ready_for_generation: ["可生成正文", "success"],
    generating: ["生成中", "warning"],
    draft_generated: ["初稿已生成", "success"],
    partial_draft: ["部分章节完成", "warning"],
    generation_failed: ["生成失败", "danger"],
    visual_analysis_pending: ["待视觉分析", "warning"],
    analyzing_visuals: ["视觉分析中", "warning"],
    visual_analysis_failed: ["视觉分析失败", "danger"],
    empty: ["未导入", "neutral"],
    not_started: ["未开始", "neutral"],
    duplicate: ["重复文件", "neutral"],
  };
  const [label, tone] = map[value] || [value || "未开始", "neutral"];
  return <span className={`status-pill ${tone}`}>{label}</span>;
}

function ProgressRing({ value, label, detail, tone = "blue" }) {
  return (
    <div className="progress-stat">
      <div className={`ring ${tone}`} style={{ "--progress": `${value * 3.6}deg` }}>
        <span>{value}%</span>
      </div>
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function ImportModal({ open, onClose, onPrepared }) {
  const [projectDir, setProjectDir] = useState("");
  const [projectType, setProjectType] = useState("水利工程通用");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  if (!open) return null;

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const state = await api("/api/projects/prepare", {
        method: "POST",
        body: JSON.stringify({
          project_dir: projectDir,
          project_type: projectType,
          expand_archives: true,
        }),
      });
      onPrepared(state);
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
            <h2>导入待编制项目</h2>
            <p>系统会解压资料包、识别文件角色，并建立证据库与参照库。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </header>
        <form onSubmit={submit}>
          <label>
            项目资料夹
            <div className="input-with-icon">
              <FolderOpen size={20} />
              <input
                autoFocus
                value={projectDir}
                onChange={(event) => setProjectDir(event.target.value)}
                placeholder="例如 C:\项目资料\某河道治理工程"
                required
              />
            </div>
          </label>
          <label>
            工程类型
            <select value={projectType} onChange={(event) => setProjectType(event.target.value)}>
              <option>水利工程通用</option>
              <option>河道治理工程</option>
              <option>堤防工程</option>
              <option>泵站工程</option>
              <option>水闸工程</option>
              <option>水库除险加固工程</option>
            </select>
          </label>
          <div className="modal-note">
            <ShieldCheck size={20} />
            原始资料不会被修改；解压文件、规范原文和输出成果保存在项目目录内。
          </div>
          {error && <div className="form-error">{error}</div>}
          <footer>
            <button type="button" className="button secondary" onClick={onClose}>取消</button>
            <button className="button primary" disabled={loading}>
              {loading ? <ArrowClockwise className="spin" size={18} /> : <UploadSimple size={18} />}
              {loading ? "正在建立项目…" : "导入并分析"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function Sidebar({ active, onChange, data }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Buildings weight="fill" size={30} />
        <div>
          <strong>施工组织设计</strong>
          <span>生产工作台</span>
        </div>
      </div>
      <nav>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button key={id} className={active === id ? "active" : ""} onClick={() => onChange(id)}>
            <Icon size={21} />
            <span>{label}</span>
            {id === "review" && data?.metrics?.open_confirmations > 0 && (
              <b>{data.metrics.open_confirmations}</b>
            )}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <BookOpenText size={20} />
        <div><strong>水利工程</strong><span>标准蓝图 v1.0</span></div>
      </div>
    </aside>
  );
}

function Header({ data, onImport, onRefresh }) {
  const models = data.models || [];
  const text = models.find((item) => item.role === "text_master");
  const vision = models.find((item) => item.role === "vision_primary");
  return (
    <header className="topbar">
      <div className="project-title">
        <h1>{data.project?.name || "尚未导入项目"}</h1>
        <StatusPill value={data.status === "empty" ? "not_started" : data.status} />
        <span>{data.project?.project_type}</span>
      </div>
      <div className="model-strip">
        <span className={text?.configured ? "configured" : ""}>文字：{text?.model || "DeepSeek"}</span>
        <span className={vision?.configured ? "configured" : ""}>视觉：{vision?.model || "千问"}</span>
      </div>
      <div className="top-actions">
        <button className="icon-button" onClick={onRefresh} title="刷新"><ArrowClockwise size={19} /></button>
        <button className="button primary compact" onClick={onImport}><FolderOpen size={18} />导入项目</button>
      </div>
    </header>
  );
}

function StageRail({ current, visualStatus }) {
  return (
    <section className="stage-rail">
      {STAGES.map((stage, index) => {
        const step = index + 1;
        const done = step < current;
        const active = step === current;
        const needsVisionReview =
          step === 10 && ["not_configured", "error"].includes(visualStatus);
        return (
          <div
            key={stage}
            className={`stage ${done ? "done" : ""} ${active ? "active" : ""} ${needsVisionReview ? "warning" : ""}`}
          >
            <div className="stage-node">
              {needsVisionReview ? <Warning weight="fill" size={18} /> : done ? <CheckCircle weight="fill" size={22} /> : step}
            </div>
            <strong>{stage}</strong>
            <span>{needsVisionReview ? "待配置/人工复核" : done ? "已完成" : active ? "进行中" : "待开始"}</span>
          </div>
        );
      })}
    </section>
  );
}

function WorkQueue({ sections, onSelect }) {
  const [query, setQuery] = useState("");
  const filtered = sections.filter((item) => item.title.includes(query));
  return (
    <section className="panel queue-panel">
      <div className="panel-heading">
        <div><h2>当前工作队列</h2><span>{filtered.length} 个章节任务</span></div>
        <div className="search">
          <MagnifyingGlass size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索章节" />
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>章节任务</th><th>项目依据</th><th>编制依据</th><th>模型</th><th>进度</th><th>状态</th></tr>
          </thead>
          <tbody>
            {filtered.map((section) => (
              <tr key={section.code} onClick={() => onSelect(section)}>
                <td><strong>{section.code} {section.title}</strong><small>{section.components.length} 个交付组件</small></td>
                <td>{section.project_basis.length} 项</td>
                <td>{section.reference_basis.length} 项</td>
                <td><span className="model-tag">{section.model || "deepseek-v4-pro"}</span></td>
                <td><div className="bar"><i style={{ width: `${section.completion}%` }} /></div><span>{section.completion}%</span></td>
                <td><StatusPill value={section.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RiskRail({ confirmations, standards, onOpenReview }) {
  const open = confirmations.filter((item) => item.status === "open");
  const groups = [
    { key: "规范待下载", label: "待下载规范", icon: CloudArrowDown, tone: "blue" },
    { key: "资料冲突", label: "资料冲突", icon: Warning, tone: "orange" },
    { key: "模型分歧", label: "模型分歧", icon: ShieldCheck, tone: "teal" },
    { key: "章节输入缺失", label: "人工确认", icon: ListChecks, tone: "violet" },
  ];
  return (
    <aside className="panel risk-panel">
      <div className="panel-heading"><div><h2>风险与待办</h2><span>必须处理后才能定稿</span></div></div>
      <div className="risk-list">
        {groups.map(({ key, label, icon: Icon, tone }) => {
          let count = open.filter((item) => item.category === key).length;
          if (key === "规范待下载") count = standards.filter((item) => item.status === "pending_download").length;
          if (key === "章节输入缺失") count = open.filter((item) => item.category.includes("缺失") || item.category.includes("确认")).length;
          return (
            <button key={key} className={`risk-item ${tone}`} onClick={onOpenReview}>
              <Icon size={24} />
              <div><strong>{label}</strong><span>{count ? `${count} 项需要处理` : "当前无待处理项"}</span></div>
              <b>{count}</b><CaretRight size={18} />
            </button>
          );
        })}
      </div>
      <button className="text-button" onClick={onOpenReview}>查看全部风险与待办 <CaretRight size={16} /></button>
    </aside>
  );
}

function Overview({ data, setActive, onSelectSection, onAction }) {
  const metrics = data.metrics || {};
  return (
    <>
      <StageRail
        current={data.stage_index || 1}
        visualStatus={data.visual_report?.status}
      />
      <div className="main-grid">
        <WorkQueue sections={data.sections || []} onSelect={onSelectSection} />
        <RiskRail
          confirmations={data.confirmations || []}
          standards={data.standards || []}
          onOpenReview={() => setActive("review")}
        />
      </div>
      <div className="lower-grid">
        <section className="panel metrics-panel">
          <div className="panel-heading"><div><h2>生产进度概览</h2><span>由真实证据和任务状态计算</span></div></div>
          <div className="metric-row">
            <ProgressRing value={metrics.requirement_coverage || 0} label="要求覆盖率" detail={`${metrics.requirement_count || 0} 项招标要求`} />
            <ProgressRing value={Math.min(100, Math.round((metrics.fact_count || 0) / Math.max(metrics.file_count || 1, 1) * 12))} label="资料利用率" detail={`${metrics.fact_count || 0} 项项目事实`} tone="teal" />
            <ProgressRing value={metrics.standards_readiness || 0} label="规范齐备率" detail={`${metrics.standards_ready || 0} / ${metrics.standards_count || 0} 份`} tone="amber" />
            <ProgressRing value={metrics.chapter_completion || 0} label="章节完成率" detail={`${metrics.section_count || 0} 个章节`} tone="green" />
          </div>
          <div className="action-row">
            <button className="button primary" onClick={() => onAction("continue")}><PlayCircle size={20} />继续执行流程</button>
            <button className="button secondary" onClick={() => setActive("task")}><FolderOpen size={20} />打开编制任务书</button>
            <button className="button secondary" onClick={() => onAction("reports")}><ListChecks size={20} />生成补漏清单</button>
          </div>
        </section>
        <section className="panel recent-panel">
          <div className="panel-heading"><div><h2>项目基线</h2><span>当前生产任务的可信输入</span></div></div>
          <dl>
            <div><dt>资料文件</dt><dd>{metrics.file_count || 0}</dd></div>
            <div><dt>已提取事实</dt><dd>{metrics.fact_count || 0}</dd></div>
            <div><dt>引用规范</dt><dd>{metrics.standards_count || 0}</dd></div>
            <div><dt>高风险项</dt><dd className="danger-text">{metrics.high_risks || 0}</dd></div>
          </dl>
          <button className="text-button" onClick={() => setActive("sources")}>查看全部项目依据 <CaretRight size={16} /></button>
        </section>
      </div>
    </>
  );
}

function SourcesView({ data, onData, onToast, onConfirmRoles, onAnalyzeVisuals }) {
  const [tab, setTab] = useState("files");
  const [updating, setUpdating] = useState("");

  const changeRole = async (file, role) => {
    setUpdating(file.path);
    try {
      const next = await api(`/api/runs/${data.run_id}/files/role`, {
        method: "PATCH",
        body: JSON.stringify({ path: file.path, role }),
      });
      onData(next);
      onToast("文件角色已确认，并按新角色重建证据与任务书");
    } catch (error) {
      onToast(error.message);
    } finally {
      setUpdating("");
    }
  };

  const uploadStandard = async (standard, file) => {
    if (!file) return;
    setUpdating(standard.code);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(
        `/api/standards/upload?run_id=${data.run_id}&standard_code=${encodeURIComponent(standard.code)}`,
        { method: "POST", body },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "规范上传失败");
      const next = await api(`/api/dashboard?run_id=${data.run_id}`);
      onData(next);
      onToast(`${standard.code} 已进入本地规范库`);
    } catch (error) {
      onToast(error.message);
    } finally {
      setUpdating("");
    }
  };

  const changeStandardStatus = async (standard, status) => {
    setUpdating(standard.code);
    try {
      const next = await api("/api/standards/status", {
        method: "PATCH",
        body: JSON.stringify({
          run_id: data.run_id,
          standard_code: standard.code,
          status,
          resolution: status === "not_applicable" ? "人工确认本项目不适用" : "",
        }),
      });
      onData(next);
      onToast(`${standard.code} 状态已更新`);
    } catch (error) {
      onToast(error.message);
    } finally { setUpdating(""); }
  };

  return (
    <section className="workspace-view">
      <div className="view-heading">
        <div><h2>资料与依据</h2><p>每项项目事实和规范依据都保留来源位置与状态。</p></div>
        {data.status === "awaiting_role_confirmation" && (
          <button className="button primary" onClick={onConfirmRoles}>
            <CheckCircle size={18} />确认全部文件角色
          </button>
        )}
        {["visual_analysis_pending", "visual_analysis_failed"].includes(data.status) && (
          <button className="button primary" onClick={onAnalyzeVisuals}>
            <PlayCircle size={18} />运行多模态资料分析
          </button>
        )}
      </div>
      <div className="tabs">
        <button className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>项目资料 {data.files.length}</button>
        <button className={tab === "facts" ? "active" : ""} onClick={() => setTab("facts")}>项目事实 {data.facts.length}</button>
        <button className={tab === "standards" ? "active" : ""} onClick={() => setTab("standards")}>规范库 {data.standards.length}</button>
        <button className={tab === "standard_clauses" ? "active" : ""} onClick={() => setTab("standard_clauses")}>规范条款 {data.standard_clauses?.length || 0}</button>
        <button className={tab === "case_assets" ? "active" : ""} onClick={() => setTab("case_assets")}>案例资产 {data.case_assets?.length || 0}</button>
        <button className={tab === "visual_jobs" ? "active" : ""} onClick={() => setTab("visual_jobs")}>视觉证据 {data.visual_jobs?.length || 0}</button>
      </div>
      <div className="panel list-panel">
        {tab === "files" && data.files.map((file) => (
          <div className="data-row" key={file.path}>
            <FileDoc size={22} />
            <div><strong>{file.name}</strong><span>{file.path}</span></div>
            <select
              className="role-select"
              value={file.role}
              disabled={updating === file.path}
              onChange={(event) => changeRole(file, event.target.value)}
              aria-label={`${file.name} 文件角色`}
            >
              <option value="tender">招标文件</option>
              <option value="design_report">初设/设计报告</option>
              <option value="budget">预算/工程量清单</option>
              <option value="drawing">图纸/CAD</option>
              <option value="standard">规范原文</option>
              <option value="accepted_bid">历史成品</option>
              <option value="attachment">其他附件</option>
            </select>
            <StatusPill value={file.is_duplicate ? "duplicate" : file.confidence > .75 ? "available" : "open"} />
          </div>
        ))}
        {tab === "facts" && data.facts.map((fact, index) => (
          <div className="data-row" key={`${fact.key}-${index}`}><CheckCircle size={22} /><div><strong>{fact.key}：{fact.value}{fact.unit}</strong><span>{fact.source_path}{fact.source_page ? ` · 第${fact.source_page}页` : ""}</span></div><span>置信度 {Math.round(fact.confidence * 100)}%</span><StatusPill value={fact.status === "extracted" ? "available" : fact.status} /></div>
        ))}
        {tab === "standards" && data.standards.map((standard) => (
          <div className="data-row" key={standard.code}>
            <BookOpenText size={22} />
            <div>
              <strong>{standard.code} {standard.title}</strong>
              <span>招标文件第 {standard.source_page || "—"} 页 · {standard.official_platform}</span>
            </div>
            <div className="row-actions">
              <a href={standard.official_url} target="_blank" rel="noreferrer">官方平台</a>
              <label className="upload-link">
                <UploadSimple size={15} />
                {updating === standard.code ? "上传中" : "上传原文"}
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  disabled={updating === standard.code}
                  onChange={(event) => uploadStandard(standard, event.target.files?.[0])}
                />
              </label>
              <select className="mini-select" value={standard.status} onChange={(event) => changeStandardStatus(standard, event.target.value)}>
                <option value="pending_download">待下载</option>
                <option value="needs_confirmation">待核验</option>
                <option value="not_applicable">不适用</option>
                {standard.local_path && <option value="available">已取得</option>}
              </select>
            </div>
            <StatusPill value={standard.status} />
          </div>
        ))}
        {tab === "standard_clauses" && (data.standard_clauses || []).map((clause, index) => (
          <div className="data-row" key={`${clause.standard_code}-${clause.clause_id}-${index}`}>
            <BookOpenText size={22} />
            <div><strong>{clause.standard_code} {clause.clause_id}</strong><span>{clause.text}</span></div>
            <span>原文第 {clause.page || "—"} 页</span>
            <StatusPill value="available" />
          </div>
        ))}
        {tab === "case_assets" && (data.case_assets || []).map((asset) => (
          <div className="data-row" key={asset.asset_id}>
            <Archive size={22} />
            <div><strong>{asset.case_title} · {asset.title}</strong><span>{asset.source_path || "公司案例库"}</span></div>
            <span>{asset.reuse_rule === "layout_only" ? "仅复用版式" : asset.reuse_rule === "replace_parameters" ? "替换参数后使用" : "仅复用结构"}</span>
            <StatusPill value="available" />
          </div>
        ))}
        {tab === "visual_jobs" && (data.visual_jobs || []).map((job) => (
          <div className="data-row" key={job.job_id}>
            <FileText size={22} />
            <div><strong>{job.source_name}</strong><span>{job.error || job.result?.document_summary || "等待结构化"}</span></div>
            <span>{job.model || (job.source_role === "drawing" ? "千问视觉主模型" : "千问批处理模型")}</span>
            <StatusPill value={job.status === "ready" ? "available" : job.status === "failed" ? "blocked" : "open"} />
          </div>
        ))}
        {!data[tab]?.length && <div className="empty-state">导入项目后，这里会显示可追溯的依据。</div>}
      </div>
    </section>
  );
}

function BlueprintView({ data, onToast }) {
  const [caseDir, setCaseDir] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const ingest = async () => {
    if (!caseDir.trim()) return;
    setIngesting(true);
    try {
      const result = await api("/api/cases/ingest", {
        method: "POST",
        body: JSON.stringify({
          project_dir: caseDir,
          project_type: data.project?.project_type || "",
          auto_visual: true,
        }),
      });
      onToast(`已学习案例：${result.case?.title || "公司成品"}；重新导入项目后进入参照库`);
      setCaseDir("");
    } catch (error) {
      onToast(error.message);
    } finally { setIngesting(false); }
  };
  return (
    <section className="workspace-view">
      <div className="view-heading"><div><h2>{data.blueprint?.title}</h2><p>受控版本 {data.blueprint?.version} · 历史案例只补充结构和资产，不覆盖项目事实。</p></div><StatusPill value="available" /></div>
      <div className="case-ingest panel">
        <div><strong>学习公司已通过成品</strong><span>资料夹内需同时包含招标文件和已通过技术标；系统提取结构、措辞和版式资产。</span></div>
        <input value={caseDir} onChange={(event) => setCaseDir(event.target.value)} placeholder="projects/passed_cases/某项目" />
        <button className="button secondary" onClick={ingest} disabled={!caseDir.trim() || ingesting}><UploadSimple size={18} />{ingesting ? "正在学习…" : "导入案例"}</button>
      </div>
      <div className="blueprint-grid">
        {data.sections.map((section) => (
          <article className="blueprint-section" key={section.code}>
            <span>{section.code}</span><div><h3>{section.title}</h3><p>{section.purpose}</p><small>{section.components.join(" · ")}</small></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TaskView({ data, onConfirm }) {
  return (
    <section className="workspace-view">
      <div className="view-heading">
        <div><h2>施组编制任务书</h2><p>确认每章要交付什么、依据什么、还缺什么，确认后才允许批量写正文。</p></div>
        <button className="button primary" onClick={onConfirm} disabled={!data.run_id || data.status !== "awaiting_confirmation"}><CheckCircle size={19} />确认任务书</button>
      </div>
      <div className="panel task-table">
        <table><thead><tr><th>章节</th><th>完成标准</th><th>交付组件</th><th>项目依据</th><th>编制依据</th><th>缺失输入</th></tr></thead>
          <tbody>{data.sections.map((section) => <tr key={section.code}><td><strong>{section.code} {section.title}</strong></td><td>{section.acceptance.join("；")}</td><td>{section.components.join("、")}</td><td>{section.project_basis.length} 项</td><td>{section.reference_basis.length} 项</td><td>{section.missing_inputs.length ? section.missing_inputs.join("、") : "—"}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function ChapterView({ data, selected, onSelect, onGenerate }) {
  const section = selected || data.sections[0];
  const generation = data.generation || {};
  return (
    <section className="workspace-view chapter-view">
      <div className="chapter-list panel">
        <div className="panel-heading"><div><h2>章节目录</h2><span>{data.sections.length} 章</span></div></div>
        {data.sections.map((item) => <button key={item.code} className={item.code === section?.code ? "active" : ""} onClick={() => onSelect(item)}><span>{item.code}</span><div><strong>{item.title}</strong><small>{item.completion}% · {item.components.length} 个组件</small></div></button>)}
      </div>
      <div className="chapter-detail panel">
        {section && <>
          <div className="panel-heading"><div><h2>{section.code} {section.title}</h2><span>{section.purpose}</span></div><StatusPill value={section.status} /></div>
          <h3>应交付组件</h3><div className="component-list">{section.components.map((item) => <div key={item}><FileText size={20} /><span>{item}</span><StatusPill value={section.status === "generated" ? "generated" : "not_started"} /></div>)}</div>
          <h3>完成标准</h3><ul>{section.acceptance.map((item) => <li key={item}>{item}</li>)}</ul>
          {section.content && <><h3>已生成正文预览</h3><pre className="content-preview">{section.content}</pre></>}
        </>}
      </div>
      <aside className="basis-panel panel">
        <div className="panel-heading"><div><h2>章节依据</h2><span>生成正文时只使用以下内容</span></div></div>
        <h3>项目依据</h3>{section?.project_basis.map((item) => <p key={item}>{item}</p>)}{!section?.project_basis.length && <em>暂无已核验项目依据</em>}
        <h3>编制依据</h3>{section?.reference_basis.map((item) => <p key={item}>{item}</p>)}
        <h3>缺失输入</h3>{section?.missing_inputs.map((item) => <p className="missing" key={item}>{item}</p>)}{!section?.missing_inputs.length && <em>本章输入已齐备</em>}
        {data.status === "generating" && (
          <div className="generation-progress">
            <strong>DeepSeek 正在并行生成</strong>
            <span>{generation.completed || 0} / {generation.total || data.sections.length} 章完成</span>
            <div className="bar"><i style={{ width: `${Math.round((generation.completed || 0) / Math.max(generation.total || data.sections.length, 1) * 100)}%` }} /></div>
            <small>任务在后台运行，可以切换页面。</small>
          </div>
        )}
        <button className="button primary wide" onClick={onGenerate} disabled={!data.run_id || !["ready_for_generation", "generation_failed", "partial_draft"].includes(data.status)}><PlayCircle size={19} />{data.status === "generating" ? "正在生成全部章节" : data.status === "generation_failed" ? "恢复并重试失败章节" : "批量生成全部章节"}</button>
      </aside>
    </section>
  );
}

function ReviewView({ data, onResolve, onResolveDifference }) {
  const [filter, setFilter] = useState("open");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 30;
  const confirmationRows = data.confirmations
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      if (filter === "open" && item.status !== "open") return false;
      if (filter === "resolved" && item.status === "open") return false;
      if (filter === "high" && !(item.status === "open" && item.severity === "high")) return false;
      const haystack = `${item.title} ${item.detail} ${item.category} ${(item.affected_sections || []).join(" ")}`;
      return haystack.toLowerCase().includes(query.trim().toLowerCase());
    });
  const pageCount = Math.max(1, Math.ceil(confirmationRows.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const visibleConfirmations = confirmationRows.slice(safePage * pageSize, (safePage + 1) * pageSize);
  return (
    <section className="workspace-view">
      <div className="view-heading"><div><h2>复核中心</h2><p>冲突、缺失和模型分歧不会被系统自动投票掩盖。</p></div></div>
      <div className="review-columns">
        <section className="panel">
          <div className="panel-heading"><div><h2>待确认事项</h2><span>{data.confirmations.filter((item) => item.status === "open").length} 项未关闭</span></div></div>
          <div className="review-toolbar">
            <div className="search"><MagnifyingGlass size={17} /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="搜索标题、来源或影响章节" /></div>
            <select aria-label="确认项筛选" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(0); }}>
              <option value="open">未关闭</option>
              <option value="high">高风险</option>
              <option value="resolved">已处理</option>
              <option value="all">全部</option>
            </select>
          </div>
          {visibleConfirmations.map(({ item, index }) => <article className={`finding ${item.severity}`} key={`${item.title}-${index}`}><Warning size={22} /><div><strong>{item.title}</strong><p>{item.detail}</p><small>{item.category} · 影响：{item.affected_sections.join("、") || "全局"}</small></div><div className="finding-actions"><StatusPill value={item.status} />{item.status === "open" && <button className="text-button compact-link" onClick={() => onResolve(index)}>标记已处理</button>}</div></article>)}
          {!visibleConfirmations.length && <div className="empty-state">当前筛选条件下没有确认项。</div>}
          <div className="pagination">
            <button className="button secondary compact" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>上一页</button>
            <span>第 {safePage + 1} / {pageCount} 页 · {confirmationRows.length} 项</span>
            <button className="button secondary compact" disabled={safePage + 1 >= pageCount} onClick={() => setPage(safePage + 1)}>下一页</button>
          </div>
        </section>
        <section className="panel"><div className="panel-heading"><div><h2>模型差异</h2><span>不一致时交由人工判断</span></div></div>{data.model_differences.length ? data.model_differences.map((item, index) => <article className="finding" key={index}><ShieldCheck size={22} /><div><strong>{item.task}</strong><p>{typeof item.difference === "string" ? item.difference : JSON.stringify(item.difference, null, 2)}</p><small>{item.primary_model} ↔ {item.review_model}</small></div><div className="finding-actions"><StatusPill value={item.status} />{item.status === "open" && <button className="text-button compact-link" onClick={() => onResolveDifference(index)}>记录人工结论</button>}</div></article>) : <div className="empty-state">当前没有已记录的模型差异。</div>}</section>
      </div>
    </section>
  );
}

function DeliveryView({ data, onReports, onReview }) {
  const reports = Object.entries(data.reports || {});
  const assets = Object.entries(data.assets || {});
  return (
    <section className="workspace-view">
      <div className="view-heading"><div><h2>交付中心</h2><p>所有报告都来自当前生产状态，可随项目更新重新生成。</p></div><div className="heading-actions"><button className="button secondary" onClick={onReview} disabled={!data.docx?.docx_path}><ShieldCheck size={18} />重新执行四项复核</button><button className="button primary" onClick={onReports} disabled={!data.run_id}><ArrowClockwise size={18} />重新生成报告</button></div></div>
      <div className="delivery-grid">
        {reports.map(([key, path]) => <article className="delivery-card" key={key}><FileDoc size={30} /><div><strong>{path.split(/[\\/]/).pop()}</strong><span>{path}</span></div><a href={`/api/files?path=${encodeURIComponent(path)}`}>打开文件</a></article>)}
        {assets.map(([key, path]) => <article className="delivery-card" key={key}><SquaresFour size={30} /><div><strong>{path.split(/[\\/]/).pop()}</strong><span>可编辑图表源文件</span></div><a href={`/api/files?path=${encodeURIComponent(path)}`}>打开文件</a></article>)}
        {data.docx?.docx_path && <article className="delivery-card featured"><FileDoc size={30} /><div><strong>施工组织设计_初稿.docx</strong><span>{data.docx.docx_path}</span></div><a href={`/api/files?path=${encodeURIComponent(data.docx.docx_path)}`}>打开文件</a></article>}
        {!reports.length && <div className="empty-state panel">导入项目后，系统会自动生成六份控制与复核报告。</div>}
      </div>
    </section>
  );
}

export function App() {
  const [data, setData] = useState(null);
  const [active, setActive] = useState("overview");
  const [selected, setSelected] = useState(null);
  const [importOpen, setImportOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      setData(await api("/api/dashboard"));
    } catch (error) {
      setToast(error.message);
    }
  };
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (!["generating", "analyzing_visuals"].includes(data?.status) || !data.run_id) return undefined;
    const timer = setInterval(async () => {
      try {
        const next = await api(`/api/dashboard?run_id=${data.run_id}`);
        setData(next);
        if (["draft_generated", "partial_draft"].includes(next.status)) {
          setActive("delivery");
          setToast(next.status === "draft_generated" ? "施工组织设计初稿已生成" : "初稿已生成，部分章节需要人工补充");
        }
        if (next.status === "generation_failed") setToast(next.generation?.error || "章节生成失败");
        if (next.status === "awaiting_confirmation" && data.status === "analyzing_visuals") {
          setActive("task");
          setToast("多模态资料分析已完成，请复核并确认编制任务书");
        }
        if (next.status === "visual_analysis_failed") setToast(next.visual_analysis?.error || "视觉资料分析失败");
      } catch (error) {
        setToast(error.message);
      }
    }, 2200);
    return () => clearInterval(timer);
  }, [data?.status, data?.run_id]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4200);
    return () => clearTimeout(timer);
  }, [toast]);

  const runAction = async (kind) => {
    if (!data?.run_id) {
      setImportOpen(true);
      return;
    }
    setBusy(true);
    try {
      if (kind === "continue") {
        if (data.status === "awaiting_role_confirmation") setActive("sources");
        else if (data.status === "awaiting_confirmation") setActive("task");
        else if (data.status === "ready_for_generation") setActive("chapters");
        else setActive("delivery");
      } else if (kind === "reports") {
        const reports = await api(`/api/runs/${data.run_id}/export-reports`, { method: "POST" });
        setData({ ...data, reports });
        setToast("六份生产控制报告已更新");
      }
    } catch (error) {
      setToast(error.message);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    try {
      const next = await api(`/api/runs/${data.run_id}/confirm-task-spec`, {
        method: "POST",
        body: JSON.stringify({ confirmed: true }),
      });
      setData(next);
      setActive("chapters");
      setToast("编制任务书已确认，章节生成已解锁");
    } catch (error) {
      setToast(error.message);
    } finally { setBusy(false); }
  };

  const confirmRoles = async () => {
    setBusy(true);
    try {
      const next = await api(`/api/runs/${data.run_id}/confirm-file-roles`, { method: "POST" });
      setData(next);
      if (next.status === "visual_analysis_pending") {
        setActive("sources");
        setToast("文件角色已确认，请运行多模态资料分析");
      } else {
        setActive("task");
        setToast("文件角色已确认，编制任务书已解锁");
      }
    } catch (error) {
      setToast(error.message);
    } finally { setBusy(false); }
  };

  const analyzeVisuals = async () => {
    setBusy(true);
    try {
      const next = await api(`/api/runs/${data.run_id}/analyze-visuals`, { method: "POST" });
      setData(next);
      setToast("千问正在后台结构化扫描件、表格和图纸；争议项按需交给智谱复核");
    } catch (error) {
      setToast(error.message);
    } finally { setBusy(false); }
  };

  const resolveConfirmation = async (index) => {
    try {
      const next = await api(`/api/runs/${data.run_id}/confirmations/${index}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "resolved", resolution: "人工已核对" }),
      });
      setData(next);
      setToast("待确认事项已标记为处理完成");
    } catch (error) {
      setToast(error.message);
    }
  };

  const resolveDifference = async (index) => {
    try {
      const next = await api(`/api/runs/${data.run_id}/model-differences/${index}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "resolved", resolution: "已对照来源页面人工确认" }),
      });
      setData(next);
      setToast("模型差异已记录人工处理结果");
    } catch (error) {
      setToast(error.message);
    }
  };

  const generate = async () => {
    setBusy(true);
    setToast("DeepSeek 已进入后台并行生成，可以切换页面");
    try {
      const next = await api(`/api/runs/${data.run_id}/generate-docx`, { method: "POST" });
      setData(next);
    } catch (error) {
      setToast(error.message);
    } finally { setBusy(false); }
  };

  const reviewDraft = async () => {
    setBusy(true);
    setToast("正在重新执行要求覆盖、文档结构、DeepSeek文字和视觉复核");
    try {
      const next = await api(`/api/runs/${data.run_id}/review-draft`, { method: "POST" });
      setData(next);
      setToast("四项复核已更新");
    } catch (error) {
      setToast(error.message);
    } finally { setBusy(false); }
  };

  const page = useMemo(() => {
    if (!data) return null;
    if (active === "sources") return <SourcesView data={data} onData={setData} onToast={setToast} onConfirmRoles={confirmRoles} onAnalyzeVisuals={analyzeVisuals} />;
    if (active === "blueprint") return <BlueprintView data={data} onToast={setToast} />;
    if (active === "task") return <TaskView data={data} onConfirm={confirm} />;
    if (active === "chapters") return <ChapterView data={data} selected={selected} onSelect={setSelected} onGenerate={generate} />;
    if (active === "review") return <ReviewView data={data} onResolve={resolveConfirmation} onResolveDifference={resolveDifference} />;
    if (active === "delivery") return <DeliveryView data={data} onReports={() => runAction("reports")} onReview={reviewDraft} />;
    return <Overview data={data} setActive={setActive} onSelectSection={(item) => { setSelected(item); setActive("chapters"); }} onAction={runAction} />;
  }, [active, data, selected]);

  if (!data) return <div className="loading-screen"><ArrowClockwise className="spin" size={30} />正在载入生产工作台…</div>;

  return (
    <div className="app-shell">
      <Sidebar active={active} onChange={setActive} data={data} />
      <main className="app-main">
        <Header data={data} onImport={() => setImportOpen(true)} onRefresh={refresh} />
        <div className="content">{page}</div>
      </main>
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} onPrepared={(next) => { setData(next); setActive("sources"); setToast("资料已分类，请先核对并确认文件角色"); }} />
      {toast && <div className="toast">{busy && <ArrowClockwise className="spin" size={18} />}{toast}</div>}
    </div>
  );
}
