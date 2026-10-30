"""Public, strict host-agent interchange contracts. No executable edit payloads."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNVERIFIED = "UNVERIFIED"


class SourceMap(Contract):
    file: str
    locator: str
    fingerprint: str | None = None


Role = Literal["title", "author", "author_zh", "author_en", "affiliation", "affiliation_zh", "affiliation_en", "subtitle", "subtitle_zh", "subtitle_en", "correspondence", "correspondence_zh", "correspondence_en", "body_start", "title_zh", "title_en", "abstract_zh", "abstract_en", "keywords_zh", "keywords_en", "figure_caption_zh", "figure_caption_en", "table_caption_zh", "table_caption_en", "heading1", "heading2", "heading3", "heading4", "heading5", "heading6", "body", "abstract_heading", "abstract", "keywords", "references_heading", "reference", "caption", "figure_caption", "table_caption", "equation", "table", "table_body", "image", "legacy_image", "toc", "unknown"]


class ContentBlock(Contract):
    id: str
    role: Role = "unknown"
    text: str = ""
    source: SourceMap
    properties: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None


class DocumentIR(Contract):
    version: str = "1.0.0"
    source: str
    kind: Literal["docx", "latex"]
    blocks: list[ContentBlock]
    inventory: dict[str, Any]


class RoleMap(Contract):
    roles: dict[str, Role]
    evidence: dict[str, str] = Field(default_factory=dict)


class FormatRule(Contract):
    font: str | None = None
    east_asia_font: str | None = None
    size_pt: float | None = Field(default=None, gt=0, le=200)
    bold: bool | None = None
    italic: bool | None = None
    font_color: str | None = Field(default=None, pattern=r"^(?:[0-9a-fA-F]{6}|auto)$")
    alignment: Literal["left", "center", "right", "justify", "both"] | None = None
    line_spacing: float | None = Field(default=None, gt=0, le=10)
    line_spacing_rule: Literal["auto", "exact", "atLeast"] | None = None
    line_spacing_pt: float | None = Field(default=None, gt=0, le=500)
    space_before_pt: float | None = Field(default=None, ge=0, le=500)
    space_after_pt: float | None = Field(default=None, ge=0, le=500)
    first_line_pt: float | None = Field(default=None, ge=-200, le=500)
    left_indent_pt: float | None = Field(default=None, ge=-200, le=500)
    right_indent_pt: float | None = Field(default=None, ge=-200, le=500)

    @model_validator(mode="after")
    def spacing_units(self):
        if self.line_spacing_pt is not None and self.line_spacing_rule not in {"exact", "atLeast"}:
            raise ValueError("Point line spacing requires exact or atLeast")
        if self.line_spacing_rule in {"exact", "atLeast"}:
            if self.line_spacing_pt is None or self.line_spacing is not None:
                raise ValueError("Fixed/minimum line spacing needs points and cannot carry an automatic ratio")
        return self


class PageRule(Contract):
    width_mm: float | None = Field(default=None, ge=50, le=600)
    height_mm: float | None = Field(default=None, ge=50, le=600)
    margin_top_mm: float | None = Field(default=None, ge=0, le=80)
    margin_bottom_mm: float | None = Field(default=None, ge=0, le=80)
    margin_left_mm: float | None = Field(default=None, ge=0, le=80)
    margin_right_mm: float | None = Field(default=None, ge=0, le=80)
    columns: Literal[1, 2] | None = None
    column_gap_mm: float | None = Field(default=None, ge=0, le=50)
    column_widths_mm: list[Annotated[float, Field(gt=0, le=600, strict=True)]] | None = Field(default=None, min_length=1, max_length=2)
    header_distance_mm: float | None = Field(default=None, ge=0, le=100)
    footer_distance_mm: float | None = Field(default=None, ge=0, le=100)
    mirror_margins: bool | None = Field(default=None, strict=True)
    grid_type: Literal["default", "lines", "linesAndChars", "snapToChars"] | None = None
    grid_line_pitch_pt: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def coherent_columns(self):
        if self.column_widths_mm is not None and self.columns is not None and len(self.column_widths_mm) != self.columns:
            raise ValueError("Column widths must match the column count")
        return self


class SectionsRule(Contract):
    """Bounded continuous front-matter/body column transition."""
    front_matter_columns: Literal[1]
    body_columns: Literal[2]
    body_starts_at: Literal["first_heading1", "marked_body_start", "first_abstract"]
    body_column_gap_mm: float | None = Field(default=None, ge=0, le=50, strict=True)
    different_first_page: bool | None = Field(default=None, strict=True)
    different_odd_even_headers: bool | None = Field(default=None, strict=True)
    front_matter_page: PageRule | None = None
    body_page: PageRule | None = None

    @model_validator(mode="after")
    def coherent_pages(self):
        for page, columns in ((self.front_matter_page, self.front_matter_columns), (self.body_page, self.body_columns)):
            if page is not None:
                if page.mirror_margins is not None:
                    raise ValueError("Mirror margins apply to the whole Word document")
                if page.columns is not None and page.columns != columns:
                    raise ValueError("Section page columns conflict with the section layout")
                if page.column_widths_mm is not None and len(page.column_widths_mm) != columns:
                    raise ValueError("Section column widths conflict with the section layout")
        return self

    @model_validator(mode="before")
    @classmethod
    def integer_columns(cls, value):
        if isinstance(value, dict):
            for key in ("front_matter_columns", "body_columns"):
                if key in value and (not isinstance(value[key], int) or isinstance(value[key], bool)):
                    raise ValueError("Section column counts must be integers")
        return value


class BorderRule(Contract):
    style: Literal["single", "double", "dashed", "dotted", "nil", "none"]
    size_pt: float = Field(ge=0, le=12)
    color: str = Field(pattern=r"^(?:[0-9a-fA-F]{6}|auto)$")


class TableRule(Contract):
    borders: dict[Literal["top", "bottom", "left", "right", "insideH", "insideV"], BorderRule] = Field(default_factory=dict)
    header_bottom: BorderRule | None = None


class RunningRule(Contract):
    header: FormatRule | None = None
    footer: FormatRule | None = None


class LaTeXRule(Contract):
    documentclass: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    options: list[str] | None = None
    packages: dict[str, str | list[str]] = Field(default_factory=dict)
    pre_class_packages: dict[str, str] = Field(default_factory=dict)
    bibliography_style: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    compatibility: list[Literal["cmss_bold_alias"]] = Field(default_factory=list)
    engine: Literal["auto", "tectonic", "xelatex", "pdflatex", "latexmk", "latexmk-pdf", "latexmk-ps"] | None = None


class StyleProfile(BaseModel):
    # Extension metadata is retained; executable properties remain strictly typed.
    model_config = ConfigDict(extra="allow")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    name: str
    version: str
    rules: dict[Role, FormatRule]
    page: PageRule = Field(default_factory=PageRule)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] | list[Any] = Field(default_factory=dict)
    latex: LaTeXRule = Field(default_factory=LaTeXRule)
    tables: TableRule | None = None
    running: RunningRule | None = None
    sections: SectionsRule | None = None


class EditOperation(Contract):
    op: Literal["format_document", "assign_role"]
    target: str
    role: Role | None = None
    risk: Literal["low", "medium"] = "low"
    rollback: Literal["restore_source_copy"] = "restore_source_copy"

    @model_validator(mode="after")
    def consistent(self):
        if self.op == "assign_role" and self.role is None:
            raise ValueError("assign_role requires a role")
        if self.op == "format_document" and self.target != "document":
            raise ValueError("format_document must target document")
        return self


class EditPlan(Contract):
    version: str = "1.0.0"
    source: str
    source_hash: str
    profile: StyleProfile
    operations: list[EditOperation]
    mode: Literal["format_only"] = "format_only"


class AuditCheck(Contract):
    name: str
    status: Status
    details: Any = None


class AuditReport(Contract):
    status: Status
    checks: list[AuditCheck]
    unresolved: list[str] = Field(default_factory=list)


CONTRACTS = [DocumentIR, SourceMap, StyleProfile, RoleMap, EditPlan, AuditReport]

