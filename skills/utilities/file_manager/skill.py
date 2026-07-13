"""File Manager Skill — File operations, search, organization."""
import os
import shutil
import logging
from typing import Dict, Any, List
from skills import BaseSkill
logger = logging.getLogger(__name__)

class FileManagerSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="file_manager", category="utilities", capabilities=["file_manager"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "list")
        if method == "list": return self.list_dir(params)
        elif method == "copy": return self.copy(params)
        elif method == "move": return self.move(params)
        elif method == "delete": return self.delete(params)
        elif method == "search": return self.search(params)
        elif method == "info": return self.info(params)
        return {"error": f"Unknown method: {method}"}

    def list_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", ".")
        try:
            items = [{"name": f, "is_dir": os.path.isdir(os.path.join(path, f)), "size": os.path.getsize(os.path.join(path, f)) if os.path.isfile(os.path.join(path, f)) else 0} for f in os.listdir(path)]
            return {"success": True, "path": path, "items": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src, dst = params.get("source", ""), params.get("destination", "")
        try:
            shutil.copy2(src, dst)
            return {"success": True, "copied": True, "from": src, "to": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src, dst = params.get("source", ""), params.get("destination", "")
        try:
            shutil.move(src, dst)
            return {"success": True, "moved": True, "from": src, "to": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        try:
            if os.path.isdir(path): shutil.rmtree(path)
            else: os.remove(path)
            return {"success": True, "deleted": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        root = params.get("path", ".")
        pattern = params.get("pattern", "")
        results = []
        for dirpath, _, filenames in os.walk(root):
            for f in filenames:
                if pattern.lower() in f.lower():
                    results.append(os.path.join(dirpath, f))
            if len(results) > 100: break
        return {"success": True, "results": results, "count": len(results)}

    def info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        if not os.path.exists(path): return {"success": False, "error": "Not found"}
        stat = os.stat(path)
        return {"success": True, "path": path, "size": stat.st_size, "is_dir": os.path.isdir(path), "modified": stat.st_mtime}
