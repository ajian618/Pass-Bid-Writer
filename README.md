# 通过制技术标制标助手

## 新版施工组织设计生产工作台

新版把“直接让模型写一本标书”改成可追溯的生产流程：项目证据库负责说明本项目
真实是什么，编制参照库负责说明成品为什么要有、应当做到什么程度。每章正文、
表格和图形任务都同时记录项目依据、编制依据和待人工确认项。

启动工作台：

```powershell
cd C:\Users\ajian\Documents\通过制标书撰写
.\scripts\start-workbench.ps1
```

然后打开：

```text
http://127.0.0.1:8000
```

首次使用时，在“导入项目”中选择包含招标文件、初设、预算、图纸包和附件的
项目资料夹。推荐工作顺序：

1. 在“资料与依据”中确认每个文件角色。
2. 若存在 PDF 页面、扫描件、复杂表格或图纸，运行千问视觉结构化；没有密钥时系统明确转入人工复核，不伪装成已完成。
3. 上传系统列出的规范原文；无法公开下载的规范会进入待下载清单。
4. 检查《施组编制任务书》的目录、表图、依据链接和缺失资料。
5. 确认任务书后，由 DeepSeek 在后台按章并行生成正文；中断后只重试失败章节。
6. 在“复核中心”处理缺失、冲突、模型差异和确定性数字拦截项。
7. 在“交付中心”重新执行要求覆盖、DOCX结构、DeepSeek一致性和视觉复核。
8. 打开 DOCX、六份控制报表和 `assets` 图表源文件，人工补齐待确认参数后再导出 PDF。

生产系统的强制门禁顺序是：

```text
writing_prepare_production_system
→ writing_confirm_production_file_roles
→ writing_analyze_production_visual_sources（有视觉资料时）
→ writing_confirm_production_task_spec
→ writing_generate_production_docx
→ writing_get_production_status
→ writing_review_production_draft
→ writing_export_production_reports
```

系统会生成原生 Word 表格、SVG/PNG 流程图、组织机构图和进度结构图。模型输出的
Mermaid、ASCII 图、无依据数量、未经验证的条款引用和历史案例参数在装配前会被
确定性检查拦截。

工作台不会把模型记忆当作项目参数或规范条文，也不会承诺投标通过。PDF 应在
人工修改 DOCX 后再导出和执行视觉检查。

这个项目是一个独立的 Hermes 制标工作区，核心是 `pass-bid-writing`
MCP。它和之前的 `bid-review` MCP 分开：

- `bid-review`：用于标书评审、证据检索、保存评审报告。
- `pass-bid-writing`：用于通过制技术标制作、案例学习、DOCX 初稿生成、PDF 导出。

Hermes 仍然是主控；本项目只给 Hermes 提供本地工具、数据库和文档输出能力。

## 1. 当前已经安装好的东西

本机已经创建并切换到 Hermes profile：

```text
pass-bid-writer
```

这个 profile 已注册 MCP：

```text
pass-bid-writing
```

确认命令：

```powershell
hermes profile show pass-bid-writer
hermes mcp list
hermes mcp test pass-bid-writing
```

正常结果应看到：

```text
Profile: pass-bid-writer
pass-bid-writing ✓ enabled
Tools discovered: 21
```

## 2. 怎么启动这个制标 profile

推荐用：

```powershell
pass-bid-writer chat
```

`pass-bid-writer` 是 Hermes 自动创建的 wrapper，已经在本机 PATH 里。它的本质等价于：

```powershell
hermes -p pass-bid-writer
```

所以这些写法都可以：

```powershell
pass-bid-writer chat
pass-bid-writer -z "列出你当前可用的 pass-bid-writing 工具"
hermes -p pass-bid-writer chat
```

日常建议用 `pass-bid-writer chat`，因为它最明确。

## 3. 推荐资料目录

新版推荐直接把资料按项目放到本仓库下：

