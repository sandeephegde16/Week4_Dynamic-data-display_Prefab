"""Render validated UI specs in Streamlit."""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from app.debug import log_event
from app.ui.prefab_file import render_current_prefab_html, write_current_prefab_app
from app.ui.specs import AssistantResponse, UISpec


def render_assistant_response(response: AssistantResponse, *, show_debug: bool, use_prefab: bool = False) -> None:
    if _should_render_response_message(response):
        st.markdown(response.message)
    if response.ui_spec is not None:
        write_current_prefab_app(response.ui_spec)
        if use_prefab:
            rendered = _try_render_prefab(response.ui_spec)
            if not rendered:
                render_ui_spec(response.ui_spec)
        else:
            render_ui_spec(response.ui_spec)
    if show_debug and (response.debug or (response.ui_spec and response.ui_spec.debug)):
        with st.expander("Debug", expanded=False):
            if response.debug:
                st.json(response.debug)
            if response.ui_spec is not None:
                st.subheader("UI Spec")
                st.json(response.ui_spec.model_dump())


def _should_render_response_message(response: AssistantResponse) -> bool:
    message = response.message.strip()
    if not message:
        return False
    if response.ui_spec is None:
        return True
    if response.ui_spec.type in {"text", "error"} and message == (response.ui_spec.message or "").strip():
        return False
    return True


def _try_render_prefab(spec: UISpec) -> bool:
    try:
        html = render_current_prefab_html()
        components.html(html, height=_prefab_height(spec), scrolling=True)
        log_event(
            "Rendered response from generated Prefab file.",
            {"type": spec.type, "title": spec.title},
        )
        return True
    except Exception as exc:
        log_event("Prefab render failed. Falling back to Streamlit renderer.", {"error": str(exc), "type": spec.type})
        st.warning(f"Prefab render failed, using Streamlit fallback: {exc}")
        return False


def _prefab_height(spec: UISpec) -> int:
    if spec.type == "table":
        return 520
    if spec.type == "schema_analysis":
        return 620
    if spec.type == "dashboard":
        return 720
    if spec.type in {"detail", "filters", "schema_map"}:
        return 560
    if spec.type == "chart":
        return _chart_prefab_height(spec)
    if spec.type == "kpi":
        return 220
    if spec.type == "text":
        return 160
    return 260


def _chart_prefab_height(spec: UISpec) -> int:
    chart_type = spec.chart.chart_type if spec.chart is not None else None
    row_count = len(spec.rows)
    if chart_type == "bar":
        return min(720, max(290, 185 + min(row_count, 20) * 34))
    if chart_type == "pie":
        return 350
    if chart_type in {"line", "area", "scatter", "histogram"}:
        return 430
    return 360


def render_ui_spec(spec: UISpec) -> None:
    if spec.type == "error":
        st.error(spec.message or spec.title)
        return

    if spec.type == "text":
        return

    if spec.type == "schema_analysis":
        _render_schema_analysis(spec)
        return

    if spec.type == "dashboard":
        _render_dashboard(spec)
        return

    if spec.type == "detail":
        _render_detail(spec)
        return

    if spec.type == "filters":
        _render_filter_panel(spec)
        return

    if spec.type == "schema_map":
        _render_schema_map(spec)
        return

    if spec.title:
        st.markdown(f"**{spec.title}**")
    if spec.message:
        st.caption(spec.message)

    if spec.type == "kpi":
        _render_kpis(spec)
    elif spec.type == "table":
        _render_table(spec)
    elif spec.type == "chart":
        _render_chart(spec)
    else:
        st.info(spec.message or "Unsupported UI spec.")


def _render_kpis(spec: UISpec) -> None:
    metrics = spec.metrics[:12]
    if not metrics:
        _render_table(spec)
        return
    for start in range(0, len(metrics), 4):
        row_metrics = metrics[start : start + 4]
        columns = st.columns(len(row_metrics))
        for column, metric in zip(columns, row_metrics, strict=False):
            column.metric(metric.label, metric.value, metric.delta, help=metric.help)


