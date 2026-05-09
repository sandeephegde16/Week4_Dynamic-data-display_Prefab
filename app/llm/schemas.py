"""LLM output schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


RenderKind = Literal[
    "text",
    "kpi",
    "table",
    "bar_chart",
    "line_chart",
    "area_chart",
    "pie_chart",
    "scatter",
    "histogram",
    "dashboard",
    "detail_panel",
    "filter_panel",
    "schema_map",
]


class RenderPlan(BaseModel):
    kind: RenderKind = "table"
    title: str = "Query Result"
    reason: str = ""
    x_field: str | None = None
    y_field: str | None = None
    color_field: str | None = None
    label_field: str | None = None
    value_field: str | None = None
    metric_fields: list[str] = Field(default_factory=list)


class QueryBlock(BaseModel):
    name: str = ""
    title: str = ""
    purpose: str = ""
    sql: str
    render: RenderPlan = Field(default_factory=RenderPlan)


class QueryPlan(BaseModel):
    action: Literal["run_sql", "answer_text", "clarify"] = "clarify"
    question_rewrite: str = ""
    explanation: str = ""
    sql: str | None = None
    queries: list[QueryBlock] = Field(default_factory=list)
    render: RenderPlan = Field(default_factory=RenderPlan)
    confidence: float = 0.0

    @field_validator("queries", mode="before")
    @classmethod
    def _none_queries_to_empty_list(cls, value: object) -> object:
        return [] if value is None else value


class SchemaAnalysis(BaseModel):
    domain_guess: str = "general relational database"
    summary: str = ""
    likely_questions: list[str] = Field(default_factory=list)
    recommended_widgets: list[dict[str, Any]] = Field(default_factory=list)
    risky_or_ambiguous_terms: list[str] = Field(default_factory=list)


class UISpecReview(BaseModel):
    is_valid: bool
    reason: str = ""
    repaired_ui_spec: dict[str, Any] | None = None
