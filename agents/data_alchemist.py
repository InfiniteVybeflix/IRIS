#!/usr/bin/env python3
"""
data_alchemist.py — CRUCIBLE
Data Intelligence Agent for IRIS v1.0
Handles scraping, entity extraction, data cleaning, API integration,
content change detection, price tracking, and search aggregation.
"""

import threading
import hashlib
import json
import logging
import re
import time
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from html.parser import HTMLParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CRUCIBLE")


@dataclass
class ScrapedItem:
    """Container for a scraped data item."""
    url: str
    title: str = ""
    content: str = ""
    raw_html: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class PricePoint:
    """Single price observation."""
    source: str
    price: float
    currency: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MLStripper(HTMLParser):
    """Simple HTML-to-text converter."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: List[str] = []
    def handle_data(self, d: str) -> None:
        self.fed.append(d)
    def get_data(self) -> str:
        return "".join(self.fed)


def strip_tags(html: str) -> str:
    s = MLStripper()
    try:
        s.feed(html)
        return s.get_data()
    except Exception:
        return re.sub(r"<[^>]+>", "", html)


class DataAlchemist:
    CODENAME = "CRUCIBLE"

    # Regex patterns for entity extraction
    _EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    _PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}")
    _URL_RE = re.compile(r"https?://[^\s<>"{}|\^`[\]]+")
    _IP_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
    _SSN_RE = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")
    _CC_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        self._change_baseline: Dict[str, str] = {}  # url -> hash
        self._price_history: Dict[str, List[PricePoint]] = {}  # url/item -> prices
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("CRUCIBLE started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("CRUCIBLE stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "baselines_tracked": len(self._change_baseline),
                "price_tracks": len(self._price_history),
                "timestamp": datetime.utcnow().isoformat(),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Core capabilities
    # ------------------------------------------------------------------
    def scrape_static(self, url: str, timeout: int = 30) -> ScrapedItem:
        """Fetch and parse a static HTML page using urllib (no JS)."""
        if not self._running:
            raise RuntimeError("Agent not running")
        req = urllib.request.Request(url, headers=self._headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            self._report_to_commander(f"HTTPError {e.code} for {url}", level="error")
            raise
        except Exception as e:
            self._report_to_commander(f"Fetch failed for {url}: {e}", level="error")
            raise

        title_match = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        content = strip_tags(raw)
        item = ScrapedItem(url=url, title=title, content=content, raw_html=raw)
        item.entities = self.extract_entities(content)
        self._store_memory(f"scrape:{url}", asdict(item))
        self._report_to_commander(f"Scraped {url}", data={"title": title, "len": len(content)})
        return item

    def scrape_js_rendered(self, url: str, timeout: int = 45) -> ScrapedItem:
        """Fetch a JS-rendered page using Playwright via subprocess fallback."""
        if not self._running:
            raise RuntimeError("Agent not running")
        script = f"""
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{url}", wait_until="networkidle", timeout={timeout * 1000})
        html = await page.content()
        title = await page.title()
        print("---TITLE---")
        print(title)
        print("---HTML---")
        print(html)
        await browser.close()
