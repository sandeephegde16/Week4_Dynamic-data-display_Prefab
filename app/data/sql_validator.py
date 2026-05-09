"""Conservative SQL validation for LLM-produced read-only queries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.data.schema import DatabaseSchema


DENIED_KEYWORDS = {
    "alter",
    "analyze",
    "call",
    "create",
    "delete",
    "drop",
    "grant",
    "insert",
    "load_file",
    "lock",
    "optimize",
    "outfile",
    "procedure",
    "rename",
    "replace",
    "revoke",
    "set",
    "truncate",
    "update",
}


@dataclass(frozen=True)
class SqlValidationResult:
    ok: bool
    sql: str
    errors: list[str]
    referenced_tables: set[str]


def validate_select_sql(sql: str, schema: DatabaseSchema, *, max_rows: int) -> SqlValidationResult:
    cleaned = _clean_sql(sql)
    errors: list[str] = []

    if not cleaned:
        errors.append("SQL is empty.")

    lowered = cleaned.lower()
    first_word = lowered.split(maxsplit=1)[0] if lowered else ""
    if first_word not in {"select", "with"}:
        errors.append("Only SELECT queries are allowed.")

    if ";" in cleaned.rstrip(";"):
        errors.append("Multiple SQL statements are not allowed.")

    for keyword in DENIED_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            errors.append(f"Denied SQL keyword detected: {keyword}")

    cte_names = extract_cte_names(cleaned)
    referenced_tables = extract_referenced_tables(cleaned) - cte_names
    allowed_tables = schema.table_names()
    unknown_tables = {table for table in referenced_tables if table not in allowed_tables}
    if unknown_tables:
        errors.append(f"Query references unknown or disallowed tables: {sorted(unknown_tables)}")

    limited_sql = cleaned.rstrip(";")
    if not re.search(r"\blimit\s+\d+\b", lowered):
        limited_sql = f"{limited_sql}\nLIMIT {max_rows}"

    return SqlValidationResult(
        ok=not errors,
        sql=limited_sql,
        errors=errors,
        referenced_tables=referenced_tables,
    )


def extract_referenced_tables(sql: str) -> set[str]:
    tables: set[str] = set()
    pattern = re.compile(r"\b(?:from|join)\s+(`?[\w]+`?(?:\s*\.\s*`?[\w]+`?)?)", re.IGNORECASE)
    for match in pattern.finditer(sql):
        raw = match.group(1).replace("`", "").replace(" ", "")
        if raw.startswith("("):
            continue
        table = raw.split(".")[-1]
        if table:
            tables.add(table)
    return tables


def extract_cte_names(sql: str) -> set[str]:
    if not re.match(r"^\s*with\b", sql, flags=re.IGNORECASE):
        return set()

    names: set[str] = set()
    pattern = re.compile(
        r"(?:\bwith\s+(?:recursive\s+)?|,\s*)(`?[\w]+`?)\s*(?:\([^)]*\)\s*)?as\s*\(",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        name = match.group(1).replace("`", "")
        if name:
            names.add(name)
    return names


def _clean_sql(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    without_line_comments = re.sub(r"(^|\n)\s*--.*?(?=\n|$)", "\n", without_block_comments)
    return without_line_comments.strip()
