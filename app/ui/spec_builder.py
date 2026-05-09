"""Convert query results into validated dynamic UI specs."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import pandas as pd

from app.data.schema import DatabaseSchema
from app.llm.schemas import QueryPlan, RenderPlan
from app.ui.specs import AssistantResponse, ChartSpec, ColumnSpec, FilterSpec, MetricSpec, UISpec


def response_for_text(message: str, *, debug: dict[str, Any] | None = None) -> AssistantResponse:
    return AssistantResponse(
        message=message,
        ui_required=False,
        ui_spec=None,
        debug=debug or {},
    )


def response_for_error(message: str, *, debug: dict[str, Any] | None = None) -> AssistantResponse:
    spec = UISpec(type="error", title="Error", message=message, debug=debug or {})
    return AssistantResponse(message=message, ui_required=True, ui_spec=spec, debug=debug or {})


def response_for_schema_analysis(
    analysis: dict[str, Any],
    *,
    schema: DatabaseSchema | None = None,
    debug: dict[str, Any] | None = None,
) -> AssistantResponse:
    rows = []
    for widget in analysis.get("recommended_widgets", []):
        if isinstance(widget, dict):
            components = widget.get("recommended_components") or widget.get("components") or []
            if isinstance(components, list):
                components = ", ".join(str(component) for component in components)
            rows.append(
                {
                    "widget": widget.get("widget"),
                    "components": components,
                    "use_for": widget.get("use_for"),
                    "reason": widget.get("reason", ""),
                }
            )
    questions = analysis.get("likely_questions", [])
    message = analysis.get("summary") or "Database schema analyzed. Suggested questions and widgets are available."
    mermaid = _schema_mermaid(schema) if schema is not None else None
    children = []
    if mermaid:
        children.append(
            UISpec(
                type="schema_map",
                title="Schema Relationships",
                message="Foreign-key and table relationship overview.",
                mermaid=mermaid,
            )
        )
    if rows:
        children.append(
            UISpec(
                type="table",
                title="Recommended Widgets",
                message="Component recommendations inferred from the schema.",
                rows=rows,
                columns=[
                    ColumnSpec(field="widget", label="Widget"),
                    ColumnSpec(field="components", label="Prefab Components"),
                    ColumnSpec(field="use_for", label="Use For"),
                    ColumnSpec(field="reason", label="Reason"),
                ],
            )
        )

    spec = UISpec(
        type="schema_analysis",
        title=f"Schema Analysis: {analysis.get('domain_guess', 'database')}",
        message=message,
        rows=rows,
        columns=[
            ColumnSpec(field="widget", label="Widget"),
            ColumnSpec(field="components", label="Prefab Components"),
            ColumnSpec(field="use_for", label="Use For"),
            ColumnSpec(field="reason", label="Reason"),
        ]
        if rows
        else [],
        children=children,
        mermaid=mermaid,
        debug={**(debug or {}), "analysis": analysis, "likely_questions": questions},
    )
    return AssistantResponse(message=message, ui_required=True, ui_spec=spec, debug=debug or {})


def response_for_query_result(
    frame: pd.DataFrame,
    plan: QueryPlan,
    *,
    debug: dict[str, Any] | None = None,
) -> AssistantResponse:
    rows = _frame_to_rows(frame)
    render = plan.render
    spec = _build_spec(frame, rows, render, fallback_title=plan.question_rewrite or "Query Result")
    spec.debug = debug or {}
    message = _default_message(frame) if frame.empty else plan.explanation or _default_message(frame)
    return AssistantResponse(message=message, ui_required=spec.type != "text", ui_spec=spec, debug=debug or {})


def _build_spec(frame: pd.DataFrame, rows: list[dict[str, Any]], render: RenderPlan, *, fallback_title: str) -> UISpec:
    if frame.empty:
        return UISpec(type="text", title=render.title or fallback_title, message="No rows matched this question.")

    columns = [ColumnSpec(field=str(column), label=_humanize(str(column))) for column in frame.columns]
    kind = render.kind

    if kind == "text":
        return UISpec(type="text", title=render.title or fallback_title, message=_rows_as_text(rows), rows=rows)

    if kind == "dashboard":
        return _dashboard_from_frame(frame, rows, render, columns, fallback_title=fallback_title)

    if kind == "kpi" or _looks_like_kpi(frame, render):
        return UISpec(
            type="kpi",
            title=render.title or fallback_title,
            message=render.reason,
            metrics=_metrics_from_frame(frame, render),
            rows=rows,
            columns=columns,
        )

    if kind == "filter_panel":
        return UISpec(
            type="filters",
            title=render.title or fallback_title,
            message=render.reason,
            rows=rows,
            columns=columns,
            filters=_filters_from_frame(frame),
        )

    if kind == "schema_map":
        return UISpec(
            type="detail",
            title=render.title or fallback_title,
            message=render.reason or "This query returned rows; schema maps are available from the database overview.",
            rows=rows,
            columns=columns,
        )

    if kind == "detail_panel" or _looks_like_detail(frame, render):
        return UISpec(
            type="detail",
            title=render.title or fallback_title,
            message=render.reason,
            rows=rows,
            columns=columns,
            filters=_filters_from_frame(frame),
        )

    if kind in {"bar_chart", "line_chart", "area_chart", "pie_chart", "scatter", "histogram"}:
        chart = _chart_from_render(frame, render)
        if chart is not None:
            return UISpec(
                type="chart",
                title=render.title or fallback_title,
                message=render.reason,
                rows=rows,
                columns=columns,
                chart=chart,
            )

    inferred_chart = _infer_chart(frame)
    if inferred_chart is not None and len(frame) <= 200:
        return UISpec(
            type="chart",
            title=render.title or fallback_title,
            message=render.reason,
            rows=rows,
            columns=columns,
            chart=inferred_chart,
        )

    return UISpec(type="table", title=render.title or fallback_title, message=render.reason, rows=rows, columns=columns)


def _dashboard_from_frame(
    frame: pd.DataFrame,
    rows: list[dict[str, Any]],
    render: RenderPlan,
    columns: list[ColumnSpec],
    *,
    fallback_title: str,
    chart: ChartSpec | None = None,
) -> UISpec:
    metrics = _metrics_from_frame(frame, render)
    chart = chart or _chart_from_render(frame, render) or _infer_chart(frame)
    filters = _filters_from_frame(frame)
    children: list[UISpec] = []

    if metrics:
        children.append(
            UISpec(
                type="kpi",
                title="Key Metrics",
                message="",
                metrics=metrics,
                rows=rows[:1],
                columns=columns,
            )
        )

    if chart is not None:
        children.append(
            UISpec(
                type="chart",
                title="Visual Breakdown",
                message=render.reason,
                rows=rows,
                columns=columns,
                chart=chart,
            )
        )

    children.append(
        UISpec(
            type="table",
            title="Drilldown Rows",
            message="",
            rows=rows,
            columns=columns,
        )
    )

    return UISpec(
        type="dashboard",
        title=render.title or fallback_title,
        message=render.reason,
        metrics=metrics,
        rows=rows,
        columns=columns,
        chart=chart,
        filters=filters,
        children=children,
    )


def _metrics_from_frame(frame: pd.DataFrame, render: RenderPlan) -> list[MetricSpec]:
    metric_fields = [field for field in render.metric_fields if field in frame.columns]
    if not metric_fields:
        metric_fields = [str(column) for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    if not metric_fields and len(frame.columns) <= 4:
        metric_fields = [str(column) for column in frame.columns[:4]]

    first_row = frame.iloc[0].to_dict()
    return [MetricSpec(label=_humanize(field), value=_jsonable(first_row.get(field))) for field in metric_fields[:12]]


def _filters_from_frame(frame: pd.DataFrame) -> list[FilterSpec]:
    filters: list[FilterSpec] = []

    for column in frame.columns:
        if len(filters) >= 4:
            break
        field = str(column)
        series = frame[column].dropna()
        if series.empty:
            continue

        if pd.api.types.is_bool_dtype(series) or _looks_boolean(series):
            filters.append(FilterSpec(field=field, label=_humanize(field), control="switch", value=False))
            continue

        if pd.api.types.is_datetime64_any_dtype(series) or _looks_temporal(series):
            filters.append(
                FilterSpec(
                    field=field,
                    label=_humanize(field),
                    control="date",
                    min_value=_jsonable(series.min()),
                    max_value=_jsonable(series.max()),
                )
            )
            continue

        if pd.api.types.is_numeric_dtype(series):
            min_value = _jsonable(series.min())
            max_value = _jsonable(series.max())
            if min_value != max_value:
                filters.append(
                    FilterSpec(
                        field=field,
                        label=_humanize(field),
                        control="slider",
                        min_value=min_value,
                        max_value=max_value,
                        value=min_value,
                    )
                )
            continue

        options = sorted({str(value) for value in series.astype(str).head(200).tolist() if str(value).strip()})
        if 1 < len(options) <= 12:
            filters.append(FilterSpec(field=field, label=_humanize(field), control="select", options=options))
        elif len(options) > 12:
            filters.append(FilterSpec(field=field, label=_humanize(field), control="combobox", options=options[:40]))

    return filters


def _chart_from_render(frame: pd.DataFrame, render: RenderPlan) -> ChartSpec | None:
    chart_type_map = {
        "bar_chart": "bar",
        "line_chart": "line",
        "area_chart": "area",
        "pie_chart": "pie",
        "scatter": "scatter",
        "histogram": "histogram",
    }
    chart_type = chart_type_map.get(render.kind)
    if chart_type is None:
        return None

    fields = set(str(column) for column in frame.columns)
    x_field = render.x_field if render.x_field in fields else None
    y_field = render.y_field if render.y_field in fields else None
    label_field = render.label_field if render.label_field in fields else None
    value_field = render.value_field if render.value_field in fields else None
    color_field = render.color_field if render.color_field in fields else None

    if chart_type in {"bar", "line", "area", "scatter"} and not (x_field and y_field):
        inferred = _infer_xy(frame)
        if inferred is None:
            return None
        x_field, y_field = inferred

    if chart_type == "pie" and not (label_field and value_field):
        inferred = _infer_xy(frame)
        if inferred is None:
            return None
        label_field, value_field = inferred

    if chart_type == "histogram" and not x_field:
        numeric = _numeric_columns(frame)
        if not numeric:
            return None
        x_field = numeric[0]

    return ChartSpec(
        chart_type=chart_type,
        x_field=x_field,
        y_field=y_field,
        label_field=label_field,
        value_field=value_field,
        color_field=color_field,
    )


def _infer_chart(frame: pd.DataFrame) -> ChartSpec | None:
    inferred = _infer_xy(frame)
    if inferred is None:
        return None
    x_field, y_field = inferred
    chart_type = "line" if _looks_temporal(frame[x_field]) else "bar"
    return ChartSpec(chart_type=chart_type, x_field=x_field, y_field=y_field)


def _infer_xy(frame: pd.DataFrame) -> tuple[str, str] | None:
    columns = [str(column) for column in frame.columns]
    numeric = _numeric_columns(frame)
    if not numeric:
        return None

    non_numeric = [column for column in columns if column not in numeric]
    if non_numeric:
        return non_numeric[0], numeric[0]
    if len(numeric) >= 2:
        return numeric[0], numeric[1]
    return columns[0], numeric[0]


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(column) for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]


def _looks_temporal(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().astype(str).head(5).tolist()
    return any(_looks_like_date_string(value) for value in sample)


def _looks_like_date_string(value: str) -> bool:
    text = value.strip()
    return bool(
        re.match(r"^\d{4}([-/]\d{1,2}([-/]\d{1,2})?)?([ T]\d{1,2}:\d{2}(:\d{2})?)?$", text)
        or re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$", text)
    )


def _looks_like_kpi(frame: pd.DataFrame, render: RenderPlan) -> bool:
    if len(frame) != 1:
        return False
    if render.kind == "kpi":
        return True
    numeric_columns = _numeric_columns(frame)
    if not numeric_columns:
        return False
    return len(numeric_columns) == len(frame.columns) or len(frame.columns) <= 4


def _looks_like_detail(frame: pd.DataFrame, render: RenderPlan) -> bool:
    if render.kind == "detail_panel":
        return True
    return len(frame) <= 5 and len(frame.columns) >= 5


def _looks_boolean(series: pd.Series) -> bool:
    values = {str(value).strip().lower() for value in series.head(50).tolist()}
    return bool(values) and values.issubset({"0", "1", "true", "false", "yes", "no"})


def _frame_to_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(key): _jsonable(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def _jsonable(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _rows_as_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No rows matched this question."
    if len(rows) == 1:
        return ", ".join(f"{_humanize(key)}: {value}" for key, value in rows[0].items())
    return f"Returned {len(rows)} rows."


def _default_message(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows matched this question."
    return f"Returned {len(frame)} rows."


def _schema_mermaid(schema: DatabaseSchema | None) -> str | None:
    if schema is None or not schema.tables:
        return None

    selected_tables = schema.tables[:12]
    selected_names = {table.table_name for table in selected_tables}
    lines = ["erDiagram"]

    for table in selected_tables:
        lines.append(f"  {_mermaid_id(table.table_name)} {{")
        for column in table.columns[:8]:
            flags = []
            if column.column_name in table.primary_keys:
                flags.append("PK")
            if any(fk.column_name == column.column_name for fk in table.foreign_keys):
                flags.append("FK")
            flag_text = f" {' '.join(flags)}" if flags else ""
            lines.append(f"    {_mermaid_type(column.data_type)} {_mermaid_id(column.column_name)}{flag_text}")
        lines.append("  }")

    for table in selected_tables:
        for foreign_key in table.foreign_keys:
            if foreign_key.referenced_table_name not in selected_names:
                continue
            left = _mermaid_id(foreign_key.referenced_table_name)
            right = _mermaid_id(table.table_name)
            label = f"{foreign_key.column_name}"
            lines.append(f'  {left} ||--o{{ {right} : "{label}"')

    return "\n".join(lines)


def _mermaid_id(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    return cleaned or "unnamed"


def _mermaid_type(value: str) -> str:
    normalized = value.lower()
    if normalized in {"varchar", "char", "text", "longtext", "mediumtext", "tinytext", "enum", "set"}:
        return "string"
    if normalized in {"int", "integer", "bigint", "smallint", "tinyint", "decimal", "double", "float", "numeric"}:
        return "number"
    if normalized in {"date", "datetime", "timestamp", "time", "year"}:
        return "datetime"
    return "string"
