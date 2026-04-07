from pydantic import BaseModel, Field
from typing import Literal


class Intake(BaseModel):
    title: str = ""
    domain: str = ""
    academic_level: str = ""
    required_length_pages: int = 0
    language: str = "ro"
    citation_style: str = "APA"
    research_questions: list[str] = Field(default_factory=list)
    deadline: str = ""
    mandatory_sections: list[str] = Field(default_factory=list)
    provided_sources: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: str = ""


class CandidatePassage(BaseModel):
    source_id: str
    chunk_id: str
    passage_text: str
    passage_type: Literal["definition", "method", "result", "limitation", "context"] = "context"


class EvidencePack(BaseModel):
    section_id: str
    section_goal: str
    questions_to_answer: list[str] = Field(default_factory=list)
    candidate_passages: list[CandidatePassage] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class ClaimUnit(BaseModel):
    claim_id: str
    text: str
    supporting_chunks: list[str] = Field(default_factory=list)


class ClaimPlan(BaseModel):
    section_id: str
    argument_order: list[str] = Field(default_factory=list)
    claim_units: list[ClaimUnit] = Field(default_factory=list)


class SectionDraft(BaseModel):
    section_id: str
    title: str
    draft_markdown: str
    used_chunks: list[str] = Field(default_factory=list)
    citations_needed: list[str] = Field(default_factory=list)