```text
projects\passed_cases\<已通过项目名>\
projects\new_tenders\<待撰写项目名>\
```

`passed_cases` 放已经通过的项目资料，`new_tenders` 放要 Hermes 写的新项目资料。
每个项目文件夹里可以直接堆 PDF/DOCX/TXT/MD，不强制再分子目录。工具会根据文件名和内容角色推断“招标文件”“已通过技术标”“附件”。

兼容旧口语目录：

```text
projects\passed\<已通过项目名>\
projects\unpassed\<待撰写项目名>\
```

但新资料建议用 `passed_cases` 和 `new_tenders`，比 `unpassed` 更不容易被理解成“未通过废标”。

扫描资料库：

```text
请扫描 projects 资料库，列出已通过案例和待撰写项目。
```

它会调用 `writing_scan_projects`。

## 4. 怎么喂一套通过制案例

推荐把一套资料放成：

```text
projects\passed_cases\某河道治理项目\招标文件.pdf
projects\passed_cases\某河道治理项目\已通过技术标.pdf
```

进入 Hermes：

```powershell
cd C:\Users\ajian\Documents\通过制标书撰写
pass-bid-writer chat
```

然后直接发项目文件夹：

```text
请学习这个已通过项目：
C:\Users\ajian\Documents\通过制标书撰写\projects\passed_cases\某河道治理项目
```

它会调用 `writing_ingest_passed_case`，抽正文、章节结构、响应习惯，并默认把 PDF/DOCX 渲染成页面截图做视觉版式分析。

如果你仍然只有两个散落文件，也可以继续使用旧方式。现在 `pass-bid-writer`
的 SOUL 和 `AGENTS.md` 已经写了意图路由规则：看到“招标文件 + 已通过技术标”时，
它应该自己判断这是案例学习任务，并调用 `writing_ingest_case_pair`。

推荐自然语言：

```text
请学习这一套通过制案例：

招标文件：C:\资料\某河道治理项目\招标文件.pdf
已通过技术标：C:\资料\某河道治理项目\已通过技术标.docx

项目类型：河道治理
地区：浙江
标签：水利,通过制,河道治理

请沉淀章节结构、硬性响应项、常用施工组织写法、水利专项场景和人工复核风险点。
```

调试时也可以把工具名说得更死：

```text
请使用 pass-bid-writing MCP 的 writing_ingest_case_pair 工具学习这一套通过制案例：

招标文件：C:\资料\某河道治理项目\招标文件.pdf
已通过技术标：C:\资料\某河道治理项目\已通过技术标.docx

项目类型：河道治理
地区：浙江
标签：水利,通过制,河道治理

请沉淀章节结构、硬性响应项、常用施工组织写法、水利专项场景和人工复核风险点。
```

只要 Hermes 调用了 `writing_ingest_case_pair`，数据就会进入本项目数据库：

```text
C:\Users\ajian\Documents\通过制标书撰写\storage\pass_bid_writing.db
```

如果它没有自动调用工具，说明文件角色或路径不够清楚。此时再补一句：

```text
这是成对通过案例，请调用 writing_ingest_case_pair 入库。
```

## 5. 怎么用新招标文件生成通过制技术标初稿

推荐把新项目资料放成：

```text
projects\new_tenders\某新项目\招标文件.pdf
projects\new_tenders\某新项目\补充说明.pdf
```

然后对 Hermes 说：

```text
请根据这个待撰写项目生成一份通过制技术标 Word 初稿：
C:\Users\ajian\Documents\通过制标书撰写\projects\new_tenders\某新项目

请先抽取招标要求和响应矩阵，再参考历史通过案例写法和版式，最后生成 DOCX、导出 PDF 视觉检查，并做一次漏项检查。
不要虚构项目参数，缺少信息的地方标成人工确认项。
```

生成结果默认在：

```text
projects\new_tenders\某新项目\outputs\
```