asyncio.run(main())
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            tmp_path = f.name
        try:
            rc, out, err = self._execute_shell(f"python3 {tmp_path}", timeout=timeout + 15)
            if rc != 0:
                self._report_to_commander(f"Playwright failed for {url}: {err}", level="error")
                raise RuntimeError(f"Playwright error: {err}")
            parts = out.split("---HTML---")
            title = parts[0].replace("---TITLE---", "").strip()
            raw = parts[1].strip() if len(parts) > 1 else out
        finally:
            self._execute_shell(f"rm -f {tmp_path}")

        content = strip_tags(raw)
        item = ScrapedItem(url=url, title=title, content=content, raw_html=raw)
        item.entities = self.extract_entities(content)
        self._store_memory(f"scrape_js:{url}", asdict(item))
        self._report_to_commander(f"JS-rendered scrape complete: {url}")
        return item

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract emails, phones, URLs, IPs, SSNs, credit cards from text."""
        return {
            "emails": list(set(self._EMAIL_RE.findall(text))),
            "phones": list(set(self._PHONE_RE.findall(text))),
            "urls": list(set(self._URL_RE.findall(text))),
            "ips": list(set(self._IP_RE.findall(text))),
            "ssns": list(set(self._SSN_RE.findall(text))),
            "credit_cards": list(set(self._CC_RE.findall(text))),
        }

    def clean_data(self, data: List[str], operations: Optional[List[str]] = None) -> List[str]:
        """Clean a list of strings: strip, lowercase, remove_html, normalize, regex_replace."""
        ops = operations or ["strip", "lowercase", "remove_html", "normalize"]
        cleaned: List[str] = []
        for s in data:
            val = s
            if "strip" in ops:
                val = val.strip()
            if "lowercase" in ops:
                val = val.lower()
            if "remove_html" in ops:
                val = strip_tags(val)
            if "normalize" in ops:
                val = re.sub(r"\s+", " ", val)
            if "regex_replace" in ops:
                val = re.sub(r"[^a-zA-Z0-9\s\-_.@]", "", val)
            cleaned.append(val)
        self._store_memory("clean_batch", {"input_count": len(data), "output_count": len(cleaned)})
        return cleaned

    def detect_change(self, url: str, content: str) -> Dict[str, Any]:
        """Compare content hash to baseline; return change status."""
        current_hash = hashlib.sha256(content.encode()).hexdigest()
        with self._lock:
            baseline = self._change_baseline.get(url)
            changed = baseline is not None and baseline != current_hash
            self._change_baseline[url] = current_hash
        result = {
            "url": url,
            "changed": changed,
            "previous_hash": baseline,
            "current_hash": current_hash,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._store_memory(f"change:{url}", result)
        return result

    def track_price(self, item_id: str, source: str, price: float, currency: str = "USD") -> Dict[str, Any]:
        """Track price history for an item."""
        point = PricePoint(source=source, price=price, currency=currency)
        with self._lock:
            hist = self._price_history.setdefault(item_id, [])
            hist.append(point)
            if len(hist) > 1000:
                hist.pop(0)
            prices = [p.price for p in hist]
            avg = sum(prices) / len(prices)
            min_p = min(prices)
            max_p = max(prices)
        result = {
            "item_id": item_id,
            "current": asdict(point),
            "history_count": len(hist),
            "average": round(avg, 2),
            "min": min_p,
            "max": max_p,
        }
        self._store_memory(f"price:{item_id}", result)
        return result

    def search_aggregate(self, queries: List[str], engines: Optional[List[str]] = None) -> Dict[str, Any]:
        """Aggregate search results from multiple engines (DuckDuckGo HTML scraping fallback)."""
        engines = engines or ["duckduckgo"]
        aggregated: List[Dict[str, Any]] = []
        for q in queries:
            for engine in engines:
                if engine == "duckduckgo":
                    try:
                        encoded = urllib.parse.quote_plus(q)
                        url = f"https://html.duckduckgo.com/html/?q={encoded}"
                        item = self.scrape_static(url, timeout=20)
                        links = re.findall(r"<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>", item.raw_html)
                        for href, title in links[:10]:
                            aggregated.append({"query": q, "engine": engine, "title": title, "url": href})
                    except Exception as e:
                        self._report_to_commander(f"Search failed for '{q}': {e}", level="warning")
        self._store_memory("search_aggregate", {"queries": queries, "results": len(aggregated)})
        return {"queries": queries, "engines": engines, "results": aggregated, "count": len(aggregated)}

    def api_integrate(self, endpoint: str, method: str = "GET", payload: Optional[Dict] = None,
                      headers: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        """Generic REST API integration with real HTTP."""
        h = {**self._headers, **(headers or {})}
        data = json.dumps(payload).encode() if payload else None
        if data:
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(endpoint, data=data, headers=h, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = body
                result = {
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": parsed,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self._store_memory(f"api:{endpoint}", result)
                return result
        except urllib.error.HTTPError as e:
            return {"status": e.code, "error": e.reason, "body": e.read().decode(errors="replace")}
        except Exception as e:
            return {"status": -1, "error": str(e)}

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_scrape_static(self) -> bool:
        try:
            item = self.scrape_static("https://example.com")
            return item.url == "https://example.com"
        except Exception:
            return False

    def test_extract_entities(self) -> bool:
        text = "Contact us at admin@example.com or call 555-123-4567. Visit https://aevibron.com"
        ents = self.extract_entities(text)
        return "admin@example.com" in ents.get("emails", [])

    def test_clean_data(self) -> bool:
        out = self.clean_data(["  <b>Hello</b> World  ", "TEST"])
        return out[0] == "hello world" and out[1] == "test"

    def test_detect_change(self) -> bool:
        r1 = self.detect_change("https://test.local", "contentA")
        r2 = self.detect_change("https://test.local", "contentB")
        return r1["changed"] is False and r2["changed"] is True

    def test_track_price(self) -> bool:
        r = self.track_price("item_1", "amazon", 99.99)
        return r["current"]["price"] == 99.99

    def test_api_integrate(self) -> bool:
        r = self.api_integrate("https://httpbin.org/get")
        return r.get("status") == 200


if __name__ == "__main__":
    agent = DataAlchemist()
    agent.start()
    print(agent.health())
    agent.stop()
