# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 저장소 성격

`aiffel_work`는 AIFFEL 부트캠프 학습자(사용자)의 **개인 실습 워크스페이스**다. 하나의 앱이 아니라
서로 독립된 여러 미니 프로젝트(머신러닝 실습, 게임, 웹 앱, 블로그)가 한 폴더 아래 모여 있다.
프로젝트마다 언어·스택·목적이 다르므로, 작업 전 반드시 해당 하위 폴더로 들어가 그 폴더의
`README.md`(있다면 `CLAUDE.md`도)를 먼저 읽는다.

### 독립 git 저장소 vs 이 저장소가 직접 추적하는 폴더

다음 폴더는 **자체 `.git`을 가진 별도의 GitHub 저장소**다 (`aiffel_work`의 커밋 이력과 무관):

| 폴더 | 원격 |
|---|---|
| `TestGame_G/` | 별도 저장소 |
| `TestGame_Grop1/` | `github.com/lightnine999/TestGame_Grop1` |
| `blog_ggg/` | `github.com/lightnine999/blog_ggg` (Jekyll 블로그) |
| `hello_test/` | 별도 저장소 |
| `rolepicker_Review01/` | 별도 저장소 (Next.js, 배포: Vercel) |

반면 `ToDoApp/`, `ToDoApp_CLI/`, `ResNet18_test/`, `mnist_pytorch/` 등은 자체 `.git`이 없고
루트 `aiffel_work` 저장소(`github.com/Lightnine999/aiffel_work`)가 직접 추적한다.

**커밋·푸시 전 반드시 확인**: 지금 있는 폴더가 독립 저장소인지 루트 저장소 소속인지 헷갈리면
`git remote -v`로 원격을 확인한다. 독립 저장소 폴더에서 실수로 루트 저장소 명령을 실행하면
엉뚱한 곳에 푸시될 수 있다.

## 하위 프로젝트 개요

### 머신러닝 실습

- **`mnist_pytorch/`** — MNIST/FashionMNIST 손글씨·의류 분류 (PyTorch, MLP vs CNN 비교)
  ```bash
  cd mnist_pytorch
  pip install -r requirements.txt
  python train.py                        # CNN, 5 epoch (기본)
  python train.py --model mlp --epochs 3  # MLP로 비교
  python predict.py                       # 오답 분석
  ```
  코드 읽는 순서: `data.py`(전처리) → `model.py`(구조) → `train.py`의 `run_epoch()`(순전파→손실→역전파→가중치 수정) → `predict.py`(오답 분석).

- **`ResNet18_test/`** — 개 vs 고양이 이진 분류. 전이학습(pretrained) vs 밑바닥 학습(scratch) vs
  linear-probe 3조건 비교. 노트북(`resnet18_cats_dogs.ipynb`, Colab용)과 CLI(`train.py`) 두 버전 제공.
  ```bash
  cd ResNet18_test
  python3 -m venv .venv
  .venv/bin/python -m pip install torch torchvision matplotlib jupyter
  .venv/bin/python train.py --epochs 5 --with-linear-probe
  ```
  장치는 CUDA → MPS(Apple GPU) → CPU 순 자동 선택. 데이터는 Oxford-IIIT Pet(토치비전 내장, 최초 실행 시 자동 다운로드).

### 웹 앱 — Todo