推荐自然语言：

```text
请根据这个新招标文件生成一份通过制技术标 Word 初稿：
C:\资料\新项目\招标文件.pdf

请先抽取招标要求和响应矩阵，再参考历史通过案例写法，最后生成 DOCX 并做一次漏项检查。
不要虚构项目参数，缺少信息的地方标成人工确认项。
```

在调试或它没有自动走工具时，再使用更明确的版本：

```text
请使用 pass-bid-writing MCP 处理这个新招标文件：
C:\资料\新项目\招标文件.pdf

依次调用 writing_extract_tender_requirements、writing_build_response_matrix、
writing_search_case_patterns、writing_generate_outline、writing_generate_docx、
writing_check_draft_compliance。
```

如果只给单个招标文件，不使用项目资料夹，生成的 Word 默认在：

```text
storage\drafts\
```

如果确认 Word 可以定稿，再让 Hermes 导出 PDF：

```text
请调用 writing_export_pdf，把刚才生成的 DOCX 导出为 PDF。
```

本机已验证可以通过 Microsoft Word COM 导出 PDF。

## 6. 视觉模型怎么配置

Hermes 主模型可以继续用 DeepSeek。多模态模型只作为 `pass-bid-writing`
MCP 里的视觉副脑，用来读取 PDF/Word 渲染后的页面截图，并返回结构化版式
JSON。当前实现不是调用 DashScope SDK，而是直接调用百炼 OpenAI 兼容
Chat Completions HTTP 接口。

默认推荐阿里云百炼：

```powershell
cd C:\Users\<公司电脑用户名>\Documents\通过制标书撰写
.\scripts\configure-vision.ps1 -Provider aliyun_qwen -Model qwen3.7-plus-2026-05-26
```

脚本会提示输入百炼 API Key，并写入仓库根目录的 `.env`。这个文件默认不进
Git；`pass-bid-writing` MCP 启动时会自动加载它，所以电脑重启后也不用重新
输入。

百炼中国内地/北京地域默认会写入：

```text
PASS_BID_VISION_PROVIDER="aliyun_qwen"
PASS_BID_VISION_MODEL="qwen3.7-plus-2026-05-26"
PASS_BID_BATCH_MODEL="qwen3.6-flash-2026-04-16"
PASS_BID_VISION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_API_KEY="..."
```

代码实际发请求时会把 base URL 拼成：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

如果你的百炼账号使用新加坡或美国地域，可以用 `-BaseUrl` 显式覆盖。例如：

```powershell
.\scripts\configure-vision.ps1 -Provider aliyun_qwen -Model qwen3.7-plus-2026-05-26 -BaseUrl "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
```

也可以切到 Kimi：

```powershell
.\scripts\configure-vision.ps1 -Provider kimi -Model kimi-k2.6
```

或豆包：

```powershell
.\scripts\configure-vision.ps1 -Provider doubao -Model 你的火山方舟视觉模型ID
```

如果要临时关闭视觉模型：

```powershell
.\scripts\configure-vision.ps1 -Disable
```

如果没有配置 API key，工具不会崩溃；它会完成本地渲染并返回
`not_configured`，提醒人工复核最终 PDF 观感。

配置完成后建议跑一次无公司资料的连通性测试：

```powershell
.\scripts\test-vision-config.ps1
```

这个脚本会生成一个临时测试 PDF，渲染成图片，然后调用当前 `.env` 里的模型。
看到 `status` 为 `ready` 就说明 base URL、API Key 和模型名称都能正常调用。

## 7. 这个 MCP 有哪些工具

```text
writing_ingest_case_pair
writing_scan_projects
writing_ingest_passed_case
writing_prepare_new_tender
writing_extract_layout_profile
writing_prepare_production_system
writing_confirm_production_file_roles
writing_analyze_production_visual_sources
writing_confirm_production_task_spec
writing_get_production_status
writing_generate_production_docx
writing_review_production_draft
writing_export_production_reports
writing_extract_tender_requirements
writing_build_response_matrix
writing_search_case_patterns
writing_generate_outline
writing_generate_docx
writing_check_draft_compliance
writing_visual_check_document
writing_export_pdf
```

