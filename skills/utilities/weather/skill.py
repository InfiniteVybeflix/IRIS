"""Weather Skill — Current weather, forecasts, alerts."""
import logging
import urllib.request
import json
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class WeatherSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="weather", category="utilities", capabilities=["weather"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "current")
        if method == "current": return self.current(params)
        elif method == "forecast": return self.forecast(params)
        return {"error": f"Unknown method: {method}"}

    def current(self, params: Dict[str, Any]) -> Dict[str, Any]:
        city = params.get("city", "")
        if not city: return {"success": False, "error": "No city provided"}
        try:
            encoded = city.replace(" ", "%20")
            req = urllib.request.Request(f"https://wttr.in/{encoded}?format=j1", headers={"User-Agent": "IRIS-OMNIS/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            current = data["current_condition"][0]
            return {"success": True, "city": city, "temperature_c": current.get("temp_C"), "temperature_f": current.get("temp_F"), "humidity": current.get("humidity"), "condition": current.get("weatherDesc", [{}])[0].get("value", ""), "wind_kph": current.get("windspeedKmph"), "feels_like_c": current.get("FeelsLikeC")}
        except Exception as e:
            return {"success": False, "error": str(e), "city": city}

    def forecast(self, params: Dict[str, Any]) -> Dict[str, Any]:
        city = params.get("city", "")
        days = params.get("days", 3)
        try:
            encoded = city.replace(" ", "%20")
            req = urllib.request.Request(f"https://wttr.in/{encoded}?format=j1", headers={"User-Agent": "IRIS-OMNIS/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            forecast_days = data.get("weather", [])[:days]
            simplified = [{"date": d["date"], "max_c": d["maxtempC"], "min_c": d["mintempC"], "condition": d.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value", "")} for d in forecast_days]
            return {"success": True, "city": city, "forecast": simplified}
        except Exception as e:
            return {"success": False, "error": str(e)}
