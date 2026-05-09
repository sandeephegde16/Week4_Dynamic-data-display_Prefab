"""Build compact schema context for LLM planning."""

from __future__ import annotations

import re

from app.data.schema import ColumnInfo, DatabaseSchema, TableInfo


def schema_context_for_question(
    schema: DatabaseSchema,
    question: str,
    chat_context: list[dict[str, str]],
    *,
    max_tables: int = 8,
    max_columns_per_table: int = 35,
) -> str:
    """Return a prompt-sized schema subset relevant to a user question."""
    terms = _terms(question + " " + " ".join(item.get("content", "") for item in chat_context[-4:]))
    selected = _select_tables(schema, terms, max_tables=max_tables)
    selected = _with_fk_neighbors(schema, selected, max_tables=max_tables)

    lines = [
        "Database: runtime_configured_database",
        f"Total tables: {len(schema.tables)}",
        "",
        "Available table names:",
        ", ".join(table.table_name for table in schema.tables),
        "",
        "Detailed schema for likely relevant tables:",
    ]

    for table in selected:
        row_count = f", approx rows: {table.row_count_estimate}" if table.row_count_estimate is not None else ""
        lines.append("")
        lines.append(f"Table `{table.table_name}` ({table.table_type}{row_count})")
        if table.primary_keys:
            lines.append(f"  primary_keys: {', '.join(table.primary_keys)}")
        for column in table.columns[:max_columns_per_table]:
            flags = []
            if column.column_key:
                flags.append(column.column_key)
            if column.is_datetime:
                flags.append("date_time")
            if column.is_numeric and not _looks_like_id(column):
                flags.append("numeric_measure")
            if column.looks_categorical:
                flags.append("categorical")
            flag_text = f" [{' '.join(flags)}]" if flags else ""
            lines.append(f"  - {column.column_name}: {column.column_type}{flag_text}")
        for foreign_key in table.foreign_keys:
            lines.append(
                "  FK "
                f"{foreign_key.column_name} -> "
                f"{foreign_key.referenced_table_name}.{foreign_key.referenced_column_name}"
            )

    lines.extend(
        [
            "",
            "Schema context policy:",
            "- The detailed schema above is a selected subset to keep prompts small.",
            "- Use only listed detailed tables/columns for SQL.",
            "- If the user asks about a table not detailed here, ask a clarification question or request schema refresh/context.",
            "- Never invent table or column names.",
        ]
    )
    return "\n".join(lines)


def _select_tables(schema: DatabaseSchema, terms: set[str], *, max_tables: int) -> list[TableInfo]:
    scored: list[tuple[int, int, TableInfo]] = []
    for index, table in enumerate(schema.tables):
        score = _score_table(table, terms)
        if score > 0:
            scored.append((score, -index, table))

    if not scored:
        scored = [
            (_fallback_score(table), -index, table)
            for index, table in enumerate(schema.tables)
        ]

    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [table for _, _, table in scored[:max_tables]]


def _with_fk_neighbors(schema: DatabaseSchema, selected: list[TableInfo], *, max_tables: int) -> list[TableInfo]:
    if len(selected) >= max_tables:
        return selected[:max_tables]

    by_name = {table.table_name: table for table in schema.tables}
    selected_names = {table.table_name for table in selected}
    expanded = list(selected)

    for table in selected:
        for foreign_key in table.foreign_keys:
            neighbor = by_name.get(foreign_key.referenced_table_name)
            if neighbor is None or neighbor.table_name in selected_names:
                continue
            expanded.append(neighbor)
            selected_names.add(neighbor.table_name)
            if len(expanded) >= max_tables:
                return expanded

    return expanded


def _score_table(table: TableInfo, terms: set[str]) -> int:
    table_terms = _terms(table.table_name)
    score = 0
    score += 12 * len(terms & table_terms)

    for column in table.columns:
        column_terms = _terms(column.column_name)
        overlap = len(terms & column_terms)
        if overlap:
            score += 5 * overlap
            if column.is_primary_key:
                score += 1
            if column.is_datetime:
                score += 2
            if column.is_numeric and not _looks_like_id(column):
                score += 2
            if column.looks_categorical:
                score += 2

    if {"date", "month", "year", "time", "trend", "recent"} & terms:
        score += 2 * sum(1 for column in table.columns if column.is_datetime)
    if {"status", "state", "type", "category", "group", "breakdown", "distribution"} & terms:
        score += 2 * sum(1 for column in table.columns if column.looks_categorical)
    if {"amount", "total", "sum", "average", "avg", "count", "top", "balance"} & terms:
        score += 2 * sum(1 for column in table.columns if column.is_numeric and not _looks_like_id(column))

    return score


def _fallback_score(table: TableInfo) -> int:
    score = 0
    if table.row_count_estimate:
        score += min(int(table.row_count_estimate // 100_000), 20)
    score += min(len(table.foreign_keys), 5)
    score += min(sum(1 for column in table.columns if column.is_datetime), 5)
    score += min(sum(1 for column in table.columns if column.is_numeric and not _looks_like_id(column)), 5)
    return score


def _terms(value: str) -> set[str]:
    raw = re.split(r"[^a-zA-Z0-9]+", value.lower())
    return {term for term in raw if len(term) >= 3}


def _looks_like_id(column: ColumnInfo) -> bool:
    name = column.column_name.lower()
    return column.is_primary_key or name == "id" or name.endswith("_id")