- **`ToDoApp/`**, **`ToDoApp_CLI/`** — 같은 계보의 1인용 할 일 관리 앱. 저장소는 SQLite/Supabase를
  `.env`의 `STORAGE` 한 줄로 전환하며, CLI(`todo.py`)와 웹(`app.py`, Flask, 포트 5001)이
  `todoapp/service.py`를 공유한다. 계층 구조(`models.py` → `service.py` → `stores/{sqlite,supabase}_store.py`)와
  테스트 규칙은 **`ToDoApp_CLI/CLAUDE.md`와 `HANDOFF.md`를 반드시 먼저 읽는다** — 이미 상세한
  프로젝트별 규칙(저장소 양쪽 동시 구현, 계층 경계 테스트, RLS 보안 범위 등)이 정리돼 있다.
  ```bash
  cd ToDoApp_CLI   # 또는 ToDoApp
  python3 -m pytest tests/ -q                                              # 전체
  python3 -m pytest tests/ -q --ignore=tests/test_supabase_integration.py  # 네트워크 없이
  python3 app.py   # 웹: http://localhost:5001
  ```
  ⚠️ macOS는 5000번 포트를 AirPlay가 점유하므로 5001을 쓴다([macos-port-5000-airplay 메모리] 참고).
  ⚠️ `todo.db`(실데이터)는 직접 지우거나 덮어쓰지 않는다 — 실험은 `DB_PATH`로 임시 파일을 지정한다.
  `mcp_todo.py`는 MCP(stdio JSON-RPC) 서버이며 루트 `.mcp.json`에 `todoapp`으로 등록돼 있다.

### 웹/게임

- **`TestGame_Grop1/`** — "PLANET DODGE", 바닐라 JS + Canvas 2D 세로 스크롤 아케이드 게임.
  빌드 도구 없음, `index.html`을 브라우저로 바로 열면 실행된다. 밸런스 조정은 `js/config.js` 하나만
  고치면 된다.
- **`TestGame_G/`** — 같은 계열의 또 다른 바닐라 JS 게임 실습(지형/장애물 회피형).

### 그 외

- **`blog_ggg/`** — Jekyll(Chirpy 테마) 개인 학습 기록 블로그. GitHub Actions로 GitHub Pages에 배포.
  새 글은 `_posts/YYYY-MM-DD-제목.md` 형식으로 추가한다.
- **`rolepicker_Review01/`** — Next.js(App Router) + Supabase 웹 서비스(조 역할 뽑기 + 타이머).
  Vercel 배포. `npm install && npm run dev`(포트 3000), `npm test`, `npm run typecheck`.
  프론트/백 경계를 `back/boundaries.test.ts`가 코드로 강제한다.
- **`hello_test/`** — 실습용 더미 저장소(가상 회사 소개 README뿐, 실제 코드 없음).

## 작업 규칙

이 워크스페이스에서 작업할 때는 아래 규칙을 코드보다 우선한다.

1. **모든 답변과 설명은 한국어로 한다.** 커밋 메시지·주석도 한국어, 코드 식별자·기술 용어는
   기존 관례대로 영어를 유지한다.
2. **사용자는 학습 중이다.** 코드를 고치거나 새로 짤 때는 결과만 던지지 말고, *왜 이렇게 고치는지*와
   *그 코드가 동작하는 원리*를 초보자도 따라올 수 있게 풀어서 설명한다. 비유를 먼저 들고 기술 설명을
   붙이는 순서가 이해에 도움이 된다. 정답만 주고 끝내지 말 것 — 배우는 과정이 목적이다.
3. **과제 제출을 성실하게 돕는다.** AIFFEL 과제·노트북 작업은 결과 수치를 지어내지 말고 실제로
   실행한 근거(로그·출력·스크린샷)를 확인한 뒤 보고한다. 요구사항이 모호하면 조용히 짐작해서
   진행하지 말고 먼저 확인한다.
4. **기존 파일을 지우거나 덮어쓰기 전에는 반드시 먼저 확인받는다.** 특히 다음은 실데이터/성과물이므로
   각별히 주의한다: `ToDoApp*/db/*.db`(실 데이터베이스), 각 프로젝트의 `outputs/`·`checkpoints/`
   (학습 결과물), 노트북(`.ipynb`, 실행 결과가 셀에 남아 있음), `plan.md`/`HANDOFF.md` 같은
   인수인계 문서. 실험용으로 다시 만들 수 있는 파일(`data/`, `.venv/`, `__pycache__/` 등, 각 프로젝트
   `.gitignore` 참고)은 예외로 취급해도 된다.
