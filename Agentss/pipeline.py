import sys
import json
import asyncio
import argparse


from .config import REPORT_DIR, DUMMY_DIR
from .utils import AgentResult, write_json
from .llm_router import LLMRouter
from .agents import MailFetchAgent, ClassificationAgent, ScheduleAgent, ReplyAgent
from .report_agent import ReportAgent, print_progress, print_console_report, summarize_body


async def run_pipeline(args: argparse.Namespace) -> list[AgentResult]:
    ensure_runtime_files()
    fetcher = MailFetchAgent(args.source, args.limit)
    
    llm_choice = getattr(args, "llm", "ask")
    if llm_choice == "ask":
        if sys.stdin.isatty():
            print("메일 분류에 사용할 판단 엔진을 선택하세요.")
            print("1) LLM (Ollama)  2) 규칙 기반 (Rules)")
            try:
                choice = input("엔진 번호 [1]: ").strip()
                llm_choice = "rules" if choice == "2" else "ollama"
            except EOFError:
                llm_choice = "ollama"
            print()
        else:
            llm_choice = "ollama"
            
    classifier = ClassificationAgent(LLMRouter(llm_choice))
    schedule_agent = ScheduleAgent()
    reply_agent = ReplyAgent(args.source)
    review_only = bool(getattr(args, "review_only", False))

    if review_only:
        print("검토 전용 모드: 메일을 읽고 분류하지만 Draft/스팸 DB 변경은 하지 않습니다.")
        print()

    emails = await fetcher.fetch()
    tasks = [classifier.classify(email_item) for email_item in emails]
    classified = await asyncio.gather(*tasks)
    print("분류한 메일")
    results: list[AgentResult] = []

    for index, result in enumerate(classified, start=1):
        result = schedule_agent.enrich(result)
        if review_only and result.category == "auto_reply":
            result.gmail_action = "review_only_no_draft"
        elif not review_only:
            await reply_agent.handle(result)
        print_progress(index, result)
        results.append(result)

    handle_interactive_decisions(results, args.interactive)
    ReportAgent().save(results)
    print_console_report(results, classifier.llm.last_provider)
    return results

def handle_interactive_decisions(results: list[AgentResult], interactive: bool) -> None:
    decision_items = [r for r in results if r.requires_user_decision]
    if not decision_items:
        return
    if not interactive or not sys.stdin.isatty():
        for result in decision_items:
            result.user_decision = "pending"
            result.user_note = "사용자 판단 대기"
        return

    print()
    print("=" * 68)
    print("사용자 판단 입력")
    print("각 항목에 대해 선택을 남깁니다. Enter만 누르면 보류 처리됩니다.")
    print("=" * 68)
    for index, result in enumerate(decision_items, start=1):
        email_item = result.email
        print()
        print(f"[{index}/{len(decision_items)}] {email_item.get('subject')}")
        print(f"발신자: {email_item.get('sender_name')} <{email_item.get('sender_email')}>")
        print(summarize_body(email_item.get("body", "")))
        if result.schedule_conflict:
            print(f"일정 판단: {json.dumps(result.schedule_conflict, ensure_ascii=False)}")
        print("선택: 1) 보류  2) 승인  3) 거절  4) 추가 검토")
        choice = input("판단 번호 [1]: ").strip() or "1"
        mapping = {"1": "pending", "2": "approved", "3": "rejected", "4": "needs_more_review"}
        result.user_decision = mapping.get(choice, "pending")
        note = input("메모(선택): ").strip()
        result.user_note = note or "사용자 판단 기록됨"

def ensure_runtime_files() -> None:
    for path in (REPORT_DIR, DUMMY_DIR):
        path.mkdir(parents=True, exist_ok=True)
    if not (DUMMY_DIR / "sent_mails.json").exists():
        write_json(DUMMY_DIR / "sent_mails.json", {"sent_mails": []})

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dummy email / Ollama")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="메일 에이전트를 실행합니다.")
    run.add_argument("--source", choices=["dummy"], default="dummy")
    run.add_argument("--limit", type=int, default=20)
    run.add_argument("--llm", choices=["ollama", "rules", "ask"], default="ask")
    run.add_argument("--interactive", action="store_true")
    run.add_argument("--report", action="store_true")
    run.add_argument("--review-only", action="store_true")
    return parser

async def main_async(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in (None, "run"):
        if args.command is None:
            args = parser.parse_args(["run"])
        await run_pipeline(args)
        return 0
    parser.print_help()
    return 1

if __name__ == "__main__":
    asyncio.run(main_async())