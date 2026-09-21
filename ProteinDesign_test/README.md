# ProteinDesign_test — RFdiffusion + ProteinMPNN 파이프라인

RFdiffusion으로 단백질 백본(뼈대 구조)을 생성하고, ProteinMPNN으로 그 백본에 맞는
아미노산 서열을 설계하는 2단계 파이프라인 실습.

## 왜 Colab인가

RFdiffusion은 NVIDIA의 SE3Transformer(DGL + CUDA 커스텀 커널)에 의존하는데, 이
저장소를 작업 중인 Mac(Apple M5 Pro)은 NVIDIA GPU가 없어 로컬 실행이 불가능하다.
그래서 GPU가 제공되는 Google Colab에서 실행한다.

## 구조

- `colab/rfdiffusion_proteinmpnn.ipynb` — 실제로 실행한 Colab 노트북 (한국어 설명 포함,
  gugudan.ipynb와 같은 스타일: 비유로 먼저 설명 → 코드 → 결과 확인)

## 파이프라인 요약

1. **RFdiffusion** — 무조건부(unconditional) 100잔기 단일 사슬 백본 생성.
   공식 요구 환경(python 3.9 + torch 1.9 + cudatoolkit 11.1 + dgl-cuda11.1)이 Colab
   기본 커널(python 3.13 + torch 2.11)과 맞지 않아, `conda`로 별도 환경(`SE3nv`,
   저장소의 `env/SE3nv.yml` 그대로 사용)을 만들고 그 환경의 파이썬을 서브프로세스로
   호출하는 방식을 쓴다.
2. **ProteinMPNN** — 순수 PyTorch라 DGL 의존성이 없어 Colab 기본 커널에서 바로 실행.
   RFdiffusion이 만든 백본(PDB)을 jsonl로 변환한 뒤, 그 좌표에 맞는 서열을 샘플링.

## 실행 방법

Colab에서 노트북을 열고 `런타임 > 런타임 유형 변경 > T4 GPU`로 설정한 뒤, 위에서부터
순서대로 셀을 실행한다. 첫 실행 시 conda 환경 생성에 5~10분 정도 걸린다(캐시되면
이후 재실행은 더 빠름).
