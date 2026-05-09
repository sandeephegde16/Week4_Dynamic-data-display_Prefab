"""Validated UI response specs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

UIKind = Literal[
    "text",
    "kpi",
    "table",
    "chart",
    "dashboard",
    "detail",
    "filters",
    "schema_map",
    "schema_analysis",
    "error",
]
ChartKind = Literal["bar", "line", "area", "pie", "scatter", "histogram"]
FilterKind = Literal["date", "select", "combobox", "slider", "switch"]


class MetricSpec(BaseModel):
    label: str
    value: str | int | float | None
    delta: str | None = None
    help: str | None = None


class ColumnSpec(BaseModel):
    field: str
    label: str | None = None


class ChartSpec(BaseModel):
    chart_type: ChartKind
    x_field: str | None = None
    y_field: str | None = None
    color_field: str | None = None
    label_field: str | None = None
    value_field: str | None = None


class FilterSpec(BaseModel):
    field: str
    label: str | None = None
    control: FilterKind
    options: list[str] = Field(default_factory=list)
    min_value: int | float | str | None = None
    max_value: int | float | str | None = None
    value: Any = None
    help: str | None = None


class UISpec(BaseModel):
    type: UIKind
    title: str = "Result"
    message: str = ""
    metrics: list[MetricSpec] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    chart: ChartSpec | None = None
    filters: list[FilterSpec] = Field(default_factory=list)
    children: list["UISpec"] = Field(default_factory=list)
    mermaid: str | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    message: str
    ui_required: bool
    ui_spec: UISpec | None = None
    debug: dict[str, Any] = Field(default_factory=dict)
