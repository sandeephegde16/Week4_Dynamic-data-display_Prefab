"""Chat question handling."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

from app.data.mysql import execute_query
from app.data.schema import DatabaseSchema
from app.data.sql_validator import validate_select_sql
from app.debug import log_event
from app.llm.schemas import QueryBlock, QueryPlan
from app.llm.planner import plan_query, repair_query_plan, review_ui_spec
from app.settings import Settings
from app.ui.spec_builder import (
    response_for_error,
    response_for_query_result,
    response_for_schema_analysis,
    response_for_text,
)
from app.ui.specs import AssistantResponse, UISpec
from app.ui.spec_validator import (
    deterministic_repair_for_prefab,
    table_spec_from_rows,
    validate_ui_spec_for_prefab,
)


def handle_question(
    question: str,
    *,
    settings: Settings,
    engine: Engine | None,
    schema: DatabaseSchema | None,
    schema_analysis: dict[str, Any] | None,
    chat_context: list[dict[str, str]],
) -> AssistantResponse:
    log_event("Handling user question.", {"question": question})

    if schema is None or engine is None:
        return response_for_error(
            "Connect to a database source first. The app needs schema introspection before it can answer database questions.",
            debug={"question": question},
        )

    if _asks_for_schema_analysis(question):
        return response_for_schema_analysis(
            schema_analysis or {},
            schema=schema,
            debug={"question": question, "source": "schema_analysis"},
        )

    if not settings.claude_configured:
        return response_for_error(
            "ANTHROPIC_API_KEY is missing. Add it to `.env` so Claude can plan SQL for natural-language questions.",
            debug={"question": question, "settings": settings.public_status()},
        )

    try:
        plan = plan_query(schema, settings, question, chat_context)
    except Exception as exc:
        log_event("Query planning failed.", {"error": str(exc), "question": question})
        return response_for_error(
            "Claude could not produce a valid query plan.",
            debug={"question": question, "error": str(exc)},
        )

    debug: dict[str, Any] = {"question": question, "plan": plan.model_dump()}

    if plan.action in {"answer_text", "clarify"}:
        return response_for_text(plan.explanation or "I need a little more detail.", debug=debug)

    if plan.queries:
        return _handle_multi_query_plan(
            plan=plan,
            settings=settings,
            engine=engine,
            schema=schema,
            question=question,
            chat_context=chat_context,
            debug=debug,
        )

    if not plan.sql:
        return response_for_error("Claude selected SQL execution but did not provide SQL.", debug=debug)

    validation = validate_select_sql(plan.sql, schema, max_rows=settings.query_max_rows)
    debug["sql_validation"] = {
        "ok": validation.ok,
        "sql": validation.sql,
        "errors": validation.errors,
        "referenced_tables": sorted(validation.referenced_tables),
    }
    log_event("SQL validation completed.", debug["sql_validation"])

    frame = None
    if not validation.ok:
        repaired = _repair_and_execute_sql(
            settings=settings,
            engine=engine,
            schema=schema,
            question=question,
            chat_context=chat_context,
            plan=plan,
            failed_sql=plan.sql,
            error=f"SQL validation failed: {'; '.join(validation.errors)}",
            debug=debug,
        )
        if repaired is None:
            return response_for_error("Generated SQL was rejected by the safety validator.", debug=debug)
        plan, validation, frame = repaired
    else:
        try:
            frame = execute_query(engine, validation.sql)
        except Exception as exc:
            log_event("SQL execution failed.", {"error": str(exc), "sql": validation.sql})
            repaired = _repair_and_execute_sql(
                settings=settings,
                engine=engine,
                schema=schema,
                question=question,
                chat_context=chat_context,
                plan=plan,
                failed_sql=validation.sql,
                error=str(exc),
                debug=debug,
            )
            if repaired is None:
                return response_for_error(
                    "The SQL query failed against the configured database.",
                    debug={**debug, "execution_error": str(exc)},
                )
            plan, validation, frame = repaired

    if frame is None:
        return response_for_error("The SQL query did not return a result.", debug=debug)

    debug["result"] = {"rows": len(frame), "columns": list(frame.columns)}
    response = response_for_query_result(frame, plan, debug=debug)
    return _validate_and_repair_response_for_prefab(
        response,
        settings=settings,
        question=question,
        sql=validation.sql,
    )


def _asks_for_schema_analysis(question: str) -> bool:
    normalized = question.lower()
    phrases = [
        "what questions",
        "what kind of questions",
        "what can i ask",
        "what widgets",
        "suitable widgets",
        "analyze schema",
        "schema map",
        "schema relationships",
        "relationships",
        "foreign keys",
        "understand db",
        "understand database",
        "database overview",
    ]
    return any(phrase in normalized for phrase in phrases)


def _handle_multi_query_plan(
    *,
    plan: QueryPlan,
    settings: Settings,
    engine: Engine,
    schema: DatabaseSchema,
    question: str,
    chat_context: list[dict[str, str]],
    debug: dict[str, Any],
) -> AssistantResponse:
    children: list[UISpec] = []
    combined_sql: list[str] = []
    block_debugs: list[dict[str, Any]] = []

    log_event("Executing multi-query dashboard plan.", {"query_blocks": len(plan.queries)})

    for index, block in enumerate(plan.queries, start=1):
        block_plan = _query_plan_for_block(block, parent=plan, index=index)
        block_title = block_plan.render.title or block_plan.question_rewrite or f"Query {index}"
        block_debug: dict[str, Any] = {
            "index": index,
            "name": block.name,
            "title": block_title,
            "sql": block.sql,
        }
        block_debugs.append(block_debug)
        log_event("Handling query block.", {"index": index, "title": block_title})

        validation = validate_select_sql(block.sql, schema, max_rows=settings.query_max_rows)
        block_debug["sql_validation"] = {
            "ok": validation.ok,
            "sql": validation.sql,
            "errors": validation.errors,
            "referenced_tables": sorted(validation.referenced_tables),
        }
        log_event("SQL validation completed for query block.", block_debug["sql_validation"])

        if not validation.ok:
            repaired = _repair_and_execute_sql(
                settings=settings,
                engine=engine,
                schema=schema,
                question=question,
                chat_context=chat_context,
                plan=block_plan,
                failed_sql=block.sql,
                error=f"SQL validation failed: {'; '.join(validation.errors)}",
                debug=block_debug,
            )
            if repaired is None:
                debug["multi_query"] = {"blocks": block_debugs}
                return response_for_error(
                    f"Generated SQL for `{block_title}` was rejected by the safety validator.",
                    debug=debug,
                )
            block_plan, validation, frame = repaired
        else:
            try:
                frame = execute_query(engine, validation.sql)
            except Exception as exc:
                log_event("SQL execution failed for query block.", {"error": str(exc), "sql": validation.sql})
                repaired = _repair_and_execute_sql(
                    settings=settings,
                    engine=engine,
                    schema=schema,
                    question=question,
                    chat_context=chat_context,
                    plan=block_plan,
                    failed_sql=validation.sql,
                    error=str(exc),
                    debug=block_debug,
                )
                if repaired is None:
                    debug["multi_query"] = {"blocks": block_debugs}
                    return response_for_error(
                        f"The SQL query for `{block_title}` failed against the configured database.",
                        debug=debug,
                    )
                block_plan, validation, frame = repaired

        combined_sql.append(f"-- {block_title}\n{validation.sql}")
        block_debug["result"] = {"rows": len(frame), "columns": list(frame.columns)}
        child_response = response_for_query_result(frame, block_plan, debug=block_debug)
        if child_response.ui_spec is None:
            child_spec = UISpec(type="text", title=block_title, message=child_response.message)
        else:
            child_spec = child_response.ui_spec
        child_spec = _repair_spec_tree_for_prefab(child_spec)
        child_validation = validate_ui_spec_for_prefab(child_spec)
        block_debug["ui_spec_validation"] = {
            "ok": child_validation.ok,
            "errors": child_validation.errors,
            "warnings": child_validation.warnings,
            "spec_type": child_spec.type,
        }
        if not child_validation.ok and child_spec.rows:
            child_spec = table_spec_from_rows(
                title=child_spec.title or block_title,
                message="The visual spec was incomplete, so this section is shown as a table.",
                rows=child_spec.rows,
                debug=child_spec.debug,
            )
        children.append(child_spec)

    debug["multi_query"] = {"blocks": block_debugs}
    title = plan.render.title if plan.render.title != "Query Result" else plan.question_rewrite
    spec = UISpec(
        type="dashboard",
        title=title or "Dashboard",
        message=plan.render.reason or plan.explanation,
        children=children,
        debug=debug,
    )
    response = AssistantResponse(
        message=plan.explanation or f"Built dashboard from {len(children)} query sections.",
        ui_required=True,
        ui_spec=spec,
        debug=debug,
    )
    return _validate_and_repair_response_for_prefab(
        response,
        settings=settings,
        question=question,
        sql="\n\n".join(combined_sql),
    )


def _query_plan_for_block(block: QueryBlock, *, parent: QueryPlan, index: int) -> QueryPlan:
    title = block.title or block.name or f"Query {index}"
    render = block.render
    updates: dict[str, Any] = {}
    if title and render.title == "Query Result":
        updates["title"] = title
    if block.purpose and not render.reason:
        updates["reason"] = block.purpose
    if updates:
        render = render.model_copy(update=updates)
    return QueryPlan(
        action="run_sql",
        question_rewrite=title,
        explanation=block.purpose or parent.explanation,
        sql=block.sql,
        render=render,
        confidence=parent.confidence,
    )


def _repair_and_execute_sql(
    *,
    settings: Settings,
    engine: Engine,
    schema: DatabaseSchema,
    question: str,
    chat_context: list[dict[str, str]],
    plan: Any,
    failed_sql: str,
    error: str,
    debug: dict[str, Any],
) -> tuple[Any, Any, Any] | None:
    debug["execution_error"] = error
    try:
        repaired_plan = repair_query_plan(
            schema=schema,
            settings=settings,
            question=question,
            chat_context=chat_context,
            failed_plan=plan,
            failed_sql=failed_sql,
            error=error,
        )
    except Exception as exc:
        debug["sql_repair_error"] = str(exc)
        log_event("SQL repair planning failed.", {"error": str(exc)})
        return None

    debug["repaired_plan"] = repaired_plan.model_dump()
    if not repaired_plan.sql:
        debug["sql_repair_error"] = "Claude repair did not return SQL."
        return None

    repaired_validation = validate_select_sql(repaired_plan.sql, schema, max_rows=settings.query_max_rows)
    debug["sql_validation_after_repair"] = {
        "ok": repaired_validation.ok,
        "sql": repaired_validation.sql,
        "errors": repaired_validation.errors,
        "referenced_tables": sorted(repaired_validation.referenced_tables),
    }
    log_event("SQL validation after repair completed.", debug["sql_validation_after_repair"])
    if not repaired_validation.ok:
        return None

    try:
        frame = execute_query(engine, repaired_validation.sql)
    except Exception as exc:
        debug["sql_repair_execution_error"] = str(exc)
        log_event("Repaired SQL execution failed.", {"error": str(exc), "sql": repaired_validation.sql})
        return None

    log_event("Repaired SQL execution succeeded.", {"rows": len(frame), "columns": list(frame.columns)})
    return repaired_plan, repaired_validation, frame


def _validate_and_repair_response_for_prefab(
    response: AssistantResponse,
    *,
    settings: Settings,
    question: str,
    sql: str,
) -> AssistantResponse:
    if response.ui_spec is None:
        return response

    spec = response.ui_spec
    validation = validate_ui_spec_for_prefab(spec)
    response.debug["ui_spec_validation"] = {
        "ok": validation.ok,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "before_spec_type": spec.type,
    }
    log_event("Deterministic UI spec validation completed.", response.debug["ui_spec_validation"])

    if spec.type == "dashboard" and spec.children:
        response.debug["llm_ui_spec_review_skipped"] = "Dashboard children were built from separate executed result sets."
    else:
        try:
            review = review_ui_spec(
                settings=settings,
                question=question,
                sql=sql,
                result_columns=[column.field for column in spec.columns] or list(spec.rows[0].keys() if spec.rows else []),
                sample_rows=spec.rows[:20],
                ui_spec=spec,
                validation_errors=validation.errors,
            )
            response.debug["llm_ui_spec_review"] = review.model_dump()
            if not review.is_valid and review.repaired_ui_spec:
                repaired_data = _sanitize_ui_spec_data(dict(review.repaired_ui_spec))
                repaired_data["rows"] = spec.rows
                if not repaired_data.get("columns"):
                    repaired_data["columns"] = [column.model_dump() for column in spec.columns]
                spec = UISpec.model_validate(repaired_data)
                log_event("Claude repaired UI spec.", {"type": spec.type, "title": spec.title})
        except Exception as exc:
            response.debug["llm_ui_spec_review_error"] = str(exc)
            log_event("Claude UI spec review failed. Continuing with deterministic repair.", {"error": str(exc)})

    spec = _repair_spec_tree_for_prefab(spec)
    repaired_validation = validate_ui_spec_for_prefab(spec)
    response.debug["ui_spec_validation_after_repair"] = {
        "ok": repaired_validation.ok,
        "errors": repaired_validation.errors,
        "warnings": repaired_validation.warnings,
        "after_spec_type": spec.type,
    }

    if not repaired_validation.ok:
        spec = table_spec_from_rows(
            title=spec.title or "Query Result",
            message="The visual spec was incomplete, so the result is shown as a table.",
            rows=spec.rows,
            debug=spec.debug,
        )
        response.debug["ui_spec_final_fallback"] = "table"

    spec.debug = {**spec.debug, **response.debug}
    response.ui_spec = spec
    response.ui_required = spec.type != "text"
    return response


def _repair_spec_tree_for_prefab(spec: UISpec) -> UISpec:
    repaired = deterministic_repair_for_prefab(spec)
    if not repaired.children:
        return repaired
    return repaired.model_copy(
        update={"children": [_repair_spec_tree_for_prefab(child) for child in repaired.children]}
    )


def _sanitize_ui_spec_data(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: _sanitize_ui_spec_data(value)
            for key, value in data.items()
            if value is not None
        }
    if isinstance(data, list):
        return [_sanitize_ui_spec_data(item) for item in data]
    return data
