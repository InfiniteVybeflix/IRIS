"""Inbuilt Apps Skill — calendar, calculator, maps, file explorer.

These are IRIS's built-in mini-apps, callable as OMNIS capabilities:
  - calendar_create_event / calendar_list_events (JSON file-backed)
  - calculator_compute (safe math expression evaluator, no eval())
  - maps_geocode (OpenStreetMap Nominatim — no API key needed)
  - maps_search (OpenStreetMap Overpass API — no API key needed)
  - file_explorer_list (rich directory listing with mtime)
  - file_explorer_search (recursive file search by name pattern)
"""

from __future__ import annotations

import ast
import json
import logging
import operator
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills import BaseSkill

logger = logging.getLogger(__name__)


class InbuiltAppsSkill(BaseSkill):
    """Calendar, calculator, maps, file explorer mini-apps."""

    def __init__(self):
        super().__init__(
            name="inbuilt_apps",
            category="utilities",
            capabilities=[
                "calendar_create_event", "calendar_list_events",
                "calculator_compute",
                "maps_geocode", "maps_search",
                "file_explorer_list", "file_explorer_search",
            ],
        )
        # Calendar events persisted to a JSON file in IRIS's data dir
        self._calendar_file = os.path.join(
            os.environ.get("IRIS_DATA_DIR", os.path.join(PROJECT_ROOT, "data")),
            "calendar", "events.json",
        )
        os.makedirs(os.path.dirname(self._calendar_file), exist_ok=True)

    def init(self) -> bool:
        return True

    def shutdown(self) -> bool:
        return True

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if capability == "calendar_create_event":
                return self._calendar_create(params)
            elif capability == "calendar_list_events":
                return self._calendar_list(params)
            elif capability == "calculator_compute":
                return self._calculator(params)
            elif capability == "maps_geocode":
                return self._maps_geocode(params)
            elif capability == "maps_search":
                return self._maps_search(params)
            elif capability == "file_explorer_list":
                return self._file_list(params)
            elif capability == "file_explorer_search":
                return self._file_search(params)
            return {"success": False, "error": f"unknown capability: {capability}"}
        except Exception as e:
            logger.exception("InbuiltApps.execute failed for %s", capability)
            return {"success": False, "error": str(e), "capability": capability}

    # ─── Calendar ──────────────────────────────────────────────────
    def _load_events(self) -> list:
        try:
            with open(self._calendar_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_events(self, events: list) -> None:
        with open(self._calendar_file, "w") as f:
            json.dump(events, f, indent=2, default=str)

    def _calendar_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        title = params.get("title")
        start = params.get("start")  # ISO datetime string
        end = params.get("end")
        location = params.get("location", "")
        description = params.get("description", "")
        if not title or not start:
            return {"success": False, "error": "title and start required"}
        events = self._load_events()
        event = {
            "id": f"evt-{len(events)+1}-{int(datetime.utcnow().timestamp())}",
            "title": title,
            "start": start,
            "end": end,
            "location": location,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
        }
        events.append(event)
        self._save_events(events)
        return {"success": True, "event": event}

    def _calendar_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        events = self._load_events()
        # Filter upcoming events (start time >= now)
        now = datetime.utcnow().isoformat()
        upcoming = [e for e in events if e.get("start", "") >= now]
        upcoming.sort(key=lambda e: e.get("start", ""))
        limit = int(params.get("limit", 50))
        return {"success": True, "count": len(upcoming[:limit]), "events": upcoming[:limit]}

    # ─── Calculator (safe — no eval()) ────────────────────────────
    # AST-based evaluator — only allows +, -, *, /, **, %, (), numbers,
    # and a small set of math functions (sqrt, sin, cos, etc.)
    _SAFE_BINOPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _SAFE_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
    _SAFE_FUNCS = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "sqrt": __import__("math").sqrt, "sin": __import__("math").sin,
        "cos": __import__("math").cos, "tan": __import__("math").tan,
        "log": __import__("math").log, "log10": __import__("math").log10,
        "pi": __import__("math").pi, "e": __import__("math").e,
    }

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"constant {node.value!r} not allowed")
        if isinstance(node, ast.BinOp):
            op = self._SAFE_BINOPS.get(type(node.op))
            if not op:
                raise ValueError(f"binop {type(node.op).__name__} not allowed")
            return op(self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            op = self._SAFE_UNARYOPS.get(type(node.op))
            if not op:
                raise ValueError(f"unaryop {type(node.op).__name__} not allowed")
            return op(self._eval_node(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in self._SAFE_FUNCS:
                raise ValueError("function call not allowed")
            func = self._SAFE_FUNCS[node.func.id]
            args = [self._eval_node(a) for a in node.args]
            return func(*args)
        if isinstance(node, ast.Name):
            if node.id in self._SAFE_FUNCS:
                return self._SAFE_FUNCS[node.id]
            raise ValueError(f"name {node.id!r} not allowed")
        raise ValueError(f"node type {type(node).__name__} not allowed")

    def _calculator(self, params: Dict[str, Any]) -> Dict[str, Any]:
        expression = params.get("expression") or params.get("expr")
        if not expression:
            return {"success": False, "error": "expression required"}
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval_node(tree.body)
            return {"success": True, "expression": expression, "result": result}
        except (ValueError, SyntaxError, TypeError) as e:
            return {"success": False, "error": f"could not evaluate: {e}", "expression": expression}

    # ─── Maps (OpenStreetMap — no API key) ────────────────────────
    def _maps_geocode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        address = params.get("address") or params.get("q")
        if not address:
            return {"success": False, "error": "address required"}
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "IRIS/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                results = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "address": address,
                "count": len(results),
                "results": [
                    {"lat": float(r["lat"]), "lon": float(r["lon"]),
                     "display_name": r["display_name"], "type": r.get("type")}
                    for r in results
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _maps_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Use Overpass API to find places near a coordinate
        query_text = params.get("query") or params.get("q")
        lat = params.get("lat")
        lon = params.get("lon")
        radius = int(params.get("radius_m", 1000))
        limit = int(params.get("limit", 20))
        if not query_text:
            return {"success": False, "error": "query required (e.g. 'restaurant')"}
        if lat is None or lon is None:
            # Geocode the address first
            address = params.get("address")
            if not address:
                return {"success": False, "error": "either lat+lon or address required"}
            geo = self._maps_geocode({"address": address})
            if not geo.get("success") or not geo.get("results"):
                return geo
            lat = geo["results"][0]["lat"]
            lon = geo["results"][0]["lon"]
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["name"~"{query_text}",i](around:{radius},{lat},{lon});
          way["name"~"{query_text}",i](around:{radius},{lat},{lon});
        );
        out center {limit};
        """
        url = "https://overpass-api.de/api/interpreter"
        data = urllib.parse.urlencode({"data": overpass_query}).encode()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": "IRIS/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            places = []
            for el in data.get("elements", [])[:limit]:
                tags = el.get("tags", {})
                if el.get("type") == "node":
                    places.append({
                        "name": tags.get("name", ""),
                        "lat": el.get("lat"), "lon": el.get("lon"),
                        "type": tags.get("amenity", tags.get("shop", "")),
                    })
                elif el.get("type") == "way" and "center" in el:
                    places.append({
                        "name": tags.get("name", ""),
                        "lat": el["center"].get("lat"), "lon": el["center"].get("lon"),
                        "type": tags.get("amenity", tags.get("shop", "")),
                    })
            return {"success": True, "query": query_text, "center": {"lat": lat, "lon": lon},
                    "count": len(places), "places": places}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── File explorer ────────────────────────────────────────────
    def _file_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", ".")
        try:
            entries = []
            for entry in sorted(os.listdir(path)):
                full = os.path.join(path, entry)
                stat = os.stat(full)
                entries.append({
                    "name": entry,
                    "type": "dir" if os.path.isdir(full) else "file",
                    "size": stat.st_size if os.path.isfile(full) else None,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "mode": oct(stat.st_mode)[-3:],
                })
            return {"success": True, "path": os.path.abspath(path), "entries": entries, "count": len(entries)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _file_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", ".")
        pattern = params.get("pattern") or params.get("name")
        limit = int(params.get("limit", 100))
        if not pattern:
            return {"success": False, "error": "pattern required (e.g. '*.py')"}
        # Convert glob to regex
        regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        regex = re.compile(regex_pattern, re.IGNORECASE)
        matches = []
        try:
            for root, dirs, files in os.walk(path):
                for name in files + dirs:
                    if regex.match(name):
                        full = os.path.join(root, name)
                        matches.append({
                            "name": name,
                            "path": full,
                            "type": "dir" if os.path.isdir(full) else "file",
                        })
                        if len(matches) >= limit:
                            return {"success": True, "pattern": pattern, "count": len(matches), "matches": matches}
            return {"success": True, "pattern": pattern, "count": len(matches), "matches": matches}
        except Exception as e:
            return {"success": False, "error": str(e)}
