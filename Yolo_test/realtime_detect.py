"""
YOLO 기반 실시간 웹캠 객체 탐지 프로그램

사용법:
    python3 realtime_detect.py                # 기본 카메라(0번), yolov8n 모델
    python3 realtime_detect.py --camera 1     # 다른 카메라 장치 사용
    python3 realtime_detect.py --model yolov8s.pt --conf 0.5
    python3 realtime_detect.py --save out.mp4 # 탐지 결과를 영상으로 저장

종료: 실행 창에서 'q' 키
"""

import argparse
import time

import cv2
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="YOLO 실시간 웹캠 객체 탐지")
    parser.add_argument("--model", default="yolov8n.pt", help="사용할 YOLO 모델 (기본: yolov8n.pt)")
    parser.add_argument("--camera", type=int, default=0, help="카메라 장치 인덱스 (기본: 0)")
    parser.add_argument("--conf", type=float, default=0.4, help="탐지 신뢰도 임계값 (기본: 0.4)")
    parser.add_argument("--width", type=int, default=1280, help="캡처 해상도 가로")
    parser.add_argument("--height", type=int, default=720, help="캡처 해상도 세로")
    parser.add_argument("--save", default=None, help="탐지 결과를 저장할 mp4 경로 (선택)")
    return parser.parse_args()


def main():
    args = parse_args()

    model = YOLO(args.model)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise RuntimeError(f"카메라(index={args.camera})를 열 수 없습니다. 다른 --camera 값을 시도하세요.")

    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(args.save, fourcc, fps, (w, h))

    prev_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("프레임을 읽지 못했습니다. 종료합니다.")
                break

            results = model.predict(frame, conf=args.conf, verbose=False)
            annotated = results[0].plot()

            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now
            cv2.putText(
                annotated,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )

            cv2.imshow("YOLO Realtime Detection (q to quit)", annotated)

            if writer is not None:
                writer.write(annotated)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
