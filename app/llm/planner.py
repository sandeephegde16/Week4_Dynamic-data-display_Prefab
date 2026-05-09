"""High-level Claude planning operations."""

from __future__ import annotations

from app.data.analyzer import analyze_schema_heuristically
from app.data.schema import DatabaseSchema
from app.debug import log_event
from app.llm.claude import ClaudeClient
from app.llm.prompts import query_planner_prompt, schema_analysis_prompt, sql_repair_prompt, ui_spec_review_prompt
from app.llm.schemas import QueryPlan, SchemaAnalysis, UISpecReview
from app.settings import Settings
from app.ui.specs import UISpec


def analyze_schema(schema: DatabaseSchema, settings: Settings) -> dict[str, object]:
    fallback = analyze_schema_heuristically(schema)
    if not settings.enable_claude_schema_analysis:
        log_event("Using local heuristic schema analysis. Claude schema analysis is disabled.")
        return fallback

    if not settings.claude_configured:
        log_event("Claude token missing. Using heuristic schema analysis.")
        return fallback

    try:
        client = ClaudeClient(settings)
        prompt = schema_analysis_prompt(schema)
        log_event(
            "Sending compact database schema summary to Claude schema analysis.",
            {
                "database_name_set": bool(schema.database_name),
                "tables": len(schema.tables),
                "columns": sum(len(table.columns) for table in schema.tables),
                "foreign_keys": sum(len(table.foreign_keys) for table in schema.tables),
                "prompt_chars": len(prompt),
                "rough_prompt_tokens": len(prompt) // 4,
            },
        )
        raw = client.json_completion(prompt, max_tokens=4096)
        analysis = SchemaAnalysis.model_validate(raw).model_dump()
        log_event("Claude schema analysis succeeded.", analysis)
        return analysis
    except Exception as exc:
        log_event("Claude schema analysis failed. Falling back to heuristics.", {"error": str(exc)})
        return fallback


def plan_query(schema: DatabaseSchema, settings: Settings, question: str, chat_context: list[dict[str, str]]) -> QueryPlan:
    if not settings.claude_configured:
        raise ValueError("ANTHROPIC_API_KEY is required for natural-language SQL planning.")

    client = ClaudeClient(settings)
    prompt = query_planner_prompt(schema, question, chat_context)
    log_event(
        "Sending full database schema to Claude query planner.",
        {
            "database_name_set": bool(schema.database_name),
            "tables": len(schema.tables),
            "columns": sum(len(table.columns) for table in schema.tables),
            "foreign_keys": sum(len(table.foreign_keys) for table in schema.tables),
            "prompt_chars": len(prompt),
            "rough_prompt_tokens": len(prompt) // 4,
        },
    )
    raw = client.json_completion(prompt, max_tokens=4096)
    plan = QueryPlan.model_validate(raw)
    log_event("Validated query plan.", plan.model_dump())
    return plan


def repair_query_plan(
    *,
    schema: DatabaseSchema,
    settings: Settings,
    question: str,
    chat_context: list[dict[str, str]],
    failed_plan: QueryPlan,
    failed_sql: str,
    error: str,
) -> QueryPlan:
    if not settings.claude_configured:
        raise ValueError("ANTHROPIC_API_KEY is required for SQL repair.")

    client = ClaudeClient(settings)
    prompt = sql_repair_prompt(
        schema=schema,
        question=question,
        chat_context=chat_context,
        failed_plan=failed_plan.model_dump(),
        failed_sql=failed_sql,
        error=error,
    )
    log_event(
        "Sending failed SQL to Claude repair planner.",
        {
            "database_name_set": bool(schema.database_name),
            "tables": len(schema.tables),
            "columns": sum(len(table.columns) for table in schema.tables),
            "foreign_keys": sum(len(table.foreign_keys) for table in schema.tables),
            "prompt_chars": len(prompt),
            "rough_prompt_tokens": len(prompt) // 4,
        },
    )
    raw = client.json_completion(prompt, max_tokens=4096)
    repaired = QueryPlan.model_validate(raw)
    log_event("Validated repaired query plan.", repaired.model_dump())
    return repaired


def review_ui_spec(
    *,
    settings: Settings,
    question: str,
    sql: str,
    result_columns: list[str],
    sample_rows: list[dict[str, object]],
    ui_spec: UISpec,
    validation_errors: list[str],
) -> UISpecReview:
    if not settings.claude_configured:
        return UISpecReview(
            is_valid=not validation_errors,
            reason="Claude is not configured; deterministic validation only.",
            repaired_ui_spec=None,
        )

    client = ClaudeClient(settings)
    raw = client.json_completion(
        ui_spec_review_prompt(
            question=question,
            sql=sql,
            result_columns=result_columns,
            sample_rows=sample_rows,
            ui_spec=ui_spec,
            validation_errors=validation_errors,
        ),
        max_tokens=4096,
    )
    review = UISpecReview.model_validate(raw)
    log_event("Validated UI spec review.", review.model_dump())
    return review
