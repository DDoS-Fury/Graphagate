"""Wrap the row-only tables emitted by regen_report_tables.py into a complete LaTeX ``table*``.

    python3 tests/make_standalone_table.py ablation  [SRC] [OUT]
    python3 tests/make_standalone_table.py baselines [SRC] [OUT]

Same numbers as SRC, grouped by attack class; no retraining. Requires booktabs + multirow.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "docs" / "paper" / "generated"
PERF = ROOT / "docs" / "performance"
GROUPS = ("Aggregate", "Lateral", "Theft", "Policy", "Contextual")

KINDS = {
    "ablation": dict(
        src=GEN / "tab_ablation.tex", out=PERF / "panelD_gate" / "generated" / "tab_ablation_standalone.tex",
        label="tab:ablation", order=None,
        caption=("Component ablation on the held-out test split (single seed, 1000; no dispersion). "
                 "Each column switches one component off; recall@1\\%FPR uses a global threshold "
                 "calibrated on benign validation events."),
    ),
    "baselines": dict(
        src=GEN / "tab_baselines.tex", out=PERF / "panelA_gate" / "generated" / "tab_baselines_standalone.tex",
        label="tab:baselines",
        # generated: TGN | IF | IF-noprec | OCSVM-noprec | GNN | 2-node  ->  paper header order
        order=[0, 1, 2, 5, 4, 3],
        heads=["Graphagate", "IForest", "IF (no prec.)", "2-Node TGN", "Static GNN", "OCSVM (no prec.)"],
        caption=("Detection performance on the held-out test split (mean $\\pm$ std over 5 seeds). "
                 "Recall@1\\%FPR uses a global threshold calibrated on benign validation events; "
                 "routed recall applies to Graphagate only."),
    ),
}


def column_heads(src_lines):
    for line in src_lines:
        if line.startswith("% Columns: Metric & "):
            return [c.strip().replace("no ", "w/o ") if c.strip() != "full" else "Full"
                    for c in line.split("&")[1:]]
    raise SystemExit("no '% Columns:' header in source")


def main():
    kind = sys.argv[1]
    k = KINDS[kind]
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else k["src"]
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else k["out"]
    lines = src.read_text().splitlines()
    heads = k.get("heads") or column_heads(lines)
    order = k["order"]
    groups = {}
    for line in lines:
        if line.startswith("%") or not line.strip():
            continue
        cells = [c.strip() for c in line.removesuffix("\\\\").strip().split(" & ")]
        m = re.match(rf"({'|'.join(GROUPS)})\s*(?:---)?\s*(.*)", cells[0])
        metric = (m.group(2).replace("recall (@1\\%FPR)", "Recall@1\\%FPR")
                  .replace("recall (routed)", "Recall (routed)")
                  .replace("blocked (@1\\%FPR)", "Blocked@1\\%FPR")
                  .replace("blocked (routed)", "Blocked (routed)"))
        vals = cells[1:]
        if order:
            vals = [vals[i] for i in order]
        assert len(vals) == len(heads), (cells[0], len(vals), len(heads))
        groups.setdefault(m.group(1), []).append((metric, vals))

    out_lines = [f"% Standalone wrapper of {src.name} (same numbers). Requires booktabs and multirow.",
                 "\\begin{table*}[t]", "\\centering\\small", f"\\caption{{{k['caption']}}}",
                 f"\\label{{{k['label']}}}", "\\resizebox{\\textwidth}{!}{%",
                 f"\\begin{{tabular}}{{ll{'c' * len(heads)}}}", "\\toprule",
                 "Class & Metric & " + " & ".join(heads) + " \\\\"]
    for g, rows in groups.items():
        out_lines.append("\\midrule")
        for i, (metric, vals) in enumerate(rows):
            first = f"\\multirow{{{len(rows)}}}{{*}}{{{g}}}" if i == 0 else ""
            out_lines.append(f"{first} & {metric} & " + " & ".join(vals) + " \\\\")
    out_lines += ["\\bottomrule", "\\end{tabular}}", "\\end{table*}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(out_lines) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
