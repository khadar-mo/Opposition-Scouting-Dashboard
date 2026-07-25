"""Train the xT value model. Run: python -m ml.train"""

import json

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml.data import build_dataset, load_actions, split_by_match
from ml.xt_model import ARTIFACTS_DIR, XTNet, save_model, value_at

EPOCHS = 40
BATCH = 4096
LR = 1e-3
PATIENCE = 5


def train() -> dict[str, float]:
    torch.manual_seed(7)
    actions = load_actions()
    print(f"{actions.height} on-ball actions loaded")
    ds = build_dataset(actions)
    train_ds, val_ds = split_by_match(ds)
    print(
        f"train: {len(train_ds.labels)} samples / "
        f"{len(np.unique(train_ds.match_ids))} matches; "
        f"val: {len(val_ds.labels)} samples / "
        f"{len(np.unique(val_ds.match_ids))} matches"
    )

    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(train_ds.features), torch.from_numpy(train_ds.labels)
        ),
        batch_size=BATCH,
        shuffle=True,
    )
    x_val = torch.from_numpy(val_ds.features)
    y_val = torch.from_numpy(val_ds.labels)

    model = XTNet()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.BCEWithLogitsLoss()

    best_val = float("inf")
    best_state = None
    stale = 0
    for epoch in range(EPOCHS):
        model.train()
        total = 0.0
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            total += loss.item() * len(xb)
        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(x_val), y_val).item()
        print(f"epoch {epoch + 1:02d}  train {total / len(train_ds.labels):.4f}  "
              f"val {val_loss:.4f}")
        if val_loss < best_val - 1e-5:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= PATIENCE:
                print("early stop")
                break

    assert best_state is not None
    model.load_state_dict(best_state)
    save_model(model)

    # Baseline: predict the constant base rate.
    base = float(np.mean(train_ds.labels))
    eps = 1e-7
    p = np.clip(base, eps, 1 - eps)
    y = val_ds.labels
    baseline_bce = float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))))

    # Quick shape checks on the learned surface.
    center_line = value_at(model, np.array([60.0]), np.array([40.0]))[0]
    penalty_spot = value_at(model, np.array([108.0]), np.array([40.0]))[0]
    own_box = value_at(model, np.array([10.0]), np.array([40.0]))[0]
    metrics = {
        "val_bce": best_val,
        "baseline_bce": baseline_bce,
        "v_own_box": float(own_box),
        "v_center_line": float(center_line),
        "v_penalty_spot": float(penalty_spot),
    }
    (ARTIFACTS_DIR / "train_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    train()
