from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceLocator(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_path: str
    page: int | None = None
    sheet: str = ""
    cell: str = ""
    figure: str = ""
    excerpt: str = ""


class StandardDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    title: str
    version: str = ""
    source_page: int | None = None
    source_path: str = ""
    official_platform: str = ""
    official_url: str = ""
    local_path: str = ""
    sha256: str = ""
    status: Literal[
        "pending_download",
        "available",
        "metadata_only",
        "blocked",
        "not_applicable",
        "needs_confirmation",
    ] = "pending_download"
    affected_sections: list[str] = Field(default_factory=list)


class StandardClause(BaseModel):
    model_config = ConfigDict(extra="allow")

    standard_code: str
    clause_id: str
    text: str
    source_path: str
    page: int | None = None
    applicable_sections: list[str] = Field(default_factory=list)
    applicability: str = ""
    mandatory_level: Literal["mandatory", "recommended", "unknown"] = "unknown"
    verification_status: Literal["verified_local_source", "needs_confirmation"] = "verified_local_source"


class ContentComponent(BaseModel):
    model_config = ConfigDict(extra="allow")

    component_id: str
    kind: Literal["text", "table", "flowchart", "organization_chart", "gantt", "cad_reference", "attachment"]
    title: str
    required: bool = True
    status: str = "not_started"
    source_path: str = ""


class BasisLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    deliverable_id: str
    project_basis: list[str] = Field(default_factory=list)
    reference_basis: list[str] = Field(default_factory=list)
    missing_basis: list[str] = Field(default_factory=list)


class DeliverableBlueprint(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    title: str
    purpose: str
    required_inputs: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    special_modules: list[dict[str, Any]] = Field(default_factory=list)


class CaseAsset(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str
    case_id: int
    case_title: str
    asset_type: Literal["outline", "wording", "table", "diagram", "layout", "style_note"]
    title: str
    content: Any
    applicable_project_types: list[str] = Field(default_factory=list)
    applicable_sections: list[str] = Field(default_factory=list)
    reuse_rule: Literal["structure_only", "replace_parameters", "layout_only"] = "structure_only"
    source_path: str = ""
    layout_profile_id: int | None = None


class ProjectFact(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    value: str
    unit: str = ""
    source_path: str
    source_page: int | None = None
    source_excerpt: str = ""
    confidence: float = 0
    status: Literal["extracted", "confirmed", "conflicted", "needs_confirmation"] = "extracted"


class ConfirmationItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    title: str
    detail: str
    severity: Literal["low", "medium", "high"] = "medium"
    affected_sections: list[str] = Field(default_factory=list)
    status: Literal["open", "resolved", "dismissed"] = "open"
    recommended_action: str = ""
    resolution: str = ""


def validate_core_state(state: dict[str, Any]) -> None:
    """Fail fast when production state no longer matches its core contracts."""
    for item in state.get("standards", []):
        StandardDocument.model_validate(item)
    for item in state.get("standard_clauses", []):
        StandardClause.model_validate(item)
    for item in state.get("case_assets", []):
        CaseAsset.model_validate(item)
    for item in state.get("facts", []):
        ProjectFact.model_validate(item)
    for item in state.get("confirmations", []):
        ConfirmationItem.model_validate(item)
    for section in state.get("sections", []):
        DeliverableBlueprint.model_validate(section)
        BasisLink.model_validate(
            {
                "deliverable_id": section.get("code", ""),
                "project_basis": section.get("project_basis", []),
                "reference_basis": section.get("reference_basis", []),
                "missing_basis": section.get("missing_inputs", []),
            }
        )
