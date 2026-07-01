# Python 多模型施工组织设计生成台 V1

这是面向浙江水利工程通过制技术标的 Windows 单机生产台。它把招标文件、初设、预算、规范、设计图纸 PDF 和历史案例变成可追溯证据，再由 DeepSeek 逐章编写施工组织设计。

系统不依赖 Hermes、飞书、MCP 或 AutoCAD。DWG 只作为原始依据保存；V1 需要用户在 AutoCAD 中手动导出同名或近似文件名的 PDF。

## 首次安装

要求 Windows 10/11、64 位 Python 3.12。Node.js 只用于开发构建，正式发布包运行时不需要。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

安装脚本会创建：

```text
%LOCALAPPDATA%\PassBidWriter\
  venv\
  config\
  database\
  projects\
  cases\
  logs\
```

## 日常启动

```powershell
.\start.ps1
```

浏览器打开 `http://127.0.0.1:8000`。日常启动不会联网下载依赖。

## 从旧 Hermes 版本升级

旧版删除了大量已跟踪文件，因此升级前先看工作区是否存在本地修改。不要使用 `git reset --hard`。

### Git 工作区无本地修改

```powershell
cd C:\Users\taizhoushuijia\Documents\Pass-Bid-Writer
git status --short
git pull --ff-only origin main
Set-ExecutionPolicy -Scope Process Bypass
.\update.ps1 -SkipPull -CleanLegacyWorkspace
.\start.ps1
```

`-CleanLegacyWorkspace` 会删除仓库内旧 `.venv`、`storage`、`projects`、Hermes 缓存和前端依赖。只在旧资料已有备份时使用。它不会删除 `%LOCALAPPDATA%\PassBidWriter` 中的新 V1 数据。

### `git status --short` 有输出

先备份修改，再查看差异：

```powershell
git status --short
git diff
```

保留需要的文件后再执行 `git pull --ff-only origin main`。Git 的已跟踪文件冲突不是 `.gitignore` 导致的；升级脚本不会替你执行强制重置。

### 最稳妥的全新安装

如果旧目录非常乱，直接解压 `PassBidWriter-V1.1.0.zip` 到一个新目录，再运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\start.ps1
```

V1 不迁移旧数据库、旧学习数据和旧成果。旧目录可以保留为只读备份。

## 新电脑配置模型

安装并启动工作台后：

1. 打开 `http://127.0.0.1:8000`。
2. 点击右上角齿轮按钮“模型配置”。
3. 填写下表；模型名称留空时使用系统默认值。

| 工作台字段 | 必填 | 默认模型 | 用途 |
|---|---|---|---|
| DeepSeek API Key | 是 | `deepseek-v4-pro` | 任务书归纳、逐章正文、重写和文字复核 |
| 阿里云百炼 API Key | 是 | `qwen3.7-plus-2026-05-26` | 扫描件、复杂表格和图纸 PDF |
| 千问批处理模型 | 自动 | `qwen3.6-flash-2026-04-16` | OCR、页面分类和普通字段抽取 |
| 智谱 API Key | 否 | `glm-5v-turbo` | 只复核关键图纸、低置信数字和视觉冲突 |

4. 点击“保存配置”。
5. 回到顶部模型状态区。显示“已配置”代表密钥已经写入本机；第一次真实调用仍可能因密钥余额、模型权限或网络策略失败，失败信息会进入工作流任务和复核项。

密钥保存在：

```text
%LOCALAPPDATA%\PassBidWriter\config\.env
```

它不会进入 Git、项目源资料、DOCX、PDF或控制报告。保存后立即生效，通常不需要重启。

如果新旧两台电脑都已经使用 V1，可以通过安全方式复制上述 `.env` 文件；不要复制旧 Hermes 的 SOUL、MCP 或飞书配置。

也可以退出工作台后，参考仓库中的 `.env.example` 手工创建该文件。不要把真实密钥写进仓库根目录或提交到 Git。

## 实际使用流程

1. 点击“新建项目”，选择整个项目资料文件夹。
2. 在“资料与依据”确认文件角色。
3. 如果存在 DWG，先手工导出图纸 PDF 并通过“补充资料文件夹”上传。
4. 运行千问视觉分析。
5. 在“复核中心”处理冲突、缺失和人工补项。
6. 在“图纸中心”核对图号、图名、裁剪范围、插入章节与整页/局部方式。
7. 在“成品蓝图”检查已通过案例熔炼出的目录、场景词、写作规律和可复用措辞；修正错误并决定是否启用匹配。
8. 在“编制任务书”按当前资料与启用案例生成建议目录。系统默认以公司常用8章结构起步，但章数不锁定。
9. 人工增删章节、改名、排序，并修改每章目的、输入、交付组件和完成标准；保存后重新匹配依据与缺口。
10. 确认最终《施组编制任务书》。此后正文生产只认这份人工确认版本。
11. 在“章节生产”逐章生成、重写并接受。
12. 全部章节接受后，在“交付中心”装配 DOCX/PDF并更新控制报告。

成果默认位于：

```text
%LOCALAPPDATA%\PassBidWriter\projects\<project_id>\outputs\
```

包括施工组织设计 DOCX、PDF、编制任务书、响应矩阵、资料与规范依据报告、规范待下载清单、待补漏和冲突清单、模型复核差异报告，以及 `assets/` 图表和图纸图片。

## 案例库

在“成品蓝图”中导入包含“招标文件 + 已通过技术标”的整个文件夹。系统提取目录、场景词、可复用措辞、写作规律和版式模式。每个案例均可查看、修正、标记审核状态和停用；停用案例不会参与新项目匹配。历史项目的数字、人员、设备和工期不会作为新项目事实复用。

## 开发与发布

```powershell
py -3.12 -m pip install -r requirements.txt
cd workbench
npm ci
npm run build
cd ..
py -3.12 -m pytest -q
.\build-release.ps1
```

发布包生成在 `release\PassBidWriter-V1.1.0.zip`，内含编译前端、Python 源码、`setup.ps1` 和 `start.ps1`。

## V1 边界

- 不直接解析、编辑或计算 DWG。
- 不从图纸自动计算工程量。
- 缺少依据时保留人工确认标记。
- 不承诺投标通过；最终文字修改仍在 Word 中完成。
