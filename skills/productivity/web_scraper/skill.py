"""Web Scraper Skill — Structured data extraction and monitoring."""

import re
import hashlib
import urllib.request
import urllib.parse
import logging
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class WebScraperSkill(BaseSkill):
    """Structured data extraction, crawling, and change monitoring."""

    def __init__(self):
        super().__init__(name="web_scraper", category="productivity", capabilities=["web_scraper"])
        self._user_agent = "IRIS-OMNIS/1.0 (Web Scraper)"
        self._snapshots: Dict[str, str] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "scrape")
        if method == "scrape":
            return self.scrape(params)
        elif method == "crawl":
            return self.crawl(params)
        elif method == "extract_table":
            return self.extract_table(params)
        elif method == "monitor_changes":
            return self.monitor_changes(params)
        return {"error": f"Unknown method: {method}"}

    def scrape(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url", "")
        selector = params.get("selector", "")
        extract = params.get("extract", "text")
        if not url:
            return {"success": False, "error": "No URL provided"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent, "Accept": "text/html", "Accept-Language": "en-US"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            result: Dict[str, Any] = {"url": url, "success": True}
            if extract in ("text", "full"):
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
                if body_match:
                    text = re.sub(r'<script[^>]*>.*?</script>', ' ', body_match.group(1), flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.DOTALL)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    result["text"] = text[:10000]
            if extract in ("links", "full"):
                result["links"] = list(set(re.findall(r'href="(https?://[^"]+)"', html)))[:50]
                result["internal_links"] = list(set(re.findall(r'href="(/[^"]+)"', html)))[:50]
            if extract in ("images", "full"):
                result["images"] = list(set(re.findall(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"', html, re.IGNORECASE)))[:30]
            if extract in ("meta", "full"):
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                result["title"] = re.sub(r'\s+', ' ', title_match.group(1).strip()) if title_match else ""
                desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
                result["meta_description"] = desc_match.group(1) if desc_match else ""
                og_matches = re.findall(r'<meta[^>]*property=["\']og:([^"\']+)["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
                result["open_graph"] = {k: v for k, v in og_matches}
            result["size_bytes"] = len(html)
            return result
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}

    def crawl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        urls = params.get("urls", [])
        max_depth = params.get("max_depth", 1)
        max_pages = params.get("max_pages", 10)
        if isinstance(urls, str):
            urls = [urls]
        results = []
        visited = set()
        to_visit = [(url, 0) for url in urls]
        while to_visit and len(visited) < max_pages:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            result = self.scrape({"url": url, "extract": "full"})
            results.append(result)
            if result.get("success") and depth < max_depth:
                for link in result.get("links", [])[:5]:
                    if link not in visited:
                        to_visit.append((link, depth + 1))
        return {"success": True, "pages_crawled": len(results), "results": results}

    def extract_table(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url", "")
        table_index = params.get("table_index", 0)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
            if table_index >= len(tables):
                return {"success": False, "error": f"Table index {table_index} out of range ({len(tables)} tables found)"}
            table_html = tables[table_index]
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.IGNORECASE | re.DOTALL)
            parsed_rows = []
            for row in rows:
                cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.IGNORECASE | re.DOTALL)
                parsed_rows.append([re.sub(r'<[^>]+>', '', c).strip() for c in cells])
            return {"success": True, "url": url, "table_index": table_index, "rows": len(parsed_rows), "data": parsed_rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def monitor_changes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url", "")
        if not url:
            return {"success": False, "error": "No URL provided"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            current_hash = hashlib.sha256(content.encode()).hexdigest()
            previous_hash = self._snapshots.get(url)
            changed = previous_hash is not None and previous_hash != current_hash
            self._snapshots[url] = current_hash
            return {"success": True, "url": url, "changed": changed, "first_check": previous_hash is None, "hash": current_hash[:16]}
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}
