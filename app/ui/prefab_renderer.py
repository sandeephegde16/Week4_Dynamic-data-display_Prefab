"""Render dynamic UI specs as inline Prefab HTML."""

from __future__ import annotations

import html
import json
from typing import Any

from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Accordion,
    AccordionItem,
    Alert,
    AlertDescription,
    AlertTitle,
    Badge,
    Card,
    Code,
    Column,
    Combobox,
    ComboboxOption,
    Dashboard,
    DashboardItem,
    DataTable,
    DataTableColumn,
    DatePicker,
    Div,
    Grid,
    Heading,
    Histogram,
    Markdown,
    Mermaid,
    Metric,
    Row,
    Select,
    SelectOption,
    Slider,
    Svg,
    Switch,
    Tab,
    Tabs,
    Text,
)

from app.ui.specs import ColumnSpec, FilterSpec, UISpec
from app.ui.theme import PREFAB_APP_CLASS, PREFAB_EMBED_STYLES, PREFAB_MUTED_TEXT_CLASS, PREFAB_SURFACE_CLASS


def render_prefab_html(spec: UISpec) -> str:
    return build_prefab_app(spec).html()


def build_prefab_app(spec: UISpec) -> PrefabApp:
    with PrefabApp(
        title=spec.title or "Dynamic Result",
        css_class=PREFAB_APP_CLASS,
        stylesheets=[PREFAB_EMBED_STYLES],
    ) as app:
        with Column(gap=4, css_class="w-full"):
            Heading(spec.title or "Result", level=2, css_class="text-xl font-semibold text-slate-950")
            if spec.message and spec.type != "text":
                Text(content=spec.message, css_class=PREFAB_MUTED_TEXT_CLASS)
            _render_spec_body(spec)
    return app


def build_empty_state_app() -> PrefabApp:
    with PrefabApp(
        title="Dynamic Database Chat",
        css_class=PREFAB_APP_CLASS,
        stylesheets=[PREFAB_EMBED_STYLES],
    ) as app:
        with Column(gap=3, css_class=PREFAB_SURFACE_CLASS):
            Heading("Ready for database analysis", level=2, css_class="text-xl font-semibold text-slate-950")
            Text(
                content="Ask a question and the assistant will choose an interactive view when it helps the answer.",
                css_class=PREFAB_MUTED_TEXT_CLASS,
            )
    return app


def _render_spec_body(spec: UISpec) -> None:
    if spec.type == "error":
        with Alert(variant="destructive", icon="circle-alert"):
            AlertTitle("Error")
            AlertDescription(spec.message or "Something went wrong.")
        return

    if spec.type == "kpi":
        _render_metrics(spec)
    elif spec.type == "table":
        _render_table(spec)
    elif spec.type == "chart":
        _render_chart(spec)
    elif spec.type == "dashboard":
        _render_dashboard(spec)
    elif spec.type == "detail":
        _render_detail(spec)
    elif spec.type == "filters":
        _render_filter_panel(spec)
    elif spec.type == "schema_map":
        _render_schema_map(spec)
    elif spec.type == "schema_analysis":
        _render_schema_analysis(spec)
    elif spec.type == "text":
        Markdown(content=spec.message or "", css_class="text-slate-900")
    else:
        Text(content="Unsupported Prefab spec.")


def _render_metrics(spec: UISpec) -> None:
    if not spec.metrics:
        _render_table(spec)
        return
    with Grid(minColumnWidth="11rem", gap=3, css_class="w-full"):
        for metric in spec.metrics[:4]:
            with Card(css_class="rounded-lg border border-slate-200 bg-white p-4"):
                Metric(
                    label=metric.label,
                    value=_string_value(metric.value),
                    delta=metric.delta,
                    description=metric.help,
                )


def _render_table(spec: UISpec) -> None:
    rows = spec.rows[:100]
    if not rows:
        Text(content="No rows to display.")
        return
    columns = spec.columns or [ColumnSpec(field=key, label=_humanize(key)) for key in rows[0].keys()]
    DataTable(
        columns=[
            DataTableColumn(key=column.field, header=column.label or _humanize(column.field), sortable=True)
            for column in columns
        ],
        rows=rows,
        search=True,
        paginated=True,
        page_size=10,
        css_class="rounded-lg border border-slate-200 bg-white text-slate-900",
    )


