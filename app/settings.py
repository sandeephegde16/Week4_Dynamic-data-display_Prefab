"""Application settings loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_debug: bool
    query_max_rows: int
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    anthropic_api_key: str
    claude_model: str
    enable_prefab_embed: bool
    enable_claude_schema_analysis: bool

    @property
    def mysql_configured(self) -> bool:
        return all([self.mysql_host, self.mysql_database, self.mysql_user, self.mysql_password])

    @property
    def claude_configured(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key != "replace_me")

    def public_status(self) -> dict[str, object]:
        return {
            "app_debug": self.app_debug,
            "query_max_rows": self.query_max_rows,
            "mysql_port": self.mysql_port,
            "mysql_configured": self.mysql_configured,
            "mysql_host_set": bool(self.mysql_host),
            "mysql_database_set": bool(self.mysql_database),
            "mysql_user_set": bool(self.mysql_user),
            "mysql_password_set": bool(self.mysql_password and self.mysql_password != "replace_me"),
            "claude_model": self.claude_model,
            "anthropic_api_key_set": self.claude_configured,
            "enable_prefab_embed": self.enable_prefab_embed,
            "enable_claude_schema_analysis": self.enable_claude_schema_analysis,
        }


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        app_debug=_get_bool("APP_DEBUG", default=False),
        query_max_rows=_get_int("QUERY_MAX_ROWS", default=500),
        mysql_host=os.getenv("MYSQL_HOST", ""),
        mysql_port=_get_int("MYSQL_PORT", default=3306),
        mysql_database=os.getenv("MYSQL_DATABASE", ""),
        mysql_user=os.getenv("MYSQL_USER", ""),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        enable_prefab_embed=_get_bool("ENABLE_PREFAB_EMBED", default=True),
        enable_claude_schema_analysis=_get_bool("ENABLE_CLAUDE_SCHEMA_ANALYSIS", default=False),
    )


def _get_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
