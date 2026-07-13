"""Budgeting Skill — Budget creation, tracking, alerts."""
import logging
from typing import Dict, Any
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class BudgetingSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="budgeting", category="finance", capabilities=["budgeting"])
        self._budgets: Dict[str, Dict[str, Any]] = {}
        self._spending: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create_budget")
        if method == "create_budget": return self.create_budget(params)
        elif method == "log_spending": return self.log_spending(params)
        elif method == "check_budget": return self.check_budget(params)
        return {"error": f"Unknown method: {method}"}

    def create_budget(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cat = params.get("category", "general")
        self._budgets[cat] = {"category": cat, "limit": params.get("limit", 0), "period": params.get("period", "monthly"), "created": datetime.utcnow().isoformat()}
        return {"success": True, "budget": self._budgets[cat]}

    def log_spending(self, params: Dict[str, Any]) -> Dict[str, Any]:
        s = {"category": params.get("category", ""), "amount": params.get("amount", 0), "date": datetime.utcnow().strftime("%Y-%m-%d")}
        self._spending.append(s)
        return {"success": True, "logged": s}

    def check_budget(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cat = params.get("category", "")
        budget = self._budgets.get(cat, {})
        spent = sum(s["amount"] for s in self._spending if s["category"] == cat)
        limit = budget.get("limit", 0)
        remaining = limit - spent
        alert = spent > limit * 0.9 if limit else False
        return {"success": True, "category": cat, "budget": limit, "spent": spent, "remaining": remaining, "alert": alert, "percentage_used": round(spent/limit*100, 1) if limit else 0}
