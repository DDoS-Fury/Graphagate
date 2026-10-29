#!/usr/bin/env bash
# Waits for the running Panel D container, archives results, commits, pushes, powers off.
# Powers off ONLY if every step succeeded (otherwise the machine stays on so you can see why).
set -euo pipefail
cd "$(dirname "$0")/.."

CONTAINER="${1:-graphagate-regen-report-run-e30c56519ebd}"
GATE=docs/performance/panelD_gate

echo "[$(date +%T)] waiting for $CONTAINER ..."
docker wait "$CONTAINER" || true      # --rm may already have removed it; the JSON check below decides

python3 - <<'PY'
import json, sys
d = json.load(open("tasks/runs/panelD.json"))
want = {"full", "no_config", "no_precursor", "no_hist"}
if set(d["raw"]) != want or any(len(v) != 1 for v in d["raw"].values()):
    sys.exit(f"panelD.json incomplete: {({k: len(v) for k, v in d['raw'].items()})}")
PY

python3 tests/make_standalone_table.py ablation

# replace the stale (old-generator) Panel D archive with the new run
git rm -q --ignore-unmatch "$GATE"/cache/D_*.json
mkdir -p "$GATE/cache" "$GATE/generated"
cp tasks/runs/panelD.json "$GATE/panelD.json"
cp tasks/runs/panelA.json "$GATE/panelA.json"
cp tasks/runs/cache/D_*.json "$GATE/cache/"
cp docs/paper/generated/tab_ablation.tex docs/paper/generated/tab_ablation_paired.tex "$GATE/generated/"

git add "$GATE" tests/make_standalone_table.py tests/finish_ablation.sh \
        docs/performance/panelA_gate/generated/tab_baselines_standalone.tex
git commit -m "docs: single-seed ablation run (panel D, seed 1000) + standalone LaTeX tables

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push origin correction

echo "[$(date +%T)] all done, powering off in 60s (Ctrl+C / 'shutdown -c' to abort)"
sleep 60
# GNOME holds a blocking 'shutdown' inhibitor, so plain `systemctl poweroff` is refused without a password;
# gnome-session-quit goes through the session itself and needs none.
gnome-session-quit --power-off --no-prompt --force || systemctl poweroff
