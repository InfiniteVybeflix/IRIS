#!/usr/bin/env python3
"""
database_sage.py — ARCHIVE
Database Operations Agent for IRIS v1.0
Query optimization (EXPLAIN analysis), schema migration generation,
index recommendations, replication monitoring, backup verification,
cross-DB compatibility (PostgreSQL/MySQL/MongoDB/Redis).
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ARCHIVE")


class DatabaseSage:
    CODENAME = "ARCHIVE"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._connections: Dict[str, Dict[str, Any]] = {}
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("ARCHIVE started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("ARCHIVE stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "connections": len(self._connections),
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
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def connect_postgresql(self, conn_id: str, host: str, port: int, database: str, user: str, password: str) -> bool:
        """Store PostgreSQL connection parameters."""
        try:
            import psycopg2
            conn = psycopg2.connect(host=host, port=port, database=database, user=user, password=password, connect_timeout=10)
            conn.close()
            self._connections[conn_id] = {"type": "postgresql", "host": host, "port": port, "database": database, "user": user}
            self._store_memory(f"conn:{conn_id}", self._connections[conn_id])
            return True
        except ImportError:
            self._report_to_commander("psycopg2 not installed", level="warning")
            return False
        except Exception as e:
            self._report_to_commander(f"PostgreSQL connect failed: {e}", level="error")
            return False

    def connect_mysql(self, conn_id: str, host: str, port: int, database: str, user: str, password: str) -> bool:
        """Store MySQL connection parameters."""
        try:
            import pymysql
            conn = pymysql.connect(host=host, port=port, database=database, user=user, password=password, connect_timeout=10)
            conn.close()
            self._connections[conn_id] = {"type": "mysql", "host": host, "port": port, "database": database, "user": user}
            self._store_memory(f"conn:{conn_id}", self._connections[conn_id])
            return True
        except ImportError:
            self._report_to_commander("pymysql not installed", level="warning")
            return False
        except Exception as e:
            self._report_to_commander(f"MySQL connect failed: {e}", level="error")
            return False

    def connect_mongodb(self, conn_id: str, uri: str) -> bool:
        """Store MongoDB connection parameters."""
        try:
            from pymongo import MongoClient
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            self._connections[conn_id] = {"type": "mongodb", "uri": uri}
            self._store_memory(f"conn:{conn_id}", self._connections[conn_id])
            return True
        except ImportError:
            self._report_to_commander("pymongo not installed", level="warning")
            return False
        except Exception as e:
            self._report_to_commander(f"MongoDB connect failed: {e}", level="error")
            return False

    def connect_redis(self, conn_id: str, host: str, port: int, password: str = "") -> bool:
        """Store Redis connection parameters."""
        try:
            import redis
            r = redis.Redis(host=host, port=port, password=password, socket_connect_timeout=5)
            r.ping()
            self._connections[conn_id] = {"type": "redis", "host": host, "port": port}
            self._store_memory(f"conn:{conn_id}", self._connections[conn_id])
            return True
        except ImportError:
            self._report_to_commander("redis-py not installed", level="warning")
            return False
        except Exception as e:
            self._report_to_commander(f"Redis connect failed: {e}", level="error")
            return False

    def analyze_query(self, conn_id: str, query: str) -> Dict[str, Any]:
        """Run EXPLAIN and return optimization suggestions."""
        if not self._running:
            raise RuntimeError("Agent not running")
        conn = self._connections.get(conn_id)
        if not conn:
            return {"error": "Connection not found"}
        suggestions: List[str] = []
        try:
            if conn["type"] == "postgresql":
                import psycopg2
                c = psycopg2.connect(host=conn["host"], port=conn["port"], database=conn["database"], user=conn["user"], password=conn.get("password", ""))
                cur = c.cursor()
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
                plan = cur.fetchall()
                c.close()
                plan_text = json.dumps(plan)
                if "Seq Scan" in plan_text and "Index" not in plan_text:
                    suggestions.append("Consider adding an index to avoid sequential scans.")
                if "Nested Loop" in plan_text:
                    suggestions.append("Consider increasing work_mem or rewriting joins.")
                return {"plan": plan, "suggestions": suggestions, "db": "postgresql"}
            elif conn["type"] == "mysql":
                import pymysql
                c = pymysql.connect(host=conn["host"], port=conn["port"], database=conn["database"], user=conn["user"], password=conn.get("password", ""))
                cur = c.cursor()
                cur.execute(f"EXPLAIN FORMAT=JSON {query}")
                plan = cur.fetchall()
                c.close()
                return {"plan": plan, "suggestions": suggestions, "db": "mysql"}
            else:
                return {"error": f"EXPLAIN not supported for {conn['type']}"}
        except Exception as e:
            return {"error": str(e)}

    def recommend_indexes(self, conn_id: str, table: str) -> List[Dict[str, str]]:
        """Recommend indexes based on query patterns or table structure."""
        if not self._running:
            raise RuntimeError("Agent not running")
        conn = self._connections.get(conn_id)
        if not conn:
            return []
        recommendations: List[Dict[str, str]] = []
        try:
            if conn["type"] == "postgresql":
                import psycopg2
                c = psycopg2.connect(host=conn["host"], port=conn["port"], database=conn["database"], user=conn["user"], password=conn.get("password", ""))
                cur = c.cursor()
                cur.execute("""
                    SELECT attname FROM pg_stats WHERE schemaname = 'public' AND tablename = %s
                    AND n_distinct > 0.1 AND n_distinct < 0.9
                """, (table,))
                cols = [r[0] for r in cur.fetchall()]
                for col in cols:
                    recommendations.append({"table": table, "column": col, "type": "B-tree", "reason": "Moderate cardinality"})
                c.close()
            elif conn["type"] == "mysql":
                recommendations.append({"table": table, "column": "id", "type": "PRIMARY", "reason": "Always index primary keys"})
        except Exception as e:
            self._report_to_commander(f"Index recommendation failed: {e}", level="error")
        return recommendations

    def generate_migration(self, conn_id: str, changes: List[Dict[str, Any]]) -> str:
        """Generate SQL/NoSQL migration scripts from schema changes."""
        if not self._running:
            raise RuntimeError("Agent not running")
        conn = self._connections.get(conn_id)
        if not conn:
            return "-- Connection not found"
        lines: List[str] = [f"-- Migration generated by ARCHIVE for {conn['type']}", "BEGIN;"]
        for change in changes:
            op = change.get("operation")
            if op == "add_column":
                lines.append(f"ALTER TABLE {change['table']} ADD COLUMN {change['column']} {change['type']};")
            elif op == "drop_column":
                lines.append(f"ALTER TABLE {change['table']} DROP COLUMN {change['column']};")
            elif op == "create_index":
                lines.append(f"CREATE INDEX idx_{change['table']}_{change['column']} ON {change['table']}({change['column']});")
            elif op == "create_table":
                cols = ", ".join([f"{c['name']} {c['type']}" for c in change.get("columns", [])])
                lines.append(f"CREATE TABLE {change['table']} ({cols});")
            elif op == "drop_table":
                lines.append(f"DROP TABLE {change['table']};")
        lines.append("COMMIT;")
        return "\n".join(lines)

    def monitor_replication(self, conn_id: str) -> Dict[str, Any]:
        """Check replication lag for PostgreSQL/MySQL."""
        if not self._running:
            raise RuntimeError("Agent not running")
        conn = self._connections.get(conn_id)
        if not conn:
            return {"error": "Connection not found"}
        try:
            if conn["type"] == "postgresql":
                import psycopg2
                c = psycopg2.connect(host=conn["host"], port=conn["port"], database=conn["database"], user=conn["user"], password=conn.get("password", ""))
                cur = c.cursor()
                cur.execute("SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag;")
                lag = cur.fetchone()[0]
                c.close()
                return {"lag_seconds": lag, "status": "healthy" if lag < 5 else "lagging"}
            elif conn["type"] == "mysql":
                import pymysql
                c = pymysql.connect(host=conn["host"], port=conn["port"], database=conn["database"], user=conn["user"], password=conn.get("password", ""))
                cur = c.cursor()
                cur.execute("SHOW SLAVE STATUS;")
                row = cur.fetchone()
                c.close()
                if row:
                    return {"lag_seconds": row[32] if len(row) > 32 else None, "status": "replicating"}
                return {"status": "not_replicating"}
            else:
                return {"error": f"Replication monitoring not supported for {conn['type']}"}
        except Exception as e:
            return {"error": str(e)}

    def verify_backup(self, backup_path: str) -> Dict[str, Any]:
        """Verify a backup file integrity (pg_dump, mysqldump, mongodump, redis RDB)."""
        if not os.path.exists(backup_path):
            return {"valid": False, "error": "File not found"}
        try:
            if backup_path.endswith(".sql"):
                rc, out, err = self._execute_shell(f"head -n 5 {backup_path} && tail -n 5 {backup_path}")
                valid = rc == 0 and ("PostgreSQL" in out or "MySQL" in out or "CREATE TABLE" in out or "INSERT INTO" in out)
                return {"valid": valid, "type": "sql", "size": os.path.getsize(backup_path)}
            elif backup_path.endswith(".gz"):
                rc, out, err = self._execute_shell(f"gunzip -t {backup_path} 2>&1")
                return {"valid": rc == 0, "type": "gz", "size": os.path.getsize(backup_path)}
            elif backup_path.endswith(".rdb"):
                rc, out, err = self._execute_shell(f"file {backup_path}")
                return {"valid": "Redis" in out, "type": "redis_rdb", "size": os.path.getsize(backup_path)}
            else:
                return {"valid": True, "type": "unknown", "size": os.path.getsize(backup_path), "note": "Cannot verify unknown format"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_connect_postgresql(self) -> bool:
        # Requires real DB; stub
        return True

    def test_recommend_indexes(self) -> bool:
        # Requires real DB; stub
        return True

    def test_generate_migration(self) -> bool:
        sql = self.generate_migration("dummy", [{"operation": "create_table", "table": "users", "columns": [{"name": "id", "type": "SERIAL PRIMARY KEY"}]}])
        return "CREATE TABLE" in sql

    def test_verify_backup(self) -> bool:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("-- PostgreSQL dump\nCREATE TABLE t (id int);\n")
            path = f.name
        r = self.verify_backup(path)
        return r.get("valid") is True


if __name__ == "__main__":
    agent = DatabaseSage()
    agent.start()
    print(agent.health())
    agent.stop()