def _render_table(spec: UISpec) -> None:
    frame = pd.DataFrame(spec.rows)
    if frame.empty:
        st.info("No rows to display.")
        return
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _render_chart(spec: UISpec) -> None:
    frame = pd.DataFrame(spec.rows)
    if frame.empty or spec.chart is None:
        st.info("No chart data to display.")
        return

    chart = spec.chart
    try:
        if chart.chart_type == "bar":
            fig = px.bar(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field)
        elif chart.chart_type == "line":
            fig = px.line(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field, markers=True)
        elif chart.chart_type == "area":
            fig = px.area(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field)
        elif chart.chart_type == "pie":
            fig = px.pie(frame, names=chart.label_field, values=chart.value_field)
        elif chart.chart_type == "scatter":
            fig = px.scatter(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field)
        elif chart.chart_type == "histogram":
            fig = px.histogram(frame, x=chart.x_field, color=chart.color_field)
        else:
            _render_table(spec)
            return
        fig.update_layout(
            margin=dict(l=8, r=8, t=28, b=8),
            height=360,
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font_color="#0f172a",
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Chart rendering failed: {exc}")
        _render_table(spec)


def _render_dashboard(spec: UISpec) -> None:
    _render_header(spec)
    filtered_rows = _render_filters(spec)
    working_spec = spec.model_copy(update={"rows": filtered_rows}) if filtered_rows is not spec.rows else spec

    if spec.metrics:
        _render_kpis(spec)

    if spec.children:
        for child in spec.children:
            with st.container(border=True):
                render_ui_spec(child)
        return

    visual_tab, rows_tab, detail_tab = st.tabs(["Visual", "Rows", "Details"])
    with visual_tab:
        if working_spec.chart is not None:
            _render_chart(working_spec)
        elif working_spec.rows:
            _render_table(working_spec)
        else:
            st.info("No rows to display.")
    with rows_tab:
        _render_table(working_spec)
    with detail_tab:
        _render_detail(working_spec, include_header=False)


def _render_detail(spec: UISpec, *, include_header: bool = True) -> None:
    if include_header:
        _render_header(spec)
    if spec.filters:
        rows = _render_filters(spec)
        spec = spec.model_copy(update={"rows": rows})

    if not spec.rows:
        st.info("No rows to display.")
        return

    if len(spec.rows) == 1:
        row = spec.rows[0]
        numeric_items = [(key, value) for key, value in row.items() if _is_number(value)]
        text_items = [(key, value) for key, value in row.items() if not _is_number(value) and value not in {None, ""}]
        if numeric_items:
            for start in range(0, min(len(numeric_items), 12), 4):
                row_items = numeric_items[start : start + 4]
                columns = st.columns(len(row_items))
                for column, (key, value) in zip(columns, row_items, strict=False):
                    column.metric(_humanize(str(key)), value)
        if text_items:
            columns = st.columns(min(3, len(text_items)))
            for index, (key, value) in enumerate(text_items[:12]):
                with columns[index % len(columns)]:
                    st.caption(_humanize(str(key)))
                    st.markdown(f"**{value}**")
        return

    for index, row in enumerate(spec.rows[:12], start=1):
        label = _detail_label(row, index)
        with st.expander(label, expanded=index == 1):
            frame = pd.DataFrame([{"Field": _humanize(key), "Value": value} for key, value in row.items()])
            st.dataframe(frame, use_container_width=True, hide_index=True)

    if len(spec.rows) > 12:
        st.caption(f"{len(spec.rows) - 12} more rows are available in the table view.")


def _render_filter_panel(spec: UISpec) -> None:
    _render_header(spec)
    rows = _render_filters(spec)
    _render_table(spec.model_copy(update={"rows": rows}))


def _render_schema_analysis(spec: UISpec) -> None:
    _render_header(spec)

    likely_questions = spec.debug.get("likely_questions") or []
    if likely_questions:
        st.markdown("**Likely questions**")
        for question in likely_questions[:10]:
            st.markdown(f"- {question}")

    if spec.mermaid:
        _render_schema_map(
            spec.model_copy(
                update={
                    "type": "schema_map",
                    "title": "Schema Relationships",
                    "message": "Foreign-key and table relationship overview.",
                }
            )
        )

    if spec.rows:
        st.markdown("**Recommended widgets**")
        st.dataframe(pd.DataFrame(spec.rows), use_container_width=True, hide_index=True)


def _render_schema_map(spec: UISpec) -> None:
    if spec.title:
        st.markdown(f"**{spec.title}**")
    if spec.message:
        st.caption(spec.message)
    if not spec.mermaid:
        st.info("No schema diagram available.")
        return
    diagram = html.escape(spec.mermaid)
    components.html(
        f"""
        <html>
        <head>
          <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
          </script>
          <style>
            html, body {{
              margin: 0;
              background: #ffffff;
              color: #0f172a;
            }}
            .mermaid {{
              display: flex;
              justify-content: center;
              min-height: 300px;
              padding: 1rem;
              border: 1px solid #cbd5e1;
              border-radius: 10px;
              background: #ffffff;
            }}
          </style>
        </head>
        <body><pre class="mermaid">{diagram}</pre></body>
        </html>
        """,
        height=360,
        scrolling=True,
    )


def _render_header(spec: UISpec) -> None:
    if spec.title:
        st.markdown(f"**{spec.title}**")
    if spec.message:
        st.caption(spec.message)


def _render_filters(spec: UISpec) -> list[dict[str, object]]:
    if not spec.filters or not spec.rows:
        return spec.rows

    frame = pd.DataFrame(spec.rows)
    with st.container():
        columns = st.columns(min(4, len(spec.filters)))
        for index, filter_spec in enumerate(spec.filters):
            column = columns[index % len(columns)]
            label = filter_spec.label or _humanize(filter_spec.field)
            key = f"filter_{spec.title}_{filter_spec.field}_{filter_spec.control}_{index}"
            if filter_spec.field not in frame.columns:
                continue
            with column:
                if filter_spec.control in {"select", "combobox"}:
                    options = ["All", *filter_spec.options]
                    value = st.selectbox(label, options, key=key)
                    if value != "All":
                        frame = frame[frame[filter_spec.field].astype(str) == str(value)]
                elif filter_spec.control == "slider":
                    low = _number_or_default(filter_spec.min_value, 0.0)
                    high = _number_or_default(filter_spec.max_value, low)
                    if low != high:
                        selected = st.slider(label, min_value=float(low), max_value=float(high), value=(float(low), float(high)), key=key)
                        numeric = pd.to_numeric(frame[filter_spec.field], errors="coerce")
                        frame = frame[(numeric >= selected[0]) & (numeric <= selected[1])]
                elif filter_spec.control == "switch":
                    enabled = st.toggle(label, value=bool(filter_spec.value), key=key)
                    if enabled:
                        frame = frame[frame[filter_spec.field].astype(str).str.lower().isin({"1", "true", "yes"})]
                elif filter_spec.control == "date":
                    dates = pd.to_datetime(frame[filter_spec.field], errors="coerce")
                    valid_dates = dates.dropna()
                    if not valid_dates.empty:
                        min_date = valid_dates.min().date()
                        max_date = valid_dates.max().date()
                        selected = st.date_input(label, value=(min_date, max_date), key=key)
                        if isinstance(selected, tuple) and len(selected) == 2:
                            start, end = selected
                            if isinstance(start, date) and isinstance(end, date):
                                frame = frame[(dates.dt.date >= start) & (dates.dt.date <= end)]

    return frame.to_dict(orient="records")


def _number_or_default(value: object, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _detail_label(row: dict[str, object], index: int) -> str:
    for key, value in row.items():
        if value not in {None, ""} and not isinstance(value, int | float | bool):
            return str(value)[:80]
    return f"Row {index}"


def _is_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
        return value is not None
    except (TypeError, ValueError):
        return False


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()
