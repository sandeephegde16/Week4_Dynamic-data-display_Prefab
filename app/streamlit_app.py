"""Single-screen Streamlit app."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
from sqlalchemy.engine import Engine

from app.chat.controller import handle_question
from app.data.mysql import create_mysql_engine, introspect_schema, test_connection
from app.data.schema import DatabaseSchema
from app.debug import configure_logging, log_event
from app.llm.planner import analyze_schema
from app.settings import Settings, load_settings
from app.ui.prefab_file import initialize_prefab_files
from app.ui.specs import AssistantResponse
from app.ui.streamlit_renderer import render_assistant_response
from app.ui.theme import STREAMLIT_THEME_CSS


def main() -> None:
    settings = load_settings()
    configure_logging(debug=settings.app_debug)
    log_event("Streamlit app rerun.", settings.public_status())

    st.set_page_config(page_title="Dynamic DB UI Demo", page_icon="DB", layout="wide")
    initialize_prefab_files()
    _ensure_state()
    st.session_state.show_debug = False
    _render_page_chrome()
    _auto_connect_if_needed(settings)
    _drop_startup_schema_messages()
    _render_connection_summary(settings)

    welcome_slot = st.empty()
    if not st.session_state.messages and st.session_state.pending_question is None:
        with welcome_slot.container():
            _render_welcome_prompts()

    _render_messages(settings)
    _handle_pending_or_typed_question(settings, welcome_slot=welcome_slot)


def _ensure_state() -> None:
    defaults = {
        "engine": None,
        "schema": None,
        "schema_analysis": None,
        "messages": [],
        "show_debug": False,
        "pending_question": None,
        "auto_connect_attempted": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_page_chrome() -> None:
    st.markdown(STREAMLIT_THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="db-hero">
          <div class="db-eyebrow">Live database workspace</div>
          <h1>Dynamic Database Chat</h1>
          <p>Ask in plain English and turn live MySQL answers into clean, interactive Prefab UI.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_connection_summary(settings: Settings) -> None:
    schema: DatabaseSchema | None = st.session_state.schema
    left, right = st.columns([0.76, 0.24], vertical_alignment="top")

    with left:
        if schema is None:
            if settings.mysql_configured:
                st.info("Connecting to MySQL and reading schema...")
            else:
                st.error("MySQL settings are incomplete. Fill `.env` and reload the app.")
        else:
            _render_schema_stats(
                [
                    ("Connection", "Ready"),
                    ("Tables", f"{len(schema.tables):,}"),
                ],
            )

    with right:
        if st.button("Refresh schema", use_container_width=True):
            _connect_and_analyze(settings, source="manual_refresh", rerun=True)
        if st.session_state.messages and st.button("New chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_question = None
            st.rerun()

    if schema is not None:
        _render_connection_line(f"Connected to configured MySQL source. Claude: {settings.claude_model}.")


def _auto_connect_if_needed(settings: Settings) -> None:
    if st.session_state.schema is not None:
        return
    if st.session_state.auto_connect_attempted:
        return

    st.session_state.auto_connect_attempted = True
    if not settings.mysql_configured:
        log_event("Auto-connect skipped because MySQL settings are incomplete.", settings.public_status())
        return

    log_event("Auto-connecting to MySQL on app open.")
    _connect_and_analyze(settings, source="auto_connect", rerun=False)


def _connect_and_analyze(settings: Settings, *, source: str, rerun: bool) -> None:
    if not settings.mysql_configured:
        log_event("MySQL connection skipped because settings are incomplete.", settings.public_status())
        st.error("MySQL settings are incomplete. Fill `.env` and retry.")
        return

    try:
        with st.spinner("Connecting to MySQL and reading schema..."):
            engine = create_mysql_engine(settings)
            test_connection(engine)
            schema = introspect_schema(engine, settings.mysql_database)
            analysis = analyze_schema(schema, settings)
    except Exception as exc:
        log_event("MySQL connect/analyze failed.", {"error": str(exc)})
        st.error(f"MySQL connection or schema analysis failed: {exc}")
        return

    st.session_state.engine = engine
    st.session_state.schema = schema
    st.session_state.schema_analysis = analysis
    log_event("MySQL schema stored in session.", {"tables": len(schema.tables), "source": source})
    if source != "auto_connect":
        st.toast("MySQL schema refreshed.")
    if rerun:
        st.rerun()


def _drop_startup_schema_messages() -> None:
    has_user_message = any(message.get("role") == "user" for message in st.session_state.messages)
    if has_user_message:
        return

    filtered = []
    for message in st.session_state.messages:
        response_data = message.get("response")
        if not response_data:
            filtered.append(message)
            continue
        try:
            response = AssistantResponse.model_validate(response_data)
        except Exception:
            filtered.append(message)
            continue
        if response.ui_spec is not None and response.ui_spec.type == "schema_analysis":
            continue
        filtered.append(message)
    st.session_state.messages = filtered


def _render_welcome_prompts() -> None:
    schema: DatabaseSchema | None = st.session_state.schema
    if schema is None:
        return

    st.markdown('<div class="db-section-title">Suggested questions</div>', unsafe_allow_html=True)

    questions = _sample_questions()
    for row_start in range(0, len(questions), 2):
        columns = st.columns(2)
        for offset, column in enumerate(columns):
            index = row_start + offset
            if index >= len(questions):
                continue
            question = questions[index]
            if column.button(question, key=f"sample_question_{index}", use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()


def _sample_questions(limit: int = 4) -> list[str]:
    questions = ["What kind of questions can I ask?"]
    analysis = st.session_state.get("schema_analysis") or {}
    likely_questions = analysis.get("likely_questions", [])
    if isinstance(likely_questions, list):
        questions.extend(str(question) for question in likely_questions if str(question).strip())

    schema: DatabaseSchema | None = st.session_state.schema
    if schema is not None:
        questions.extend(_generic_schema_questions(schema))

    deduped = []
    seen = set()
    for question in questions:
        normalized = question.strip().lower()
        if not normalized or normalized in seen:
            continue
        deduped.append(question.strip())
        seen.add(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _generic_schema_questions(schema: DatabaseSchema) -> list[str]:
    questions = ["Show me schema relationships"]
    for table in schema.tables:
        date_column = next((column for column in table.columns if column.is_datetime), None)
        numeric_column = next((column for column in table.columns if column.is_numeric and not column.is_primary_key), None)
        category_column = next((column for column in table.columns if column.looks_categorical), None)

        if numeric_column is not None:
            questions.append(f"What is the total {numeric_column.column_name} in {table.table_name}?")
        if date_column is not None:
            questions.append(f"Show records in {table.table_name} by month using {date_column.column_name}.")
        if category_column is not None:
            questions.append(f"Show distribution of {table.table_name} by {category_column.column_name}.")
        if len(questions) >= 8:
            break
    return questions


def _render_schema_stats(stats: list[tuple[str, str]]) -> None:
    stat_cards = "\n".join(
        f"""
        <div class="db-stat-card">
          <div class="db-stat-label">{html.escape(label)}</div>
          <div class="db-stat-value" title="{html.escape(value)}">{html.escape(value)}</div>
        </div>
        """
        for label, value in stats
    )
    st.markdown(
        f"""
        <div class="db-stats-grid">
          {stat_cards}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_connection_line(caption: str) -> None:
    st.markdown(
        f"""
        <div class="db-connection-line">
          <span class="db-status-dot"></span>
          <span>{html.escape(caption)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_messages(settings: Settings) -> None:
    for message in st.session_state.messages:
        role = message["role"]
        with st.chat_message(role):
            if role == "assistant" and message.get("response"):
                response = AssistantResponse.model_validate(message["response"])
                render_assistant_response(
                    response,
                    show_debug=st.session_state.show_debug,
                    use_prefab=settings.enable_prefab_embed,
                )
            else:
                st.markdown(message["content"])


def _handle_pending_or_typed_question(settings: Settings, *, welcome_slot: Any) -> None:
    typed = st.chat_input("Ask about the connected database")
    question = st.session_state.pending_question or typed
    if not question:
        return

    welcome_slot.empty()
    st.session_state.pending_question = None
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Planning query and building UI..."):
            response = handle_question(
                question,
                settings=settings,
                engine=_session_engine(),
                schema=st.session_state.schema,
                schema_analysis=st.session_state.schema_analysis,
                chat_context=_chat_context(),
            )
        render_assistant_response(
            response,
            show_debug=st.session_state.show_debug,
            use_prefab=settings.enable_prefab_embed,
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.message,
            "response": response.model_dump(),
        }
    )


def _session_engine() -> Engine | None:
    engine: Engine | None = st.session_state.engine
    return engine


def _chat_context() -> list[dict[str, str]]:
    context: list[dict[str, str]] = []
    for message in st.session_state.messages[-8:]:
        context.append({"role": message["role"], "content": _message_text(message)})
    return context


def _message_text(message: dict[str, Any]) -> str:
    if message["role"] == "assistant" and message.get("response"):
        response = AssistantResponse.model_validate(message["response"])
        return response.message
    return str(message.get("content", ""))
