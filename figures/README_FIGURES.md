# Figures and tables

Generators read the authoritative raw files in `experiments/obsdet/results/final/` and `.../results/v7/` (override
with `OBSDET_DATA` / `OBSDET_V7`) and write next to themselves (override with `FIG_OUT`). They need Python with
matplotlib, numpy and sqlglot (the coverage and divergence figures import the frozen analysis code in
`experiments/obsdet/results/final/code/`).

    python gen_table_agents.py       # TABLE_agents.tex       (Table 1; the 1-vs-8-thread counts it prints are quoted in the text)
    python gen_table_soundness.py    # TABLE_soundness.tex    (Table 2)
    python gen_table_cost.py         # TABLE_cost.tex         (Table 3, from experiments/obsdet/results/E3_analysis_v6.json)
    python gen_fig_divergence.py     # fig_divergence.pdf     (Figure 3; checks its counts against Table 2's rules)
    python gen_fig_coverage.py       # fig_coverage.pdf       (Figure 4)
    python gen_fig_agents.py         # fig_agents.pdf         (Figure 5; replaces the former Table 3, TABLE_replication.tex)
    python gen_fig_cost.py           # fig_cost.pdf           (Figure 6)
    python text_stats.py             # text_stats.txt         (numbers quoted in the text)
    python rejection_stats.py        # rejection_stats.txt    (numbers quoted in the text)

Figures 3, 5 and 6 are laid out at the exact column width (`fig_qa.py`), pass its QA gate (font size, label overlap,
clipping, panel alignment; reports in `QA_*.txt`) and copy the values they plot to `fig_*_data.json`.

Tables 1-3 and the first version of Figure 4 were produced on the cluster (project environment, matplotlib 3.11.2).
Figures 3, 5 and 6 and the current Figure 4 were produced with matplotlib 3.11.2, numpy 2.5.3 and sqlglot 30.19.0 and
then passed through ghostscript 9.27 (`gs -sDEVICE=pdfwrite -dEmbedAllFonts=true -dSubsetFonts=true`), the step that
`paper_plot_style.save` runs when `gs` is available, so that the fonts are embedded as plain CFF.

`fonts/` holds the Linux Libertine OTF files (the acmart body font) so that figure text matches the paper.
`FIGURE_NOTES.md` records the design choices and the alternatives that were tried and rejected.
