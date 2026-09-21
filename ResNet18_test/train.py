"""ResNet18로 개 vs 고양이 이진 분류: 사전학습 파인튜닝 vs 밑바닥 학습 비교.

데이터셋: torchvision 내장 OxfordIIITPet (인증 불필요, 공개 다운로드)
  - target_types="binary-category" -> 0=Cat, 1=Dog
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import transforms
from torchvision.datasets import OxfordIIITPet
from torchvision.models import ResNet18_Weights, resnet18

CLASS_NAMES = ["Cat", "Dog"]
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def pick_device() -> torch.device:
    """CUDA > MPS > CPU 순으로 쓸 수 있는 가속기를 고른다."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_transforms(img_size: int):
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(img_size, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize(int(img_size * 1.14)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    return train_tf, eval_tf


def binary_labels(ds: OxfordIIITPet) -> np.ndarray:
    """데이터셋의 이진 라벨(0=고양이, 1=개) 배열을 이미지 로딩 없이 얻는다."""
    for attr in ("_bin_labels", "_binary_labels"):
        if hasattr(ds, attr):
            return np.asarray(getattr(ds, attr))
    # 폴백: Oxford-IIIT Pet 규칙상 고양이 품종 파일명만 대문자로 시작한다.
    return np.asarray([0 if Path(p).name[0].isupper() else 1 for p in ds._images])


def stratified_subset(ds: OxfordIIITPet, n: int, seed: int) -> Subset:
    """클래스 비율을 유지하면서 n장만 뽑는다 (n<=0 이면 전체 사용)."""
    labels = binary_labels(ds)
    if n <= 0 or n >= len(labels):
        return Subset(ds, list(range(len(labels))))

    rng = np.random.default_rng(seed)
    picked: list[int] = []
    for cls in (0, 1):
        idx = np.flatnonzero(labels == cls)
        take = round(n * len(idx) / len(labels))
        picked.extend(rng.choice(idx, size=min(take, len(idx)), replace=False).tolist())
    rng.shuffle(picked)
    return Subset(ds, picked)


def build_model(pretrained: bool, freeze_backbone: bool) -> nn.Module:
    """ResNet18을 만들고 마지막 분류층(fc)만 2-클래스로 교체한다."""
    weights = ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    model = resnet18(weights=weights)
    if freeze_backbone:
        for p in model.parameters():
            p.requires_grad = False
    model.fc = nn.Linear(model.fc.in_features, 2)  # 교체된 fc는 항상 학습 대상
    return model


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, np.ndarray]:
    model.eval()
    correct = total = 0
    confusion = np.zeros((2, 2), dtype=int)  # [정답][예측]
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        pred = model(x).argmax(1)
        correct += (pred == y).sum().item()
        total += y.numel()
        for t, p in zip(y.cpu().numpy(), pred.cpu().numpy()):
            confusion[t, p] += 1
    return correct / max(total, 1), confusion


def run_one(name: str, cfg: dict, loaders: tuple[DataLoader, DataLoader],
            device: torch.device, args: argparse.Namespace) -> dict:
    train_loader, test_loader = loaders
    set_seed(args.seed)  # 조건 간 초기화·데이터 순서를 동일하게 맞춘다

    model = build_model(cfg["pretrained"], cfg["freeze_backbone"]).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=cfg["lr"], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()

    trainable = sum(p.numel() for p in params)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\n{'=' * 68}\n[{name}] {cfg['desc']}")
    print(f"  학습 파라미터 {trainable:,} / 전체 {total_params:,} | lr={cfg['lr']}")

    history: list[dict] = []
    best_acc = 0.0
    started = time.time()

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        seen = 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * y.size(0)
            seen += y.size(0)
        scheduler.step()

        acc, confusion = evaluate(model, test_loader, device)
        best_acc = max(best_acc, acc)
        history.append({"epoch": epoch, "train_loss": running_loss / seen, "test_acc": acc})
        print(f"  epoch {epoch}/{args.epochs}  train_loss={running_loss / seen:.4f}  test_acc={acc * 100:.2f}%")

    elapsed = time.time() - started
    final_acc, confusion = evaluate(model, test_loader, device)
    print(f"  -> 최종 시험 정확도 {final_acc * 100:.2f}% (최고 {best_acc * 100:.2f}%), {elapsed:.1f}s")
    print(f"     혼동행렬 [정답x예측]  Cat: {confusion[0].tolist()}   Dog: {confusion[1].tolist()}")

    return {
        "name": name,
        "desc": cfg["desc"],
        "lr": cfg["lr"],
        "trainable_params": trainable,
        "final_acc": final_acc,
        "best_acc": best_acc,
        "seconds": elapsed,
        "confusion": confusion.tolist(),
        "history": history,
    }


def save_plot(results: list[dict], out_path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    plt.figure(figsize=(7, 4.5))
    for r in results:
        xs = [h["epoch"] for h in r["history"]]
        ys = [h["test_acc"] * 100 for h in r["history"]]
        plt.plot(xs, ys, marker="o", label=f"{r['name']} (final {r['final_acc'] * 100:.1f}%)")
    plt.xlabel("epoch")
    plt.ylabel("test accuracy (%)")
    plt.title("ResNet18 Cat vs Dog - pretrained vs scratch")
    plt.ylim(40, 101)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=140)
    plt.close()
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="ResNet18 개/고양이 분류: 사전학습 vs 스크래치")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--train-size", type=int, default=1500, help="학습에 쓸 이미지 수 (0=전체)")
    ap.add_argument("--test-size", type=int, default=800, help="시험에 쓸 이미지 수 (0=전체)")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--img-size", type=int, default=224)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lr-pretrained", type=float, default=3e-4)
    ap.add_argument("--lr-scratch", type=float, default=1e-3)
    ap.add_argument("--lr-linear", type=float, default=1e-3)
    ap.add_argument("--with-linear-probe", action="store_true",
                    help="백본을 얼리고 fc만 학습하는 조건을 추가로 실행")
    ap.add_argument("--data-root", default="./data")
    ap.add_argument("--out-dir", default="./outputs")
    args = ap.parse_args()

    device = pick_device()
    print(f"device: {device}")

    train_tf, eval_tf = build_transforms(args.img_size)
    root = Path(args.data_root)
    root.mkdir(parents=True, exist_ok=True)

    common = dict(root=str(root), target_types="binary-category", download=True)
    train_full = OxfordIIITPet(split="trainval", transform=train_tf, **common)
    test_full = OxfordIIITPet(split="test", transform=eval_tf, **common)

    train_ds = stratified_subset(train_full, args.train_size, args.seed)
    test_ds = stratified_subset(test_full, args.test_size, args.seed + 1)

    tr_lab = binary_labels(train_full)[train_ds.indices]
    te_lab = binary_labels(test_full)[test_ds.indices]
    print(f"학습 {len(train_ds)}장 (Cat {int((tr_lab == 0).sum())} / Dog {int((tr_lab == 1).sum())})"
          f"  |  시험 {len(test_ds)}장 (Cat {int((te_lab == 0).sum())} / Dog {int((te_lab == 1).sum())})")
    print(f"항상 Dog로 찍었을 때 정확도(기준선): {(te_lab == 1).mean() * 100:.2f}%")

    loader_kw = dict(batch_size=args.batch_size, num_workers=args.workers,
                     pin_memory=(device.type == "cuda"), persistent_workers=args.workers > 0)
    train_loader = DataLoader(train_ds, shuffle=True, **loader_kw)
    test_loader = DataLoader(test_ds, shuffle=False, **loader_kw)

    configs = {
        "pretrained": {"desc": "ImageNet 사전학습 가중치 로드 + fc 교체 후 전체 파인튜닝",
                       "pretrained": True, "freeze_backbone": False, "lr": args.lr_pretrained},
        "scratch": {"desc": "가중치 랜덤 초기화, 밑바닥부터 학습",
                    "pretrained": False, "freeze_backbone": False, "lr": args.lr_scratch},
    }
    if args.with_linear_probe:
        configs["linear-probe"] = {"desc": "사전학습 백본 동결, 교체한 fc만 학습",
                                   "pretrained": True, "freeze_backbone": True, "lr": args.lr_linear}

    results = [run_one(name, cfg, (train_loader, test_loader), device, args)
               for name, cfg in configs.items()]

    print(f"\n{'=' * 68}\n최종 비교 (시험 {len(test_ds)}장, {args.epochs} epoch)")
    print(f"{'조건':<14}{'최종 정확도':>12}{'최고 정확도':>12}{'학습 파라미터':>16}{'시간(s)':>10}")
    for r in results:
        print(f"{r['name']:<14}{r['final_acc'] * 100:>11.2f}%{r['best_acc'] * 100:>11.2f}%"
              f"{r['trainable_params']:>16,}{r['seconds']:>10.1f}")

    pre = next(r for r in results if r["name"] == "pretrained")
    scr = next(r for r in results if r["name"] == "scratch")
    print(f"\n사전학습 - 스크래치 = {(pre['final_acc'] - scr['final_acc']) * 100:+.2f}%p")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"device": str(device), "args": vars(args), "class_names": CLASS_NAMES,
               "train_size": len(train_ds), "test_size": len(test_ds), "results": results}
    (out_dir / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    plotted = save_plot(results, out_dir / "comparison.png")
    print(f"\n저장: {out_dir / 'results.json'}" + (f", {out_dir / 'comparison.png'}" if plotted else ""))


if __name__ == "__main__":
    main()
