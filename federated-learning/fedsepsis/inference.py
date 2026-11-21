"""Scoring one window inside a hospital unit, with the audit fields the Audit agent stores."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import joblib
import numpy as np
import torch

from . import models as M
from .config import N_FEATURES, WINDOW
from .fedstats import Preprocessor


class HospitalPredictor:
    def __init__(self, folder):
        with open(os.path.join(folder, "model_card.json")) as f:
            self.card = json.load(f)
        with open(os.path.join(folder, "preprocessor.json")) as f:
            self.prep = Preprocessor.from_dict(json.load(f))
        self.neural = {}
        for name in self.card["neural_models"]:
            m = M.build(name)
            m.load_state_dict(torch.load(os.path.join(folder, f"{name}.pt"), map_location="cpu"))
            self.neural[name] = m.eval()
        trees = os.path.join(folder, "trees.joblib")
        self.tree_sets = joblib.load(trees) if os.path.exists(trees) else []
        self.cal = joblib.load(os.path.join(folder, "calibrators.joblib"))

    @torch.no_grad()
    def predict(self, window: np.ndarray) -> dict:
        """window: raw (16, 39) values with NaN for missing."""
        window = np.asarray(window, np.float32)
        if window.shape != (WINDOW, N_FEATURES):
            raise ValueError(f"expected ({WINDOW}, {N_FEATURES}), got {window.shape}")
        x = self.prep.transform(window[None])
        raw = {n: float(torch.sigmoid(m(torch.from_numpy(x)))[0]) for n, m in self.neural.items()}
        if self.tree_sets:
            total = sum(n for _, n in self.tree_sets)
            for name in self.tree_sets[0][0]:
                raw[name] = float(sum(t[name].predict_proba(x.reshape(1, -1))[0, 1] * n
                                      for t, n in self.tree_sets) / total)
        weights = self.card["ensemble_weights"]
        calibrated = {m: float(self.cal[m].predict([r])[0]) for m, r in raw.items()}
        p = float(sum(calibrated[m] * w for m, w in weights.items()))
        thr = self.card["threshold"]
        return {"probability": p, "alert": p >= thr, "raw": raw, "calibrated": calibrated,
                "audit": {"hospital_id": self.card["hospital_id"],
                          "model_version": self.card["model_version"],
                          "trained_on": self.card["trained_on"],
                          "input_sha256": hashlib.sha256(window.tobytes()).hexdigest(),
                          "ensemble_weights": weights, "threshold": thr,
                          "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}}
