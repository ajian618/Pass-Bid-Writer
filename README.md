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

第一次进入工作台后，在右上角“模型配置”中填写：

- DeepSeek API Key：章节正文、任务书归纳和文字复核；
- 阿里云百炼 API Key：千问 Flash / Plus 的 OCR、表格和图纸理解；
- 智谱 API Key：可选，仅用于关键图纸或低置信视觉结果复核。

密钥保存在 `%LOCALAPPDATA%\PassBidWriter\config\.env`，不会进入仓库或项目成果。

## 实际使用流程

1. 点击“新建项目”，选择整个项目资料文件夹。
2. 在“资料与依据”确认文件角色。
3. 如果存在 DWG，先手工导出图纸 PDF 并通过“补充资料文件夹”上传。
4. 运行千问视觉分析。
5. 在“复核中心”处理冲突、缺失和人工补项。
6. 在“图纸中心”核对图号、图名、裁剪范围、插入章节与整页/局部方式。
7. 确认《施组编制任务书》。
8. 在“章节生产”逐章生成、重写并接受。
9. 全部章节接受后，在“交付中心”装配 DOCX/PDF并更新控制报告。

成果默认位于：

```text
%LOCALAPPDATA%\PassBidWriter\projects\<project_id>\outputs\
```

包括施工组织设计 DOCX、PDF、编制任务书、响应矩阵、资料与规范依据报告、规范待下载清单、待补漏和冲突清单、模型复核差异报告，以及 `assets/` 图表和图纸图片。

## 案例库

在“成品蓝图”中导入包含“招标文件 + 已通过技术标”的整个文件夹。系统提取目录、措辞、表格和版式模式。历史项目的数字、人员、设备和工期不会作为新项目事实复用。

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

发布包生成在 `release\PassBidWriter-V1.0.0.zip`，内含编译前端、Python 源码、`setup.ps1` 和 `start.ps1`。

## V1 边界

- 不直接解析、编辑或计算 DWG。
- 不从图纸自动计算工程量。
- 缺少依据时保留人工确认标记。
- 不承诺投标通过；最终文字修改仍在 Word 中完成。
