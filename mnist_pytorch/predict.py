"""학습된 모델로 예측해보고, 틀린 것들을 이미지로 저장한다.

사용법:
    python predict.py                                   # MNIST + CNN
    python predict.py --dataset fashion                 # FashionMNIST + CNN
    python predict.py --dataset fashion --model mlp
"""

import argparse
from pathlib import Path

import torch

from data import denormalize, get_dataloaders, get_spec
from model import build_model
from train import pick_device

CKPT_DIR = Path(__file__).parent / "checkpoints"
OUT_DIR = Path(__file__).parent / "outputs"


def load_model(dataset: str, name: str, device: torch.device):
    ckpt_path = CKPT_DIR / f"{dataset}_{name}_best.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(
            f"체크포인트가 없습니다: {ckpt_path}\n"
            f"먼저 `python train.py --dataset {dataset} --model {name}` 을 실행하세요."
        )
    ckpt = torch.load(ckpt_path, map_location=device)
    model = build_model(name).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    print(f"불러옴: {ckpt_path.name} (학습 당시 정확도 {ckpt['test_acc']*100:.2f}%)")
    return model


@torch.no_grad()
def collect_predictions(model, loader, device, num_classes: int = 10):
    """전체 테스트셋 예측을 모으고, 오답 샘플과 혼동 행렬을 함께 만든다."""
    per_class_correct = torch.zeros(num_classes)
    per_class_total = torch.zeros(num_classes)
    confusion = torch.zeros(num_classes, num_classes, dtype=torch.long)  # [정답][예측]
    wrong = []  # (이미지, 정답, 예측, 확신도)

    for images, labels in loader:
        images = images.to(device)
        probs = model(images).softmax(dim=1).cpu()
        preds = probs.argmax(dim=1)

        for true, pred in zip(labels.tolist(), preds.tolist()):
            confusion[true][pred] += 1

        for i in range(num_classes):
            mask = labels == i
            per_class_total[i] += mask.sum()
            per_class_correct[i] += (preds[mask] == i).sum()

        for idx in (preds != labels).nonzero(as_tuple=True)[0]:
            if len(wrong) < 24:
                wrong.append((images[idx].cpu(), labels[idx].item(),
                              preds[idx].item(), probs[idx].max().item()))

    return per_class_correct, per_class_total, confusion, wrong


def _use_korean_font(matplotlib) -> None:
    """한글 제목이 네모(□)로 깨지지 않게 시스템 한글 폰트를 잡아준다."""
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Pretendard", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
        if name in installed:
            matplotlib.rcParams["font.family"] = name
            break
    matplotlib.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지


def save_mistakes(wrong, spec, out_path: Path):
    """오답 24장을 격자 이미지로 저장한다. matplotlib이 없으면 건너뛴다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib이 없어 오답 이미지는 건너뜁니다. (pip install matplotlib)")
        return

    _use_korean_font(matplotlib)

    fig, axes = plt.subplots(4, 6, figsize=(13, 9))
    for ax, (img, true, pred, conf) in zip(axes.flat, wrong):
        ax.imshow(denormalize(img, spec).squeeze(), cmap="gray")
        ax.set_title(
            f"정답 {spec.classes[true]}\n예측 {spec.classes[pred]} ({conf*100:.0f}%)",
            fontsize=8,
        )
        ax.axis("off")
    for ax in axes.flat[len(wrong):]:
        ax.axis("off")

    fig.suptitle("모델이 틀린 것들", fontsize=14)
    fig.tight_layout()
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=120)
    print(f"오답 이미지 저장: {out_path}")


def print_top_confusions(confusion, spec, top_n: int = 5) -> None:
    """어떤 클래스를 어떤 클래스로 헷갈리는지 상위 N개."""
    pairs = []
    for true in range(len(spec.classes)):
        for pred in range(len(spec.classes)):
            if true != pred and confusion[true][pred] > 0:
                pairs.append((confusion[true][pred].item(), true, pred))
    pairs.sort(reverse=True)

    print(f"\n가장 많이 헷갈린 조합 Top {top_n}")
    for count, true, pred in pairs[:top_n]:
        print(f"  {spec.classes[true]} -> {spec.classes[pred]}: {count}장")


def main():
    parser = argparse.ArgumentParser(description="예측 및 오답 분석")
    parser.add_argument("--dataset", default="mnist", choices=["mnist", "fashion"])
    parser.add_argument("--model", default="cnn", choices=["cnn", "mlp"])
    parser.add_argument("--num-workers", type=int, default=2)
    args = parser.parse_args()

    spec = get_spec(args.dataset)
    device = pick_device()
    model = load_model(args.dataset, args.model, device)
    _, test_loader = get_dataloaders(
        dataset=args.dataset, num_workers=args.num_workers, augment=False
    )

    correct, total, confusion, wrong = collect_predictions(model, test_loader, device)

    width = max(len(name) for name in spec.classes)
    print("\n클래스별 정확도")
    for idx, name in enumerate(spec.classes):
        acc = correct[idx] / total[idx] * 100
        bar = "#" * int(acc / 100 * 30)
        print(f"  {name:>{width}}: {acc:5.2f}%  {bar}")

    overall = correct.sum() / total.sum() * 100
    print(f"\n전체 정확도: {overall:.2f}%  (틀린 개수 {int(total.sum() - correct.sum())}장)")

    print_top_confusions(confusion, spec)

    if wrong:
        save_mistakes(wrong, spec, OUT_DIR / f"{args.dataset}_{args.model}_mistakes.png")


if __name__ == "__main__":
    main()
