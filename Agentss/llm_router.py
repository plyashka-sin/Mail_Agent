import os
import json
import asyncio
import textwrap
import urllib.request
import urllib.error
from typing import Any
CATEGORY_LABELS = ["spam", "no_response", "decision_required", "auto_reply", "schedule_update"]

class LLMProvider:
    name = "base"
    def is_available(self) -> bool: return False
    async def analyze(self, email_item: dict[str, Any], rule_hint: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, force: bool = False) -> None:
        self.force = force
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")

    def is_available(self) -> bool:
        return self.force or os.getenv("LLM_PROVIDER", "").lower() == "ollama" or self.server_is_running()

    def server_is_running(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url.rstrip('/')}/api/tags", timeout=0.5):
                return True
        except OSError:
            return False

    async def analyze(self, email_item: dict[str, Any], rule_hint: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._analyze_sync, email_item, rule_hint)

    def _analyze_sync(self, email_item: dict[str, Any], rule_hint: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": make_llm_prompt(email_item, rule_hint),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return json.loads(data.get("response", "{}"))

class LLMRouter:
    def __init__(self, provider_name: str | None = None) -> None:
        provider_name = (provider_name or os.getenv("LLM_PROVIDER", "auto")).lower()
        ordered: list[LLMProvider]
        if provider_name == "rules":
            ordered = []
        elif provider_name == "ollama":
            ordered = [OllamaProvider(force=True)]
        else:
            ordered = [OllamaProvider()]
        self.providers = ordered
        self.requested_provider = provider_name
        self.last_provider = "rules"

    async def analyze(self, email_item: dict[str, Any], rule_hint: dict[str, Any]) -> dict[str, Any]:
        for provider in self.providers:
            if not provider.is_available():
                continue
            try:
                result = await provider.analyze(email_item, rule_hint)
                self.last_provider = provider.name
                return normalize_llm_result(result, rule_hint)
            except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, KeyError):
                continue
        self.last_provider = "rules"
        return rule_hint

def make_llm_prompt(email_item: dict[str, Any], rule_hint: dict[str, Any]) -> str:
    schema = {
        "category": "spam | no_response | decision_required | auto_reply | schedule_update",
        "confidence": "0.0-1.0",
        "reason": "Korean short reason",
        "requires_user_decision": "boolean",
        "proposed_reply": "Korean reply body or null",
        "schedule_action": "none | add | conflict | review",
    }
    return textwrap.dedent(
        f"""
        다음 이메일을 분류하세요. 규칙 기반 힌트는 참고하되, 최종 판단은 메일 의미를 보고 하세요.

        JSON 스키마:
        {json.dumps(schema, ensure_ascii=False)}

        규칙 힌트:
        {json.dumps(rule_hint, ensure_ascii=False)}

        이메일:
        {json.dumps(email_item, ensure_ascii=False)}
        """
    ).strip()

def normalize_llm_result(result: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    category = result.get("category")
    if category not in CATEGORY_LABELS:
        category = fallback["category"]
    confidence = result.get("confidence", fallback.get("confidence", 0.7))
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = fallback.get("confidence", 0.7)
    return {
        "category": category,
        "confidence": max(0.0, min(1.0, confidence)),
        "reason": str(result.get("reason") or fallback.get("reason") or ""),
        "requires_user_decision": bool(
            result.get("requires_user_decision", fallback.get("requires_user_decision", False))
        ),
        "proposed_reply": result.get("proposed_reply", fallback.get("proposed_reply")),
        "schedule_action": result.get("schedule_action", fallback.get("schedule_action", "none")),
    }