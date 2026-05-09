"""Database schema models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    column_type: str
    is_nullable: bool
    column_key: str = ""
    column_default: str | None = None
    extra: str = ""
    column_comment: str = ""

    @property
    def is_primary_key(self) -> bool:
        return self.column_key.upper() == "PRI"

    @property
    def is_numeric(self) -> bool:
        return self.data_type.lower() in {
            "bigint",
            "decimal",
            "double",
            "float",
            "int",
            "integer",
            "mediumint",
            "numeric",
            "real",
            "smallint",
            "tinyint",
        }

    @property
    def is_datetime(self) -> bool:
        return self.data_type.lower() in {"date", "datetime", "timestamp", "time", "year"}

    @property
    def is_text(self) -> bool:
        return self.data_type.lower() in {"char", "longtext", "mediumtext", "text", "tinytext", "varchar"}

    @property
    def looks_categorical(self) -> bool:
        name = self.column_name.lower()
        return (
            self.data_type.lower() in {"enum", "set", "bool", "boolean"}
            or name.endswith("_status")
            or name in {"status", "state", "type", "category", "channel", "source", "stage"}
            or name.endswith("_type")
            or name.endswith("_category")
        )


class ForeignKeyInfo(BaseModel):
    table_name: str
    column_name: str
    referenced_table_name: str
    referenced_column_name: str


class TableInfo(BaseModel):
    table_name: str
    table_type: str
    row_count_estimate: int | None = None
    table_comment: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)

    @property
    def primary_keys(self) -> list[str]:
        return [column.column_name for column in self.columns if column.is_primary_key]


class DatabaseSchema(BaseModel):
    database_name: str
    tables: list[TableInfo] = Field(default_factory=list)

    def table_names(self) -> set[str]:
        return {table.table_name for table in self.tables}

    def column_names_by_table(self) -> dict[str, set[str]]:
        return {table.table_name: {column.column_name for column in table.columns} for table in self.tables}

    def compact_summary(self, *, max_tables: int = 80, max_columns_per_table: int = 80) -> dict[str, object]:
        tables = []
        for table in self.tables[:max_tables]:
            tables.append(
                {
                    "name": table.table_name,
                    "type": table.table_type,
                    "row_count_estimate": table.row_count_estimate,
                    "primary_keys": table.primary_keys,
                    "columns": [
                        {
                            "name": column.column_name,
                            "data_type": column.data_type,
                            "column_type": column.column_type,
                            "nullable": column.is_nullable,
                            "key": column.column_key,
                            "comment": column.column_comment,
                        }
                        for column in table.columns[:max_columns_per_table]
                    ],
                    "foreign_keys": [foreign_key.model_dump() for foreign_key in table.foreign_keys],
                    "comment": table.table_comment,
                }
            )

        return {
            "database": "runtime_configured_database",
            "table_count": len(self.tables),
            "tables": tables,
        }

    def as_prompt_text(self) -> str:
        lines = ["Database: runtime_configured_database", f"Tables: {len(self.tables)}"]
        for table in self.tables:
            lines.append("")
            row_count = f", approx rows: {table.row_count_estimate}" if table.row_count_estimate is not None else ""
            lines.append(f"Table `{table.table_name}` ({table.table_type}{row_count})")
            if table.table_comment:
                lines.append(f"  comment: {table.table_comment}")
            for column in table.columns:
                flags = []
                if column.column_key:
                    flags.append(column.column_key)
                if not column.is_nullable:
                    flags.append("not null")
                flag_text = f" [{' '.join(flags)}]" if flags else ""
                comment = f" -- {column.column_comment}" if column.column_comment else ""
                lines.append(f"  - {column.column_name}: {column.column_type}{flag_text}{comment}")
            for foreign_key in table.foreign_keys:
                lines.append(
                    "  FK "
                    f"{foreign_key.column_name} -> "
                    f"{foreign_key.referenced_table_name}.{foreign_key.referenced_column_name}"
                )
        return "\n".join(lines)
