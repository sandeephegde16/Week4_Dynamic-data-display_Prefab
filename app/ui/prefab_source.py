"""Generate direct Prefab DSL source from a clean UI spec."""

from __future__ import annotations

from typing import Any

from app.ui.theme import PREFAB_APP_CLASS, PREFAB_MUTED_TEXT_CLASS, PREFAB_SURFACE_CLASS


def build_prefab_source(spec: dict[str, Any]) -> str:
    """Return a direct Prefab app for the current spec only."""
    imports = _imports_for_spec(spec)
    chart_imports = _chart_imports_for_spec(spec)
    lines = [
        "from prefab_ui.app import PrefabApp",
        f"from prefab_ui.components import {', '.join(imports)}",
    ]
    if chart_imports:
        lines.append(f"from prefab_ui.components.charts import {', '.join(chart_imports)}")
    lines.extend([
        "",
        "",
        f"with PrefabApp(title={_repr(spec.get('title') or 'Result')}, css_class={PREFAB_APP_CLASS!r}) as app:",
        "    with Column(gap=4, css_class='w-full'):",
    ])
    _append_header(lines, spec, indent=8)
    _append_body(lines, spec, indent=8)
    return "\n".join(lines).rstrip() + "\n"


def _imports_for_spec(spec: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    _add_component_imports(spec, names)
    return sorted(names)


def _add_component_imports(spec: dict[str, Any], names: set[str]) -> None:
    names.update({"Column", "Heading", "Text"})
    spec_type = spec.get("type")
    if spec_type == "kpi":
        names.update({"Card", "Grid", "Metric"})
    elif spec_type in {"table", "filters", "schema_analysis"}:
        names.update({"DataTable", "DataTableColumn"})
    elif spec_type == "detail":
        names.update({"Card", "Div", "Grid", "Metric"})
    elif spec_type == "chart":
        names.add("Card")
        if _chart_needs_table(spec):
            names.update({"DataTable", "DataTableColumn"})
        if (spec.get("chart") or {}).get("chart_type") == "histogram":
            names.update({"Div", "Histogram"})
    elif spec_type == "dashboard":
        names.update({"Card", "Grid", "Metric"})
        if spec.get("rows"):
            names.update({"DataTable", "DataTableColumn"})
    elif spec_type == "schema_map":
        names.update({"Card", "Mermaid"})
    elif spec_type == "error":
        names.update({"Alert", "AlertDescription", "AlertTitle"})
    if spec.get("filters"):
        names.update({"Badge", "Combobox", "ComboboxOption", "DatePicker", "Div", "Grid", "Select", "SelectOption", "Slider", "Switch"})
    for child in spec.get("children") or []:
        if isinstance(child, dict):
            _add_component_imports(child, names)


def _chart_imports_for_spec(spec: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    _add_chart_imports(spec, names)
    return sorted(names)


def _add_chart_imports(spec: dict[str, Any], names: set[str]) -> None:
    if spec.get("type") == "chart":
        chart_type = (spec.get("chart") or {}).get("chart_type")
        if chart_type == "bar":
            names.update({"BarChart", "ChartSeries"})
        elif chart_type in {"line", "area", "scatter"}:
            names.update({"ChartSeries", "LineChart"})
        elif chart_type == "pie":
            names.add("PieChart")
    for child in spec.get("children") or []:
        if isinstance(child, dict):
            _add_chart_imports(child, names)


def _append_header(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    title = spec.get("title")
    summary = spec.get("summary")
    if title:
        lines.append(f"{prefix}Heading({_repr(title)}, level=2, css_class='text-xl font-semibold text-slate-950')")
    if summary and spec.get("type") != "text":
        lines.append(f"{prefix}Text(content={_repr(summary)}, css_class={PREFAB_MUTED_TEXT_CLASS!r})")


def _append_body(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    spec_type = spec.get("type")
    if spec_type == "kpi":
        _append_kpi(lines, spec, indent=indent)
    elif spec_type == "table":
        _append_table(lines, spec, indent=indent)
    elif spec_type == "chart":
        _append_chart(lines, spec, indent=indent)
    elif spec_type == "dashboard":
        _append_dashboard(lines, spec, indent=indent)
    elif spec_type == "detail":
        _append_detail(lines, spec, indent=indent)
    elif spec_type == "schema_map":
        _append_schema_map(lines, spec, indent=indent)
    elif spec_type == "error":
        _append_error(lines, spec, indent=indent)
    elif spec_type == "text":
        summary = spec.get("summary") or ""
        lines.append(f"{' ' * indent}Text(content={_repr(summary)}, css_class='text-slate-900')")
    else:
        if spec.get("rows"):
            _append_table(lines, spec, indent=indent)
        else:
            lines.append(f"{' ' * indent}Text(content='No rows to display.')")


def _append_dashboard(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    if spec.get("metrics"):
        _append_kpi(lines, spec, indent=indent)
    if spec.get("chart"):
        _append_chart(lines, spec, indent=indent)
    for child in spec.get("children") or []:
        if not isinstance(child, dict):
            continue
        lines.append(f"{prefix}with Card(css_class={PREFAB_SURFACE_CLASS!r}):")
        _append_header(lines, child, indent=indent + 4)
        _append_body(lines, child, indent=indent + 4)
    if spec.get("rows"):
        _append_table(lines, spec, indent=indent)


def _append_kpi(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    metrics = spec.get("metrics") or []
    if not metrics:
        lines.append(f"{prefix}Text(content='No metrics to display.')")
        return
    lines.append(f"{prefix}with Grid(minColumnWidth='11rem', gap=3, css_class='w-full'):")
    for metric in metrics:
        lines.append(f"{prefix}    with Card(css_class='rounded-lg border border-slate-200 bg-white p-4'):")
        args = [
            f"label={_repr(metric.get('label') or '')}",
            f"value={_repr(_string_value(metric.get('value')))}",
        ]
        if metric.get("delta") is not None:
            args.append(f"delta={_repr(metric.get('delta'))}")
        if metric.get("help") is not None:
            args.append(f"description={_repr(metric.get('help'))}")
        lines.append(f"{prefix}        Metric({', '.join(args)})")


def _append_detail(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    rows = spec.get("rows") or []
    if not rows:
        lines.append(f"{prefix}Text(content='No details to display.')")
        return

    for index, row in enumerate(rows[:8], start=1):
        if len(rows) > 1:
            lines.append(f"{prefix}Text(content={_repr(f'Record {index}')}, css_class='text-sm font-semibold text-slate-900')")

        numeric_items = [
            (str(field), value)
            for field, value in row.items()
            if _is_number(value)
        ]
        text_items = [
            (str(field), value)
            for field, value in row.items()
            if not _is_number(value) and value not in {None, ""}
        ]

        if numeric_items:
            lines.append(f"{prefix}with Grid(minColumnWidth='11rem', gap=3, css_class='w-full'):")
            for field, value in numeric_items[:8]:
                lines.append(f"{prefix}    with Card(css_class='rounded-lg border border-slate-200 bg-white p-4'):")
                lines.append(
                    f"{prefix}        Metric(label={_repr(_humanize(field))}, value={_repr(_string_value(value))})"
                )

        if text_items:
            lines.append(f"{prefix}with Grid(minColumnWidth='12rem', gap=3, css_class='w-full'):")
            for field, value in text_items[:12]:
                lines.append(f"{prefix}    with Div(css_class='rounded-md border border-slate-200 bg-slate-50 p-3'):")
                lines.append(
                    f"{prefix}        Text(content={_repr(_humanize(field))}, css_class='text-xs font-medium uppercase text-slate-500')"
                )
                lines.append(
                    f"{prefix}        Text(content={_repr(_string_value(value))}, css_class='text-sm font-semibold text-slate-950')"
                )


def _append_table(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    rows = spec.get("rows") or []
    if not rows:
        lines.append(f"{prefix}Text(content='No rows to display.')")
        return
    columns = spec.get("columns") or [{"field": key, "label": _humanize(str(key))} for key in rows[0].keys()]
    lines.append(f"{prefix}DataTable(")
    lines.append(f"{prefix}    columns=[")
    for column in columns:
        field = str(column.get("field"))
        header = column.get("label") or _humanize(field)
        lines.append(f"{prefix}        DataTableColumn(key={_repr(field)}, header={_repr(header)}, sortable=True),")
    lines.append(f"{prefix}    ],")
    lines.append(f"{prefix}    rows={_repr(rows[:100])},")
    lines.append(f"{prefix}    search=True,")
    lines.append(f"{prefix}    paginated=True,")
    lines.append(f"{prefix}    page_size=10,")
    lines.append(f"{prefix}    css_class='rounded-lg border border-slate-200 bg-white text-slate-900',")
    lines.append(f"{prefix})")


def _append_chart(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    chart = spec.get("chart") or {}
    chart_type = chart.get("chart_type")
    if chart_type == "bar":
        _append_native_bar_chart(lines, spec, indent=indent)
    elif chart_type in {"line", "area", "scatter"}:
        _append_native_line_chart(lines, spec, indent=indent)
    elif chart_type == "pie":
        _append_native_pie_chart(lines, spec, indent=indent)
    elif chart_type == "histogram":
        _append_histogram(lines, spec, indent=indent)
    else:
        _append_table(lines, spec, indent=indent)


def _append_native_bar_chart(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    chart = spec.get("chart") or {}
    rows = spec.get("rows") or []
    x_field = chart.get("x_field")
    series_fields = _chart_series_fields(spec)
    if not x_field or not series_fields:
        _append_table(lines, spec, indent=indent)
        return
    lines.append(f"{prefix}with Card(css_class={PREFAB_SURFACE_CLASS!r}):")
    lines.append(f"{prefix}    BarChart(")
    lines.append(f"{prefix}        data={_repr(rows[:100])},")
    lines.append(f"{prefix}        series=[")
    for field in series_fields:
        lines.append(f"{prefix}            ChartSeries(data_key={_repr(field)}, label={_repr(_humanize(field))}),")
    lines.append(f"{prefix}        ],")
    lines.append(f"{prefix}        x_axis={_repr(x_field)},")
    lines.append(f"{prefix}        height=360,")
    lines.append(f"{prefix}        show_legend=True,")
    lines.append(f"{prefix}        show_tooltip=True,")
    lines.append(f"{prefix}        y_axis_format='compact',")
    lines.append(f"{prefix}    )")
    if len(series_fields) > 1 or _has_extra_measure_fields(spec, series_fields):
        _append_table(lines, spec, indent=indent)


def _append_native_line_chart(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    chart = spec.get("chart") or {}
    rows = spec.get("rows") or []
    x_field = chart.get("x_field")
    series_fields = _chart_series_fields(spec)
    if not x_field or not series_fields:
        _append_table(lines, spec, indent=indent)
        return
    lines.append(f"{prefix}with Card(css_class={PREFAB_SURFACE_CLASS!r}):")
    lines.append(f"{prefix}    LineChart(")
    lines.append(f"{prefix}        data={_repr(rows[:100])},")
    lines.append(f"{prefix}        series=[")
    for field in series_fields:
        lines.append(f"{prefix}            ChartSeries(data_key={_repr(field)}, label={_repr(_humanize(field))}),")
    lines.append(f"{prefix}        ],")
    lines.append(f"{prefix}        x_axis={_repr(x_field)},")
    lines.append(f"{prefix}        height=360,")
    lines.append(f"{prefix}        show_legend=True,")
    lines.append(f"{prefix}        show_tooltip=True,")
    lines.append(f"{prefix}        y_axis_format='compact',")
    lines.append(f"{prefix}    )")
    if len(series_fields) > 1 or _has_extra_measure_fields(spec, series_fields):
        _append_table(lines, spec, indent=indent)


def _append_native_pie_chart(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    chart = spec.get("chart") or {}
    rows = spec.get("rows") or []
    label_field = chart.get("label_field") or chart.get("x_field")
    value_field = chart.get("value_field") or chart.get("y_field")
    if not label_field or not value_field:
        _append_table(lines, spec, indent=indent)
        return
    lines.append(f"{prefix}with Card(css_class={PREFAB_SURFACE_CLASS!r}):")
    lines.append(f"{prefix}    PieChart(")
    lines.append(f"{prefix}        data={_repr(rows[:100])},")
    lines.append(f"{prefix}        data_key={_repr(value_field)},")
    lines.append(f"{prefix}        name_key={_repr(label_field)},")
    lines.append(f"{prefix}        height=360,")
    lines.append(f"{prefix}        show_legend=True,")
    lines.append(f"{prefix}        show_tooltip=True,")
    lines.append(f"{prefix}    )")
    if _has_extra_measure_fields(spec, [value_field]):
        _append_table(lines, spec, indent=indent)


def _append_histogram(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    chart = spec.get("chart") or {}
    x_field = chart.get("x_field")
    values = [_numeric_value(row.get(x_field)) for row in spec.get("rows", [])] if x_field else []
    if not values:
        lines.append(f"{prefix}Text(content='No chart data to display.')")
        return
    lines.append(f"{prefix}with Div(css_class={PREFAB_SURFACE_CLASS!r}):")
    lines.append(f"{prefix}    Histogram(values={_repr(values)}, bins=12, height=320, show_grid=True)")


def _append_schema_map(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    mermaid = spec.get("mermaid")
    if not mermaid:
        lines.append(f"{prefix}Text(content='No schema diagram available.')")
        return
    lines.append(f"{prefix}with Card(css_class={PREFAB_SURFACE_CLASS!r}):")
    lines.append(f"{prefix}    Mermaid({_repr(mermaid)})")


def _append_error(lines: list[str], spec: dict[str, Any], *, indent: int) -> None:
    prefix = " " * indent
    lines.append(f"{prefix}with Alert(variant='destructive', icon='circle-alert'):")
    lines.append(f"{prefix}    AlertTitle('Error')")
    lines.append(f"{prefix}    AlertDescription({_repr(spec.get('summary') or 'Something went wrong.')})")


def _repr(value: Any) -> str:
    return repr(value)


def _string_value(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def _numeric_value(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_numeric_field(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    for field in rows[0].keys():
        if any(_numeric_value(row.get(field)) > 0 for row in rows):
            return str(field)
    return None


def _chart_series_fields(spec: dict[str, Any]) -> list[str]:
    rows = spec.get("rows") or []
    if not rows:
        return []
    chart = spec.get("chart") or {}
    x_field = chart.get("x_field")
    preferred = [chart.get("y_field"), chart.get("value_field")]
    numeric_fields = [
        str(field)
        for field in rows[0].keys()
        if field != x_field and any(_is_number(row.get(field)) for row in rows)
    ]
    ordered = []
    for field in [*preferred, *numeric_fields]:
        if field and field in numeric_fields and field not in ordered:
            ordered.append(str(field))
    return ordered[:4]


def _has_extra_measure_fields(spec: dict[str, Any], visible_fields: list[str]) -> bool:
    rows = spec.get("rows") or []
    if not rows:
        return False
    chart = spec.get("chart") or {}
    x_field = chart.get("x_field") or chart.get("label_field")
    visible = set(visible_fields)
    for field in rows[0].keys():
        if field == x_field or field in visible:
            continue
        if any(_is_number(row.get(field)) for row in rows):
            return True
    return False


def _chart_needs_table(spec: dict[str, Any]) -> bool:
    chart = spec.get("chart") or {}
    chart_type = chart.get("chart_type")
    if chart_type not in {"bar", "line", "area", "pie"}:
        return False
    if chart_type == "pie":
        visible_fields = [field for field in [chart.get("value_field"), chart.get("y_field")] if field]
    else:
        visible_fields = _chart_series_fields(spec)
    return len(visible_fields) > 1 or _has_extra_measure_fields(spec, [str(field) for field in visible_fields])


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
        return value is not None
    except (TypeError, ValueError):
        return False


def _bar_label(row: dict[str, Any], spec: dict[str, Any]) -> str:
    chart = spec.get("chart") or {}
    fields = [
        field
        for field in [chart.get("label_field"), chart.get("x_field"), chart.get("color_field")]
        if field and field in row
    ]
    if not fields:
        fields = [field for field, value in row.items() if isinstance(value, str) and value.strip()]
    if not fields:
        return "Record"
    return " / ".join(str(row.get(field, "")) for field in fields if row.get(field) not in {None, ""})[:96]


def _format_number(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()
