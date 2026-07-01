from __future__ import annotations

from copy import deepcopy
from typing import Any


BASE_BLUEPRINT: list[dict[str, Any]] = [
    {
        "code": "01",
        "title": "编制说明",
        "purpose": "说明编制范围、依据、原则和响应边界。",
        "required_inputs": ["招标文件", "补遗澄清", "初步设计报告", "引用规范"],
        "components": ["编制依据表", "编制原则", "适用范围", "人工确认事项"],
        "acceptance": ["招标文件与规范依据可追溯", "不引用未取得原文的具体条款"],
    },
    {
        "code": "02",
        "title": "工程概况与施工条件",
        "purpose": "建立项目事实基线和施工约束。",
        "required_inputs": ["初步设计报告", "预算清单", "设计图纸", "现场条件资料"],
        "components": ["工程概况", "主要工程量表", "自然与水文条件", "施工条件", "约束与风险"],
        "acceptance": ["项目数字均有来源", "冲突数据进入人工确认"],
    },
    {
        "code": "03",
        "title": "施工总体部署",
        "purpose": "形成施工组织、区段划分、总体顺序和资源协同方案。",
        "required_inputs": ["工程概况", "工期要求", "设计图纸", "工程量清单"],
        "components": ["部署原则", "施工区段", "总体流程图", "项目组织机构图", "阶段目标"],
        "acceptance": ["部署与工期及施工条件一致", "组织关系清晰"],
    },
    {
        "code": "04",
        "title": "施工总平面布置",
        "purpose": "说明临建、道路、水电、堆场、排水及安全环保布置。",
        "required_inputs": ["总平图", "施工范围", "现场条件", "临时用地要求"],
        "components": ["布置原则", "临建设施表", "临时道路", "临水临电", "排水与环保", "CAD引用图"],
        "acceptance": ["布置内容与图纸引用一致", "缺少布置图时明确提出补图"],
    },
    {
        "code": "05",
        "title": "施工进度计划及保证措施",
        "purpose": "形成可执行、可检查、可纠偏的施工进度体系。",
        "required_inputs": ["总工期", "关键节点", "工程量", "施工顺序", "资源约束"],
        "components": ["阶段划分", "里程碑表", "活动依赖表", "甘特图", "资源匹配", "纠偏措施"],
        "acceptance": ["总工期与节点有来源", "进度与劳动力机械相互匹配", "缺失日期不得编造"],
    },
    {
        "code": "06",
        "title": "主要施工方法与技术措施",
        "purpose": "针对各专业工程形成有依据、可实施的工法。",
        "required_inputs": ["设计图纸", "初步设计", "工程量清单", "施工规范"],
        "components": ["分部分项工法", "施工流程图", "关键参数表", "机械人员配置", "检验控制点"],
        "acceptance": ["每项主要工程均有工法", "参数来自项目资料或规范", "历史案例参数不得直接复用"],
    },
    {
        "code": "07",
        "title": "质量管理体系与保证措施",
        "purpose": "建立从目标、组织、过程控制到验收资料的质量闭环。",
        "required_inputs": ["质量目标", "验收规范", "检测要求", "主要工法"],
        "components": ["质量目标", "组织机构图", "质量控制流程图", "检验试验计划表", "关键控制点", "资料管理"],
        "acceptance": ["检验项目与规范及工法对应", "质量责任和记录闭环"],
    },
    {
        "code": "08",
        "title": "安全生产、文明施工与应急措施",
        "purpose": "覆盖风险辨识、责任体系、专项措施和应急响应。",
        "required_inputs": ["安全要求", "危险性较大工程", "施工环境", "相关规范"],
        "components": ["安全体系", "风险清单", "安全控制流程", "专项措施", "应急组织图", "应急处置流程"],
        "acceptance": ["高风险工序逐项覆盖", "应急资源和责任明确"],
    },
    {
        "code": "09",
        "title": "环境保护与水土保持",
        "purpose": "形成施工期生态、扬尘、噪声、污水和弃渣控制措施。",
        "required_inputs": ["环水保要求", "施工区域", "弃渣与排水条件", "地方要求"],
        "components": ["环境目标", "污染源清单", "水土保持措施", "监测检查表", "突发环境事件处置"],
        "acceptance": ["措施与现场污染源对应", "弃渣排水去向不虚构"],
    },
    {
        "code": "10",
        "title": "主要施工设备与检验仪器投入",
        "purpose": "证明设备、检测能力与工程量和进度相匹配。",
        "required_inputs": ["工程量", "工法", "工期", "招标设备要求"],
        "components": ["主要机械设备表", "检验仪器表", "进退场计划", "维护校验措施"],
        "acceptance": ["型号数量有依据或标记待确认", "设备能力与工法匹配"],
    },
    {
        "code": "11",
        "title": "项目管理人员与劳动力配置",
        "purpose": "形成岗位、专业配置和劳动力投入计划。",
        "required_inputs": ["招标人员要求", "施工阶段", "工程量", "企业拟派信息"],
        "components": ["项目人员配置表", "岗位职责", "专业配置说明", "劳动力计划表", "动态调配措施"],
        "acceptance": ["人员姓名资格不得编造", "劳动力与进度计划一致"],
    },
    {
        "code": "12",
        "title": "材料供应与试验管理",
        "purpose": "覆盖材料计划、采购、验收、复检、储存和追溯。",
        "required_inputs": ["材料清单", "设计要求", "检验规范", "进度计划"],
        "components": ["主要材料表", "供应计划", "进场验收流程", "复检计划", "储存与追溯"],
        "acceptance": ["材料规格与设计资料一致", "检验频次有规范依据"],
    },
    {
        "code": "13",
        "title": "季节性施工、施工导流与度汛",
        "purpose": "针对雨季、台汛期、施工导流和排水降水形成专项措施。",
        "required_inputs": ["水文气象", "工期", "导流设计", "防汛要求"],
        "components": ["季节性风险", "导流方案", "围堰与排水", "度汛计划", "防汛资源表", "应急流程"],
        "acceptance": ["水位流量等参数有来源", "度汛措施与施工阶段一致"],
    },
    {
        "code": "14",
        "title": "关键部位、关键工序与技术创新",
        "purpose": "集中说明影响履约的关键控制内容。",
        "required_inputs": ["关键工程清单", "设计难点", "招标专项要求", "风险清单"],
        "components": ["关键部位识别", "控制措施表", "旁站与监测", "技术优化建议"],
        "acceptance": ["关键项来自项目资料或招标要求", "创新不改变设计边界"],
    },
    {
        "code": "15",
        "title": "资料管理、验收配合与附件",
        "purpose": "形成过程资料、验收、移交和招标附件响应闭环。",
        "required_inputs": ["验收要求", "档案要求", "附件清单", "竣工移交要求"],
        "components": ["资料目录", "验收流程", "移交计划", "附件响应清单"],
        "acceptance": ["招标附件逐项响应", "资料责任和时间节点明确"],
    },
]


