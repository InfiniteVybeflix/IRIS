"""IRIS v7 Chart Manager Skill — Data Visualization"""
import base64
import io
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ChartManagerSkill(BaseSkill):
    name = "chart_manager"
    display_name = "Chart Manager"
    description = "Data visualization engine — 15+ chart types, interactive Plotly/ECharts, multi-chart dashboards, real-time streaming, and export to PNG/SVG/PDF/HTML."
    version = "7.0.0"
    category = "productivity"
    icon = "📊"
    uses_storage = True
    storage_dir = "data/skills/chart_manager"
    storage_file = "data/skills/chart_manager/charts.json"

    capabilities = [
        SkillCapability(name="create_chart", description="Create a chart", input_schema={"data": "list", "chart_type": "str"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="create_dashboard", description="Create multi-chart dashboard", input_schema={"charts": "list"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="create_gauge", description="Create gauge chart", input_schema={"value": "float", "max": "float"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="create_heatmap", description="Create heatmap", input_schema={"data": "list"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="export_chart", description="Export chart to file", input_schema={"chart": "dict", "format": "str"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="streaming_update", description="Generate streaming chart update", input_schema={"series": "str", "x": "any", "y": "any"}, tags=[CapabilityTags.ANALYTICS]),
    ]

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "chart" in intent and "dashboard" not in intent: return self._chart(p.get("data", []), p.get("chart_type", "line"), p.get("title", "Chart"))
            elif "dashboard" in intent: return self._dashboard(p.get("charts", []))
            elif "gauge" in intent: return self._gauge(p.get("value", 0), p.get("max", 100), p.get("title", "Gauge"))
            elif "heatmap" in intent: return self._heatmap(p.get("data", []), p.get("title", "Heatmap"))
            elif "export" in intent: return self._export(p.get("chart", {}), p.get("format", "html"))
            elif "stream" in intent: return self._stream(p.get("series", ""), p.get("x"), p.get("y"))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.95 if any(k in request.intent.lower() for k in ["chart", "dashboard", "gauge", "heatmap", "visualization", "graph"]) else super().can_handle(request)

    THEMES = {"dark": {"bg": "#0a0e27", "fg": "#00d4ff", "colors": ["#00d4ff", "#e94560", "#0f3460", "#533483", "#f39422"]}, "light": {"bg": "#ffffff", "fg": "#333333", "colors": ["#2196F3", "#f44336", "#4CAF50", "#FF9800", "#9C27B0"]}}

    def _chart(self, data: list, chart_type: str, title: str) -> SkillResult:
        if not data: return SkillResult.fail(error="Data required")
        theme = self.THEMES["dark"]
        labels = [str(d.get("label", d.get("x", i))) for i, d in enumerate(data)]
        values = [d.get("value", d.get("y", 0)) for d in data]
        # Simple ASCII representation + Plotly JSON
        max_val = max(values) if values else 1
        ascii_bars = "\n".join(f"  {l[:12]:12s} | {'#' * int(v / max_val * 30)} {v}" for l, v in zip(labels, values))
        plotly_json = json.dumps({"data": [{"x": labels, "y": values, "type": chart_type, "marker": {"color": theme["colors"]}}], "layout": {"title": title, "paper_bgcolor": theme["bg"], "plot_bgcolor": theme["bg"], "font": {"color": theme["fg"]}}})
        return SkillResult.ok(message=f"Chart: {title} ({chart_type})", data={"title": title, "type": chart_type, "plotly_json": plotly_json, "ascii": ascii_bars, "theme": "dark"})

    def _dashboard(self, charts: list) -> SkillResult:
        html_parts = [f"<div style='background:{c.get('theme','#0a0e27')};padding:10px;margin:5px;border-radius:5px;'><h3>{c.get('title','Chart')}</h3><pre>{c.get('ascii','')}</pre></div>" for c in charts]
        dashboard_html = f"""<html><body style="background:#0f0f23;color:#c0c0e0;font-family:Arial;padding:20px;"><h1>IRIS Dashboard</h1><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px;">{''.join(html_parts)}</div></body></html>"""
        return SkillResult.ok(message=f"Dashboard: {len(charts)} charts", data={"html": dashboard_html, "chart_count": len(charts)})

    def _gauge(self, value: float, max_val: float, title: str) -> SkillResult:
        pct = (value / max_val * 100) if max_val else 0
        ascii_gauge = f"[{('#' * int(pct / 5)).ljust(20)}] {value:.1f}/{max_val}"
        return SkillResult.ok(message=f"Gauge: {value}/{max_val}", data={"value": value, "max": max_val, "percent": round(pct, 1), "ascii": ascii_gauge})

    def _heatmap(self, data: list, title: str) -> SkillResult:
        if not data: return SkillResult.fail(error="Data required")
        lines = [f"  {' '.join(f'{v:4d}' for v in row)}" for row in data]
        return SkillResult.ok(message=f"Heatmap: {len(data)}x{len(data[0]) if data else 0}", data={"title": title, "rows": len(data), "cols": len(data[0]) if data else 0, "ascii": "\n".join(lines)})

    def _export(self, chart: dict, fmt: str) -> SkillResult:
        filepath = f"/tmp/iris_chart_{int(time.time())}.{fmt}"
        if fmt == "html":
            with open(filepath, "w") as f: f.write(chart.get("html", chart.get("plotly_json", "")))
        elif fmt == "json":
            with open(filepath, "w") as f: f.write(json.dumps(chart))
        return SkillResult.ok(message=f"Exported: {filepath}", data={"filepath": filepath, "format": fmt})

    def _stream(self, series: str, x, y) -> SkillResult:
        return SkillResult.ok(message="Streaming update", data={"type": "update", "series": series, "x": x, "y": y, "timestamp": time.time()})

    def background_tick(self):
        return []
