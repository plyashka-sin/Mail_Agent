import re
from typing import Any

class RuleEngine:
    spam_terms = ["당첨", "무료배송", "특가", "클릭", "쿠폰", "100만원", "기회를 놓치지", "수신거부"]
    decision_terms = ["결정", "검토", "승인", "의견", "선택", "회의 안건", "예산안"]
    no_response_terms = ["merged", "점검 안내", "공지", "안내", "완료되었습니다", "추가 조치는 필요"]
    auto_reply_terms = ["오랜만", "밥 먹자", "시간 괜찮", "언제가 좋을지", "친한 동료"]

    def classify_hint(self, email_item: dict[str, Any]) -> dict[str, Any]:
        subject = email_item.get("subject", "")
        body = email_item.get("body", "")
        sender = email_item.get("sender_email", "")
        text = f"{subject}\n{body}".lower()

        if any(term.lower() in text for term in self.spam_terms) or "spam" in sender:
            return {
                "category": "spam",
                "confidence": 0.95,
                "reason": "광고/이벤트성 문구와 의심 발신자 패턴이 감지됨",
                "requires_user_decision": False,
                "proposed_reply": None,
                "schedule_action": "none",
            }

        if any(term.lower() in text for term in self.decision_terms):
            schedule_action = "conflict" if contains_date_time(text) else "review"
            return {
                "category": "decision_required",
                "confidence": 0.86,
                "reason": "사용자의 선택 또는 검토가 필요한 요청",
                "requires_user_decision": True,
                "proposed_reply": None,
                "schedule_action": schedule_action,
            }

        if any(term.lower() in text for term in self.auto_reply_terms):
            return {
                "category": "auto_reply",
                "confidence": 0.82,
                "reason": "친근한 개인 메일이며 간단한 회신 가능",
                "requires_user_decision": False,
                "proposed_reply": make_friendly_reply(email_item),
                "schedule_action": "none",
            }

        if any(term.lower() in text for term in self.no_response_terms):
            return {
                "category": "no_response",
                "confidence": 0.9,
                "reason": "공지 또는 시스템 알림으로 답장 불필요",
                "requires_user_decision": False,
                "proposed_reply": None,
                "schedule_action": "none",
            }

        return {
            "category": "no_response",
            "confidence": 0.55,
            "reason": "명확한 회신 요청이 없어 보류 없이 무응답 처리",
            "requires_user_decision": False,
            "proposed_reply": None,
            "schedule_action": "none",
        }

def contains_date_time(text: str) -> bool:
    return bool(re.search(r"20\d{2}-\d{2}-\d{2}|\d{1,2}:\d{2}|오전|오후|회의", text))

def make_friendly_reply(email_item: dict[str, Any]) -> str:
    name = email_item.get("sender_name", "친구")
    if name.endswith("희"):
        return f"안녕 {name}야! 나도 잘 지내고 있어. 서울 올라오는구나! 시간 괜찮으면 꼭 밥 먹자. 언제가 좋을지 이야기해줘 😄"
    return f"안녕하세요, {name}님. 연락 감사합니다. 가능한 시간 확인해서 다시 말씀드리겠습니다."