def _render_chart(spec: UISpec) -> None:
    if spec.chart is None or not spec.rows:
        Text(content="No chart data to display.")
        return

    chart = spec.chart
    if chart.chart_type == "bar":
        _render_bar_chart(spec)
        return

    if chart.chart_type in {"line", "area", "scatter"} and chart.x_field and chart.y_field:
        _render_xy_svg_chart(spec)
        return

    if chart.chart_type == "pie":
        _render_pie_chart(spec)
        return

    if chart.chart_type == "histogram" and chart.x_field:
        values = [_numeric_value(row.get(chart.x_field)) for row in spec.rows]
        with Div(css_class=PREFAB_SURFACE_CLASS):
            Histogram(values=values, bins=12, height=320, show_grid=True)
        return

    _render_table(spec)


def _render_bar_chart(spec: UISpec) -> None:
    chart = spec.chart
    if chart is None:
        Text(content="No chart data to display.")
        return

    y_field = chart.y_field or _first_numeric_field(spec.rows)
    if y_field is None:
        _render_table(spec)
        return

    rows = [row for row in spec.rows if _numeric_value(row.get(y_field)) > 0][:20]
    if not rows:
        Text(content="No chart data to display.")
        return

    max_value = max(_numeric_value(row.get(y_field)) for row in rows) or 1.0
    with Column(gap=3, css_class=PREFAB_SURFACE_CLASS):
        for row in rows:
            value = _numeric_value(row.get(y_field))
            width = max(3.0, min(100.0, (value / max_value) * 100.0))
            with Row(gap=3, align="center", css_class="w-full min-w-0"):
                Badge(label=_bar_label(row, spec), variant="secondary", css_class="w-44 shrink-0 truncate")
                with Div(css_class="h-4 min-w-16 flex-1 rounded bg-slate-200"):
                    with Div(css_class="h-4 rounded bg-blue-600", style={"width": f"{width:.1f}%"}):
                        pass
                Text(
                    content=_format_number(value),
                    css_class="w-36 shrink-0 overflow-hidden text-ellipsis text-right text-sm font-semibold tabular-nums text-slate-900",
                )


def _render_dashboard(spec: UISpec) -> None:
    row = 1
    with Dashboard(columns=12, rowHeight="auto", gap=3):
        if spec.filters:
            with DashboardItem(col=1, row=row, colSpan=12, rowSpan=1):
                with Card(css_class=PREFAB_SURFACE_CLASS):
                    _render_filter_controls(spec.filters)
            row += 1

        if spec.metrics:
            with DashboardItem(col=1, row=row, colSpan=12, rowSpan=1):
                _render_metrics(spec)
            row += 1

        with DashboardItem(col=1, row=row, colSpan=8, rowSpan=3):
            with Card(css_class=PREFAB_SURFACE_CLASS):
                Heading("Visual", level=3, css_class="mb-3 text-base font-semibold text-slate-950")
                if spec.chart is not None:
                    _render_chart(spec)
                elif spec.rows:
                    _render_table(spec)
                else:
                    Text(content="No rows to display.", css_class=PREFAB_MUTED_TEXT_CLASS)

        with DashboardItem(col=9, row=row, colSpan=4, rowSpan=3):
            with Card(css_class=PREFAB_SURFACE_CLASS):
                Heading("Record Preview", level=3, css_class="mb-3 text-base font-semibold text-slate-950")
                _render_record_preview(spec)

        with DashboardItem(col=1, row=row + 3, colSpan=12, rowSpan=3):
            with Card(css_class=PREFAB_SURFACE_CLASS):
                with Tabs(value="rows"):
                    with Tab("Rows", value="rows"):
                        _render_table(spec)
                    with Tab("Details", value="details"):
                        _render_detail_cards(spec)
                    if spec.debug:
                        with Tab("Debug", value="debug"):
                            _render_debug_summary(spec)


def _render_filter_panel(spec: UISpec) -> None:
    _render_filter_controls(spec.filters)
    if spec.rows:
        _render_table(spec)