PROJECT_MODULES: dict[str, list[dict[str, Any]]] = {
    "河道": [
        {"title": "河道疏浚与土方平衡", "inputs": ["河道断面图", "疏浚工程量", "弃土去向"]},
        {"title": "岸坡防护及生态修复", "inputs": ["护岸设计图", "材料要求", "生态要求"]},
    ],
    "堤防": [
        {"title": "堤身填筑与压实控制", "inputs": ["填筑断面", "土料指标", "压实标准"]},
        {"title": "防渗及护坡施工", "inputs": ["防渗设计", "护坡图纸", "材料标准"]},
    ],
    "泵站": [
        {"title": "泵站主体结构施工", "inputs": ["结构图", "混凝土要求", "基坑条件"]},
        {"title": "机电设备安装与联合调试", "inputs": ["设备清单", "安装图", "调试要求"]},
    ],
    "水闸": [
        {"title": "闸室与上下游连接段施工", "inputs": ["水闸结构图", "止水要求", "导流条件"]},
        {"title": "闸门与启闭机安装调试", "inputs": ["金结图纸", "设备清单", "验收标准"]},
    ],
    "水库": [
        {"title": "大坝及附属建筑物施工", "inputs": ["大坝设计", "运行约束", "安全监测"]},
        {"title": "除险加固与运行期保护", "inputs": ["鉴定报告", "加固图纸", "调度要求"]},
    ],
}


COMPACT_SECTION_GROUPS: list[dict[str, Any]] = [
    {"code": "01", "title": "编制说明及工程概况", "members": ["01", "02"]},
    {"code": "02", "title": "施工总体部署及总平面布置", "members": ["03", "04"]},
    {"code": "03", "title": "施工进度计划及保证措施", "members": ["05"]},
    {"code": "04", "title": "主要施工方案与关键技术措施", "members": ["06", "13", "14"]},
    {"code": "05", "title": "质量管理体系与材料试验管理", "members": ["07", "12"]},
    {"code": "06", "title": "安全文明施工、环境保护与应急措施", "members": ["08", "09"]},
    {"code": "07", "title": "项目人员、劳动力、机械设备与仪器配置", "members": ["10", "11"]},
    {"code": "08", "title": "资料管理、验收配合及招标附件", "members": ["15"]},
]


def build_blueprint(project_type: str = "水利工程通用") -> dict[str, Any]:
    reference_sections = deepcopy(BASE_BLUEPRINT)
    matched_modules: list[dict[str, Any]] = []
    for key, modules in PROJECT_MODULES.items():
        if key in project_type:
            matched_modules.extend(deepcopy(modules))
    if matched_modules:
        method_section = next(section for section in reference_sections if section["code"] == "06")
        method_section["special_modules"] = matched_modules
        method_section["components"].extend(module["title"] for module in matched_modules)
    by_code = {section["code"]: section for section in reference_sections}
    sections: list[dict[str, Any]] = []
    for group in COMPACT_SECTION_GROUPS:
        members = [by_code[code] for code in group["members"]]
        sections.append(
            {
                "code": group["code"],
                "title": group["title"],
                "purpose": "；".join(item["purpose"].rstrip("。") for item in members) + "。",
                "required_inputs": _unique(
                    value for item in members for value in item["required_inputs"]
                ),
                "components": _unique(
                    value for item in members for value in item["components"]
                ),
                "acceptance": _unique(
                    value for item in members for value in item["acceptance"]
                ),
                "special_modules": [
                    value
                    for item in members
                    for value in item.get("special_modules", [])
                ],
                "reference_member_codes": list(group["members"]),
            }
        )
    return {
        "id": "water-conservancy-v1",
        "title": "水利工程施工组织设计标准蓝图",
        "version": "1.1",
        "status": "controlled",
        "project_type": project_type,
        "sections": sections,
        "reference_sections": reference_sections,
        "default_section_strategy": "company_compact_8",
        "rules": [
            "招标文件和补遗优先确定响应范围与格式。",
            "项目数字必须来自项目事实或人工确认。",
            "规范条款必须来自已取得并验证的标准原文。",
            "历史案例仅提供结构、表达和资产模板。",
            "无法核验的信息必须进入人工确认清单。",
            "章节数量不固定，8章为公司常用起点，人工确认后的任务书为唯一生产目录。",
        ],
    }


def _unique(values: Any) -> list[Any]:
    return list(dict.fromkeys(values))
