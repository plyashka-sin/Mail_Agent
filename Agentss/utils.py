import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

@dataclass
class AgentResult:
    category: str
    confidence: float
    reason: str
    requires_user_decision: bool = False
    proposed_reply: str | None = None
    schedule_action: str = "none"
    schedule_conflict: dict[str, Any] | None = None
    gmail_action: str = "none"
    user_decision: str | None = None
    user_note: str | None = None
    email: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        labels = {
            "spam": "스팸",
            "no_response": "무응답",
            "decision_required": "결정필요",
            "auto_reply": "답장완료",
            "schedule_update": "일정추가",
        }
        return labels.get(self.category, self.category)

def now_kst_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def clean_subject_for_reply(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"

def first_recipient(email: dict[str, Any]) -> str:
    recipients = email.get("to") or ["me@gmail.com"]
    if isinstance(recipients, list) and recipients:
        return recipients[0]
    return str(recipients)