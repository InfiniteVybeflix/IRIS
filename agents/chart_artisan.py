#!/usr/bin/env python3
"""
chart_artisan.py — CANVAS
Data Visualization Agent for IRIS v7.0
Multi-chart dashboards (Plotly/ECharts/Matplotlib), real-time streaming data,
interactive charts, export (PNG/SVG/PDF/HTML), theming/dark mode, responsive layouts.
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CANVAS")


class ChartArtisan:
    CODENAME = "CANVAS"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._streaming_buffers: Dict[str, deque] = {}
        self._theme = "dark"
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("CANVAS started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("CANVAS stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "streams": len(self._streaming_buffers),
                "theme": self._theme,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def generate_plotly_chart(self, chart_type: str, data: Dict[str, Any], title: str = "") -> str:
        """Generate a self-contained HTML file with a Plotly chart."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import plotly.graph_objects as go
            import plotly.express as px
        except ImportError:
            self._report_to_commander("Plotly not installed; generating ECharts fallback", level="warning")
            return self.generate_echarts_chart(chart_type, data, title)

        fig = go.Figure()
        if chart_type == "bar":
            for trace in data.get("traces", []):
                fig.add_trace(go.Bar(x=trace.get("x"), y=trace.get("y"), name=trace.get("name", "")))
        elif chart_type == "line":
            for trace in data.get("traces", []):
                fig.add_trace(go.Scatter(x=trace.get("x"), y=trace.get("y"), mode="lines", name=trace.get("name", "")))
        elif chart_type == "pie":
            fig = go.Figure(data=[go.Pie(labels=data.get("labels"), values=data.get("values"))])
        elif chart_type == "scatter":
            for trace in data.get("traces", []):
                fig.add_trace(go.Scatter(x=trace.get("x"), y=trace.get("y"), mode="markers", name=trace.get("name", "")))
        else:
            fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="lines"))

        fig.update_layout(
            title=title,
            template="plotly_dark" if self._theme == "dark" else "plotly_white",
            autosize=True,
        )
        html = fig.to_html(include_plotlyjs="cdn", full_html=True)
        self._store_memory(f"chart:{title}", {"type": chart_type, "engine": "plotly"})
        return html

    def generate_echarts_chart(self, chart_type: str, data: Dict[str, Any], title: str = "") -> str:
        """Generate a self-contained HTML file with an ECharts chart."""
        if not self._running:
            raise RuntimeError("Agent not running")
        option = {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff" if self._theme == "dark" else "#333"}},
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0},
            "xAxis": {"type": "category", "data": data.get("categories", []), "axisLabel": {"color": "#ccc" if self._theme == "dark" else "#333"}},
            "yAxis": {"type": "value", "axisLabel": {"color": "#ccc" if self._theme == "dark" else "#333"}},
            "series": [],
            "backgroundColor": "#1a1a1a" if self._theme == "dark" else "#ffffff",
        }
        if chart_type == "bar":
            for trace in data.get("traces", []):
                option["series"].append({"type": "bar", "name": trace.get("name", ""), "data": trace.get("y", [])})
        elif chart_type == "line":
            for trace in data.get("traces", []):
                option["series"].append({"type": "line", "name": trace.get("name", ""), "data": trace.get("y", []), "smooth": True})
        elif chart_type == "pie":
            option = {
                "title": {"text": title, "left": "center"},
                "tooltip": {"trigger": "item"},
                "series": [{"type": "pie", "radius": "50%", "data": [{"value": v, "name": l} for v, l in zip(data.get("values", []), data.get("labels", []))]}],
                "backgroundColor": "#1a1a1a" if self._theme == "dark" else "#ffffff",
            }
        else:
            option["series"].append({"type": "line", "data": [1, 2, 3]})

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>body{{margin:0;background:{"#1a1a1a" if self._theme == "dark" else "#fff"};color:{"#fff" if self._theme == "dark" else "#333"};}}</style>
</head><body><div id="chart" style="width:100vw;height:100vh;"></div>
<script>var chart=echarts.init(document.getElementById('chart'));chart.setOption({json.dumps(option)});window.addEventListener('resize',function(){{chart.resize()}});</script>
</body></html>"""
        self._store_memory(f"chart:{title}", {"type": chart_type, "engine": "echarts"})
        return html

    def generate_matplotlib_chart(self, chart_type: str, data: Dict[str, Any], title: str = "",
                                   output_path: str = "chart.png") -> str:
        """Generate a static image using Matplotlib."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            self._report_to_commander("Matplotlib not installed", level="error")
            raise
        fig, ax = plt.subplots(figsize=(10, 6))
        if self._theme == "dark":
            fig.patch.set_facecolor("#1a1a1a")
            ax.set_facecolor("#1a1a1a")
            ax.tick_params(colors="white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            ax.title.set_color("white")
        if chart_type == "bar":
            for trace in data.get("traces", []):
                ax.bar(trace.get("x", []), trace.get("y", []), label=trace.get("name", ""))
        elif chart_type == "line":
            for trace in data.get("traces", []):
                ax.plot(trace.get("x", []), trace.get("y", []), label=trace.get("name", ""))
        elif chart_type == "scatter":
            for trace in data.get("traces", []):
                ax.scatter(trace.get("x", []), trace.get("y", []), label=trace.get("name", ""))
        ax.set_title(title)
        ax.legend()
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
        plt.close()
        self._store_memory(f"chart:{title}", {"path": output_path, "engine": "matplotlib"})
        return output_path

    def create_dashboard(self, charts: List[Dict[str, Any]], title: str = "Dashboard") -> str:
        """Create a responsive HTML dashboard combining multiple charts."""
        if not self._running:
            raise RuntimeError("Agent not running")
        panels = []
        for idx, chart in enumerate(charts):
            html = self.generate_echarts_chart(
                chart.get("type", "line"),
                chart.get("data", {}),
                title=chart.get("title", f"Chart {idx}")
            )
            # Extract just the script portion for embedding
            script_match = __import__("re").search(r"<script>(.*?)</script>", html, re.DOTALL)
            script = script_match.group(1) if script_match else ""
            panels.append(f'<div class="panel" id="panel{idx}"><div id="chart{idx}" style="width:100%;height:300px;"></div></div>')
        body_html = "\n".join(panels)
        dashboard = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
body{{margin:0;background:{"#1a1a1a" if self._theme == "dark" else "#f5f5f5"};color:{"#fff" if self._theme == "dark" else "#333"};font-family:sans-serif;}}
.container{{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:1rem;padding:1rem;}}
.panel{{background:{"#2a2a2a" if self._theme == "dark" else "#fff"};border-radius:8px;padding:1rem;box-shadow:0 2px 8px rgba(0,0,0,0.3);}}
h1{{text-align:center;margin:1rem 0;}}
</style></head>
<body><h1>{title}</h1><div class="container">{body_html}</div></body></html>"""
        self._store_memory(f"dashboard:{title}", {"charts": len(charts)})
        return dashboard

    def push_stream_data(self, stream_id: str, point: Dict[str, Any], max_buffer: int = 1000) -> None:
        """Push a data point into a real-time streaming buffer."""
        with self._lock:
            buf = self._streaming_buffers.setdefault(stream_id, deque(maxlen=max_buffer))
            buf.append({"timestamp": datetime.utcnow().isoformat(), **point})
        self._store_memory(f"stream:{stream_id}", list(buf)[-10:])

    def get_stream_data(self, stream_id: str, last_n: int = 100) -> List[Dict[str, Any]]:
        """Retrieve the last N points from a stream."""
        with self._lock:
            buf = self._streaming_buffers.get(stream_id, deque())
            return list(buf)[-last_n:]

    def export_chart(self, html_content: str, filepath: str, fmt: str = "png") -> Dict[str, Any]:
        """Export HTML chart to PNG/SVG/PDF using headless browser or wkhtmltoimage."""
        if not self._running:
            raise RuntimeError("Agent not running")
        with open(filepath + ".html", "w", encoding="utf-8") as f:
            f.write(html_content)
        if fmt == "png":
            rc, out, err = self._execute_shell(f"wkhtmltoimage --width 1200 {filepath}.html {filepath}.png 2>&1 || chromium --headless --disable-gpu --screenshot={filepath}.png --window-size=1200,800 {filepath}.html 2>&1", timeout=60)
            if rc == 0 and os.path.exists(f"{filepath}.png"):
                return {"path": f"{filepath}.png", "format": "png", "size": os.path.getsize(f"{filepath}.png")}
        elif fmt == "pdf":
            rc, out, err = self._execute_shell(f"wkhtmltopdf {filepath}.html {filepath}.pdf 2>&1 || chromium --headless --disable-gpu --print-to-pdf={filepath}.pdf {filepath}.html 2>&1", timeout=60)
            if rc == 0 and os.path.exists(f"{filepath}.pdf"):
                return {"path": f"{filepath}.pdf", "format": "pdf", "size": os.path.getsize(f"{filepath}.pdf")}
        return {"path": filepath + ".html", "format": "html", "size": os.path.getsize(filepath + ".html"), "note": f"{fmt} conversion failed; HTML fallback"}

    def set_theme(self, theme: str) -> None:
        """Set global theme: 'dark' or 'light'."""
        with self._lock:
            self._theme = theme

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_generate_echarts(self) -> bool:
        r = self.generate_echarts_chart("bar", {"traces": [{"name": "A", "y": [1, 2, 3]}]}, "Test")
        return "echarts" in r

    def test_dashboard(self) -> bool:
        r = self.create_dashboard([{"type": "line", "data": {"traces": [{"y": [1, 2]}]}, "title": "T"}], "D")
        return "Dashboard" in r

    def test_stream(self) -> bool:
        self.push_stream_data("s1", {"value": 10})
        return len(self.get_stream_data("s1")) == 1

    def test_export(self) -> bool:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><body>Test</body></html>")
            path = f.name
        r = self.export_chart(open(path).read(), path.replace(".html", ""), "html")
        return "path" in r

    def test_theme(self) -> bool:
        self.set_theme("light")
        return self._theme == "light"


if __name__ == "__main__":
    agent = ChartArtisan()
    agent.start()
    print(agent.health())
    agent.stop()
