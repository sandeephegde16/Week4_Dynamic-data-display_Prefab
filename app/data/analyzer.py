"""Heuristic database analysis for likely questions and UI widgets."""

from __future__ import annotations

from app.data.schema import ColumnInfo, DatabaseSchema, TableInfo
from app.ui.widget_catalog import components_for_widget


def analyze_schema_heuristically(schema: DatabaseSchema) -> dict[str, object]:
    time_tables = []
    numeric_tables = []
    categorical_tables = []
    detail_tables = []
    likely_questions: list[str] = []
    widgets: list[dict[str, object]] = []

    for table in schema.tables:
        date_columns = [column for column in table.columns if column.is_datetime]
        numeric_columns = [column for column in table.columns if column.is_numeric and not _looks_like_id(column)]
        category_columns = [column for column in table.columns if column.looks_categorical]
        name_columns = [column for column in table.columns if _looks_like_name(column)]

        if date_columns:
            time_tables.append(_table_signal(table, date_columns))
            likely_questions.append(
                f"Count records in {table.table_name} over time by month using {date_columns[0].column_name}."
            )
        if numeric_columns:
            numeric_tables.append(_table_signal(table, numeric_columns))
            likely_questions.append(f"What is the total and average {numeric_columns[0].column_name} in {table.table_name}?")
        if category_columns:
            categorical_tables.append(_table_signal(table, category_columns))
            likely_questions.append(f"Show distribution of {table.table_name} by {category_columns[0].column_name}.")
        if name_columns or table.primary_keys:
            detail_tables.append(_table_signal(table, name_columns or table.columns[:3]))
            likely_questions.append(f"List recent records from {table.table_name}.")

    if time_tables:
        widgets.append(
            _widget(
                "dashboard",
                "time-series summaries that benefit from KPI cards, trend charts, filters, and drilldown rows",
                time_tables,
            )
        )
        widgets.append(_widget("line_chart", "time trends, month-by-month counts, daily activity, date-based sums", time_tables))
        widgets.append(_widget("bar_chart", "period comparisons and grouped time buckets", time_tables))
    if categorical_tables:
        widgets.append(
            _widget(
                "filter_panel",
                "refining tables or dashboards by status, type, category, channel, source, or stage",
                categorical_tables,
            )
        )
        widgets.append(_widget("bar_chart", "counts or sums grouped by low-cardinality categorical fields", categorical_tables))
        widgets.append(_widget("pie_chart", "small category distributions with fewer than six slices", categorical_tables))
    if numeric_tables:
        widgets.append(_widget("kpi", "single totals, averages, maximums, minimums, rates, and headline metrics", numeric_tables))
        widgets.append(_widget("histogram", "distribution of numeric values", numeric_tables))
    if detail_tables:
        widgets.append(_widget("table", "record lists, top-N rankings, audit-style results, and drilldown rows", detail_tables))
        widgets.append(_widget("detail_panel", "one selected record from any table", detail_tables))
    if any(table.foreign_keys for table in schema.tables):
        widgets.append(
            {
                "widget": "schema_map",
                "recommended_components": components_for_widget("schema_map"),
                "use_for": "foreign-key and table relationship overviews rendered as a Mermaid diagram",
                "schema_signals": [
                    {
                        "table": table.table_name,
                        "foreign_keys": [foreign_key.model_dump() for foreign_key in table.foreign_keys[:4]],
                    }
                    for table in schema.tables
                    if table.foreign_keys
                ][:8],
            }
        )

    return {
        "database": "runtime_configured_database",
        "table_count": len(schema.tables),
        "domain_guess": _schema_profile(schema),
        "likely_questions": _dedupe(likely_questions)[:20],
        "recommended_widgets": widgets,
        "notes": [
            "This is a heuristic analysis. Claude can refine it when ANTHROPIC_API_KEY is configured.",
            "Widget choice should be driven by result shape: one number -> KPI, rows -> table/detail, time/category aggregation -> chart/dashboard, relationship requests -> schema map.",
        ],
    }


def _widget(widget: str, use_for: str, schema_signals: list[dict[str, object]]) -> dict[str, object]:
    return {
        "widget": widget,
        "recommended_components": components_for_widget(widget),
        "use_for": use_for,
        "schema_signals": schema_signals[:8],
    }


def _table_signal(table: TableInfo, columns: list[ColumnInfo]) -> dict[str, object]:
    return {
        "table": table.table_name,
        "columns": [column.column_name for column in columns[:6]],
        "row_count_estimate": table.row_count_estimate,
    }


def _looks_like_id(column: ColumnInfo) -> bool:
    name = column.column_name.lower()
    return column.is_primary_key or name == "id" or name.endswith("_id")


def _looks_like_name(column: ColumnInfo) -> bool:
    name = column.column_name.lower()
    return column.is_text and (name in {"name", "title", "code", "email"} or name.endswith("_name"))


def _schema_profile(schema: DatabaseSchema) -> str:
    if not schema.tables:
        return "empty relational database"

    table_names = [table.table_name for table in schema.tables[:4]]
    if len(schema.tables) > 4:
        table_names.append("...")
    return f"relational database with tables: {', '.join(table_names)}"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
