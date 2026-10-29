"""Isolation Forest anomaly-detection baseline for Graphagate.
"""

import random
import argparse

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score

from graphagate.config import TGNConfig
from graphagate.data.stream_synthetic import generate_streaming_data, stream_kwargs_from_cfg
from graphagate.eval_common import (
    binary_metrics,
    causal_hist_features,
    causal_precursor_factor,
    incident_report,
)

# IF's hyperparameters
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 300,
    "max_samples": "auto",
    "max_features": 1.0,
    "contamination": "auto",
}


def _build_features(msg, src, dst, node_features, y, *, label_horizon: int):
    """Per-event feature matrix for the Isolation Forest.

    The 7-dim edge feature ``msg[i]`` concatenated with the 16-dim static attributes of
    both endpoints (device, destination resource) — 39 dims — PLUS the 3-dim causal
    interaction-history features (per-pair / per-src benign access counts; see
    ``graphagate.eval_common``), giving a 42-dim vector. The history columns are the same
    family of counters the TGN maintains online.
    """
    msg_np = msg.numpy()                       # [N, msg_dim]
    nf_np = node_features.numpy()              # [num_nodes, 16]
    src_feat = nf_np[src.numpy()]              # [N, 16]  device attributes
    dst_feat = nf_np[dst.numpy()]              # [N, 16]  destination (resource) attributes
    hist = causal_hist_features(src.numpy(), dst.numpy(), y.numpy(),
                                label_horizon=label_horizon)  # [N, 3] benign-gated up to the horizon
    return np.concatenate([msg_np, src_feat, dst_feat, hist], axis=1)


