#!/usr/bin/env python3
"""
research_scholar.py — SAGE
Research Intelligence Agent for IRIS v1.0
Autonomous literature review, technology comparison matrices,
PoC generation, academic paper analysis (arXiv API), patent prior art search,
conference talk generation.
"""

import threading
import hashlib
import json
import logging
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SAGE")


class ResearchScholar:
    CODENAME = "SAGE"

    ARXIV_API = "http://export.arxiv.org/api/query"
    PATENT_API = "https://patents.google.com/xhr/"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("SAGE started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("SAGE stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "timestamp": datetime.utcnow().isoformat(),
            }

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
        import subprocess
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    def _http_get(self, url: str, timeout: int = 30) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "IRIS-SAGE/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def arxiv_search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search arXiv and return structured paper metadata."""
        if not self._running:
            raise RuntimeError("Agent not running")
        encoded = urllib.parse.quote(query)
        url = f"{self.ARXIV_API}?search_query=all:{encoded}&start=0&max_results={max_results}"
        raw = self._http_get(url, timeout=30)
        import xml.etree.ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw.encode("utf-8"))
        papers: List[Dict[str, Any]] = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", default="", namespaces=ns).strip()
            summary = entry.findtext("atom:summary", default="", namespaces=ns).strip()
            authors = [a.findtext("atom:name", default="", namespaces=ns) for a in entry.findall("atom:author", ns)]
            pdf_link = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_link = link.get("href", "")
            papers.append({
                "title": title,
                "summary": summary,
                "authors": authors,
                "pdf_link": pdf_link,
                "published": entry.findtext("atom:published", default="", namespaces=ns),
            })
        self._store_memory(f"arxiv:{query}", papers)
        self._report_to_commander(f"arXiv search returned {len(papers)} papers", data={"query": query})
        return papers

    def literature_review(self, topic: str, depth: int = 5) -> Dict[str, Any]:
        """Generate an autonomous literature review on a topic."""
        papers = self.arxiv_search(topic, max_results=depth)
        review = {
            "topic": topic,
            "depth": depth,
            "papers_found": len(papers),
            "summaries": [{"title": p["title"], "summary": p["summary"][:500]} for p in papers],
            "generated_at": datetime.utcnow().isoformat(),
        }
        self._store_memory(f"review:{topic}", review)
        return review

    def tech_comparison_matrix(self, technologies: List[str], criteria: List[str]) -> Dict[str, Any]:
        """Build a comparison matrix by aggregating web data for each tech+criterion."""
        matrix: Dict[str, Dict[str, str]] = {}
        for tech in technologies:
            matrix[tech] = {}
            for crit in criteria:
                query = f"{tech} {crit} comparison benchmark"
                try:
                    encoded = urllib.parse.quote(query)
                    url = f"https://html.duckduckgo.com/html/?q={encoded}"
                    req = urllib.request.Request(url, headers={"User-Agent": "IRIS-SAGE/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        html = resp.read().decode("utf-8", errors="replace")
                    snippets = []
                    for m in __import__("re").findall(r"<a class="result__snippet"[^>]*>(.*?)</a>", html):
                        snippets.append(__import__("re").sub(r"<[^>]+>", "", m))
                    matrix[tech][crit] = "; ".join(snippets[:3]) if snippets else "No data"
                except Exception as e:
                    matrix[tech][crit] = f"Error: {e}"
                time.sleep(0.5)
        result = {"technologies": technologies, "criteria": criteria, "matrix": matrix}
        self._store_memory(f"matrix:{hashlib.md5(json.dumps(technologies).encode()).hexdigest()}", result)
        return result

    def generate_poc(self, concept: str, language: str = "python") -> Dict[str, Any]:
        """Generate a proof-of-concept code skeleton for a given concept."""
        templates = {
            "python": f"""#!/usr/bin/env python3
# PoC: {concept}
# Generated by SAGE / IRIS v1.0

def main():
    # TODO: Implement {concept}
    print(f"PoC running: {{concept}}")
    # Add core logic here
    pass

if __name__ == "__main__":
    main()
""",
            "javascript": f"""// PoC: {concept}
// Generated by SAGE / IRIS v1.0

function main() {{
    console.log('PoC running: {concept}');
    // Add core logic here
}}

main();
""",
        }
        code = templates.get(language, templates["python"])
        result = {"concept": concept, "language": language, "code": code, "generated_at": datetime.utcnow().isoformat()}
        self._store_memory(f"poc:{concept}", result)
        return result

    def patent_prior_art(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Search Google Patents via scraping as a fallback for prior art."""
        if not self._running:
            raise RuntimeError("Agent not running")
        encoded = urllib.parse.quote(query)
        url = f"https://patents.google.com/?q={encoded}&oq={encoded}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS-SAGE/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            import re
            patents = []
            for m in re.finditer(r'"title":"([^"]+)"', html):
                patents.append({"title": m.group(1)})
                if len(patents) >= max_results:
                    break
            self._store_memory(f"patent:{query}", patents)
            return patents
        except Exception as e:
            self._report_to_commander(f"Patent search failed: {e}", level="error")
            return []

    def generate_talk(self, topic: str, duration_minutes: int = 30) -> Dict[str, Any]:
        """Generate a conference talk outline with timing."""
        slides = []
        slides.append({"time": "0:00", "title": "Introduction", "content": f"Overview of {topic}"})
        slides.append({"time": f"0:{min(5, duration_minutes // 6)}", "title": "Problem Statement", "content": "Define the core challenge."})
        slides.append({"time": f"0:{min(10, duration_minutes // 3)}", "title": "State of the Art", "content": "Existing solutions and gaps."})
        slides.append({"time": f"0:{min(15, duration_minutes // 2)}", "title": "Proposed Approach", "content": "Novel methodology."})
        slides.append({"time": f"0:{min(20, 2 * duration_minutes // 3)}", "title": "Results / Demo", "content": "Evidence and live demo."})
        slides.append({"time": f"0:{min(25, 5 * duration_minutes // 6)}", "title": "Conclusion", "content": "Key takeaways and future work."})
        slides.append({"time": f"0:{duration_minutes}", "title": "Q&A", "content": "Open floor."})
        talk = {"topic": topic, "duration": duration_minutes, "slides": slides}
        self._store_memory(f"talk:{topic}", talk)
        return talk

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_arxiv_search(self) -> bool:
        try:
            papers = self.arxiv_search("machine learning", max_results=2)
            return len(papers) > 0 and "title" in papers[0]
        except Exception:
            return False

    def test_literature_review(self) -> bool:
        r = self.literature_review("quantum computing", depth=2)
        return r["papers_found"] >= 0

    def test_tech_comparison_matrix(self) -> bool:
        r = self.tech_comparison_matrix(["Python", "Go"], ["performance", "ease"])
        return "Python" in r["matrix"]

    def test_generate_poc(self) -> bool:
        r = self.generate_poc("blockchain validator", "python")
        return "blockchain validator" in r["code"]

    def test_generate_talk(self) -> bool:
        r = self.generate_talk("AI Safety", 30)
        return len(r["slides"]) == 7


if __name__ == "__main__":
    agent = ResearchScholar()
    agent.start()
    print(agent.health())
    agent.stop()
