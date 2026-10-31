"""Typed requests for native Chinese official-document formatting."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


OfficialRole = Literal[
    "title", "body", "heading1", "heading2", "heading3", "heading4",
    "issuing_authority", "document_number", "signatory", "recipient",
    "attachment_note", "attachment_label", "attachment_title", "signature",
    "date", "note", "copy_to", "print_line", "blank", "table_body", "image", "unknown",
]


class OfficialContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfficialMetadata(OfficialContract):
    issuing_authority: str | None = Field(default=None, min_length=1, max_length=300)
    document_number: str | None = Field(default=None, min_length=1, max_length=100)
    signatory: str | None = Field(default=None, min_length=1, max_length=100)
    date: str | None = Field(default=None, min_length=1, max_length=40)
    copy_to: str | None = Field(default=None, min_length=1, max_length=2000)
    print_authority: str | None = Field(default=None, min_length=1, max_length=300)
    print_date: str | None = Field(default=None, min_length=1, max_length=40)


class OfficialFonts(OfficialContract):
    title: str = Field(default="小标宋", min_length=1, max_length=100)
    body: str = Field(default="仿宋", min_length=1, max_length=100)
    heading1: str = Field(default="黑体", min_length=1, max_length=100)
    heading2: str = Field(default="楷体", min_length=1, max_length=100)
    page_number: str = Field(default="宋体", min_length=1, max_length=100)


class OfficialRequest(OfficialContract):
    scope: Literal["body", "full"] = "body"
    direction: Literal["up", "down", "parallel"] = "down"
    mode: Literal["standard", "template"] = "standard"
    reference: str | None = None
    reference_roles: dict[str, OfficialRole] = Field(default_factory=dict)
    metadata: OfficialMetadata = Field(default_factory=OfficialMetadata)
    seal_mode: Literal["none", "reserved"] = "none"
    fonts: OfficialFonts = Field(default_factory=OfficialFonts)

    @model_validator(mode="after")
    def reference_mode(self):
        if self.mode == "template" and not self.reference:
            raise ValueError("Template mode requires a reference DOCX")
        if self.mode == "standard" and (self.reference or self.reference_roles):
            raise ValueError("Reference options require template mode")
        for value in self.metadata.model_dump().values():
            if value is not None and (not value.strip() or any(c in value for c in "\r\n\x00")):
                raise ValueError("Metadata must contain single-line nonempty text")
        return self


class OfficialPlan(OfficialContract):
    version: Literal["1.0.0"] = "1.0.0"
    document_type: Literal["official"] = "official"
    source: str
    source_hash: str
    request: OfficialRequest
    roles: dict[str, OfficialRole]
    issues: list[dict] = Field(default_factory=list)
    status: Literal["PASS", "NEEDS_INPUT"]
    reference_hash: str | None = None
    template: dict = Field(default_factory=dict)
    profile: dict = Field(default_factory=dict)
