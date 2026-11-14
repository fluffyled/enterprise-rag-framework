"""Validated interchange models for fixed evidence and verified answers."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from answering.contracts import Fragment

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requirement(Model):
    id: Text
    text: Text


class Evidence(Model):
    id: Text
    document_id: Text
    full_text: Annotated[str, StringConstraints(min_length=1)]
    document_title: str | None = None
    node_id: str | None = None
    parent_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    source_spans: list[tuple[int, int]] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    document_version: str | None = None
    validity_status: str | None = None
    source_hash: str | None = None
    locator: str | None = None
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_spans(self):
        if not self.full_text.strip():
            raise ValueError("Empty evidence text")
        if any(start < 0 or end <= start for start, end in self.source_spans):
            raise ValueError("Invalid source span")
        return self


class AnswerInputV1(Model):
    schema_version: Literal["1.0"] = "1.0"
    question: Text
    requirements: list[Requirement] = Field(default_factory=list)
    evidence: list[Evidence]
    relations: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_ids(self):
        requirements = {item.id for item in self.requirements}
        if len(requirements) != len(self.requirements) or len({e.id for e in self.evidence}) != len(self.evidence):
            raise ValueError("Duplicate requirement or evidence ID")
        if self.requirements and any(set(e.requirement_ids) - requirements for e in self.evidence):
            raise ValueError("Unknown requirement in evidence")
        return self

    @classmethod
    def from_fragments(cls, question: str, fragments: list[Fragment]):
        return cls(question=question, evidence=[
            Evidence(id=f.id, document_id=f.document_id, full_text=f.text,
                     document_title=f.title, locator=f.locator, metadata={"url": f.url})
            for f in fragments
        ])


class Citation(Model):
    evidence_id: Text
    quote: Text


class Fact(Model):
    id: Text
    text: Text
    kind: Literal["action", "document", "deadline", "condition", "exception", "result", "other"]
    requirement_ids: list[str] = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)
    actor: str | None = None
    action: str | None = None
    modality: Literal["required", "permitted", "prohibited", "conditional", "exception", "alternative", "descriptive"] | None = None
    recipient: str | None = None
    condition: str | None = None
    deadline: str | None = None
    exception: str | None = None
    alternative: str | None = None


class Step(Model):
    id: Text
    action: Text
    fact_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    dependency_citations: list[Citation] = Field(default_factory=list)
    actor: str | None = None
    modality: Literal["required", "permitted", "prohibited", "conditional", "exception", "alternative", "descriptive"] | None = None
    recipient: str | None = None
    condition: str | None = None
    deadline: str | None = None
    exception: str | None = None
    alternative: str | None = None


class Summary(Model):
    text: str = ""
    fact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Coverage(Model):
    requirement_id: Text
    status: Literal["supported", "partial", "missing", "conflict"]
    evidence_ids: list[str] = Field(default_factory=list)


class Missing(Model):
    id: Text
    reason: Text
    suggested_query: Text


class Verification(Model):
    passed: bool = False
    issues: list[str] = Field(default_factory=list)


class VerifiedAnswerV1(Model):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["answered", "partial", "insufficient", "conflict", "error"]
    summary: Summary = Field(default_factory=Summary)
    steps: list[Step] = Field(default_factory=list)
    claims: list[Fact] = Field(default_factory=list)
    requirement_coverage: list[Coverage] = Field(default_factory=list)
    missing_requirements: list[Missing] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)
    trace: dict = Field(default_factory=dict)
