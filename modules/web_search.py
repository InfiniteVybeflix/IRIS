"""IRIS v1 Web Search — Real-time Search with Source Attribution
Uses DuckDuckGo + optional web scraping for full content extraction.
"""
import requests
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from config import config

logger = logging.getLogger(__name__)

class WebSearchEngine:
    """Production-grade web search with source tracking and content extraction."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "IRIS-Agent/9.0 (Aevibron Partner; Jarvis Edition)"
        })
        self.search_history = []
        self.max_history = 50

    def search(self, query: str, max_results: int = 5, fetch_content: bool = True, 
               source_filter: str = None, time_filter: str = None) -> Dict:
        """
        Search the web with full content extraction and source attribution.

        Args:
            query: Search query
            max_results: Number of results (1-10)
            fetch_content: Whether to fetch full page content
            source_filter: Filter by domain (e.g., "github.com", "stackoverflow.com")
            time_filter: "day", "week", "month", "year"
        """
        try:
            with DDGS() as ddgs:
                # Time-based filtering
                time_param = None
                if time_filter == "day":
                    time_param = "d"
                elif time_filter == "week":
                    time_param = "w"
                elif time_filter == "month":
                    time_param = "m"
                elif time_filter == "year":
                    time_param = "y"

                results = list(ddgs.text(query, max_results=min(max_results, 10), timelimit=time_param))

                # Filter by source if specified
                if source_filter:
                    results = [r for r in results if source_filter in r.get('href', '')]

                enriched_results = []
                for result in results:
                    item = {
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                        "source": self._extract_domain(result.get("href", "")),
                        "timestamp": datetime.now().isoformat(),
                        "fetched_content": None,
                        "content_length": 0
                    }

                    if fetch_content and item["url"]:
                        content = self._fetch_page_content(item["url"])
                        if content:
                            item["fetched_content"] = content[:5000]  # Limit content
                            item["content_length"] = len(content)

                    enriched_results.append(item)

                # Log search
                self._log_search(query, len(enriched_results))

                return {
                    "success": True,
                    "query": query,
                    "results_count": len(enriched_results),
                    "results": enriched_results,
                    "sources": list(set(r["source"] for r in enriched_results)),
                    "time_filter": time_filter
                }
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {"success": False, "error": str(e), "query": query}

    def search_news(self, query: str, max_results: int = 5) -> Dict:
        """Search specifically for news articles."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=min(max_results, 10)))
                return {
                    "success": True,
                    "query": query,
                    "results": [{
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", ""),
                        "date": r.get("date", ""),
                        "body": r.get("body", "")
                    } for r in results]
                }
        except Exception as e:
            logger.error(f"News search failed: {e}")
            return {"success": False, "error": str(e)}

    def search_code(self, query: str, language: str = None, max_results: int = 5) -> Dict:
        """Search for code examples and documentation."""
        code_query = f"{query} code example"
        if language:
            code_query += f" {language}"

        result = self.search(code_query, max_results=max_results, source_filter="github.com" if not language else None)
        result["search_type"] = "code"
        result["language"] = language
        return result

    def _fetch_page_content(self, url: str, timeout: int = 10) -> Optional[str]:
        """Fetch and clean page content."""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script/style/nav/footer tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return "unknown"

    def _log_search(self, query: str, results_count: int):
        """Log search to history."""
        self.search_history.append({
            "query": query,
            "results_count": results_count,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.search_history) > self.max_history:
            self.search_history.pop(0)

    def get_search_history(self, limit: int = 10) -> List[Dict]:
        """Get recent search history."""
        return self.search_history[-limit:]

    def summarize_results(self, search_result: Dict, max_length: int = 500) -> str:
        """Generate a summary of search results for the AI."""
        if not search_result.get("success"):
            return f"Search failed: {search_result.get('error', 'Unknown error')}"

        results = search_result.get("results", [])
        if not results:
            return "No results found."

        summary_parts = [f"Found {len(results)} results for '{search_result['query']}':\n"]

        for i, result in enumerate(results[:3], 1):
            summary_parts.append(f"{i}. {result['title']} ({result['source']})")
            summary_parts.append(f"   {result['snippet'][:200]}...")
            if result.get('fetched_content'):
                summary_parts.append(f"   Content preview: {result['fetched_content'][:300]}...")
            summary_parts.append("")

        return "\n".join(summary_parts)


# Singleton
web_search = WebSearchEngine()
