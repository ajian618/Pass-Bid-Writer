# 施工组织设计生产系统实施审计

审计日期：2026-06-30

## 结论

原重构方案的系统能力已经实现并完成真实端到端验证。系统可以从项目资料建立证据与参照体系，经人工门禁后使用 DeepSeek 生成 15 章施工组织设计，装配原生 Word 表格和图形，执行四类交付复核，并输出 DOCX、六份 XLSX 报告及 `assets/`。

这不等于任意项目导入后可直接投标。缺少图纸、工程量、人员、节点、规范原文或视觉模型密钥时，系统会保留人工确认项，不允许模型补造。

## 原计划覆盖情况

| 计划能力 | 实现位置 | 验证结果 |
|---|---|---|
| 项目证据库 | `schemas.py`、`production.py`、`db.py` | 项目事实保留文件、页码、表格单元格、图号和状态 |
| 编制参照库 | `blueprints.py`、`knowledge.py` | 蓝图、规范条款和案例资产分别受控 |
| 规范待下载与原文解析 | `knowledge.py`、`reports.py` | 可上传原文、校验编号、解析条款；缺失规范进入 XLSX 队列 |
| 公司成品蓝图 | `blueprints.py`、案例入库工具 | 历史参数脱敏，仅复用结构、规则和版式 |
| DeliverableBlueprint | `schemas.py`、`blueprints.py` | 15 章均有目的、组件、输入和完成标准 |
| 任务书确认门禁 | `production.py`、`api.py`、MCP | 文件角色、视觉任务、冲突和任务书均有强制门禁 |
| DeepSeek 文字主脑 | `model_router.py`、`production.py` | 支持并行、重试、断点续写、JSON 输出和最终一致性复核 |
| 千问视觉结构化 | `visual_sources.py` | PDF/图片/DXF 进入结构化视觉任务；无密钥明确转人工 |
| GLM 按需复核 | `visual_sources.py` | 仅低置信或冲突任务调用，不做自动投票 |
| 原生表格和图形 | `documents.py`、`assets.py` | Word 表格、SVG/PNG 流程图、组织图、进度结构图已嵌入 |
| 冲突和确认工作台 | `workbench/src/App.jsx` | 支持搜索、筛选、分页和人工处理结果 |
| 六份生产报告 | `reports.py` | 六个目标 XLSX 均可打开且通过工作簿检查 |
| DOCX/PDF 视觉检查 | `documents.py`、视觉检查工具 | Word COM 成功渲染；78 页逐页抽检无溢出或代码残留 |

## 真实端到端结果

- 生产运行：run 6，15/15 章完成。
- 招标要求覆盖：10/10，缺失 0。
- DOCX 结构：通过，49 个 Word 表格、5 张嵌入图形。
- 断点恢复：首次有 1 章 JSON 失败，第二次仅重试失败章并完成。
- 确定性拦截：无依据数量、历史参数、未验证条款、Mermaid、ASCII 图和 HTML 尾标均在装配前处理。
- 文档渲染：78 页；封面、目录、页眉页脚、表格、图形和响应矩阵正常。
- 浏览器走查：7 个主流程页面，控制台错误 0，横向溢出 0。
- MCP 连通：21 个工具成功发现。

## 尚需外部条件

- 当前机器未配置 `DASHSCOPE_API_KEY`，因此千问真实视觉调用未执行；系统已将其标为待配置/人工复核。
- `ZHIPU_API_KEY` 是按需复核项，只有视觉冲突或低置信任务才需要。
- E2E 样例故意缺少大量工程参数，因此初稿包含较多待人工确认项；这是防止虚构的验收结果，不是生成失败。
- `SL 223-2008` 原文尚未上传，仍位于规范待下载队列。

## 验收命令

```powershell
python -m pytest -q
python -m compileall -q pass_bid_writing
cd workbench
npm run build
cd ..
hermes mcp test pass-bid-writing
python scripts/e2e-production-smoke.py
```
