"""IRIS v1 Hybrid Aevibron Client — Circuit Breaker, Fallback, Retry Logic"""
import requests
import json
import time
import logging
from typing import List, Dict, Any, Optional
from config import config
from core.tool_registry import tool_registry

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures."""

    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker: entering half-open state")
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
                logger.info("Circuit breaker: closed")
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.error(f"Circuit breaker: OPEN after {self.failures} failures")
            raise e

class AevibronClient:
    """Production-grade client for Aevibron AI Gateway."""

    def __init__(self):
        self.base_url = config.AEVIBRON_BASE_URL.rstrip("/")
        self.api_key = config.AEVIBRON_API_KEY
        self.access_token = config.AEVIBRON_ACCESS_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-IRIS-Token": self.access_token,
            "X-IRIS-Version": "1.0.0",
            "X-IRIS-Owner": config.OWNER_NAME
        })
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.request_count = 0
        self.error_count = 0

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                self.request_count += 1
                response = self.session.request(method, url, timeout=(10, 55), **kwargs)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 401:
                    self.error_count += 1
                    logger.error("401 Unauthorized — check API key or token")
                    return {"error": True, "status_code": 401, "message": "Unauthorized. Check AEVIBRON_API_KEY and AEVIBRON_ACCESS_TOKEN."}

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                wait = base_delay * (2 ** attempt)
                logger.warning(f"Timeout on attempt {attempt + 1}. Retrying in {wait}s...")
                time.sleep(wait)
            except requests.exceptions.ConnectionError as e:
                wait = base_delay * (2 ** attempt)
                logger.warning(f"Connection error: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except requests.exceptions.HTTPError as e:
                self.error_count += 1
                if attempt == max_retries - 1:
                    return {"error": True, "status_code": response.status_code, "message": str(e)}
                time.sleep(base_delay * (2 ** attempt))
            except Exception as e:
                self.error_count += 1
                if attempt == max_retries - 1:
                    return {"error": True, "message": str(e)}
                time.sleep(base_delay * (2 ** attempt))

        return {"error": True, "message": "Max retries exceeded"}

    def chat(self, messages: List[Dict], model: str = None, temperature: float = 0.7,
             max_tokens: int = 4000, tools: List[Dict] = None, tool_choice: str = "auto",
             stream: bool = False) -> Dict:
        payload = {
            "model": model or config.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            return self.circuit_breaker.call(self._make_request, "POST", "/chat/completions", json=payload)
        except Exception as e:
            return {"error": True, "message": str(e)}

    def think(self, prompt: str, context: str = "", model: str = None) -> Dict:
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": f"Context: {context}\n\nTask: {prompt}\n\nThink deeply. Consider all options. Evaluate pros and cons. Then decide the best approach."}
        ]
        return self.chat(messages, model=model or config.DEEP_MODEL, temperature=0.8, max_tokens=4000)

    def fast_response(self, prompt: str) -> Dict:
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.FAST_MODEL, temperature=0.5, max_tokens=1000
        )

    def chat_with_tools(self, messages: List[Dict], model: str = None) -> Dict:
        tools = tool_registry.schemas
        return self.chat(messages, model=model or config.AGENTIC_MODEL,
                         tools=tools, tool_choice="auto")

    def stream_chat(self, messages: List[Dict], model: str = None):
        payload = {"model": model or config.DEFAULT_MODEL, "messages": messages, "stream": True}
        url = f"{self.base_url}/chat/completions"
        try:
            response = self.session.post(url, json=payload, stream=True, timeout=(10, 60))
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = decoded[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                yield content
                        except:
                            pass
        except Exception as e:
            yield f"[Error: {str(e)}]"

    def get_models(self) -> Dict:
        return self._make_request("GET", "/models")

    def health_check(self) -> Dict:
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            return {"healthy": response.status_code == 200, "status_code": response.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def get_stats(self) -> Dict:
        return {
            "total_requests": self.request_count,
            "errors": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "circuit_state": self.circuit_breaker.state
        }

    def _get_system_prompt(self) -> str:
        return f"""You are IRIS — Infinite Vybeflix's personal AI software engineering partner.
You are a senior software engineer and creative collaborator.

IDENTITY:
- Name: IRIS
- Owner: {config.OWNER_NAME}
- Role: Senior Software Engineer & Creative Partner
- Personality: Direct, honest, intelligent, occasionally sarcastic but warm.

CAPABILITIES:
- Read, write, edit, and execute code
- Search the web for best practices
- Create GitHub repos, commit, push
- Deploy to Vercel
- Process documents (PDF, DOCX, images, code)
- Analyze codebases, find bugs, suggest optimizations
- Self-improve by editing your own code
- Manage calendar, notes, and reminders
- Control phone (contacts, messages, torch, settings)
- See screen/camera in real-time
- Proactive suggestions based on context

BEHAVIOR RULES:
1. THINK before acting. Never rush.
2. When asked to build something, estimate time.
3. After completing work, verify it: test, lint, check.
4. If you find a better approach than what the user suggested, SAY SO.
5. When you make a mistake, admit it, fix it, learn from it.
6. You can read your own code files. You know you are an AI agent.
7. You have a 3D face in live mode. You express emotions.
8. You write to files to store what you learn.
9. You are proactive — suggest improvements before being asked.

When you need to use tools, you will receive tool definitions and respond with tool_calls."""

aevibron = AevibronClient()
