import json
from typing import Any
from .config import REPORT_DIR
from .utils import AgentResult, now_kst_text

class ReportAgent:
    def __init__(self) -> None:
        self.report_path = REPORT_DIR / "email_report.md"

    def save(self, results: list[AgentResult]) -> None:
        self.write_markdown(results)

    def write_markdown(self, results: list[AgentResult]) -> None:
        counts = count_results(results)
        lines = [
            "# 이메일 에이전트 처리 리포트",
            "",
            f"- 생성 시각: {now_kst_text()}",
            f"- 총 처리: {len(results)}개",
            f"- 의사결정: {counts['decision_required']}",
            f"- 일정추가: {counts['schedule_update']}",
            f"- 답장: {counts['auto_reply']}",
            f"- 무응답: {counts['no_response']}",
            f"- 스팸: {counts['spam']}",
            "",
            "## 처리 결과",
        ]
        for result in results:
            email_item = result.email
            lines.extend(
                [
                    "",
                    f"### {result.label} - {email_item.get('subject', '')}",
                    f"- 발신자: {email_item.get('sender_name')} <{email_item.get('sender_email')}>",
                    f"- 이유: {result.reason}",
                    f"- 신뢰도: {result.confidence:.2f}",
                ]
            )
            if result.proposed_reply:
                lines.append(f"- 답장: {result.proposed_reply}")
            if result.schedule_conflict:
                lines.append(f"- 일정 판단: `{json.dumps(result.schedule_conflict, ensure_ascii=False)}`")
            if result.user_decision:
                lines.append(f"- 사용자 판단: {result.user_decision}")
            if result.user_note:
                lines.append(f"- 사용자 메모: {result.user_note}")

        # 폴더 존재 확인 후 파일 쓰기
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def count_results(results: list[AgentResult]) -> dict[str, int]:
    counts = {
        "spam": 0,
        "no_response": 0,
        "decision_required": 0,
        "auto_reply": 0,
        "schedule_update": 0
    }
    for result in results:
        counts[result.category] = counts.get(result.category, 0) + 1
    return counts

def print_progress(index: int, result: AgentResult) -> None:
    print(f"{index}. {result.label}")

def print_console_report(results: list[AgentResult], llm_provider: str) -> None:
    counts = count_results(results)
    print()
    print("이메일 에이전트 처리 리포트")
    print(
        f"총 처리: {len(results)}개  |  의사결정 {counts['decision_required']}  |  "
        f"일정추가 {counts['schedule_update']}  |  답장완료 {counts['auto_reply']}  |  "
        f"무응답 {counts['no_response']}  |  스팸 {counts['spam']}"
    )
    
def summarize_body(body: str) -> str:
    text = " ".join(body.split())
    return text[:120] + ("..." if len(text) > 120 else "")