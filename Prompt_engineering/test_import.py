"""simple_chat 모듈을 import해서 ask() 함수를 사용합니다."""

import asyncio
from simple_chat import ask


async def main():
    print("Test 1: 간단한 질문")
    answer1 = await ask("너 뭐하는 AI야?")
    print(f"답변: {answer1}\n")

    print("Test 2: 다른 질문 (메모리 없음)")
    answer2 = await ask("아까 내가 뭐라고 했지?")
    print(f"답변: {answer2}\n")

    print("Test 3: 수학 문제")
    answer3 = await ask("2+3은 뭐야?")
    print(f"답변: {answer3}\n")


if __name__ == "__main__":
    asyncio.run(main())
