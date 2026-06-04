from __future__ import annotations

import argparse
import asyncio
import sys

from Agentss.pipeline import main_async

def build_parser() -> argparse.ArgumentParser: # 메일 수 조절
    parser = argparse.ArgumentParser(description="Ollama Multi_Agent / Email")
    parser.add_argument("--limit", type=int, default=20, help="가져올 최대 메일 수")
    parser.add_argument("--source", type=str, default="dummy", help="메일 소스 선택 (예: dummy, imap 등)")
    return parser

async def run_app() -> int:
    args = build_parser().parse_args()
    
    print("\n# Ollama 로컬 사용으로 더미 메일 확인")
    print()

    # pipeline.py에 구현된 대화형 질문(1: LLM, 2: 규칙 기반)을 띄우기 위해 "ask" 전달
    return await main_async([
        "run",
        "--source", args.source,
        "--llm", "ask",
        "--limit", str(args.limit),
        "--interactive",
        "--report"
    ])

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run_app()))
    except KeyboardInterrupt:
        print("\n사용자가 실행을 중단했습니다.")
        sys.exit(130)
