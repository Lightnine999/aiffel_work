"""MNIST 분류 모델 정의 (MLP / CNN 두 가지)."""

import torch.nn as nn


class SimpleMLP(nn.Module):
    """완전연결 신경망.

    비유: 사진을 잘게 잘라 한 줄(784칸)로 늘어놓고 보는 방식.
    빠르지만 '픽셀이 어디에 있었는지'라는 위치 정보를 잃는다.
    """

    def __init__(self, num_classes: int = 10) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),                 # (B, 1, 28, 28) -> (B, 784)
            nn.Linear(28 * 28, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, num_classes),  # 출력 10개 = 숫자 0~9 점수
        )

    def forward(self, x):
        return self.net(x)


class SimpleCNN(nn.Module):
    """합성곱 신경망.

    비유: 돋보기(3x3 필터)로 이미지를 훑으며 선·모서리 같은 패턴을 모으는 방식.
    이미지를 2D 그대로 보기 때문에 손글씨에 훨씬 강하다.
    """

    def __init__(self, num_classes: int = 10) -> None:
        super().__init__()
        self.features = nn.Sequential(
            # 28x28 -> (padding=1이라 크기 유지) -> MaxPool로 14x14
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 14x14 -> 7x7
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),                    # (B, 64, 7, 7) -> (B, 3136)
            nn.Linear(64 * 7 * 7, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


def build_model(name: str = "cnn", num_classes: int = 10) -> nn.Module:
    """이름으로 모델을 만든다. 'cnn' 또는 'mlp'."""
    registry = {"cnn": SimpleCNN, "mlp": SimpleMLP}
    if name not in registry:
        raise ValueError(f"알 수 없는 모델: {name!r} (가능: {list(registry)})")
    return registry[name](num_classes=num_classes)
