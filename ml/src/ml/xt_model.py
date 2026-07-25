"""Expected-threat value model: V(position) -> P(shot value in next K actions).

A small MLP rather than a lookup grid so the surface is smooth and data
volume per cell is not a constraint; the published Karun Singh xT grid is
used as an external sanity reference in the evaluation, not as training data.
"""

from pathlib import Path

import numpy as np
import torch
from torch import nn

from ml.data import featurize

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "xt_model.pt"


class XTNet(nn.Module):
    def __init__(self, n_features: int = 4, hidden: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.net(x)
        return out.squeeze(-1)


def value_at(model: XTNet, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """V(x, y) as probabilities, for arrays of pitch coordinates."""
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(featurize(x, y)))
        return torch.sigmoid(logits).numpy()


def save_model(model: XTNet) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)


def load_model() -> XTNet:
    model = XTNet()
    model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
    model.eval()
    return model
