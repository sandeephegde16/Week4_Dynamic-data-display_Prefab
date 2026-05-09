"""Prompts for schema analysis and SQL planning."""

from __future__ import annotations

import json

from app.data.schema import DatabaseSchema
from app.ui.specs import UISpec
from app.ui.widget_catalog import component_catalog_text


SCHEMA_WIDGET_KINDS = (
    "kpi, table, bar_chart, line_chart, area_chart, pie_chart, scatter, histogram, "
    "dashboard, detail_panel, filter_panel, schema_map"
)
QUERY_RENDER_KINDS = (
    "text, kpi, table, bar_chart, line_chart, area_chart, pie_chart, scatter, histogram, "
    "dashboard, detail_panel, filter_panel, schema_map"
)
FORBIDDEN_SQL = ", ".join(
    [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "SET",
        "CALL",
        "LOCK",
        "GRANT",
        "REVOKE",
        "OUTFILE",
        "LOAD_FILE",
    ]
)
UI_SPEC_TYPES = "text, kpi, table, chart, dashboard, detail, filters, schema_map, error"
CHART_TYPES = "bar, line, area, pie, scatter, histogram"
FILTER_CONTROLS = "date, select, combobox, slider, switch"


def _compact_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def _dialect_name(schema: DatabaseSchema) -> str:
    return "SQLite" if schema.sql_dialect.lower() == "sqlite" else "MySQL"


def _dialect_rule(schema: DatabaseSchema) -> str:
    if schema.sql_dialect.lower() == "sqlite":
        return (
            "Use SQLite syntax. For month buckets use strftime('%Y-%m', date_column); "
            "do not use MySQL-only functions such as DATE_FORMAT, YEAR, MONTH, or INTERVAL."
        )
    return "Use MySQL syntax."


def schema_analysis_prompt(schema: DatabaseSchema) -> str:
    compact_schema = schema.compact_summary(max_tables=15, max_columns_per_table=10)
    return f"""\
Analyze this {_dialect_name(schema)} schema for a dynamic UI demo.

Tasks:
- Infer likely business questions.
- Recommend suitable widgets from: {SCHEMA_WIDGET_KINDS}.
- Include installed Prefab components from: {component_catalog_text()}.
- Flag ambiguous business terms.
- Use only tables/columns in the schema.

Return keys:
domain_guess, summary, likely_questions, recommended_widgets, risky_or_ambiguous_terms.
recommended_widgets item keys: widget, recommended_components, use_for, relevant_tables, relevant_columns, reason.

Schema JSON:
{_compact_json(compact_schema)}
"""


def query_planner_prompt(schema: DatabaseSchema, question: str, chat_context: list[dict[str, str]]) -> str:
    context = _compact_json(chat_context[-6:])
    schema_context = schema.as_prompt_text()
    return f"""\
You are a careful {_dialect_name(schema)} analytics planner for a Streamlit + Prefab-style dynamic UI demo.

Action rules:
- clarify: ambiguous database request.
- answer_text: no database access is needed.
- run_sql: database access is needed; produce either one safe SQL query in sql, or multiple safe SQL queries in queries.

SQL rules:
- Use only the full schema below; never invent tables, columns, or render fields.
- Read all table and column names before choosing SQL. Prefer the most semantically exact table/column, not the first lexical match.
- If multiple tables could answer the question, choose the base business table over audit/history/archive tables unless the user asks for history/audit/archive.
- Each SQL string must be read-only: one SELECT or WITH ... SELECT.
- {_dialect_rule(schema)}
- Do not use: {FORBIDDEN_SQL}.
- Prefer aliases that are easy to render, such as period, category, total_value, record_count.
- For dashboard or overview requests with several independent facts or sections, prefer queries over one large UNION query. Use one focused query per independent result section, grouping fields only when they share the same grain, filters, and source relationship.
- Do not force unrelated facts into a single rectangular result with NULL-filled UNION rows just to satisfy one-query output.

Render rules:
- Prefer useful interactive UI; use text only for clarification, non-database answers, or when UI adds no value.
- render.kind must be one of: {QUERY_RENDER_KINDS}.
- Pick render.kind from the question and result shape, not only from the user's wording.
- Use dashboard only when the user asks for an overview/dashboard or the answer clearly needs KPIs, chart, filters, and drilldown together.
- detail_panel is for entity inspection or small wide row sets.
- filter_panel is for refining categorical, date, boolean, or numeric fields.
- schema_map is for schema relationships or foreign-key overviews.
- Chart/KPI/table fields must be exact SQL output aliases.

Return keys:
action, question_rewrite, explanation, sql, queries, render, confidence.
render keys: kind, title, reason, x_field, y_field, color_field, label_field, value_field, metric_fields.
queries item keys: name, title, purpose, sql, render.
- If queries is non-empty, sql can be null. Each query item needs its own render object using exact output aliases from that query.
- explanation is shown directly to the user. Keep it to one short result-oriented sentence.
- Do not put schema deliberation, rejected approaches, "Actually", "I will query", or hidden reasoning in explanation.
- Use render.reason only for a short UI caption; do not include planning notes there either.

Recent chat context JSON:
{context}

Full database schema:
{schema_context}

User question:
{question}
"""


