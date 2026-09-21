# ResNet18 개 vs 고양이 — 전이학습 vs 밑바닥 학습

torchvision 사전학습 ResNet18의 마지막 층만 2-클래스로 갈아끼워 파인튜닝하고,
같은 조건에서 랜덤 초기화로 밑바닥부터 학습한 결과와 비교한다.

## 두 가지 사용법

| 파일 | 용도 |
|---|---|
| **`resnet18_cats_dogs.ipynb`** | **공부용 노트북.** 설명 + 그림 + 실험이 한 파일에. Colab에 그대로 올려서 실행 가능 |
| `train.py` | CLI 버전. 같은 실험을 옵션으로 조절해 한 번에 돌린다 |

### Google Colab에서

1. [colab.research.google.com](https://colab.research.google.com) → **파일 → 노트북 업로드** →
   `resnet18_cats_dogs.ipynb` 선택
2. **런타임 → 런타임 유형 변경 → T4 GPU**
3. **런타임 → 모두 실행**

라이브러리 설치와 데이터 다운로드는 노트북 안에서 알아서 처리한다.
(Colab에는 torch가 이미 있어 설치 셀은 대개 건너뛴다.)

### 로컬에서

```bash
cd ResNet18_test
python3 -m venv .venv
.venv/bin/python -m pip install torch torchvision matplotlib jupyter
.venv/bin/jupyter notebook resnet18_cats_dogs.ipynb   # 노트북
.venv/bin/python train.py --epochs 5 --with-linear-probe   # 또는 CLI
```

`train.py` 주요 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--epochs` | 3 | 모든 조건에 동일 적용 |
| `--train-size` / `--test-size` | 1500 / 800 | `0`이면 전체 사용 |
| `--batch-size` | 32 | |
| `--with-linear-probe` | off | 백본 동결 + fc만 학습하는 조건 추가 |

장치는 CUDA → MPS(Apple GPU) → CPU 순으로 자동 선택한다.

## 데이터

**Oxford-IIIT Pet** (torchvision 내장, 인증·토큰 불필요).
`target_types="binary-category"`가 품종 37종을 `0=Cat / 1=Dog` 이진 라벨로 바로 내려준다.
Kaggle Dogs vs. Cats는 계정·API 키가 필요해 쓰지 않았다.

- 전체: trainval 3,680장 / test 3,669장 (공식 분할)
- 최초 실행 시 약 792MB를 `data/`에 내려받는다 (`robots.ox.ac.uk`, 공개 배포)
- 기본값은 학습 2,000장 / 시험 1,000장만 **층화 추출**(클래스 비율 유지)

## 비교 조건

| 조건 | 가중치 | 학습 대상 | lr |
|---|---|---|---|
| `pretrained` | ImageNet 사전학습 | fc 교체 후 **전체** 파인튜닝 | 3e-4 |
| `scratch` | 랜덤 초기화 | 전체 | 1e-3 |
| `linear-probe` | ImageNet 사전학습 | 교체한 fc만 (백본 동결) | 1e-3 |

`scratch`에 더 큰 lr을 준 것은 랜덤 초기화 쪽이 불리하지 않도록 한 조치다.
초기화 시드·데이터 순서·증강·에폭 수는 모든 조건에서 동일하다.

## 실행 결과 (2026-09-10, Apple MPS)

학습 2,000장(Cat 646 / Dog 1,354) · 시험 1,000장(Cat 322 / Dog 678) · 5 에폭
기준선(항상 Dog로 찍기) = **67.80%**

| 조건 | 시험 정확도 | 학습 파라미터 | 시간 |
|---|---|---|---|
| pretrained | **99.30%** | 11,177,538 | 46.6s |
| scratch | **70.80%** | 11,177,538 | 39.2s |
| linear-probe | 97.90% | 1,026 | 14.5s |

**사전학습 − 스크래치 = +28.50%p**

에폭별 시험 정확도:

| epoch | pretrained | scratch | linear-probe |
|---|---|---|---|
| 1 | 95.60% | 68.20% | 94.80% |
| 2 | 97.20% | 64.80% | 97.10% |
| 3 | 98.70% | 66.70% | 97.40% |
| 4 | 99.30% | 69.60% | 97.90% |
| 5 | 99.30% | 70.80% | 97.90% |

관찰:

- 스크래치는 5 에폭 내내 기준선(67.80%) 언저리를 벗어나지 못했다. 혼동행렬을 보면
  고양이 322장 중 145장만 맞혀 사실상 "대체로 Dog로 찍는" 상태다. 2,000장·5 에폭은
  1,100만 파라미터를 처음부터 학습시키기에 턱없이 부족하다.
- 백본을 통째로 얼리고 1,026개 파라미터만 학습한 linear-probe가 97.90%다.
  ImageNet 특징만으로도 개/고양이 구분은 거의 끝난다는 뜻이고, 이것이 전이학습의 효과다.

## 산출물

- `outputs/results.json` — 조건별 에폭 로그·최종 정확도·혼동행렬
- `outputs/comparison.png` — 에폭별 시험 정확도 곡선