def _render_filter_controls(filters: list[FilterSpec]) -> None:
    if not filters:
        return
    with Grid(minColumnWidth="12rem", gap=3, css_class="w-full rounded-lg border border-slate-200 bg-slate-50 p-3"):
        for filter_spec in filters[:4]:
            label = filter_spec.label or _humanize(filter_spec.field)
            with Div(css_class="min-w-44 flex-1"):
                Badge(label=label, variant="outline", css_class="mb-2")
                if filter_spec.control == "date":
                    DatePicker(placeholder=f"Select {label}", name=f"filter_{filter_spec.field}")
                elif filter_spec.control == "slider":
                    Slider(
                        min=_numeric_value(filter_spec.min_value),
                        max=_numeric_value(filter_spec.max_value),
                        value=_numeric_value(filter_spec.value if filter_spec.value is not None else filter_spec.min_value),
                        name=f"filter_{filter_spec.field}",
                        indicator_class="bg-blue-600",
                    )
                elif filter_spec.control == "switch":
                    Switch(label=label, value=bool(filter_spec.value), name=f"filter_{filter_spec.field}")
                elif filter_spec.control == "combobox":
                    with Combobox(placeholder=f"Search {label}", name=f"filter_{filter_spec.field}"):
                        for option in filter_spec.options[:30]:
                            ComboboxOption(str(option), value=str(option))
                else:
                    with Select(placeholder=f"Select {label}", name=f"filter_{filter_spec.field}"):
                        for option in filter_spec.options[:20]:
                            SelectOption(value=str(option), label=str(option))


def _render_detail(spec: UISpec) -> None:
    if not spec.rows:
        Text(content="No rows to display.", css_class=PREFAB_MUTED_TEXT_CLASS)
        return

    with Tabs(value="cards"):
        with Tab("Cards", value="cards"):
            _render_detail_cards(spec)
        with Tab("Table", value="table"):
            _render_table(spec)


def _render_detail_cards(spec: UISpec) -> None:
    if not spec.rows:
        Text(content="No rows to display.", css_class=PREFAB_MUTED_TEXT_CLASS)
        return

    with Accordion(default_open_items=0, css_class="rounded-lg border border-slate-200 bg-white px-3"):
        for index, row in enumerate(spec.rows[:10], start=1):
            with AccordionItem(_detail_label(row, index)):
                with Card(css_class="my-2 rounded-lg border border-slate-200 bg-slate-50 p-3"):
                    for field, value in row.items():
                        with Row(gap=2, css_class="w-full border-b border-slate-200 py-1 last:border-b-0"):
                            Badge(label=_humanize(str(field)), variant="outline", css_class="w-44")
                            Text(content=_string_value(value), css_class="flex-1 text-sm text-slate-700")


def _render_xy_svg_chart(spec: UISpec) -> None:
    chart = spec.chart
    if chart is None or not chart.y_field:
        _render_table(spec)
        return
    rows = spec.rows[:80]
    values = [_numeric_value(row.get(chart.y_field)) for row in rows]
    if not values:
        _render_table(spec)
        return

    width = 720
    height = 320
    left = 46
    top = 24
    chart_width = width - 70
    chart_height = height - 64
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 1.0)
    points = []
    for index, value in enumerate(values):
        x = left + (index / max(len(values) - 1, 1)) * chart_width
        y = top + chart_height - ((value - min_value) / span) * chart_height
        points.append((x, y))

    point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    circles = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='#2563eb' />" for x, y in points)
    area = ""
    if chart.chart_type == "area":
        area_points = f"{left},{top + chart_height} {point_text} {left + chart_width},{top + chart_height}"
        area = f"<polygon points='{area_points}' fill='rgba(37, 99, 235, 0.14)' />"
    line = "" if chart.chart_type == "scatter" else f"<polyline points='{point_text}' fill='none' stroke='#2563eb' stroke-width='3' />"
    label = html.escape(_humanize(chart.y_field))
    svg = f"""
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" aria-label="{label}">
      <rect width="{width}" height="{height}" rx="12" fill="#ffffff" />
      <line x1="{left}" y1="{top + chart_height}" x2="{left + chart_width}" y2="{top + chart_height}" stroke="#cbd5e1" />
      <line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="#cbd5e1" />
      {area}
      {line}
      {circles}
      <text x="{left}" y="{height - 16}" fill="#64748b" font-size="12">{html.escape(_humanize(chart.x_field or 'index'))}</text>
      <text x="{left}" y="18" fill="#0f172a" font-size="13">{label}</text>
    </svg>
    """
    with Div(css_class=PREFAB_SURFACE_CLASS):
        Svg(content=svg)