def sql_repair_prompt(
    *,
    schema: DatabaseSchema,
    question: str,
    chat_context: list[dict[str, str]],
    failed_plan: dict[str, object],
    failed_sql: str,
    error: str,
) -> str:
    context = _compact_json(chat_context[-6:])
    schema_context = schema.as_prompt_text()
    return f"""\
Repair a failed {_dialect_name(schema)} analytics query for a Streamlit + Prefab-style dynamic UI demo.

Return exactly one JSON object with the same keys as the query planner:
action, question_rewrite, explanation, sql, queries, render, confidence.
render keys: kind, title, reason, x_field, y_field, color_field, label_field, value_field, metric_fields.
queries item keys: name, title, purpose, sql, render.

Rules:
- action must be run_sql unless the request truly cannot be answered.
- This repair is for one failed SQL string. Return the repaired query in sql and keep queries empty.
- Keep the user's requested answer intent.
- Use only the full schema below; never invent tables or columns.
- SQL must be read-only: one SELECT or WITH ... SELECT.
- {_dialect_rule(schema)}
- Do not use: {FORBIDDEN_SQL}.
- Fix the SQL syntax, validation, or runtime problem shown by the error.
- For UNION queries, do not place ORDER BY/LIMIT directly inside individual UNION branches. Use CTEs, derived tables, or scalar subqueries when branch-level ordering/limiting is needed.
- Prefer a simple rectangular result shape that is easy to render: metric/label/value rows for dashboards, or normal grouped rows for charts/tables.
- Do not include prose, markdown, or SQL outside the JSON object.

Recent chat context JSON:
{context}

User question:
{question}

Previous query plan JSON:
{_compact_json(failed_plan)}

Failed SQL:
{failed_sql}

Database error:
{error}

Full database schema:
{schema_context}
"""


def ui_spec_review_prompt(
    *,
    question: str,
    sql: str,
    result_columns: list[str],
    sample_rows: list[dict[str, object]],
    ui_spec: UISpec,
    validation_errors: list[str],
) -> str:
    candidate_spec = ui_spec.model_dump()
    candidate_spec.pop("debug", None)
    candidate_spec["rows"] = candidate_spec.get("rows", [])[:20]
    return f"""\
Validate a Prefab UI spec for an already executed SQL result. Repair only if current Prefab support cannot render it.

Rules:
- Check completeness/correctness of the selected spec; do not force a different visual type.
- Use only result_columns and sample rows; do not invent columns or rows.
- Valid types: {UI_SPEC_TYPES}.
- kpi needs metrics with label/value.
- table/detail need rows and columns.
- chart needs rows plus chart fields from result_columns; chart_type must be one of: {CHART_TYPES}.
- dashboard needs at least one useful metric, filter, chart, child spec, or row set.
- filters need controls from: {FILTER_CONTROLS}; filter fields must exist in result_columns.
- schema_map needs Mermaid text.

Return keys:
is_valid, reason, repaired_ui_spec.
If valid, repaired_ui_spec is null.
If invalid, repaired_ui_spec is a valid render-only UI spec using existing columns/rows only.
UI spec keys: type, title, message, metrics, columns, rows, chart, filters, children, mermaid.
chart keys: chart_type, x_field, y_field, color_field, label_field, value_field.
filter keys: field, label, control, options, min_value, max_value, value, help.

User question:
{question}

SQL:
{sql}

Result columns:
{_compact_json(result_columns)}

Sample rows:
{_compact_json(sample_rows[:20])}

Deterministic validation errors:
{_compact_json(validation_errors)}

Candidate UI spec:
{_compact_json(candidate_spec)}
"""
