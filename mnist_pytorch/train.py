"""MNIST 학습 스크립트.

사용법:
    python train.py                              # MNIST + CNN, 5 epoch (기본)
    python train.py --dataset fashion            # FashionMNIST로
    python train.py --model mlp --epochs 3       # MLP로 빠르게
    python train.py --dataset fashion --epochs 10
"""

import argparse
import time
from pathlib import Path

import torch
import torch.nn as nn

from data import get_dataloaders
from model import build_model

CKPT_DIR = Path(__file__).parent / "checkpoints"


def pick_device() -> torch.device:
    """Apple Silicon(MPS) > NVIDIA(CUDA) > CPU 순으로 고른다."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def run_epoch(model, loader, device, criterion, optimizer=None):
    """optimizer가 있으면 학습, 없으면 평가. (평균 손실, 정확도)를 돌려준다."""
    is_train = optimizer is not None
    model.train(is_train)

    total_loss, correct, total = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)

            outputs = model(images)          # 앞으로: 예측 10개 점수
            loss = criterion(outputs, labels)  # 얼마나 틀렸나

            if is_train:
                optimizer.zero_grad()  # 이전 기울기 초기화
                loss.backward()        # 뒤로: 각 가중치의 책임을 계산
                optimizer.step()       # 가중치를 조금 수정

            total_loss += loss.item() * labels.size(0)
            correct += (outputs.argmax(dim=1) == labels).sum().item()
            total += labels.size(0)

    return total_loss / total, correct / total


def parse_args():
    p = argparse.ArgumentParser(description="MNIST 손글씨 분류기 학습")
    p.add_argument("--dataset", default="mnist", choices=["mnist", "fashion"])
    p.add_argument("--model", default="cnn", choices=["cnn", "mlp"])
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--no-augment", action="store_true", help="데이터 증강 끄기")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()
    torch.manual_seed(args.seed)  # 재현 가능하게

    device = pick_device()
    print(f"장치: {device} | 데이터셋: {args.dataset} | 모델: {args.model} | epoch: {args.epochs}")

    train_loader, test_loader = get_dataloaders(
        dataset=args.dataset,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        augment=not args.no_augment,
    )

    model = build_model(args.model).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"파라미터 수: {n_params:,}\n")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    CKPT_DIR.mkdir(exist_ok=True)
    ckpt_path = CKPT_DIR / f"{args.dataset}_{args.model}_best.pt"
    best_acc = 0.0

    for epoch in range(1, args.epochs + 1):
        started = time.time()
        train_loss, train_acc = run_epoch(model, train_loader, device, criterion, optimizer)
        test_loss, test_acc = run_epoch(model, test_loader, device, criterion)
        scheduler.step()

        mark = ""
        if test_acc > best_acc:
            best_acc = test_acc
            torch.save({"dataset": args.dataset, "model": args.model,
                        "state_dict": model.state_dict(),
                        "test_acc": test_acc}, ckpt_path)
            mark = "  <- 저장"

        print(
            f"[{epoch:2d}/{args.epochs}] "
            f"train loss {train_loss:.4f} acc {train_acc*100:5.2f}% | "
            f"test loss {test_loss:.4f} acc {test_acc*100:5.2f}% | "
            f"{time.time() - started:.1f}s{mark}"
        )

    print(f"\n최고 테스트 정확도: {best_acc*100:.2f}%")
    print(f"저장 위치: {ckpt_path}")


if __name__ == "__main__":
    main()