工具分工：

- `writing_ingest_case_pair`：导入“招标文件 + 已通过技术标”成对案例。
- `writing_scan_projects`：扫描 `projects\passed_cases` / `projects\new_tenders` 资料库。
- `writing_ingest_passed_case`：导入一个已通过项目文件夹，并默认做视觉版式分析。
- `writing_prepare_new_tender`：准备一个待撰写项目文件夹，抽要求、矩阵和版式要求。
- `writing_extract_layout_profile`：从 PDF/DOCX 页面截图中抽取版式 profile。
- `writing_prepare_production_system`：建立项目证据库、规范清单、案例资产和编制任务书。
- `writing_confirm_production_file_roles`：确认招标文件、初设、预算、图纸和附件角色。
- `writing_analyze_production_visual_sources`：用千问结构化视觉资料，争议项按需交给 GLM。
- `writing_confirm_production_task_spec`：执行正文生成前的强制任务书确认门禁。
- `writing_get_production_status`：查询后台视觉分析或章节生成进度。
- `writing_generate_production_docx`：用 DeepSeek 按章生成并装配 DOCX、原生表格和图形。
- `writing_review_production_draft`：重跑要求覆盖、结构、文字一致性和视觉检查。
- `writing_export_production_reports`：重新导出六份受控生产报告。
- `writing_extract_tender_requirements`：抽取新招标文件中的技术标要求。
- `writing_build_response_matrix`：建立“招标要求 -> 标书章节”的响应矩阵。
- `writing_search_case_patterns`：检索已通过案例里的结构、片段和写法。
- `writing_generate_outline`：生成通过制技术标目录。
- `writing_generate_docx`：生成可编辑 Word 初稿，默认含封面、目录、页眉页脚、页码；可把 Markdown 表格渲染成真正的 Word 表格，可应用版式 profile 里的颜色、字体、表头底色、封面文字和封面强调色，并自动做视觉检查。
- `writing_check_draft_compliance`：反向检查漏项、占位符和人工确认项。
- `writing_visual_check_document`：渲染 DOCX/PDF 并检查最终 PDF 观感。
- `writing_export_pdf`：把 DOCX 导出为 PDF。

## 8. 公司电脑部署和升级步骤

### 8.1 从上一版升级

公司电脑如果已经正常运行上一版，并且 `pass-bid-writer` 飞书机器人已经接好，
不要重新执行 `pass-bid-writer gateway setup`。只更新仓库、依赖、MCP 注册和
SOUL 即可：

```powershell
cd C:\Users\<公司电脑用户名>\Documents\通过制标书撰写
git pull --ff-only origin main
py -3.12 -m pip install -r requirements.txt
.\scripts\register-hermes-mcp.ps1
.\scripts\configure-vision.ps1 -Provider aliyun_qwen -Model qwen3.7-plus-2026-05-26
.\scripts\test-vision-config.ps1
hermes mcp test pass-bid-writing
```

看到 `Tools discovered: 21` 就说明新版 MCP 已加载。

如果公司电脑的飞书网关正在后台运行，升级后重启网关，让它加载新版代码和
SOUL：

```powershell
pass-bid-writer gateway status
pass-bid-writer gateway stop
pass-bid-writer gateway start
pass-bid-writer gateway status
```

注意：这一步只是重启已配置好的网关，不会重新配置飞书应用。开发机没有配置
飞书机器人时，不需要运行这些 gateway 命令。

### 8.2 准备环境

新电脑首次部署需要：

- Python 3.12
- Git
- Hermes Agent
- Microsoft Word，若要本机导出 PDF

