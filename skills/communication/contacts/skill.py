"""Contacts Skill — Contact management, search, groups."""
import logging
from typing import Dict, Any, List
from skills import BaseSkill
logger = logging.getLogger(__name__)

class ContactsSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="contacts", category="communication", capabilities=["contacts"])
        self._contacts: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "add")
        if method == "add": return self.add(params)
        elif method == "search": return self.search(params)
        elif method == "get": return self.get(params)
        elif method == "delete": return self.delete(params)
        elif method == "list": return self.list_all(params)
        return {"error": f"Unknown method: {method}"}

    def add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cid = params.get("id", params.get("email", ""))
        self._contacts[cid] = {"id": cid, "name": params.get("name", ""), "email": params.get("email", ""), "phone": params.get("phone", ""), "company": params.get("company", ""), "tags": params.get("tags", [])}
        return {"success": True, "contact": self._contacts[cid]}

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "").lower()
        results = [c for c in self._contacts.values() if query in c["name"].lower() or query in c.get("email", "").lower() or query in c.get("company", "").lower()]
        return {"success": True, "results": results, "count": len(results)}

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cid = params.get("contact_id", "")
        return {"success": True, "contact": self._contacts.get(cid)} if cid in self._contacts else {"success": False, "error": "Contact not found"}

    def delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cid = params.get("contact_id", "")
        removed = self._contacts.pop(cid, None)
        return {"success": True, "deleted": removed is not None}

    def list_all(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "contacts": list(self._contacts.values()), "count": len(self._contacts)}
