#!/usr/bin/env bash
# ==============================================================================
# Graphagate - Panel D Execution on 3 Seeds (1000, 1001, 1002)
# ==============================================================================
# - Reuses the 'full' TGN runs for seeds 1000, 1001, 1002 from Panel A (0 sec).
# - Reuses seed 1000 ablation runs from cache (0 sec).
# - Computes seeds 1001 and 1002 for: no_config, no_precursor, no_hist.
#   Total runs: 2 seeds * 3 variants = 6 runs (~3 hours on RTX 5070 Ti).
# - Produces mean ± std and 95% bootstrap CI for the ablation table.
# - Formats tables, updates docs/performance/LATEX_TABLES_READY.tex, commits & pushes.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/tasks/runs/panelD_3seeds.log"
mkdir -p "$REPO_ROOT/tasks/runs" "$REPO_ROOT/docs/paper/generated" "$REPO_ROOT/docs/performance"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================================================"
echo "START PANEL D (3 SEEDS: 1000, 1001, 1002): $(date)"
echo "Log file: $LOG_FILE"
echo "========================================================================"

# --- 1. RUN PANEL D ON SEEDS 1000 1001 1002 ---
echo ""
echo ">>> [1/4] Running Panel D on seeds 1000, 1001, 1002 (seed 1000 is loaded from cache)..."
docker compose run --rm regen-report \
    /app/tests/regen_report_tables.py --panels D --seeds 1000 1001 1002 --ablations no_config no_precursor no_hist

echo ">>> Panel D completed at $(date)!"

# --- 2. FORMAT STANDALONE LATEX TABLES ---
echo ""
echo ">>> [2/4] Formatting standalone LaTeX ablation tables..."
python3 "$REPO_ROOT/tests/make_standalone_table.py" ablation

# Sync updated JSON to docs/performance/
cp "$REPO_ROOT/tasks/runs/panelD.json" "$REPO_ROOT/docs/performance/panelD_gate/panelD.json" 2>/dev/null || true

# --- 3. REGENERATE LATEX_TABLES_READY.tex ---
echo ""
echo ">>> [3/4] Updating docs/performance/LATEX_TABLES_READY.tex..."
cat << 'EOF' > "$REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"
% ==============================================================================
% TABELLE PRONTE DA COPIARE E INCOLLARE NEL PAPER (LaTeX)
% Richiedono nel preambolo: \usepackage{booktabs} \usepackage{multirow}
% ==============================================================================

% ------------------------------------------------------------------------------
% 1. TABELLA PRINCIPALE (Panel A: TGN vs Baselines su 5 seed)
% ------------------------------------------------------------------------------
EOF
cat "$REPO_ROOT/docs/performance/panelA_gate/generated/tab_baselines_standalone.tex" >> "$REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

cat << 'EOF' >> "$REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

% ------------------------------------------------------------------------------
% 2. TABELLA DI ABLAZIONE DELLE COMPONENTI (Panel D: Full vs no_config, no_precursor, no_hist su 3 seed)
% ------------------------------------------------------------------------------
EOF
cat "$REPO_ROOT/docs/performance/panelD_gate/generated/tab_ablation_standalone.tex" >> "$REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

echo ">>> LaTeX tables ready at: $REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

# --- 4. GIT COMMIT AND PUSH ---
echo ""
echo ">>> [4/5] Committing and pushing to GitHub (branch: runpod)..."
git add "$REPO_ROOT/docs/performance/" \
        "$REPO_ROOT/docs/paper/generated/" \
        "$REPO_ROOT/tasks/runs/panelD.json" \
        "$REPO_ROOT/tasks/runs/cache/" \
        "$REPO_ROOT/tests/make_standalone_table.py" \
        "$REPO_ROOT/scripts/" || true

git commit -m "Auto: Update Panel D with 3-seeds ablation results and tables" || true
git push origin runpod || true
echo ">>> Git push completed at $(date)!"

echo ""
echo "========================================================================"
echo "PANEL D (3 SEEDS) COMPLETED SUCCESSFULLY: $(date)"
echo "========================================================================"
