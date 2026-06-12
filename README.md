# 通过制技术标制标助手

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
Tools discovered: 8
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

## 3. 怎么喂一套通过制案例

准备一套成对资料：

```text
招标文件：C:\资料\某河道治理项目\招标文件.pdf
已通过技术标：C:\资料\某河道治理项目\已通过技术标.docx
```

进入 Hermes：

```powershell
cd C:\Users\ajian\Documents\通过制标书撰写
pass-bid-writer chat
```

然后直接把文件路径发给它，并明确要求入库：

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

注意：不是把文件路径一贴就一定自动入库。你要在提示词里明确说“调用
`writing_ingest_case_pair` 入库/学习这套案例”。这样最稳。

## 4. 怎么用新招标文件生成通过制技术标初稿

推荐提示：

```text
请使用 pass-bid-writing MCP 处理这个新招标文件：
C:\资料\新项目\招标文件.pdf

工作步骤：
1. 调用 writing_extract_tender_requirements 抽取通过制技术标要求。
2. 调用 writing_build_response_matrix 生成响应矩阵。
3. 调用 writing_search_case_patterns 检索历史通过案例写法。
4. 调用 writing_generate_outline 生成目录。
5. 你先输出完整章节正文草稿。
6. 调用 writing_generate_docx 生成 Word 初稿。
7. 调用 writing_check_draft_compliance 做反向检查。

目标：生成一份可人工复核的通过制技术标 DOCX 初稿，不要虚构项目参数。
```

生成的 Word 默认在：

```text
storage\drafts\
```

如果确认 Word 可以定稿，再让 Hermes 导出 PDF：

```text
请调用 writing_export_pdf，把刚才生成的 DOCX 导出为 PDF。
```

本机已验证可以通过 Microsoft Word COM 导出 PDF。

## 5. 这个 MCP 有哪些工具

```text
writing_ingest_case_pair
writing_extract_tender_requirements
writing_build_response_matrix
writing_search_case_patterns
writing_generate_outline
writing_generate_docx
writing_check_draft_compliance
writing_export_pdf
```

工具分工：

- `writing_ingest_case_pair`：导入“招标文件 + 已通过技术标”成对案例。
- `writing_extract_tender_requirements`：抽取新招标文件中的技术标要求。
- `writing_build_response_matrix`：建立“招标要求 -> 标书章节”的响应矩阵。
- `writing_search_case_patterns`：检索已通过案例里的结构、片段和写法。
- `writing_generate_outline`：生成通过制技术标目录。
- `writing_generate_docx`：生成可编辑 Word 初稿。
- `writing_check_draft_compliance`：反向检查漏项、占位符和人工确认项。
- `writing_export_pdf`：把 DOCX 导出为 PDF。

## 6. 公司电脑部署步骤

### 6.1 准备环境

公司电脑需要：

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

### 6.2 拉取或复制项目

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

### 6.3 安装依赖

```powershell
cd C:\Users\<公司电脑用户名>\Documents\通过制标书撰写
py -3.12 -m pip install -r requirements.txt
```

### 6.4 注册 Hermes profile 和 MCP

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

### 6.5 验证

```powershell
hermes profile show pass-bid-writer
hermes mcp list
hermes mcp test pass-bid-writing
py -3.12 -m unittest discover -s tests -v
```

看到 `Tools discovered: 8` 就说明 MCP 正常。

### 6.6 启动

```powershell
pass-bid-writer chat
```

如果提示找不到 `pass-bid-writer`，先开一个新的 PowerShell 窗口再试。仍然不行时，用完整写法：

```powershell
hermes -p pass-bid-writer chat
```

## 7. 数据怎么迁移

制标案例和草稿默认在：

```text
storage\pass_bid_writing.db
storage\drafts\
```

`storage\` 默认不进 Git。换电脑时有两种办法：

1. 在新电脑重新喂案例，重新沉淀。
2. 把旧电脑的 `storage\` 整个复制过去。

如果公司后续多人共用，可以再升级成共享数据库或同步目录；第一版先保持本地简单可靠。

## 8. 飞书机器人能不能单独配给这个 profile

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

## 9. 常用检查命令

```powershell
Get-Command pass-bid-writer
pass-bid-writer --help
pass-bid-writer gateway status
pass-bid-writer pairing list
hermes profile list
hermes profile show pass-bid-writer
hermes mcp test pass-bid-writing
```

## 10. 当前限制

- PDF/DOCX 解析以文本抽取为主，扫描件或复杂表格可能需要 OCR/人工整理。
- 合规检查是启发式反向检查，不等于法律或专家保证。
- 通过制标书仍需要人工核查格式、签章、项目参数、人员设备和最终 PDF。
- 现在是本地数据库；多人协作和统一知识库是后续阶段。
