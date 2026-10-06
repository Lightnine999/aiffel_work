"""claude-agent-sdk로 만든 아주 단순한 채팅 프로그램.

- 도구 없음 (tools=[])
- 이전 대화 기억 없음 (매 질문마다 새 query 호출)
- 프롬프트 인젝션 방지 장치 없음
종료: quit / exit / 빈 줄 / Ctrl+C
"""

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

MODEL = "haiku"

OPTIONS = ClaudeAgentOptions(
    model=MODEL,
    tools=[],          # 도구 전부 끔
    max_turns=1,       # 한 번 답하고 끝
    setting_sources=[],  # 내 CLAUDE.md·settings 안 읽음
    system_prompt="너는 친절한 한국어 챗봇이다.",
)


async def ask(prompt: str) -> str:
    """질문 하나를 보내고 답변 텍스트를 돌려준다."""
    parts = []
    async for message in query(prompt=prompt, options=OPTIONS):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return "".join(parts)


async def main() -> None:
    print(f"Claude 채팅 ({MODEL}) — 종료하려면 quit 입력")
    while True:
        try:
            user_input = input("\n나> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in ("", "quit", "exit"):
            break
        answer = await ask(user_input)
        print(f"Claude> {answer}")
    print("\n종료합니다.")


if __name__ == "__main__":
    asyncio.run(main())
