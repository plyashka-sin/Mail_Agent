import re
from datetime import datetime
from typing import Any
from .config import DUMMY_DIR
from .utils import AgentResult, read_json, write_json, now_kst_text, first_recipient, clean_subject_for_reply
from .rule_engine import RuleEngine, make_friendly_reply
from .llm_router import LLMRouter

class MailFetchAgent:
    def __init__(self, source: str, limit: int) -> None:
        self.source = source
        self.limit = limit

    async def fetch(self) -> list[dict[str, Any]]:
        data = read_json(DUMMY_DIR / "emails.json", {"emails": []})
        return list(data.get("emails", []))[: self.limit]

class ClassificationAgent:
    def __init__(self, llm: LLMRouter) -> None:
        self.rules = RuleEngine()
        self.llm = llm

    async def classify(self, email_item: dict[str, Any]) -> AgentResult:
        rule_hint = self.rules.classify_hint(email_item)
        llm_result = await self.llm.analyze(email_item, rule_hint)
        if llm_result["category"] == "auto_reply" and not llm_result.get("proposed_reply"):
            llm_result["proposed_reply"] = make_friendly_reply(email_item)
        return AgentResult(email=email_item, **llm_result)

class ScheduleAgent:
    def __init__(self) -> None:
        self.path = DUMMY_DIR / "schedule.json"
        self.events = read_json(self.path, {"events": []}).get("events", [])

    def enrich(self, result: AgentResult) -> AgentResult:
        if result.category != "decision_required":
            return result
        proposed = extract_schedule_window(result.email)
        if not proposed:
            return result
        conflict = self.find_conflict(proposed["from"], proposed["to"])
        if conflict:
            result.schedule_conflict = {
                "requested": proposed,
                "conflict": conflict,
                "alternative": suggest_alternative(result.email),
            }
            result.schedule_action = "conflict"
        else:
            result.schedule_conflict = {"requested": proposed, "conflict": None}
            result.schedule_action = "review"
        return result

    def find_conflict(self, start: str, end: str) -> dict[str, Any] | None:
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
        except ValueError:
            return None
        for event in self.events:
            try:
                event_start = datetime.strptime(event["from"], "%Y-%m-%d %H:%M")
                event_end = datetime.strptime(event["to"], "%Y-%m-%d %H:%M")
            except (KeyError, ValueError):
                continue
            if start_dt < event_end and end_dt > event_start:
                return event
        return None

def extract_schedule_window(email_item: dict[str, Any]) -> dict[str, str] | None:
    text = f"{email_item.get('subject', '')}\n{email_item.get('body', '')}"
    match = re.search(
        r"(20\d{2}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s*[~\-]\s*(20\d{2}-\d{2}-\d{2})?\s*(\d{1,2}:\d{2})",
        text,
    )
    if not match:
        return None
    start_date, start_time, end_date, end_time = match.groups()
    end_date = end_date or start_date
    return {"from": f"{start_date} {start_time}", "to": f"{end_date} {end_time}"}

def suggest_alternative(email_item: dict[str, Any]) -> str:
    body = email_item.get("body", "")
    match = re.search(r"대안:\s*(20\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\s*[~\-]\s*20\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2})", body)
    if match:
        return match.group(1)
    return "대안 일정 확인 필요"

class ReplyAgent:
    def __init__(self, source: str) -> None:
        self.source = source

    async def handle(self, result: AgentResult) -> None:
        if result.category != "auto_reply" or not result.proposed_reply:
            return
        self.save_dummy_sent_mail(result)
        result.gmail_action = "sent_dummy"

    def save_dummy_sent_mail(self, result: AgentResult) -> None:
        path = DUMMY_DIR / "sent_mails.json"
        data = read_json(path, {"sent_mails": []})
        sent = {
            "to": [result.email.get("sender_email", "")],
            "from": first_recipient(result.email),
            "subject": clean_subject_for_reply(result.email.get("subject", "")),
            "body": result.proposed_reply,
            "in_reply_to_msg_id": result.email.get("msg_id"),
            "thread_id": result.email.get("thread_id"),
            "date": now_kst_text(),
            "status": "sent_dummy",
        }
        sent_mails = data.setdefault("sent_mails", [])
        already_saved = any(
            item.get("in_reply_to_msg_id") == sent["in_reply_to_msg_id"] and item.get("status") == "sent_dummy"
            for item in sent_mails
        )
        if not already_saved:
            sent_mails.append(sent)
            write_json(path, data)