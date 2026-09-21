# YOLO 실시간 웹캠 객체 탐지

## 설치 및 실행

환경은 [uv](https://docs.astral.sh/uv/)로 관리한다. `pyproject.toml`/`uv.lock`에 의존성이
고정돼 있어 `uv run` 한 번이면 (없으면 만들고) 가상환경을 잡아 실행까지 해준다.

```bash
uv run python realtime_detect.py
```

종료는 영상 창에서 `q` 키.

## 옵션

```bash
uv run python realtime_detect.py --model yolov8s.pt --conf 0.5   # 더 정확한 모델 + 임계값 조정
uv run python realtime_detect.py --camera 1                       # 외장 카메라 등 다른 장치
uv run python realtime_detect.py --save output.mp4                # 탐지 결과 영상 저장
```

의존성을 바꿀 때는 `pip install` 대신 `uv add <패키지>` / `uv remove <패키지>`를 쓴다 —
`pyproject.toml`과 `uv.lock`이 같이 갱신되어 재현 가능한 환경이 유지된다.

## macOS 카메라 권한 (중요)

macOS는 터미널 앱에 카메라 접근 권한을 별도로 요구한다. 처음 실행 시 권한 팝업이 뜨지 않고
`OpenCV: not authorized to capture video` 에러가 나면:

1. **시스템 설정 → 개인정보 보호 및 보안 → 카메라**
2. 사용 중인 터미널 앱(Terminal, iTerm2 등)을 찾아 체크 활성화
3. 터미널 앱을 완전히 재시작 후 다시 실행

## 검증 내역

- `uv run python realtime_detect.py --help` 정상 동작을 확인했다.
- `uv run` 경로로 YOLOv8n 모델이 정상 로드되는 것을 확인했다(같은 폴더의 `yolov8n.pt`를 재사용, 재다운로드 없음).
- 카메라 미인가 상황(이 개발 환경은 원격 샌드박스라 카메라가 없음)에서 의도한 대로 `RuntimeError`로 명확히 실패하는 것을 확인했다.
- **실제 웹캠 영상으로 바운딩 박스가 그려지는지는 카메라·디스플레이가 있는 사용자 로컬 환경에서만 확인 가능** — 위 macOS 권한 설정 후 직접 실행해서 확인해야 한다.
