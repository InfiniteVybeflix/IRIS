"""Research Engine Skill — Web search, URL fetching, academic search, image search."""

import re
import json
import urllib.request
import urllib.parse
import urllib.error
import logging
import base64
import io
from typing import Dict, Any, List, Optional
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ResearchEngineSkill(BaseSkill):
    """Web search with multi-query support, URL content extraction, academic paper search, and image search."""

    def __init__(self):
        super().__init__(
            name="research_engine",
            category="intelligence",
            capabilities=["web_search", "url_fetch", "image_search_text", "image_search_image", "academic_search"]
        )
        self._user_agent = "IRIS-OMNIS/1.0 (Research Engine)"
        self._cache: Dict[str, Any] = {}
        self._search_history: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if capability == "web_search":
            return self.search(params)
        elif capability == "url_fetch":
            return self.fetch(params)
        elif capability == "image_search_text":
            return self.search_by_text(params)
        elif capability == "image_search_image":
            return self.search_by_image(params)
        elif capability == "academic_search":
            return self.academic_search(params)
        return {"error": f"Unknown capability: {capability}"}

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        queries = params.get("query", params.get("queries", ""))
        if isinstance(queries, str):
            queries = [queries]
        all_results = []
        cache_key = "search:" + "|".join(queries)
        if cache_key in self._cache and not params.get("no_cache"):
            return self._cache[cache_key]
        for query in queries:
            try:
                results = self._search_single(query, params.get("max_results_per_query", 10))
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Search error for '{query}': {e}")
                all_results.append({"query": query, "error": str(e), "source": "error"})
        self._search_history.append({"queries": queries, "results": len(all_results), "timestamp": __import__('datetime').datetime.utcnow().isoformat()})
        deduped = self._deduplicate_results(all_results)
        result = {"queries": queries, "results_count": len(deduped), "results": deduped[:params.get("max_results", 20)]}
        self._cache[cache_key] = result
        return result

    def _search_single(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        encoded = urllib.parse.quote(query)
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
            links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"', html)
            for i in range(min(len(titles), len(snippets), max_results)):
                clean_title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                results.append({"title": clean_title, "snippet": clean_snippet[:300], "url": links[i] if i < len(links) else "", "source": "duckduckgo", "query": query})
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
        if not results:
            try:
                bing_url = f"https://www.bing.com/search?q={encoded}&count={max_results}"
                req = urllib.request.Request(bing_url, headers={"User-Agent": self._user_agent, "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                bing_results = re.findall(r'<li class="b_algo"[^>]*>.*?<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<p>(.*?)</p>', html, re.DOTALL)
                for url, title, snippet in bing_results[:max_results]:
                    results.append({"title": re.sub(r'<[^>]+>', '', title).strip(), "snippet": re.sub(r'<[^>]+>', '', snippet).strip()[:300], "url": url, "source": "bing", "query": query})
            except Exception as e2:
                logger.error(f"Bing fallback failed: {e2}")
        return results

    def fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        urls = params.get("url", params.get("urls", []))
        if isinstance(urls, str):
            urls = [urls]
        extract_type = params.get("extract", "full")
        results = []
        for url in urls:
            try:
                content = self._fetch_single(url, extract_type)
                results.append({"url": url, **content})
            except Exception as e:
                results.append({"url": url, "error": str(e)})
        return {"urls_processed": len(urls), "results": results}

    def _fetch_single(self, url: str, extract_type: str = "full") -> Dict[str, Any]:
        req = urllib.request.Request(url, headers={"User-Agent": self._user_agent, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            text = content.decode(charset, errors="replace")
        title_match = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
        title = re.sub(r'\s+', ' ', title_match.group(1).strip()) if title_match else ""
        result: Dict[str, Any] = {"title": title, "size_bytes": len(content), "status": "ok"}
        if extract_type in ("full", "text"):
            body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.IGNORECASE | re.DOTALL)
            if body_match:
                body_text = re.sub(r'<script[^>]*>.*?</script>', ' ', body_match.group(1), flags=re.DOTALL | re.IGNORECASE)
                body_text = re.sub(r'<style[^>]*>.*?</style>', ' ', body_text, flags=re.DOTALL | re.IGNORECASE)
                body_text = re.sub(r'<[^>]+>', ' ', body_text)
                body_text = re.sub(r'\s+', ' ', body_text).strip()
                result["text"] = body_text[:8000]
        if extract_type in ("full", "links"):
            result["links"] = list(set(re.findall(r'href="(https?://[^"]+)"', text)))[:30]
        if extract_type in ("full", "meta"):
            meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', text, re.IGNORECASE)
            result["meta_description"] = meta_desc.group(1) if meta_desc else ""
        return result

    def search_by_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "")
        provider = params.get("provider", "unsplash")
        max_results = params.get("max_results", 10)
        results = []
        try:
            encoded = urllib.parse.quote(query)
            if provider == "unsplash":
                url = f"https://unsplash.com/s/photos/{encoded}"
                req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                images = re.findall(r'<img[^>]*src="(https://images\.unsplash\.com/[^"]+)"[^>]*>', html)
                for img_url in images[:max_results]:
                    results.append({"url": img_url, "source": "unsplash", "query": query})
            elif provider == "pexels":
                url = f"https://www.pexels.com/search/{encoded}/"
                req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                images = re.findall(r'src="(https://images\.pexels\.com/[^"]+)"', html)
                for img_url in images[:max_results]:
                    results.append({"url": img_url, "source": "pexels", "query": query})
        except Exception as e:
            logger.error(f"Image search failed: {e}")
        return {"success": True, "query": query, "provider": provider, "results_count": len(results), "images": results}

    def search_by_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_url = params.get("image_url", "")
        results = []
        try:
            encoded = urllib.parse.quote(image_url)
            google_url = f"https://www.google.com/searchbyimage?image_url={encoded}"
            req = urllib.request.Request(google_url, headers={"User-Agent": self._user_agent})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            matches = re.findall(r'<a href="(https?://[^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
            for url, title in matches[:10]:
                results.append({"url": url, "title": re.sub(r'<[^>]+>', '', title).strip(), "source": "google_reverse_image"})
        except Exception as e:
            logger.error(f"Reverse image search failed: {e}")
        return {"success": True, "image_url": image_url, "results_count": len(results), "results": results}

    def academic_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "")
        source = params.get("source", "arxiv")
        max_results = params.get("max_results", 10)
        if source == "arxiv":
            return self._arxiv_search(query, max_results)
        elif source == "crossref":
            return self._crossref_search(query, max_results)
        return {"error": f"Unknown academic source: {source}", "query": query}

    def _arxiv_search(self, query: str, max_results: int) -> Dict[str, Any]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            import xml.etree.ElementTree as ET
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            root = ET.fromstring(raw.encode("utf-8"))
            papers = []
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", default="", namespaces=ns).strip()
                summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
                authors = [a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)]
                categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]
                pdf_link = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_link = link.get("href", "")
                published = entry.findtext("atom:published", default="", namespaces=ns)
                updated = entry.findtext("atom:updated", default="", namespaces=ns)
                papers.append({"title": title, "summary": summary[:800], "authors": authors, "categories": categories, "pdf_link": pdf_link, "published": published, "updated": updated, "source": "arxiv"})
            return {"success": True, "query": query, "source": "arxiv", "papers_found": len(papers), "papers": papers}
        except Exception as e:
            return {"success": False, "error": str(e), "query": query, "papers": []}

    def _crossref_search(self, query: str, max_results: int) -> Dict[str, Any]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.crossref.org/works?query={encoded}&rows={max_results}&sort=relevance&order=desc"
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            papers = []
            for item in data.get("message", {}).get("items", []):
                papers.append({"title": item.get("title", [""])[0], "authors": [f"{a.get('given', '')} {a.get('family', '')}" for a in item.get("author", [])[:5]], "doi": item.get("DOI", ""), "published": str(item.get("published-print", {}).get("date-parts", [[""]])[0][0]), "publisher": item.get("publisher", ""), "type": item.get("type", ""), "source": "crossref"})
            return {"success": True, "query": query, "source": "crossref", "papers_found": len(papers), "papers": papers}
        except Exception as e:
            return {"success": False, "error": str(e), "query": query, "papers": []}

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for r in results:
            key = r.get("url", "") or r.get("title", "") or str(hash(str(r)))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