def isolation_forest_baseline(cfg: TGNConfig = TGNConfig(), stream=None, use_precursor: bool = True):
    """Fit/evaluate the Isolation Forest under the TGN protocol; see the module docstring.

    ``stream`` is an optional pre-built :class:`SyntheticStream` (the data-budget curve
    passes a truncated tail so every method sees the same events); ``None`` generates it
    from ``cfg`` exactly as before. ``use_precursor=False`` leaves the scores as the forest
    produced them (no kill-chain factor in model selection, calibration or test).
    """
    # Seed everything up front for reproducibility (the generator re-seeds numpy
    # and stdlib ``random`` internally too, but we seed here so the IsolationForest
    # and any incidental randomness are deterministic as well).
    np.random.seed(cfg.seed)
    random.seed(cfg.seed)

    if stream is None:
        print("Generating synthetic streaming data (same params as TGN)...")
        stream = generate_streaming_data(**stream_kwargs_from_cfg(cfg))
    # Tabular actor = the DEVICE node (hardware id), the v2 analogue of the old
    # IP-keyed src; the access target stays the resource.
    src, dst, t, msg, y, types, node_features = (
        stream.device, stream.dst, stream.t, stream.msg, stream.y, stream.types,
        stream.node_features,
    )

    # Chronological split (the stream is already time-ordered → no shuffling). Computed
    # before the features: ``calibration_end`` is the label horizon of the history counters.
    n = len(src)
    n_train = int(n * cfg.train_frac)
    n_calibration = int(n * cfg.val_frac)
    train_end, calibration_end = n_train, n_train + n_calibration

    # Per-event features incl. causal history counts (no graph structure / temporal context).
    X = _build_features(msg, src, dst, node_features, y, label_horizon=calibration_end)
    y_np = y.numpy()
    types_np = types.numpy()

    # Kill-chain precursor prior (same multiplicative factor + params as the TGN), applied
    # to the calibration/test scores so the baseline gets the SAME recon→lateral boost.
    # Measured on v5 (seeds 1000-1004, 200k): the factor alone ranks lateral at AUC 0.82-0.96,
    # the forest without it is at chance (0.43-0.53) — hence the ``use_precursor=False`` row.
    if use_precursor:
        precursor_fac = causal_precursor_factor(
            src.numpy(), t.numpy(), msg.numpy(), cfg.precursor_half_life, cfg.precursor_max_boost
        )
    else:
        precursor_fac = np.ones(len(src), dtype=np.float64)

    X_train, y_train = X[:train_end], y_np[:train_end]
    X_calibration, y_calibration = X[train_end:calibration_end], y_np[train_end:calibration_end]
    X_test, y_test = X[calibration_end:], y_np[calibration_end:]
    test_types = types_np[calibration_end:]

    # --- FIT (unsupervised, benign train events only) ---
    print("--- UNSUPERVISED TRAINING START (Isolation Forest) ---")
    X_train_benign = X_train[y_train == 0]
    print(f"Train benign: {X_train_benign.shape[0]} / {X_train.shape[0]} events")

    print(f"Fixed parameters: {ISOLATION_FOREST_PARAMS}")
    model = IsolationForest(
        random_state=cfg.seed,
        n_jobs=-1,
        **ISOLATION_FOREST_PARAMS,
    )
    model.fit(X_train_benign)

    # Anomaly score: higher = more anomalous (matches the TGN's 1 - P(benign)).
    def anomaly_score(features):
        return -model.score_samples(features)

    # --- THRESHOLD CALIBRATION (held-out benign slice) -----------------------
    print("\n--- THRESHOLD CALIBRATION (on the benign calibration stream) ---")
    calibration_scores = (
        anomaly_score(X_calibration) * precursor_fac[train_end:calibration_end]
    )
    benign_calibration_scores = calibration_scores[y_calibration == 0]
    if benign_calibration_scores.size == 0:
        raise RuntimeError("No benign events in the calibration slice for calibration.")
    threshold = float(np.quantile(benign_calibration_scores, 1.0 - cfg.target_fpr))
    print(
        f"Benign calibration score: mean={benign_calibration_scores.mean():.4f} "
        f"p95={np.quantile(benign_calibration_scores, 0.95):.4f} | "
        f"threshold@FPR={cfg.target_fpr}: {threshold:.4f}"
    )

    # --- TEST EVALUATION ----
    print("\n--- INFERENCE / ANOMALY DETECTION PHASE START ---")
    test_scores = anomaly_score(X_test) * precursor_fac[calibration_end:]

    auc = roc_auc_score(y_test, test_scores)
    ap = average_precision_score(y_test, test_scores)
    precision, recall = binary_metrics(test_scores, y_test, threshold)
    print(f"Test Stream | AUC: {auc:.4f} | AP: {ap:.4f}")
    print(f"At threshold {threshold:.4f} | Precision: {precision:.4f} | Recall: {recall:.4f}")

    # --- PER-ANOMALY-TYPE BREAKDOWN ---
    # AUC/AP per type computed benign (type 0) vs that type only, so the aggregate
    # cannot mask a class the detector handles poorly. As for the TGN: contextual
    # anomalies are near-trivial (separable on edge features), while policy and
    # lateral anomalies share benign edge features and are the genuinely hard cases
    # for a non-relational detector — that is exactly the contrast this baseline
    # is meant to expose.
    print("\n--- PER-ANOMALY-TYPE METRICS ---")
    per_type = {}
    benign = test_types == 0
    for type_id, name in ((1, "policy"), (2, "contextual"), (3, "lateral"),
                          (4, "cred-theft"), (5, "exfil"), (6, "benign-denied")):
        sel = benign | (test_types == type_id)
        s_sel, l_sel = test_scores[sel], (test_types[sel] == type_id).astype(int)
        if l_sel.sum() == 0:
            continue
        t_auc = roc_auc_score(l_sel, s_sel)
        t_ap = average_precision_score(l_sel, s_sel)
        _, t_recall = binary_metrics(s_sel, l_sel, threshold)
        per_type[name] = {"auc": float(t_auc), "ap": float(t_ap),
                          "recall": float(t_recall), "n": int(l_sel.sum())}
        print(f"  {name:10s} | n={int(l_sel.sum()):4d} | AUC: {t_auc:.4f} | "
              f"AP: {t_ap:.4f} | Recall@thr: {t_recall:.4f}")

    incident = {}
    if getattr(stream, "incident", None) is not None:
        test_preds = (test_scores >= threshold).astype(int)
        incident["global"] = incident_report(
            f"global @FPR={cfg.target_fpr}", test_preds, test_scores, test_types,
            stream.incident[calibration_end:].numpy(),
            stream.theft_variant[calibration_end:].numpy(),
        )

    # Machine-readable summary (consumed by tests/regen_report_tables.py). Recall here is
    # at the global @target_fpr threshold — the apples-to-apples Panel A (tab:baselines) metric.
    return {
        "agg_auc": float(auc), "agg_ap": float(ap),
        "agg_precision": float(precision), "agg_recall": float(recall),
        "per_type": per_type, "incident": incident,
    }


def isolation_forest_no_precursor_baseline(cfg: TGNConfig = TGNConfig(), stream=None):
    """The forest alone: same features, fit and protocol, scores without the precursor factor."""
    return isolation_forest_baseline(cfg, stream, use_precursor=False)


def main():
    parser = argparse.ArgumentParser(description="Run the Isolation Forest baseline.")
    parser.add_argument(
        "--no-precursor",
        action="store_true",
        help="Disable the causal kill-chain precursor prior.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=TGNConfig().seed,
        help=f"Random seed for data generation and model fitting (default: {TGNConfig().seed}).",
    )
    args = parser.parse_args()
    isolation_forest_baseline(
        cfg=TGNConfig(seed=args.seed),
        use_precursor=not args.no_precursor,
    )


if __name__ == "__main__":
    main()
