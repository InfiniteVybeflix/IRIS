"""Nutrition Planner Skill — Meal planning, calorie tracking, recipes."""
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class NutritionPlannerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="nutrition_planner", category="health_fitness", capabilities=["nutrition_planner"])
        self._meals: List[Dict[str, Any]] = []
        self._food_db = {
            "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "unit": "100g"},
            "chicken_breast": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "unit": "100g"},
            "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11, "unit": "100g"},
            "apple": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2, "unit": "100g"},
            "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fat": 1, "unit": "100ml"},
        }

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "log_meal")
        if method == "log_meal": return self.log_meal(params)
        elif method == "lookup": return self.lookup(params)
        elif method == "daily_summary": return self.daily_summary(params)
        elif method == "plan_meals": return self.plan_meals(params)
        return {"error": f"Unknown method: {method}"}

    def log_meal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        meal = {"time": datetime.utcnow().isoformat(), "foods": params.get("foods", []), "total_calories": sum(self._food_db.get(f["name"], {}).get("calories", 0) * f.get("quantity", 1) for f in params.get("foods", []))}
        self._meals.append(meal)
        return {"success": True, "meal": meal}

    def lookup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("food", "").lower().replace(" ", "_")
        info = self._food_db.get(name)
        return {"success": True, "food": name, "nutrition": info} if info else {"success": False, "error": "Food not in database"}

    def daily_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_meals = [m for m in self._meals if m["time"].startswith(today)]
        total = sum(m["total_calories"] for m in today_meals)
        return {"success": True, "date": today, "meals_logged": len(today_meals), "total_calories": total}

    def plan_meals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target_calories = params.get("target_calories", 2000)
        diet = params.get("diet", "balanced")
        return {"success": True, "target": target_calories, "diet": diet, "plan": {"breakfast": {"calories": target_calories * 0.25, "suggestions": ["Oatmeal with fruit", "Eggs and toast"]}, "lunch": {"calories": target_calories * 0.35, "suggestions": ["Grilled chicken salad", "Rice and vegetables"]}, "dinner": {"calories": target_calories * 0.3, "suggestions": ["Fish with steamed vegetables", "Stir fry with lean protein"]}, "snacks": {"calories": target_calories * 0.1, "suggestions": ["Nuts", "Fruit"]}}}
