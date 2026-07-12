# QA report — paper-polish-v1 final PDF (2026-07-12)

Build: `pdflatex` -> `bibtex` -> `pdflatex` x2 (TeX Live 2023), anonymous ICML
2026 style, from `paper.tex` + `numbers.tex` + `references.bib`.

| Check | Result |
|---|---|
| Total pages | **5** |
| Main text pages | 1–4 (Conclusion ends on page 4) |
| Page on which References starts | **5** (page 5 contains only References; no appendix, no figure continuation) |
| Appendix/deviation pages | none — deviations are in Section 3.4 main text |
| Overfull \hbox/\vbox | 0 (log shows only benign underfull warnings) |
| Undefined citations/references | 0 (`grep` of log: none; all \citep resolve) |
| Anonymity | Author block = style-default anonymous ("Anonymous Authors", anon institution/email); no acknowledgements; no repository names, no filesystem paths, no run IDs in PDF text |
| Forbidden phrases | "was selected", "guard-validated", "answering how much", "exact reproduction", "all three exceed", "used tables/states" — all absent from PDF text |
| CI caption consistency | Table 2 caption = studentized max-t **simultaneous** 95% CIs (primary); Table 3 caption = **pointwise** 95% bootstrap CIs (decomposition); matches numbers.tex tables |
| Figures | Figure 1 (heatmaps, 0.96\linewidth) and Figure 2 (Delta_WH, 0.84\linewidth) legible at print size; redundant decomposition figure removed |
| Visual page inspection | qa_page1..5.png rendered at 1.3x and inspected: no overlapping floats, no clipped text |

## Frozen-number check (all verified present and unchanged in PDF text)

- Primary contrasts: +0.041 [+0.029, +0.053]; -0.034 [-0.073, +0.005];
  -0.130 [-0.161, -0.100] (simultaneous 95%).
- Labels: contact-dominant / balanced-inconclusive / direction-dominant
  (applied descriptively).
- 42 of 192 tables invalid; rate 0.219 > 0.02; 6 states with re-placement
  artifact up to 6.4e-3; per-candidate invalid 8/10/16/8.
- 40 valid C0 states (12/13/15 per task); 2,560 analyzed cells; 12,288
  executed cells.
- Interactions: +0.228 [+0.217,+0.239]; +0.154 [+0.138,+0.168];
  +0.007 [-0.007,+0.020]. Decomposition table values unchanged.
- H3: -0.180 [-0.201, -0.160] (exploratory, shared strata).
- Guards: repeat agreement 1.000; settle 0.9957; non-finite 0; factor gap
  9.8e-3; placement error (analyzed) 7.8e-5; no-op median 1.0e-8 / p99
  1.5e-4 (analyzed states); zero-displacement floor median 1.4e-3 / p99
  3.1e-3; throughput 5.42 cells/s at 512 envs.
- Negative validity conclusion preserved and stated in the abstract, opening
  of Results (bold), and Conclusion: no candidate passed the preregistered
  invalid-table-rate guard; C0 not formally selected; development split only;
  no hidden-split confirmation or clean reproduction.
