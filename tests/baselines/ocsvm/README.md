# Baseline: One-Class SVM

A classic, **non-relational** unsupervised anomaly detector. Like the Isolation
Forest baseline, One-Class SVM (RBF kernel) treats every ZTA access event as an
independent static feature vector with no graph structure:
a 42-dim vector (edge features `msg` [7] ⊕ static features of device [16] ⊕ static
features of resource [16] ⊕ causal benign-gated history counters [3]).
The history counters are gated by labels only through the calibration boundary;
test labels never enter feature construction.

## Mechanism

- Evaluated under the same protocol as `graphagate.train_tgn`: same synthetic
  stream, same seed, same chronological split 70/10/20, fit on benign train events
  only.
- The threshold is calibrated on the benign calibration slice at `target_fpr`
  (99th percentile).
- Anomaly score: `-score_samples(X)` (higher = more anomalous, matching the TGN's
  `1 - P(benign)`).
- Scalability: RBF kernel fitting is $O(n^2)$, so it fits on a uniform random
  subsample (5,000 samples) of the benign training events, while evaluating on the
  full test stream.

## Execution

Because PyTorch and baseline dependencies are not installed on the host, run the baseline inside the project's Docker container:

```bash
docker run --rm --gpus all -v "$PWD:/work" -w /work --entrypoint python graphagate \
  /work/tests/baselines/ocsvm/ocsvm_baseline.py
```

Alternatively, run via Docker Compose:

```bash
docker compose --profile baseline-ocsvm up
```
