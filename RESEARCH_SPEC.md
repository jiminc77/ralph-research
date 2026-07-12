# Research Specification

```yaml
problem:
  statement: "Improve reliable selection of research candidates under fixed compute budgets."
  scope: "Offline benchmark experiments with reproducible synthetic fixtures."
hypothesis:
  observed_failure: "Single-seed candidate ranking is unstable."
  causal_hypothesis: "Aggregating independent seeds reduces ranking variance."
  falsifier: "Mean-seed aggregation does not improve confirmation agreement."
baseline:
  name: "single-seed ranking"
  command: "python -m experiments.baseline"
  fairness_constraints:
    - "Use the same data splits and compute budget."
metrics:
  primary: "confirmation_agreement"
  direction: "maximize"
  minimum_effect: 0.05
  guards:
    - name: "runtime_hours"
      operator: lte
      threshold: 8
candidates:
  min: 2
  max: 4
  representation_alternative_considered: "Bootstrap-ranked aggregation."
mechanism:
  prediction: "Variance decreases as independent seed count increases."
  required_checks:
    - ablation
    - counterfactual
```