如果 PowerShell 禁止运行脚本，先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

临时绕过也可以：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

### 8.3 拉取或复制项目

如果已经有 Git 仓库：

```powershell
cd C:\Users\<公司电脑用户名>\Documents
git clone <你的仓库地址> 通过制标书撰写
cd 通过制标书撰写
```

如果是直接拷贝文件夹，也可以把整个目录复制到：

```text
C:\Users\<公司电脑用户名>\Documents\通过制标书撰写
```

### 8.4 安装依赖

```powershell
cd C:\Users\<公司电脑用户名>\Documents\通过制标书撰写
py -3.12 -m pip install -r requirements.txt
```

### 8.5 注册 Hermes profile 和 MCP

```powershell
.\scripts\register-hermes-mcp.ps1
```

这个脚本会做几件事：

- 创建或更新 `pass-bid-writer` profile。
- 把 `config\hermes\pass-bid-writer-SOUL.md` 安装到该 profile。
- 注册 `pass-bid-writing` MCP。
- 把 Hermes 的 `terminal.cwd` 指到当前项目目录。
- 从 `pass-bid-writer` profile 中移除 `bid-review` MCP，保持制标和评审隔离。
- 切换当前 Hermes profile 到 `pass-bid-writer`。

### 8.6 验证

```powershell
hermes profile show pass-bid-writer
hermes mcp list
hermes mcp test pass-bid-writing
py -3.12 -m unittest discover -s tests -v
```

看到 `Tools discovered: 21` 就说明 MCP 正常。

### 8.7 启动

```powershell
pass-bid-writer chat
```

如果提示找不到 `pass-bid-writer`，先开一个新的 PowerShell 窗口再试。仍然不行时，用完整写法：

```powershell
hermes -p pass-bid-writer chat
```

## 9. 数据怎么迁移

制标案例和草稿默认在：

```text
storage\pass_bid_writing.db
storage\drafts\
```

`storage\` 默认不进 Git。换电脑时有两种办法：

1. 在新电脑重新喂案例，重新沉淀。
2. 把旧电脑的 `storage\` 整个复制过去。

如果公司后续多人共用，可以再升级成共享数据库或同步目录；第一版先保持本地简单可靠。

## 10. 飞书机器人能不能单独配给这个 profile

可以，而且建议单独配。

Hermes 的 profile 是隔离的：每个 profile 有自己的 `.env`、`config.yaml`、`SOUL.md`、记忆、会话、日志和 gateway 状态。所以 `pass-bid-writer` 可以配置自己的飞书机器人，不和默认 Hermes 或 `bid-review` 混用。

推荐方式：

```powershell
pass-bid-writer gateway setup
```

在向导里选择 Feishu/Lark，填入这个制标机器人自己的：

```text
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_DOMAIN=feishu
FEISHU_CONNECTION_MODE=websocket
```

配置完成后启动：

```powershell
pass-bid-writer gateway run
```

如果要开机自动运行，可尝试：

```powershell
pass-bid-writer gateway install
pass-bid-writer gateway start
pass-bid-writer gateway status
```

注意：不要让多个 profile 同时使用同一个飞书应用凭据。更稳的做法是给制标助手单独建一个飞书机器人应用。

## 11. 常用检查命令

```powershell
Get-Command pass-bid-writer
pass-bid-writer --help
pass-bid-writer gateway status
pass-bid-writer pairing list
hermes profile list
hermes profile show pass-bid-writer
hermes mcp test pass-bid-writing
```

## 12. 当前限制

- PDF/DOCX 现在支持页面渲染和视觉模型版式分析；扫描件 OCR 质量仍取决于多模态模型和源文件清晰度。
- 合规检查是启发式反向检查，不等于法律或专家保证。
- 通过制标书仍需要人工核查格式、签章、项目参数、人员设备和最终 PDF。
- 现在是本地数据库；多人协作和统一知识库是后续阶段。
