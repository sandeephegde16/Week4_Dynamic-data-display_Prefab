"""Finite Prefab component catalog used by planning and schema analysis."""

from __future__ import annotations

PREFAB_COMPONENTS = [
    "Metric",
    "DataTable",
    "DataTableColumn",
    "Histogram",
    "Dashboard",
    "DashboardItem",
    "Card",
    "Grid",
    "Row",
    "Tabs",
    "Accordion",
    "Badge",
    "Alert",
    "AlertTitle",
    "AlertDescription",
    "DatePicker",
    "Select",
    "Combobox",
    "Slider",
    "Switch",
    "Mermaid",
    "Code",
    "Markdown",
]

RENDER_KIND_COMPONENTS = {
    "text": ["Markdown"],
    "kpi": ["Metric", "Card", "Grid", "Row"],
    "table": ["DataTable", "DataTableColumn"],
    "bar_chart": ["Histogram", "DataTable", "Badge"],
    "line_chart": ["Histogram", "DataTable"],
    "area_chart": ["Histogram", "DataTable"],
    "pie_chart": ["Histogram", "DataTable", "Badge"],
    "scatter": ["Histogram", "DataTable"],
    "histogram": ["Histogram"],
    "dashboard": ["Dashboard", "DashboardItem", "Metric", "Card", "Grid", "Tabs", "DataTable"],
    "detail_panel": ["Card", "Accordion", "Tabs", "Badge", "DataTable"],
    "filter_panel": ["DatePicker", "Select", "Combobox", "Slider", "Switch", "Grid"],
    "schema_map": ["Mermaid", "Card", "DataTable", "Code"],
    "error": ["Alert", "AlertTitle", "AlertDescription"],
    "debug": ["Code", "Markdown", "Accordion", "Tabs"],
}


def components_for_widget(widget: str) -> list[str]:
    """Return Prefab components used for a render/widget kind."""
    return RENDER_KIND_COMPONENTS.get(widget, ["Card", "Markdown"])


def component_catalog_text() -> str:
    return ", ".join(PREFAB_COMPONENTS)
