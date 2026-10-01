# Figure notes (revision of 2026-09-29)

Three data figures were added and the paper kept within 12 pages. The pre-revision sources are in
`paper-backups/2026-09-29_pre_new_figures/` (outside the paper directory).

## What each new figure claims

- Figure 3 (`fig_divergence`): raw previews diverge in every statement class and certified ones in none; outside the
  fragment, smart-lex leaves many floating-point aggregates divergent. Pooled over the four statement sets with the
  inclusion rules of Table 2, which the script asserts set by set.
- Figure 5 (`fig_agents`): on every task set raw previews change many trajectories and hybrid/strict remove nearly all
  of these changes; accuracy differences with CIs. It carries every number of the former Table 3 (trajectory and
  correctness counts as cell labels) and adds the main tasks.
- Figure 6 (`fig_cost`): the per-probe smart-lex/certified time ratio is concentrated at 1 with long thin tails, and
  in the controlled LIMIT 20 study a certified key that replaces a sort saves up to three orders of magnitude.

## Tried and rejected

- Figure 5: automatic layout (tight_layout) let the legend squeeze the right panel and overlapped the column headers;
  rotated headers still collided. Replaced by hand-placed axes and a two-line "Smart-/lex" header.
- Figure 6(a): an ECDF on a log axis showed a vertical step at 1 and hid the tails, which carry the paper's point that a
  few probes decide the totals. Replaced by a histogram with a logarithmic count axis.
- Figure 3(b): "nested LIMIT" (20 statements on DuckDB) was merged into "other" rather than shown as its own row.
- The QA gate first missed overlapping top-side tick labels (it read only `label1`); it now reads `label2` too, and
  it failed on the first Figure 5 before the fix was accepted.
- `savefig(bbox_inches=None)` falls back to the style file's "tight" bbox and cropped the canvas by up to 2%; the
  figures are now saved with the full canvas, 240.25 bp = \columnwidth wide.

## What was changed to stay within 12 pages

- Table 3 (unseen tasks) is commented out; Figure 5 carries its numbers.
- Table 1 no longer shows the 1-vs-8-thread rows; their counts are in Sections 5.2 and 5.5.
- Figure 4: same data, height 4.1 in to 3.4 in, and the six-entry legend of the bottom panel became one row
  (colour = policy, hatch = statement set).
- Captions of Tables 2 and 3 and of the new figures were shortened.
- Text: the introduction's roadmap paragraph (commented out), a shorter Evaluation contribution, a shorter list of the
  adversarial suite's pitfalls, the per-set smart-lex counts in Section 5.3 (in Table 2; commented out and replaced
  by the pooled counts), a shorter strict-accuracy sentence, and a few sentences in Sections 6 and 7.
- Section 5.6 now says that smart-lex's observation takes more than 10% longer on 12% and 8% of the probes: the
  result file defines this share as ratio > 1.1, which the earlier wording ("the certified observation takes more
  than 10% less time") described inexactly.
