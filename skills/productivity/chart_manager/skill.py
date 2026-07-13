"""Chart Manager Skill — Generate charts, dashboards, and visualizations."""

import json
import base64
import io
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ChartManagerSkill(BaseSkill):
    """Chart generation: bar, line, pie, scatter, heatmap, radar."""

    def __init__(self):
        super().__init__(
            name="chart_manager",
            category="productivity",
            capabilities=["chart_generation"]
        )

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create_chart")
        if method == "create_chart":
            return self.create_chart(params)
        elif method == "create_dashboard":
            return self.create_dashboard(params)
        elif method == "export_png":
            return self.export_png(params)
        return {"error": f"Unknown method: {method}"}

    def create_chart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chart_type = params.get("type", "bar")
        title = params.get("title", "Chart")
        labels = params.get("labels", [])
        values = params.get("values", [])
        datasets = params.get("datasets", [{"label": title, "data": values}])
        x_label = params.get("x_label", "")
        y_label = params.get("y_label", "")
        if not labels and not any(d.get("data") for d in datasets):
            return {"success": False, "error": "Provide labels+values or datasets"}
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import numpy as np
            fig, ax = plt.subplots(figsize=params.get("figsize", (10, 6)))
            if chart_type == "bar":
                x = np.arange(len(labels))
                width = 0.8 / len(datasets)
                for i, ds in enumerate(datasets):
                    offset = (i - len(datasets)/2 + 0.5) * width
                    ax.bar(x + offset, ds.get("data", values), width, label=ds.get("label", f"Series {i+1}"))
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=params.get("rotation", 0))
            elif chart_type == "horizontal_bar":
                ax.barh(labels, values)
            elif chart_type == "line":
                for ds in datasets:
                    ax.plot(labels, ds.get("data", values), marker=params.get("marker", 'o'), label=ds.get("label", ""), linewidth=2)
            elif chart_type == "pie":
                colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
                wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_weight('bold')
            elif chart_type == "scatter":
                x_vals = params.get("x_values", list(range(len(values))))
                ax.scatter(x_vals, values, s=params.get("point_size", 50), alpha=0.7, c=params.get("colors", "blue"))
            elif chart_type == "heatmap":
                matrix = params.get("matrix", [values])
                im = ax.imshow(matrix, cmap=params.get("colormap", "YlOrRd"), aspect='auto')
                plt.colorbar(im, ax=ax)
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels)
            elif chart_type == "radar":
                angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
                angles += angles[:1]
                ax.remove()
                ax = fig.add_subplot(111, polar=True)
                for ds in datasets:
                    data = ds.get("data", values)
                    data += data[:1]
                    ax.plot(angles, data, 'o-', linewidth=2, label=ds.get("label", ""))
                    ax.fill(angles, data, alpha=0.15)
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels(labels)
            elif chart_type == "area":
                ax.fill_between(labels, values, alpha=0.4)
                ax.plot(labels, values, linewidth=2)
            elif chart_type == "histogram":
                bins = params.get("bins", 10)
                ax.hist(values, bins=bins, edgecolor='black', alpha=0.7)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if x_label:
                ax.set_xlabel(x_label)
            if y_label:
                ax.set_ylabel(y_label)
            if len(datasets) > 1 or (datasets and datasets[0].get("label") and datasets[0]["label"] != title):
                ax.legend()
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=params.get("dpi", 100), bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode('utf-8')
            return {"success": True, "chart_type": chart_type, "title": title, "base64_png": b64, "data_points": sum(len(ds.get("data", [])) for ds in datasets)}
        except ImportError:
            # Fallback: generate HTML/JS chart
            return self._create_html_chart(params)
        except Exception as e:
            logger.error(f"Chart creation failed: {e}")
            return {"success": False, "error": str(e)}

    def _create_html_chart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chart_type = params.get("type", "bar")
        title = params.get("title", "Chart")
        labels = json.dumps(params.get("labels", []))
        values = json.dumps(params.get("values", []))
        html = f"""<!DOCTYPE html><html><head><script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script></head>
<body><canvas id="c"></canvas><script>new Chart(document.getElementById('c').getContext('2d'),{{type:'{chart_type}',data:{{labels:{labels},datasets:[{{label:'{title}',data:{values}}}]}});</script></body></html>"""
        return {"success": True, "chart_type": chart_type, "title": title, "html_chart": html, "backend": "chartjs"}

    def create_dashboard(self, params: Dict[str, Any]) -> Dict[str, Any]:
        charts = params.get("charts", [])
        layout = params.get("layout", "grid")
        dashboard_charts = []
        for chart_def in charts:
            result = self.create_chart(chart_def)
            dashboard_charts.append({"title": chart_def.get("title", ""), **result})
        return {"success": True, "charts_included": len(dashboard_charts), "layout": layout, "charts": dashboard_charts, "dashboard_ready": True}

    def export_png(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chart_data = params.get("chart_data", {})
        output_path = params.get("output_path", "chart.png")
        result = self.create_chart(chart_data)
        if result.get("success") and result.get("base64_png"):
            import base64
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(result["base64_png"]))
            return {"success": True, "output_path": output_path, "format": "png"}
        return result
