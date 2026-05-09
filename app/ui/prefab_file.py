"""Write the latest validated UI spec as an inspectable Prefab app file."""

from __future__ import annotations

import importlib.util
import json
import time
from typing import Any
from pathlib import Path

from app.debug import log_event
from app.ui.prefab_source import build_prefab_source
from app.ui.specs import UISpec

GENERATED_DIR = Path("generated")
CURRENT_PREFAB_FILE = GENERATED_DIR / "current_prefab_app.py"
CURRENT_SPEC_FILE = GENERATED_DIR / "current_ui_spec.json"


def initialize_prefab_files() -> None:
    """Create an inspectable placeholder if no generated app exists yet."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if not CURRENT_PREFAB_FILE.exists():
        CURRENT_PREFAB_FILE.write_text(_placeholder_code(), encoding="utf-8")
    if not CURRENT_SPEC_FILE.exists():
        CURRENT_SPEC_FILE.write_text("{}\n", encoding="utf-8")


def write_current_prefab_app(spec: UISpec) -> None:
    """Write the latest validated UI spec as deterministic Prefab Python code."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    clean_spec = clean_ui_spec_data(spec)
    CURRENT_SPEC_FILE.write_text(
        json.dumps(clean_spec, indent=2, default=str),
        encoding="utf-8",
    )
    CURRENT_PREFAB_FILE.write_text(build_prefab_source(clean_spec), encoding="utf-8")
    log_event(
        "Updated inspectable Prefab app file.",
        {"path": str(CURRENT_PREFAB_FILE), "spec_type": spec.type, "title": spec.title},
    )


def render_current_prefab_html() -> str:
    """Import the generated Prefab file and return its rendered HTML."""
    if not CURRENT_PREFAB_FILE.exists():
        initialize_prefab_files()

    module_name = f"generated_current_prefab_app_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, CURRENT_PREFAB_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load generated Prefab file: {CURRENT_PREFAB_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prefab_app = getattr(module, "app", None)
    if prefab_app is None and hasattr(module, "build_app"):
        prefab_app = module.build_app()
    if prefab_app is None:
        raise RuntimeError(f"Generated Prefab file did not define `app`: {CURRENT_PREFAB_FILE}")
    return prefab_app.html()


def _placeholder_code() -> str:
    return build_prefab_source(
        {
            "type": "text",
            "title": "Dynamic Database Chat",
            "summary": "Ask a question and the assistant will write the latest Prefab UI here.",
            "metrics": [],
            "columns": [],
            "rows": [],
            "chart": None,
            "filters": [],
            "children": [],
            "mermaid": None,
        }
    )


def clean_ui_spec_data(spec: UISpec) -> dict[str, Any]:
    """Return the render-only JSON spec written to generated/current_ui_spec.json."""
    data = json.loads(json.dumps(spec.model_dump(), default=str))
    return _clean_spec_dict(data)


def _clean_spec_dict(data: dict[str, Any]) -> dict[str, Any]:
    data.pop("debug", None)
    message = data.pop("message", "")
    data["summary"] = _summary_for_spec(data, fallback=message)
    children = data.get("children")
    if isinstance(children, list):
        data["children"] = [
            _clean_spec_dict(child)
            for child in children
            if isinstance(child, dict)
        ]
    return _prune_render_spec(data)


def _prune_render_spec(data: dict[str, Any]) -> dict[str, Any]:
    spec_type = data.get("type")
    base = _copy_present(data, ["type", "title", "summary"])

    if spec_type == "kpi":
        return _copy_present(data, ["metrics"], target=base)
    if spec_type == "chart":
        return _copy_present(data, ["chart", "rows"], target=base)
    if spec_type == "table":
        return _copy_present(data, ["columns", "rows"], target=base)
    if spec_type == "detail":
        return _copy_present(data, ["columns", "rows", "filters"], target=base)
    if spec_type == "filters":
        return _copy_present(data, ["columns", "rows", "filters"], target=base)
    if spec_type == "schema_map":
        return _copy_present(data, ["mermaid"], target=base)
    if spec_type == "schema_analysis":
        return _copy_present(data, ["columns", "rows", "children", "mermaid"], target=base)
    if spec_type == "dashboard":
        return _copy_present(data, ["metrics", "columns", "rows", "chart", "filters", "children"], target=base)
    return base


def _copy_present(data: dict[str, Any], keys: list[str], *, target: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(target or {})
    for key in keys:
        if key not in data:
            continue
        value = _prune_empty(data[key])
        if value in (None, [], {}):
            continue
        result[key] = value
    return result


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: pruned
            for key, item in value.items()
            if (pruned := _prune_empty(item)) not in (None, [], {})
        }
    if isinstance(value, list):
        return [
            pruned
            for item in value
            if (pruned := _prune_empty(item)) not in (None, [], {})
        ]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _summary_for_spec(data: dict[str, Any], *, fallback: object) -> str:
    spec_type = data.get("type")
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    metrics = data.get("metrics") if isinstance(data.get("metrics"), list) else []
    chart = data.get("chart") if isinstance(data.get("chart"), dict) else {}

    if spec_type == "kpi" and metrics:
        parts = []
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            label = str(metric.get("label") or "Value")
            parts.append(f"{label}: {_format_summary_value(metric.get('value'))}")
        if parts:
            return "; ".join(parts) + "."
    if spec_type == "chart" and chart:
        x_field = chart.get("x_field") or chart.get("label_field")
        measures = _measure_fields(data)
        if x_field and measures:
            return f"{_humanize(str(x_field))} comparison for {', '.join(_humanize(field) for field in measures)}."
        chart_type = str(chart.get("chart_type") or "chart").replace("_", " ")
        return f"{chart_type.title()} summary across {len(rows)} result rows."
    if spec_type in {"table", "detail", "filters"}:
        return f"Result summary for {len(rows)} rows."
    if spec_type == "schema_map":
        return "Schema relationship summary."
    if spec_type == "error":
        return "The request could not be completed."
    text = str(fallback or "").strip()
    if text:
        return text
    return "Generated result summary."


def _format_summary_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int | float):
        return f"{value:,}"
    if value is None:
        return "-"
    return str(value)


def _measure_fields(data: dict[str, Any]) -> list[str]:
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    if not rows:
        return []
    chart = data.get("chart") if isinstance(data.get("chart"), dict) else {}
    x_field = chart.get("x_field") or chart.get("label_field")
    preferred = [chart.get("y_field"), chart.get("value_field")]
    numeric_fields = [
        str(field)
        for field in rows[0].keys()
        if field != x_field and any(_is_number(row.get(field)) for row in rows)
    ]
    result = []
    for field in [*preferred, *numeric_fields]:
        if field and field in numeric_fields and field not in result:
            result.append(str(field))
    return result[:4]


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
        return value is not None
    except (TypeError, ValueError):
        return False


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()
