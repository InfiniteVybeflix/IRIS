"""Currency Converter Skill — Real-time and cached currency conversion."""
import logging
import urllib.request
import json
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class CurrencyConverterSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="currency_converter", category="utilities", capabilities=["currency_converter"])
        self._cache: Dict[str, Any] = {}
        self._base_rates = {"USD": 1, "EUR": 0.92, "GBP": 0.79, "JPY": 148, "CNY": 7.19, "KES": 157, "NGN": 1500, "ZAR": 18.8, "CAD": 1.35, "AUD": 1.52, "CHF": 0.88, "INR": 83, "BRL": 4.95}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "convert")
        if method == "convert": return self.convert(params)
        elif method == "list_currencies": return self.list_currencies(params)
        return {"error": f"Unknown method: {method}"}

    def convert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        amount = params.get("amount", 1)
        from_c = params.get("from", "USD").upper()
        to_c = params.get("to", "EUR").upper()
        try:
            req = urllib.request.Request(f"https://api.exchangerate-api.com/v4/latest/{from_c}", headers={"User-Agent": "IRIS-OMNIS/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            rate = data["rates"].get(to_c, self._base_rates.get(to_c, 0))
        except Exception:
            if from_c in self._base_rates and to_c in self._base_rates:
                rate = self._base_rates[to_c] / self._base_rates[from_c]
            else:
                return {"success": False, "error": f"Rate unavailable for {from_c}->{to_c}"}
        return {"success": True, "amount": amount, "from": from_c, "to": to_c, "rate": rate, "result": round(amount * rate, 2)}

    def list_currencies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "currencies": list(self._base_rates.keys()), "count": len(self._base_rates)}