def _render_pie_chart(spec: UISpec) -> None:
    chart = spec.chart
    value_field = chart.value_field or chart.y_field if chart else None
    label_field = chart.label_field or chart.x_field if chart else None
    if not value_field or not label_field:
        _render_table(spec)
        return
    rows = [row for row in spec.rows if _numeric_value(row.get(value_field)) > 0][:8]
    total = sum(_numeric_value(row.get(value_field)) for row in rows)
    if not rows or total <= 0:
        _render_table(spec)
        return
    colors = ["#2563eb", "#7c3aed", "#0891b2", "#f59e0b", "#db2777", "#16a34a", "#dc2626", "#94a3b8"]
    stops = []
    start = 0.0
    for index, row in enumerate(rows):
        value = _numeric_value(row.get(value_field))
        end = start + (value / total) * 100.0
        stops.append(f"{colors[index % len(colors)]} {start:.2f}% {end:.2f}%")
        start = end
    with Row(gap=4, css_class=PREFAB_SURFACE_CLASS):
        Div(css_class="h-48 w-48 rounded-full", style={"background": f"conic-gradient({', '.join(stops)})"})
        with Column(gap=2, css_class="min-w-52 flex-1"):
            for index, row in enumerate(rows):
                value = _numeric_value(row.get(value_field))
                percent = (value / total) * 100.0
                with Row(gap=2, align="center"):
                    Div(css_class="h-3 w-3 rounded-full", style={"background": colors[index % len(colors)]})
                    Text(content=f"{row.get(label_field)}", css_class="flex-1 truncate text-sm text-slate-700")
                    Text(content=f"{percent:.1f}%", css_class="text-sm font-semibold text-slate-900")


def _render_schema_analysis(spec: UISpec) -> None:
    questions = spec.debug.get("likely_questions") or []
    if questions:
        with Card(css_class=PREFAB_SURFACE_CLASS):
            Heading("Likely questions", level=3, css_class="text-base font-semibold text-slate-950")
            Markdown(content="\n".join(f"- {question}" for question in questions[:8]), css_class="text-slate-700")
    if spec.rows:
        with Grid(minColumnWidth="9rem", gap=2, css_class="my-3"):
            for row in spec.rows[:8]:
                widget = row.get("widget")
                if widget:
                    Badge(label=str(widget), variant="info")
    if spec.mermaid:
        _render_schema_map(spec)
    if spec.rows:
        _render_table(spec)


def _render_schema_map(spec: UISpec) -> None:
    if not spec.mermaid:
        Text(content="No schema diagram available.", css_class=PREFAB_MUTED_TEXT_CLASS)
        return
    with Tabs(value="diagram"):
        with Tab("Diagram", value="diagram"):
            with Card(css_class=PREFAB_SURFACE_CLASS):
                Mermaid(spec.mermaid)
        with Tab("Mermaid Source", value="source"):
            with Card(css_class=PREFAB_SURFACE_CLASS):
                Code(content=spec.mermaid, language="mermaid")


def _render_record_preview(spec: UISpec) -> None:
    if not spec.rows:
        Text(content="No record preview available.", css_class=PREFAB_MUTED_TEXT_CLASS)
        return

    row = spec.rows[0]
    with Column(gap=2):
        for field, value in list(row.items())[:8]:
            with Row(gap=2, css_class="items-start border-b border-slate-200 pb-2 last:border-b-0"):
                Badge(label=_humanize(str(field)), variant="outline", css_class="shrink-0")
                Text(content=_string_value(value), css_class="min-w-0 flex-1 break-words text-sm text-slate-700")


def _render_debug_summary(spec: UISpec) -> None:
    with Accordion(default_open_items=None, css_class="rounded-lg border border-slate-200 bg-white px-3"):
        with AccordionItem("UI Spec Debug"):
            Markdown(content="Planner, SQL, result metadata, and validated UI spec details.", css_class=PREFAB_MUTED_TEXT_CLASS)
            Code(content=json.dumps(spec.debug, indent=2, default=str), language="json")


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


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _first_numeric_field(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    for field in rows[0].keys():
        if any(_numeric_value(row.get(field)) > 0 for row in rows):
            return str(field)
    return None


def _bar_label(row: dict[str, Any], spec: UISpec) -> str:
    chart = spec.chart
    fields: list[str] = []
    if chart is not None:
        for field in [chart.label_field, chart.x_field, chart.color_field]:
            if field and field in row and field not in fields:
                fields.append(field)

    for field, value in row.items():
        if field in fields:
            continue
        if _is_visual_label_value(value):
            fields.append(str(field))
        if len(fields) >= 3:
            break

    if not fields:
        return "Record"
    return " / ".join(str(row.get(field, "")) for field in fields if row.get(field) not in {None, ""})[:96]


def _is_visual_label_value(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return False
    return bool(str(value).strip())


def _format_number(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _detail_label(row: dict[str, Any], index: int) -> str:
    for value in row.values():
        if value not in {None, ""} and not isinstance(value, int | float | bool):
            return str(value)[:80]
    return f"Row {index}"
