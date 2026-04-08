from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AntiPromptStage = Literal["outline", "evidence", "drafting", "citation"]
NoteStatus = Literal["active", "draft", "deprecated"]
SeverityLevel = Literal["low", "medium", "high", "critical"]
SecondBrainType = Literal["decision", "playbook", "bug", "release_history"]


class AntiPromptNote(BaseModel):
    id: str
    stage: AntiPromptStage
    severity: SeverityLevel
    tags: list[str] = Field(default_factory=list)
    status: NoteStatus = "active"
    problem_pattern: str
    symptoms: list[str] = Field(default_factory=list)
    why_this_is_bad: str
    devil_advocate_checks: list[str] = Field(default_factory=list)
    counter_instruction: str
    reject_conditions: list[str] = Field(default_factory=list)
    source_note: str


class SecondBrainNote(BaseModel):
    id: str
    type: SecondBrainType
    tags: list[str] = Field(default_factory=list)
    status: NoteStatus = "active"
    context: str
    decision: str
    why: str
    alternatives_considered: list[str] = Field(default_factory=list)
    impact: str
    related_files: list[str] = Field(default_factory=list)
    source_note: str
