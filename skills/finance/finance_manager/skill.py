"""Finance Manager Skill — Income, expenses, accounts tracking."""
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class FinanceManagerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="finance_manager", category="finance", capabilities=["finance_manager"])
        self._transactions: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "add_transaction")
        if method == "add_transaction": return self.add_transaction(params)
        elif method == "summary": return self.summary(params)
        elif method == "report": return self.report(params)
        return {"error": f"Unknown method: {method}"}

    def add_transaction(self, params: Dict[str, Any]) -> Dict[str, Any]:
        t = {"id": len(self._transactions)+1, "type": params.get("type", "expense"), "amount": params.get("amount", 0), "category": params.get("category", ""), "description": params.get("description", ""), "date": params.get("date", datetime.utcnow().strftime("%Y-%m-%d"))}
        self._transactions.append(t)
        return {"success": True, "transaction": t}

    def summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        income = sum(t["amount"] for t in self._transactions if t["type"] == "income")
        expense = sum(t["amount"] for t in self._transactions if t["type"] == "expense")
        return {"success": True, "total_income": income, "total_expenses": expense, "balance": income - expense, "transaction_count": len(self._transactions)}

    def report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        by_category = {}
        for t in self._transactions:
            cat = t["category"]
            by_category[cat] = by_category.get(cat, 0) + t["amount"]
        return {"success": True, "by_category": by_category, "top_expenses": sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:10]}
