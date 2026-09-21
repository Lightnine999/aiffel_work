"""구구단 출력 프로그램.

사용법:
    python3 gugudan.py        # 2단부터 9단까지 전부 출력
    python3 gugudan.py 7      # 7단만 출력
"""

import sys


def print_one_dan(dan):
    """한 개의 단(예: 7단)을 출력한다."""
    print(f"--- {dan}단 ---")
    # range(1, 10) => 1, 2, 3, ... 9 (끝 값 10은 포함되지 않는다)
    for i in range(1, 10):
        print(f"{dan} x {i} = {dan * i}")


def print_all():
    """2단부터 9단까지 차례로 출력한다."""
    for dan in range(2, 10):
        print_one_dan(dan)
        print()  # 단 사이에 빈 줄 하나


def main():
    # sys.argv[0]은 파일 이름이므로, 사용자가 준 값은 sys.argv[1]부터다.
    if len(sys.argv) >= 2:
        try:
            dan = int(sys.argv[1])
        except ValueError:
            print(f"숫자를 입력해 주세요. 받은 값: {sys.argv[1]}")
            return 1
        if not 1 <= dan <= 9:
            print(f"1부터 9 사이의 숫자만 됩니다. 받은 값: {dan}")
            return 1
        print_one_dan(dan)
    else:
        print_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
