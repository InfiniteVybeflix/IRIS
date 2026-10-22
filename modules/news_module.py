"""IRIS v8 News Module — Real-time news via FreeNews API"""
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional

class NewsModule:
    """
    IRIS news capabilities:
    - Fetch latest news via FreeNews API
    - Search news by topic
    - Summarize headlines
    - Alert on breaking news
    """

    def __init__(self):
        self.api_key = os.getenv("IRIS_FREENEWS_API_KEY", "")
        self.base_url = "https://api.freenews.dev/api/v1"

    def get_latest(self, category: str = "general", limit: int = 10) -> Dict:
        """Fetch latest news."""
        if not self.api_key:
            return {"success": False, "error": "FreeNews API key not configured in .env"}

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"category": category, "limit": limit}
            response = requests.get(f"{self.base_url}/news", headers=headers, params=params, timeout=15)
            data = response.json()

            if response.status_code == 200:
                articles = data.get("articles", [])
                formatted = []
                for article in articles:
                    formatted.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "published_at": article.get("publishedAt", "")
                    })
                return {"success": True, "articles": formatted, "count": len(formatted)}
            return {"success": False, "error": data.get("message", "API error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search(self, query: str, limit: int = 10) -> Dict:
        """Search news by query."""
        if not self.api_key:
            return {"success": False, "error": "FreeNews API key not configured"}

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"q": query, "limit": limit}
            response = requests.get(f"{self.base_url}/search", headers=headers, params=params, timeout=15)
            data = response.json()

            if response.status_code == 200:
                return {"success": True, "articles": data.get("articles", []), "query": query}
            return {"success": False, "error": data.get("message", "API error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_headlines_summary(self, category: str = "general") -> str:
        """Get a text summary of headlines for IRIS to read."""
        result = self.get_latest(category, limit=5)
        if not result.get("success"):
            return f"News unavailable: {result.get('error')}"

        lines = [f"Here are the latest {category} headlines:"]
        for i, article in enumerate(result["articles"], 1):
            lines.append(f"{i}. {article['title']} — {article['source']}")
        return "\n".join(lines)

# Singleton
news_module = NewsModule()
