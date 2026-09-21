"""웹캠에서 사진 한 장만 찍어 저장한다 (GUI 창 없이 즉시 캡처).

realtime_detect.py는 imshow 창을 띄우고 'q' 입력을 기다리는 반면,
이 스크립트는 한 프레임만 읽어 바로 파일로 저장하고 종료한다.
"""

import argparse
import sys

import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="웹캠 사진 한 장 캡처")
    parser.add_argument("--camera", type=int, default=0, help="카메라 장치 인덱스 (기본: 0)")
    parser.add_argument("--out", default="captured.jpg", help="저장할 파일 경로 (기본: captured.jpg)")
    parser.add_argument("--warmup", type=int, default=5, help="노출/화이트밸런스 안정화를 위해 버릴 초기 프레임 수")
    return parser.parse_args()


def main():
    args = parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"카메라(index={args.camera})를 열 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    frame = None
    for _ in range(args.warmup + 1):
        ok, frame = cap.read()
        if not ok:
            print("프레임을 읽지 못했습니다.", file=sys.stderr)
            cap.release()
            sys.exit(1)

    cap.release()
    cv2.imwrite(args.out, frame)
    print(f"저장 완료: {args.out} ({frame.shape[1]}x{frame.shape[0]})")


if __name__ == "__main__":
    main()
