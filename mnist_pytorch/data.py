"""데이터 로딩 (MNIST / FashionMNIST). 처음 실행하면 data/ 로 자동 다운로드한다."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from torch.utils.data import DataLoader
from torchvision import datasets, transforms

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class DatasetSpec:
    """데이터셋 하나를 다루는 데 필요한 모든 정보."""

    cls: Callable          # torchvision 데이터셋 클래스
    mean: float            # 픽셀 평균 (정규화용)
    std: float             # 픽셀 표준편차
    flip: bool             # 좌우 반전 증강이 말이 되는가
    classes: list = field(default_factory=list)  # 라벨 이름


# 정규화 값은 각 데이터셋 학습셋 전체에서 계산한 관례값이다.
# flip: 숫자 2를 뒤집으면 2가 아니지만, 티셔츠는 뒤집어도 티셔츠다.
DATASETS = {
    "mnist": DatasetSpec(
        cls=datasets.MNIST,
        mean=0.1307,
        std=0.3081,
        flip=False,
        classes=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    ),
    "fashion": DatasetSpec(
        cls=datasets.FashionMNIST,
        mean=0.2860,
        std=0.3530,
        flip=True,
        classes=["티셔츠", "바지", "풀오버", "드레스", "코트",
                 "샌들", "셔츠", "스니커즈", "가방", "앵클부츠"],
    ),
}


def get_spec(dataset: str) -> DatasetSpec:
    if dataset not in DATASETS:
        raise ValueError(f"알 수 없는 데이터셋: {dataset!r} (가능: {list(DATASETS)})")
    return DATASETS[dataset]


def build_transforms(dataset: str, train: bool) -> transforms.Compose:
    """학습용에만 증강을 넣어 과적합을 줄인다."""
    spec = get_spec(dataset)
    steps = []
    if train:
        if spec.flip:
            steps.append(transforms.RandomHorizontalFlip())
            steps.append(transforms.RandomAffine(degrees=5, translate=(0.1, 0.1)))
        else:
            steps.append(transforms.RandomAffine(degrees=10, translate=(0.1, 0.1)))
    steps += [
        transforms.ToTensor(),                              # 0~255 -> 0.0~1.0
        transforms.Normalize((spec.mean,), (spec.std,)),
    ]
    return transforms.Compose(steps)


def get_datasets(dataset: str = "mnist", augment: bool = True):
    """학습셋 60,000장 / 테스트셋 10,000장. 두 데이터셋 모두 28x28 흑백으로 같다."""
    spec = get_spec(dataset)
    train_ds = spec.cls(DATA_DIR, train=True, download=True,
                        transform=build_transforms(dataset, train=augment))
    test_ds = spec.cls(DATA_DIR, train=False, download=True,
                       transform=build_transforms(dataset, train=False))
    return train_ds, test_ds


def get_dataloaders(dataset: str = "mnist", batch_size: int = 128,
                    num_workers: int = 2, augment: bool = True):
    """미니배치 단위로 데이터를 흘려보내는 DataLoader 한 쌍."""
    train_ds, test_ds = get_datasets(dataset, augment=augment)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, pin_memory=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size * 2, shuffle=False,
                             num_workers=num_workers, pin_memory=False)
    return train_loader, test_loader


def denormalize(tensor, spec: DatasetSpec):
    """정규화를 되돌린다. 이미지를 눈으로 보려면 필요."""
    return (tensor * spec.std + spec.mean).clamp(0, 1)
