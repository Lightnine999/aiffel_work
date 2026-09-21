"""PaddleOCR-VL 실행 예시.

공식 데모 이미지를 내려받아 문서 구조(레이아웃+텍스트+표 등)를 분석하고,
JSON/마크다운 형식으로 결과를 저장한다.

Apple Silicon(Mac)은 GPU 가속 없이 CPU로만 동작한다 (device="cpu").
"""

from pathlib import Path

from paddleocr import PaddleOCRVL

DEMO_IMAGE_URL = (
    "https://paddle-model-ecology.bj.bcebos.com/paddlex/imgs/demo_image/"
    "paddleocr_vl_demo.png"
)


def main() -> None:
    output_dir = Path("./output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 최초 실행 시 VL 모델 가중치를 자동으로 내려받는다 (수 분 소요될 수 있음).
    pipeline = PaddleOCRVL(device="cpu")

    output = pipeline.predict(DEMO_IMAGE_URL)
    for res in output:
        res.print()  # 콘솔에 구조화된 예측 결과 출력
        res.save_to_json(save_path=output_dir)  # JSON 결과 저장
        res.save_to_markdown(save_path=output_dir)  # 마크다운 결과 저장


if __name__ == "__main__":
    main()
