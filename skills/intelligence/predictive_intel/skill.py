"""Predictive Intelligence Skill — Trend prediction, forecasting, anomaly detection."""

import json
import logging
import statistics
from typing import Dict, Any, List
from datetime import datetime, timedelta
from skills import BaseSkill

logger = logging.getLogger(__name__)


class PredictiveIntelSkill(BaseSkill):
    """Trend analysis, forecasting, and anomaly detection."""

    def __init__(self):
        super().__init__(
            name="predictive_intel",
            category="intelligence",
            capabilities=["predictive_analytics"]
        )

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "forecast")
        if method == "forecast":
            return self.forecast(params)
        elif method == "trend_analysis":
            return self.trend_analysis(params)
        elif method == "anomaly_detect":
            return self.anomaly_detect(params)
        return {"error": f"Unknown method: {method}"}

    def forecast(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data = params.get("data", [])
        periods = params.get("periods", 5)
        method = params.get("forecast_method", "linear")
        if not data or len(data) < 2:
            return {"success": False, "error": "Need at least 2 data points", "forecast": []}
        if method == "linear":
            return self._linear_forecast(data, periods)
        elif method == "moving_average":
            return self._moving_average_forecast(data, periods, params)
        elif method == "exponential":
            return self._exponential_forecast(data, periods, params)
        return {"success": False, "error": f"Unknown forecast method: {method}"}

    def _linear_forecast(self, data: List[float], periods: int) -> Dict[str, Any]:
        n = len(data)
        x_mean = sum(range(n)) / n
        y_mean = sum(data) / n
        denom = sum((i - x_mean) ** 2 for i in range(n))
        slope = sum((i - x_mean) * (data[i] - y_mean) for i in range(n)) / denom if denom else 0
        intercept = y_mean - slope * x_mean
        forecast = [round(slope * (n + i) + intercept, 4) for i in range(1, periods + 1)]
        r_squared = self._r_squared(data, [slope * i + intercept for i in range(n)]) if denom else 0
        return {"success": True, "forecast": forecast, "slope": round(slope, 6), "intercept": round(intercept, 4), "r_squared": round(r_squared, 4), "method": "linear_regression"}

    def _moving_average_forecast(self, data: List[float], periods: int, params: Dict[str, Any]) -> Dict[str, Any]:
        window = min(params.get("window", 3), len(data))
        ma = statistics.mean(data[-window:])
        forecast = [round(ma, 4)] * periods
        return {"success": True, "forecast": forecast, "window": window, "method": "moving_average"}

    def _exponential_forecast(self, data: List[float], periods: int, params: Dict[str, Any]) -> Dict[str, Any]:
        alpha = params.get("alpha", 0.3)
        s = [data[0]]
        for i in range(1, len(data)):
            s.append(alpha * data[i] + (1 - alpha) * s[-1])
        forecast = [round(s[-1], 4)]
        for _ in range(1, periods):
            forecast.append(round(alpha * forecast[-1] + (1 - alpha) * forecast[-1], 4))
        return {"success": True, "forecast": forecast, "alpha": alpha, "method": "exponential_smoothing"}

    def _r_squared(self, actual: List[float], predicted: List[float]) -> float:
        ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
        y_mean = sum(actual) / len(actual)
        ss_tot = sum((a - y_mean) ** 2 for a in actual)
        return 1 - (ss_res / ss_tot) if ss_tot else 0

    def trend_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data = params.get("data", [])
        if len(data) < 4:
            return {"success": False, "error": "Need at least 4 data points", "trend": "insufficient_data"}
        q1 = data[:len(data)//4] if len(data) >= 4 else data[:1]
        q2 = data[len(data)//4:len(data)//2]
        q3 = data[len(data)//2:3*len(data)//4]
        q4 = data[3*len(data)//4:]
        means = [statistics.mean(q) if q else 0 for q in [q1, q2, q3, q4]]
        slope = means[-1] - means[0]
        if slope > abs(statistics.mean(data)) * 0.1:
            trend = "strongly_increasing"
        elif slope > 0:
            trend = "increasing"
        elif slope < -abs(statistics.mean(data)) * 0.1:
            trend = "strongly_decreasing"
        elif slope < 0:
            trend = "decreasing"
        else:
            trend = "stable"
        return {"success": True, "trend": trend, "quarterly_means": [round(m, 4) for m in means], "overall_slope": round(slope, 4), "data_points": len(data)}

    def anomaly_detect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data = params.get("data", [])
        if len(data) < 3:
            return {"success": False, "error": "Need at least 3 data points", "anomalies": []}
        mean = statistics.mean(data)
        stdev = statistics.stdev(data) if len(data) > 1 else 0
        threshold = params.get("threshold", 2)
        method = params.get("detection_method", "zscore")
        anomalies = []
        if method == "zscore" and stdev:
            for i, v in enumerate(data):
                z = abs(v - mean) / stdev
                if z > threshold:
                    anomalies.append({"index": i, "value": v, "z_score": round(z, 4), "mean": round(mean, 4)})
        elif method == "iqr":
            sorted_data = sorted(data)
            q1 = sorted_data[len(sorted_data)//4]
            q3 = sorted_data[3*len(sorted_data)//4]
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            for i, v in enumerate(data):
                if v < lower or v > upper:
                    anomalies.append({"index": i, "value": v, "bounds": [round(lower, 4), round(upper, 4)]})
        return {"success": True, "anomalies": anomalies, "anomaly_count": len(anomalies), "mean": round(mean, 4), "stdev": round(stdev, 4), "threshold": threshold}
