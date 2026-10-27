# Baseline: Isolation Forest

A classic, **non-relational** anomaly detector. Every ZTA access event
is described by a 42-dim static vector: edge features `msg` (7) ⊕
static features of the device node (16) ⊕ static features of the resource node (16) ⊕
causal benign-gated history counters (3; the same *family* of statistics the TGN
maintains online, consumed here as a flat tabular vector by the device actor). No
memory, no temporal neighbourhood, and **strictly fewer signals than the TGN**: device
actor only — no user / source / config identity and no binding counters.

The counters are gated by ground-truth benign labels up to `calibration_end` and commit every
event after it (`label_horizon=calibration_end`, required by `_build_features`); the test labels
never reach the features (`tests/test_isolation_forest_baseline.py`). The TGN's own gate
past that point is `not signal_dirty`; the two differ only on signal-dirty events
(see `docs/external_dataset_optc.md`, "Stato al 2026-09-19").

Protocol identical to `graphagate.train_tgn` (same `TGNConfig`, same seed,
same chronological split 70/10/20, same precursor prior). The `IsolationForest`
(sklearn) is trained **on the benign train events only**, with fixed detector
hyperparameters defined in `ISOLATION_FOREST_PARAMS`; the calibration slice is
not used for model selection. The anomaly score is
`-score_samples(X)` (higher = more anomalous, consistent with the TGN's `1 - P(benign)`).
The threshold is calibrated on the benign calibration scores at `target_fpr`
(99th percentile). Reported on test: aggregate AUC/AP, precision/recall at the
threshold and the per-type breakdown (policy / contextual / lateral / cred-theft / exfil /
benign-denied). The gap to the TGN measures how much the detection depends on the
graph structure and on the interaction history.

`isolation_forest_no_precursor_baseline(cfg, stream=None)` is the same pipeline without the
precursor factor (`use_precursor=False`): the forest's own scores in model selection,
calibration and test. On v5 (seeds 1000-1004, 200k events) the factor alone ranks lateral
movement at AUC 0.82–0.96 and the forest without it is at chance (0.43–0.53), so the
lateral number of the default row is the prior's, not the forest's.

## Execution

Because PyTorch and baseline dependencies are not installed on the host, run the baseline inside the project's Docker container:

```bash
docker run --rm --gpus all -v "$PWD:/work" -w /work --entrypoint python graphagate \
  /work/tests/baselines/isolation_forest/isolation_forest_baseline.py
```

Alternatively, run via Docker Compose:

```bash
docker compose --profile baseline-iforest up
```
