# Revision notes — paper-polish-v1 (final critic + revision pass, 2026-07-12)

Input: previous polished draft (6-page PDF: 4 main + refs p5 + appendix p6) plus
`paper_revision_inputs/gpt-pro-feedback.md`. All frozen experimental numbers and
the negative validity conclusion are preserved verbatim.

## Narrative changes (per GPT Pro senior review)

1. **Abstract replaced** with the reviewer-proposed arc (adapted to the frozen
   macros): hybrid action -> factorial diagnostic -> parameterization-specific
   claim -> descriptive contrasts with simultaneous CIs -> descriptive labels ->
   42/192 invalid tables, guard failure, C0 not formally selected, no hidden
   confirmation -> contribution = transparent guard-audited protocol + pilot
   evidence, not confirmatory conclusions.
2. **Introduction restructured** as DLO difficulty -> hybrid action
   representation -> joint optimization prevents attribution -> factorial
   intervention gap.
3. **Experimental-unit hierarchy made reconstructable** (new Table 1): 3 tasks
   x 16 states = 48 states; x 4 candidate execution regimes = 192
   state-candidate tables; x 64 cells = 12,288 executed cells; 42 invalid
   tables quarantined (C0/C1/C2/C3: 8/10/16/8, verified against
   `analysis_dev.json` `selection.per_candidate`); 40 valid C0 tables
   (12/13/15 per task) = 2,560 analyzed cells. The table caption states where
   invalid tables are excluded.
4. **"Candidate execution regime" defined before use** (Section 3.2); "used
   tables/states" replaced with "analyzed/included" everywhere (paper +
   `numbers.tex` prose macros).
5. **Method language fixed**: C0 is "the preregistered first-priority
   candidate, reported descriptively"; no selection language anywhere.
6. **Results opens with the required statement** (bold): "No candidate
   execution regime passed the preregistered invalid-table-rate guard; every
   number below is descriptive development-split pilot evidence."
7. **Cross-task H3 downgraded to exploratory** and tied to the shared-strata
   correction.
8. **Overclaims removed/replaced** (all five flagged phrases verified absent
   from the PDF text):
   - "C0 was selected" -> not selected, reported descriptively.
   - "guard-validated" -> "guard-audited pilot diagnostic" (conclusion).
   - "answering how much" -> "attributing ... descriptively / pilot
     observations, not confirmed findings".
   - "exact reproduction" -> "per-cell raw data, configs, and seeds are
     released" (no reproduction claim).
   - "all three exceed the noise floor" -> `\interactionsummary` now states
     t1a/t1b sit far above the floor while the t1c interval includes zero
     (numbers unchanged: +0.228 [+0.217,+0.239]; +0.154 [+0.138,+0.168];
     +0.007 [-0.007,+0.020]).
9. **Discussion/Limitations** now covers harm avoidance as an explanation for
   direction dominance, parameterization bias, candidate instability (sign of
   Delta_WH inconsistent across C0-C3), and the canonicalization artifact.
10. **Deviations appendix folded into main text** (Section 3.4 paragraph);
    appendix removed; redundant Figure 3 (decomposition bar chart) removed —
    its content is fully in Table 3.
11. **Conclusion rewritten** around "preregistered, guard-audited pilot
    diagnostic"; findings stated descriptively.

## References

- 24 entries, all verified against primary sources; no invented metadata.
- Added: Chi et al., *Iterative Residual Policy for Goal-Conditioned Dynamic
  Manipulation of Deformable Objects*, RSS 2022 (metadata verified from
  roboticsproceedings.org p016), cited in Related Work.
- Retained verified set incl. HACMan (PMLR 229), Transporter Networks
  (PMLR 155), SoftGym (PMLR 155), Wu et al. RSS 2020, Where2Act, DualAfford,
  parameterized-action MDP papers, DLO surveys, evaluation-rigor and
  preregistration references, and the simulator paper.

## Layout

- Official anonymous ICML 2026 style, two-column, submission (line-numbered)
  mode.
- 5-page PDF total: main text ends on page 4; page 5 begins with References
  and contains only References. No appendix pages.
- Achieved by removing Figure 3 + appendix, folding deviations into Section
  3.4, condensing prose (no numbers changed), inlining two display equations,
  width-reducing Figure 2 to 0.84\linewidth, and `\bibsep` 0.5pt.

## Unresolved concerns

- `analysis_dev.json` `counts.per_task_valid` reads 13/14/15 while the frozen
  paper reports 12/13/15 (n=40, matching
  `selection.per_candidate.C0.n_valid_tables=40`). The frozen paper numbers
  are kept verbatim; the JSON field appears to count a different table subset.
- The simulator citation (`cao2026dlolab`, ICML 2026 + arXiv note) is the
  environment's own reference and is retained as provided.
