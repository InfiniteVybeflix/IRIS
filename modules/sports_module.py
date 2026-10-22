"""IRIS v1 Sports Module — Live scores, odds, stats via API-Sports"""
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional

class SportsModule:
    """
    IRIS sports capabilities:
    - Live scores and fixtures
    - Team statistics
    - Player data
    - Betting odds (via Odds API)
    - League standings
    """

    def __init__(self):
        self.api_key = os.getenv("IRIS_APISPORTS_KEY", "")
        self.odds_key = os.getenv("IRIS_ODDS_API_KEY", "")
        self.base_url = "https://v3.football.api-sports.io"

    def _headers(self) -> Dict:
        return {"x-apisports-key": self.api_key}

    def get_live_matches(self, league_id: int = None) -> Dict:
        """Get currently live matches."""
        if not self.api_key:
            return {"success": False, "error": "API-Sports key not configured in .env"}

        try:
            params = {"live": "all"}
            if league_id:
                params["league"] = league_id

            response = requests.get(f"{self.base_url}/fixtures", headers=self._headers(), params=params, timeout=15)
            data = response.json()

            if response.status_code == 200:
                matches = []
                for match in data.get("response", []):
                    matches.append({
                        "id": match.get("fixture", {}).get("id"),
                        "league": match.get("league", {}).get("name"),
                        "home_team": match.get("teams", {}).get("home", {}).get("name"),
                        "away_team": match.get("teams", {}).get("away", {}).get("name"),
                        "home_score": match.get("goals", {}).get("home"),
                        "away_score": match.get("goals", {}).get("away"),
                        "status": match.get("fixture", {}).get("status", {}).get("short"),
                        "minute": match.get("fixture", {}).get("status", {}).get("elapsed")
                    })
                return {"success": True, "matches": matches, "count": len(matches)}
            return {"success": False, "error": "API error"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_odds(self, sport: str = "soccer", region: str = "us") -> Dict:
        """Get betting odds via Odds API."""
        if not self.odds_key:
            return {"success": False, "error": "Odds API key not configured in .env"}

        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
            params = {
                "apiKey": self.odds_key,
                "regions": region,
                "markets": "h2h",
                "oddsFormat": "decimal"
            }
            response = requests.get(url, params=params, timeout=15)
            data = response.json()

            if response.status_code == 200:
                odds = []
                for event in data:
                    odds.append({
                        "home_team": event.get("home_team"),
                        "away_team": event.get("away_team"),
                        "commence_time": event.get("commence_time"),
                        "bookmaker": event.get("bookmakers", [{}])[0].get("title", "Unknown")
                    })
                return {"success": True, "odds": odds, "count": len(odds)}
            return {"success": False, "error": str(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_team_stats(self, team_id: int, league_id: int, season: int = 2024) -> Dict:
        """Get team statistics."""
        if not self.api_key:
            return {"success": False, "error": "API-Sports key not configured"}

        try:
            params = {"team": team_id, "league": league_id, "season": season}
            response = requests.get(f"{self.base_url}/teams/statistics", headers=self._headers(), params=params, timeout=15)
            data = response.json()

            if response.status_code == 200:
                return {"success": True, "stats": data.get("response", {})}
            return {"success": False, "error": "API error"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_live_summary(self) -> str:
        """Get a text summary of live matches for IRIS to read."""
        result = self.get_live_matches()
        if not result.get("success"):
            return f"Sports data unavailable: {result.get('error')}"

        matches = result["matches"]
        if not matches:
            return "No live matches currently."

        lines = ["Here are the live matches:"]
        for m in matches[:5]:
            score = f"{m['home_score']}-{m['away_score']}" if m['home_score'] is not None else "vs"
            lines.append(f"{m['home_team']} {score} {m['away_team']} — {m['status']} {m.get('minute', '')}'")
        return "\n".join(lines)

# Singleton
sports_module = SportsModule()
