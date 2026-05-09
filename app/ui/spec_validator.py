"""Validate and repair UI specs before Prefab generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.ui.specs import ChartSpec, ColumnSpec, UISpec


@dataclass(frozen=True)
class UISpecValidation:
    ok: bool
    errors: list[str]
    warnings: list[str]


def validate_ui_spec_for_prefab(spec: UISpec) -> UISpecValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if spec.type == "text":
        return UISpecValidation(ok=True, errors=[], warnings=[])

    if spec.type == "error":
        if not spec.message:
            errors.append("Error specs need a message.")
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    fields = _row_fields(spec.rows)

    if spec.type == "kpi":
        if not spec.metrics:
            errors.append("KPI specs need at least one metric.")
        for metric in spec.metrics:
            if not metric.label:
                errors.append("Each KPI metric needs a label.")
            if metric.value is None:
                errors.append(f"KPI metric `{metric.label}` has no value.")
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "table":
        errors.extend(_validate_table_shape(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "schema_analysis":
        if not (spec.rows or spec.children or spec.mermaid):
            errors.append("Schema analysis specs need rows, child specs, or a Mermaid diagram.")
        if spec.rows:
            errors.extend(_validate_table_shape(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "chart":
        errors.extend(_validate_chart_shape(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "dashboard":
        if not (spec.children or spec.metrics or spec.rows or spec.chart or spec.filters):
            errors.append("Dashboard specs need at least one child, metric, chart, row, or filter.")
        if spec.chart is not None:
            errors.extend(_validate_chart_shape(spec, fields))
        errors.extend(_validate_filters(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "detail":
        errors.extend(_validate_table_shape(spec, fields))
        errors.extend(_validate_filters(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "filters":
        if not spec.filters:
            errors.append("Filter specs need at least one filter control.")
        errors.extend(_validate_filters(spec, fields))
        if spec.rows or spec.columns:
            errors.extend(_validate_table_shape(spec, fields))
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    if spec.type == "schema_map":
        if not spec.mermaid:
            errors.append("Schema map specs need a Mermaid diagram.")
        return UISpecValidation(ok=not errors, errors=errors, warnings=warnings)

    errors.append(f"Unsupported UI spec type: {spec.type}")
    return UISpecValidation(ok=False, errors=errors, warnings=warnings)


def deterministic_repair_for_prefab(spec: UISpec) -> UISpec:
    """Repair specs that current Prefab support cannot render correctly."""
    if spec.type != "chart":
        return spec

    if spec.chart is None:
        return _table_from_spec(spec, "Chart spec was missing chart configuration.")

    spec = _repair_chart_choice(spec)

    if spec.chart is None:
        return _table_from_spec(spec, "Chart spec was missing chart configuration.")

    if spec.chart.chart_type in {"bar", "line", "area", "scatter", "pie"}:
        return spec

    if spec.chart.chart_type != "histogram":
        return _table_from_spec(
            spec,
            "This chart type is not supported by the current Prefab renderer, so the result is shown as a table.",
        )

    if spec.chart.x_field is None:
        return _table_from_spec(spec, "Histogram spec was missing a numeric field.")

    values = [row.get(spec.chart.x_field) for row in spec.rows]
    if not values or not all(_is_number(value) for value in values if value is not None):
        return _table_from_spec(spec, "Histogram field is not numeric.")

    return spec


def _repair_chart_choice(spec: UISpec) -> UISpec:
    if spec.chart is None or not spec.rows:
        return spec

    chart = spec.chart
    fields = _row_fields(spec.rows)
    x_field = chart.x_field or chart.label_field
    y_field = chart.y_field or chart.value_field
    numeric_fields = _numeric_fields(spec.rows, exclude={x_field})

    if not numeric_fields:
        return spec

    if chart.chart_type == "pie":
        label_field = chart.label_field or chart.x_field
        value_field = chart.value_field or chart.y_field
        if label_field and value_field and len(spec.rows) <= 6 and len(numeric_fields) == 1:
            return spec
        replacement_type = "line" if label_field and _looks_temporal_values([row.get(label_field) for row in spec.rows]) else "bar"
        return spec.model_copy(
            update={
                "chart": ChartSpec(
                    chart_type=replacement_type,
                    x_field=label_field,
                    y_field=value_field or numeric_fields[0],
                    label_field=label_field,
                    value_field=value_field or numeric_fields[0],
                )
            }
        )

    if chart.chart_type in {"bar", "line", "area"} and x_field:
        x_values = [row.get(x_field) for row in spec.rows]
        x_is_temporal = _looks_temporal_values(x_values)
        corrected_type = chart.chart_type
        if x_is_temporal:
            corrected_type = "line"
        elif chart.chart_type in {"line", "area"} and not _field_has_numbers(spec.rows, x_field):
            corrected_type = "bar"
        if corrected_type != chart.chart_type:
            return spec.model_copy(
                update={
                    "chart": chart.model_copy(update={"chart_type": corrected_type, "x_field": x_field, "y_field": y_field or numeric_fields[0]})
                }
            )
        return spec

    if chart.chart_type == "scatter":
        if len(numeric_fields) >= 2:
            x = chart.x_field if chart.x_field in fields and _field_has_numbers(spec.rows, chart.x_field) else numeric_fields[0]
            y = chart.y_field if chart.y_field in fields and _field_has_numbers(spec.rows, chart.y_field) else numeric_fields[1]
            return spec.model_copy(update={"chart": chart.model_copy(update={"x_field": x, "y_field": y})})
        return spec.model_copy(update={"chart": chart.model_copy(update={"chart_type": "bar", "x_field": x_field, "y_field": y_field or numeric_fields[0]})})

    if chart.chart_type == "histogram":
        x = chart.x_field if chart.x_field in fields and _field_has_numbers(spec.rows, chart.x_field) else numeric_fields[0]
        return spec.model_copy(update={"chart": chart.model_copy(update={"x_field": x})})

    return spec


def _looks_temporal_values(values: list[Any]) -> bool:
    non_empty = [str(value).strip() for value in values if value not in {None, ""}]
    if not non_empty:
        return False
    if all(value.isdigit() and 1900 <= int(value) <= 2200 for value in non_empty):
        return True
    return any(_looks_like_date_string(value) for value in non_empty)


def _looks_like_date_string(value: str) -> bool:
    return bool(
        re.match(r"^\d{4}([-/]\d{1,2}([-/]\d{1,2})?)?([ T]\d{1,2}:\d{2}(:\d{2})?)?$", value)
        or re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$", value)
    )


def _field_has_numbers(rows: list[dict[str, Any]], field: str | None) -> bool:
    if field is None:
        return False
    return any(_is_number(row.get(field)) for row in rows)


def table_spec_from_rows(
    *,
    title: str,
    message: str,
    rows: list[dict[str, Any]],
    debug: dict[str, Any] | None = None,
) -> UISpec:
    columns = _columns_for_rows(rows)
    return UISpec(
        type="table",
        title=title,
        message=message,
        columns=columns,
        rows=rows,
        chart=None,
        debug=debug or {},
    )


def _validate_table_shape(spec: UISpec, fields: set[str]) -> list[str]:
    errors: list[str] = []
    if not spec.rows:
        errors.append("Table specs need rows.")
    if not spec.columns:
        errors.append("Table specs need columns.")
    for column in spec.columns:
        if column.field not in fields:
            errors.append(f"Table column `{column.field}` is not present in result rows.")
    return errors


def _validate_chart_shape(spec: UISpec, fields: set[str]) -> list[str]:
    errors: list[str] = []
    if not spec.rows:
        errors.append("Chart specs need rows.")
    if spec.chart is None:
        errors.append("Chart specs need chart configuration.")
        return errors

    chart: ChartSpec = spec.chart
    if chart.chart_type in {"bar", "line", "area", "scatter"}:
        if not chart.y_field:
            errors.append(f"{chart.chart_type.title()} chart specs need y_field.")
        elif chart.y_field not in fields:
            errors.append(f"{chart.chart_type.title()} chart y_field `{chart.y_field}` is not present in result rows.")
        else:
            values = [row.get(chart.y_field) for row in spec.rows]
            if not any(_is_number(value) for value in values):
                errors.append(f"{chart.chart_type.title()} chart y_field `{chart.y_field}` does not contain numeric values.")

        if not chart.x_field and chart.chart_type in {"line", "area", "scatter"}:
            errors.append(f"{chart.chart_type.title()} chart specs need x_field.")
        elif chart.x_field and chart.x_field not in fields:
            errors.append(f"{chart.chart_type.title()} chart x_field `{chart.x_field}` is not present in result rows.")
        if chart.label_field and chart.label_field not in fields:
            errors.append(f"{chart.chart_type.title()} chart label_field `{chart.label_field}` is not present in result rows.")
        return errors

    if chart.chart_type == "pie":
        label_field = chart.label_field or chart.x_field
        value_field = chart.value_field or chart.y_field
        if not label_field:
            errors.append("Pie chart specs need label_field or x_field.")
        elif label_field not in fields:
            errors.append(f"Pie chart label field `{label_field}` is not present in result rows.")
        if not value_field:
            errors.append("Pie chart specs need value_field or y_field.")
        elif value_field not in fields:
            errors.append(f"Pie chart value field `{value_field}` is not present in result rows.")
        else:
            values = [row.get(value_field) for row in spec.rows]
            if not any(_is_number(value) for value in values):
                errors.append(f"Pie chart value field `{value_field}` does not contain numeric values.")
        return errors

    if chart.chart_type != "histogram":
        errors.append(
            "Current Prefab renderer supports bar, line, area, pie, scatter, and histogram charts; "
            f"`{chart.chart_type}` would render incorrectly."
        )
        return errors

    if not chart.x_field:
        errors.append("Histogram specs need x_field.")
    elif chart.x_field not in fields:
        errors.append(f"Histogram x_field `{chart.x_field}` is not present in result rows.")
    else:
        values = [row.get(chart.x_field) for row in spec.rows]
        if not any(_is_number(value) for value in values):
            errors.append(f"Histogram x_field `{chart.x_field}` does not contain numeric values.")

    return errors


def _validate_filters(spec: UISpec, fields: set[str]) -> list[str]:
    errors: list[str] = []
    for filter_spec in spec.filters:
        if not filter_spec.field:
            errors.append("Each filter needs a field.")
            continue
        if fields and filter_spec.field not in fields:
            errors.append(f"Filter field `{filter_spec.field}` is not present in result rows.")
        if filter_spec.control in {"select", "combobox"} and not filter_spec.options:
            errors.append(f"{filter_spec.control.title()} filter `{filter_spec.field}` needs options.")
        if filter_spec.control == "slider" and (
            filter_spec.min_value is None or filter_spec.max_value is None
        ):
            errors.append(f"Slider filter `{filter_spec.field}` needs min_value and max_value.")
    return errors


def _table_from_spec(spec: UISpec, message: str) -> UISpec:
    return UISpec(
        type="table",
        title=spec.title,
        message=message,
        columns=spec.columns or _columns_for_rows(spec.rows),
        rows=spec.rows,
        chart=None,
        debug=spec.debug,
    )


def _columns_for_rows(rows: list[dict[str, Any]]) -> list[ColumnSpec]:
    if not rows:
        return []
    return [ColumnSpec(field=field, label=_humanize(field)) for field in rows[0].keys()]


def _row_fields(rows: list[dict[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(str(key) for key in row.keys())
    return fields


def _is_number(value: Any) -> bool:
    if value is None:
        return False
    return isinstance(value, int | float) and not isinstance(value, bool)


def _numeric_fields(rows: list[dict[str, Any]], *, exclude: set[str | None]) -> list[str]:
    if not rows:
        return []
    return [
        str(field)
        for field in rows[0].keys()
        if field not in exclude and any(_is_number(row.get(field)) for row in rows)
    ]


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()
