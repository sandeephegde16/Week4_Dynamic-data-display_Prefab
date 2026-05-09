"""MySQL connection, schema introspection, and query execution."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from app.data.schema import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from app.debug import log_event
from app.settings import Settings


def create_mysql_engine(settings: Settings) -> Engine:
    url = URL.create(
        "mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    )
    log_event(
        "Creating MySQL engine.",
        {
            "mysql_host_set": bool(settings.mysql_host),
            "port": settings.mysql_port,
            "mysql_database_set": bool(settings.mysql_database),
            "mysql_user_set": bool(settings.mysql_user),
        },
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def test_connection(engine: Engine) -> None:
    log_event("Testing MySQL connection with SELECT 1.")
    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()
    log_event("MySQL connection test succeeded.", {"select_1": value})


def introspect_schema(engine: Engine, database_name: str) -> DatabaseSchema:
    log_event("Starting MySQL schema introspection.", {"mysql_database_set": bool(database_name)})
    table_rows = _fetch_dicts(
        engine,
        """
        SELECT
            TABLE_NAME AS table_name,
            TABLE_TYPE AS table_type,
            TABLE_ROWS AS row_count_estimate,
            TABLE_COMMENT AS table_comment
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = :database_name
        ORDER BY TABLE_NAME
        """,
        {"database_name": database_name},
    )
    column_rows = _fetch_dicts(
        engine,
        """
        SELECT
            TABLE_NAME AS table_name,
            COLUMN_NAME AS column_name,
            ORDINAL_POSITION AS ordinal_position,
            DATA_TYPE AS data_type,
            COLUMN_TYPE AS column_type,
            IS_NULLABLE AS is_nullable,
            COLUMN_KEY AS column_key,
            COLUMN_DEFAULT AS column_default,
            EXTRA AS extra,
            COLUMN_COMMENT AS column_comment
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = :database_name
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """,
        {"database_name": database_name},
    )
    fk_rows = _fetch_dicts(
        engine,
        """
        SELECT
            TABLE_NAME AS table_name,
            COLUMN_NAME AS column_name,
            REFERENCED_TABLE_NAME AS referenced_table_name,
            REFERENCED_COLUMN_NAME AS referenced_column_name
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = :database_name
          AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME, COLUMN_NAME
        """,
        {"database_name": database_name},
    )

    columns_by_table: dict[str, list[ColumnInfo]] = {}
    for row in column_rows:
        row["is_nullable"] = str(row["is_nullable"]).upper() == "YES"
        column = ColumnInfo.model_validate(row)
        columns_by_table.setdefault(column.table_name, []).append(column)

    fks_by_table: dict[str, list[ForeignKeyInfo]] = {}
    for row in fk_rows:
        foreign_key = ForeignKeyInfo.model_validate(row)
        fks_by_table.setdefault(foreign_key.table_name, []).append(foreign_key)

    tables = [
        TableInfo(
            table_name=row["table_name"],
            table_type=row["table_type"],
            row_count_estimate=row["row_count_estimate"],
            table_comment=row.get("table_comment") or "",
            columns=columns_by_table.get(row["table_name"], []),
            foreign_keys=fks_by_table.get(row["table_name"], []),
        )
        for row in table_rows
    ]
    schema = DatabaseSchema(database_name=database_name, tables=tables)
    log_event(
        "Schema introspection finished.",
        {
            "tables": len(schema.tables),
            "columns": sum(len(table.columns) for table in schema.tables),
            "foreign_keys": sum(len(table.foreign_keys) for table in schema.tables),
        },
    )
    return schema


def execute_query(engine: Engine, sql: str) -> pd.DataFrame:
    log_event("Executing SQL.", {"sql": sql})
    with engine.connect() as connection:
        frame = pd.read_sql_query(text(sql), connection)
    log_event("SQL execution finished.", {"rows": len(frame), "columns": list(frame.columns)})
    return frame


def _fetch_dicts(engine: Engine, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]
