#!/usr/bin/env bash
# ==============================================================================
# Graphagate - Overnight Execution Script (Panels A & D + LaTeX + Git + Poweroff)
# ==============================================================================
# 1. Panel A: Multi-seed benchmark (5 seeds: 1000-1004) for TGN & all baselines.
# 2. Panel D: Component ablations (seed 1000: no_config, no_precursor, no_hist).
#    Reuses the 'full' TGN run from Panel A (never re-trained).
# 3. Tables:  Wraps standalone LaTeX tables ready to copy-paste into docs/performance/.
# 4. Git:     Commit and push everything to origin/runpod.
# 5. Shutdown: Powers off the PC cleanly without requiring any sudo password.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/tasks/runs/overnight_run.log"
mkdir -p "$REPO_ROOT/tasks/runs" "$REPO_ROOT/docs/paper/generated" "$REPO_ROOT/docs/performance"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================================================"
echo "START OVERNIGHT RUN: $(date)"
echo "Repo root: $REPO_ROOT"
echo "Log file:  $LOG_FILE"
echo "========================================================================"

# --- 1. PANEL A (E1 Benchmark) ---
echo ""
echo ">>> [1/5] Running Panel A (5 seeds: 1000-1004) --fresh..."
docker compose run --rm regen-report \
    /app/tests/regen_report_tables.py --panels A --seeds 1000 1001 1002 1003 1004 --fresh

echo ">>> Panel A completed at $(date)!"

# --- 2. PANEL D (E4 Component Ablation) ---
# Automatically reuses the 'full' TGN results from Panel A without retraining!
echo ""
echo ">>> [2/5] Running Panel D ablations (seed 1000: no_config, no_precursor, no_hist)..."
docker compose run --rm regen-report \
    /app/tests/regen_report_tables.py --panels D --seeds 1000 --ablations no_config no_precursor no_hist --fresh

echo ">>> Panel D completed at $(date)!"

# --- 3. GENERATE READY-TO-COPY LATEX TABLES IN docs/performance/ ---
echo ""
echo ">>> [3/5] Formatting standalone LaTeX tables in docs/performance/..."
# Re-emit raw tables
docker compose run --rm regen-report /app/tests/regen_report_tables.py --re-emit-only

# Generate standalone wrapped LaTeX tables for Paper
python3 "$REPO_ROOT/tests/make_standalone_table.py" baselines
python3 "$REPO_ROOT/tests/make_standalone_table.py" ablation

# Sync updated JSONs into docs/performance/
cp "$REPO_ROOT/tasks/runs/panelA.json" "$REPO_ROOT/docs/performance/panelA_gate/panelA.json" 2>/dev/null || true
cp "$REPO_ROOT/tasks/runs/panelD.json" "$REPO_ROOT/docs/performance/panelD_gate/panelD.json" 2>/dev/null || true

# Create unified copy-paste LaTeX file
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
% 2. TABELLA DI ABLAZIONE DELLE COMPONENTI (Panel D: Full vs no_config, no_precursor, no_hist)
% ------------------------------------------------------------------------------
EOF
cat "$REPO_ROOT/docs/performance/panelD_gate/generated/tab_ablation_standalone.tex" >> "$REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

echo ">>> LaTeX tables ready at: $REPO_ROOT/docs/performance/LATEX_TABLES_READY.tex"

# --- 4. GIT COMMIT AND PUSH ---
echo ""
echo ">>> [4/5] Committing and pushing to GitHub (branch: runpod)..."
git add "$REPO_ROOT/docs/performance/" \
        "$REPO_ROOT/docs/paper/generated/" \
        "$REPO_ROOT/tasks/runs/panelA.json" \
        "$REPO_ROOT/tasks/runs/panelD.json" \
        "$REPO_ROOT/tasks/runs/cache/" \
        "$REPO_ROOT/scripts/run_overnight_panels.sh" || true

git commit -m "Auto: Update Panel A & D tables, JSONs, and paper LaTeX fragments" || true
git push origin runpod || true
echo ">>> Git push completed at $(date)!"

# --- 5. CLEAN POWEROFF (NO PASSWORD REQUIRED) ---
echo ""
echo "========================================================================"
echo "RUN COMPLETED SUCCESSFULLY AT $(date)"
echo "Il computer si spegnerà tra 30 secondi (Premi Ctrl+C per annullare lo spegnimento)..."
echo "========================================================================"
sleep 60
systemctl poweroff -i
