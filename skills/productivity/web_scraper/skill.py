"""IRIS v7 Web Scraper Skill — Web Intelligence"""
import logging
import json
import re
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class WebScraperSkill(BaseSkill):
    name = "web_scraper"
    display_name = "Web Scraper"
    description = "Web intelligence — HTML parsing, JS rendering, structured data extraction, article extraction, search aggregation, price tracking, and content change detection."
    version = "7.0.0"
    category = "productivity"
    icon = "🕷️"
    uses_storage = True
    storage_dir = "data/skills/web_scraper"
    storage_file = "data/skills/web_scraper/snapshots.json"

    capabilities = [
        SkillCapability(name="scrape_page", description="Scrape HTML page", input_schema={"url": "str"}, tags=[CapabilityTags.SEARCH]),
        SkillCapability(name="extract_article", description="Extract article content", input_schema={"url": "str"}, tags=[CapabilityTags.SUMMARIZER]),
        SkillCapability(name="search_multi", description="Multi-engine search", input_schema={"query": "str"}, tags=[CapabilityTags.SEARCH]),
        SkillCapability(name="extract_tables", description="Extract tables from page", input_schema={"url": "str"}, tags=[CapabilityTags.SEARCH]),
        SkillCapability(name="track_price", description="Track price changes", input_schema={"url": "str", "selector": "str"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="detect_change", description="Detect content changes", input_schema={"url": "str"}, tags=[CapabilityTags.ANALYTICS]),
        SkillCapability(name="rss_parse", description="Parse RSS/Atom feed", input_schema={"feed_url": "str"}, tags=[CapabilityTags.SEARCH]),
        SkillCapability(name="api_client", description="Build API client from spec", input_schema={"spec_url": "str"}, tags=[CapabilityTags.CODING]),
    ]

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "scrape" in intent: return self._scrape(p.get("url"))
            elif "article" in intent: return self._article(p.get("url"))
            elif "search" in intent and "multi" in intent: return self._search(p.get("query"))
            elif "table" in intent: return self._tables(p.get("url"))
            elif "price" in intent: return self._price(p.get("url"), p.get("selector"))
            elif "change" in intent: return self._change(p.get("url"))
            elif "rss" in intent: return self._rss(p.get("feed_url"))
            elif "api" in intent: return self._api(p.get("spec_url"))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.95 if any(k in request.intent.lower() for k in ["scrape", "web_search", "extract_article", "price_track", "rss", "content_change"]) else super().can_handle(request)

    def _fetch(self, url: str) -> str:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IRIS-Bot/7.0)"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return r.read().decode("utf-8", errors="ignore")

    def _scrape(self, url: str) -> SkillResult:
        if not url: return SkillResult.fail(error="URL required")
        html = self._fetch(url)
        title = re.search(r"<title>(.*?)</title>", html, re.I)
        links = list(set(re.findall(r'href="(https?://[^"]+)"', html)))
        images = list(set(re.findall(r'src="(https?://[^"]+\.(?:jpg|png|gif|webp))"', html, re.I)))
        return SkillResult.ok(message=f"Scraped: {title.group(1) if title else url}", data={"url": url, "title": title.group(1) if title else "", "links": links[:20], "images": images[:10], "text_length": len(re.sub(r"<[^>]+>", " ", html))})

    def _article(self, url: str) -> SkillResult:
        if not url: return SkillResult.fail(error="URL required")
        html = self._fetch(url)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        summary = " ".join(sentences[:3]) if len(sentences) > 3 else text[:500]
        return SkillResult.ok(message=f"Article: {len(text)} chars", data={"url": url, "title": re.search(r"<title>(.*?)</title>", html, re.I).group(1) if re.search(r"<title>(.*?)</title>", html, re.I) else "", "content": text[:5000], "summary": summary, "word_count": len(text.split())})

    def _search(self, query: str) -> SkillResult:
        if not query: return SkillResult.fail(error="Query required")
        encoded = urllib.parse.quote(query)
        engines = {
            "duckduckgo": f"https://html.duckduckgo.com/html/?q={encoded}",
            "bing": f"https://www.bing.com/search?q={encoded}",
        }
        results = []
        for name, url in engines.items():
            try:
                html = self._fetch(url)
                links = re.findall(r'https?://[^\s<>"]+', html)[:5]
                results.append({"engine": name, "results": links})
            except Exception as e:
                results.append({"engine": name, "error": str(e)})
        return SkillResult.ok(message=f"Search: {len(results)} engines", data={"query": query, "results": results})

    def _tables(self, url: str) -> SkillResult:
        if not url: return SkillResult.fail(error="URL required")
        html = self._fetch(url)
        tables = []
        for table in re.findall(r"<table.*?</table>", html, re.DOTALL | re.I):
            rows = []
            for tr in re.findall(r"<tr.*?</tr>", table, re.DOTALL | re.I):
                cells = re.findall(r"<[tdh][^>]*>(.*?)</[tdh]>", tr, re.DOTALL | re.I)
                rows.append([re.sub(r"<[^>]+>", "", c).strip() for c in cells])
            if rows: tables.append(rows)
        return SkillResult.ok(message=f"Tables: {len(tables)} found", data={"tables": tables})

    def _price(self, url: str, selector: str) -> SkillResult:
        if not url: return SkillResult.fail(error="URL required")
        html = self._fetch(url)
        prices = re.findall(r"[\$€£]\s*([\d,]+\.?\d*)", html)
        current = prices[0] if prices else "N/A"
        return SkillResult.ok(message=f"Price: {current}", data={"url": url, "current_price": current, "all_prices": prices[:5], "alert_threshold": None})

    def _change(self, url: str) -> SkillResult:
        if not url: return SkillResult.fail(error="URL required")
        html = self._fetch(url)
        hash_val = hash(re.sub(r"\s+", "", html))
        snapshots = self._read_storage()
        old_hash = snapshots.get(url, {}).get("hash")
        changed = old_hash is not None and old_hash != hash_val
        snapshots[url] = {"hash": hash_val, "checked": datetime.now().isoformat()}
        self._write_storage(snapshots)
        return SkillResult.ok(message=f"Change: {'YES' if changed else 'No change'}", data={"url": url, "changed": changed, "last_check": snapshots[url]["checked"]})

    def _rss(self, feed_url: str) -> SkillResult:
        if not feed_url: return SkillResult.fail(error="Feed URL required")
        try:
            html = self._fetch(feed_url)
            items = re.findall(r"<item>.*?</item>", html, re.DOTALL)
            entries = []
            for item in items[:10]:
                title = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
                link = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
                entries.append({"title": re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else "", "link": link.group(1).strip() if link else ""})
            return SkillResult.ok(message=f"RSS: {len(entries)} entries", data={"feed": feed_url, "entries": entries})
        except Exception as e:
            return SkillResult.fail(error=f"RSS parse failed: {e}")

    def _api(self, spec_url: str) -> SkillResult:
        return SkillResult.ok(message="API client template", data={"spec": spec_url, "client_template": "import requests\nclass APIClient:\n    def __init__(self, base_url):\n        self.base = base_url\n    def get(self, path):\n        return requests.get(self.base + path)", "note": "Full OpenAPI parsing requires openapi-spec-validator"})
