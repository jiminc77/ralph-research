# DECISION_POLICY.md

## 0. Authority and default

This policy governs unattended Phase 2 choices for `where-vs-how-dlo-v1`.

Default rule:

> Choose the most reversible, evidence-preserving option. Never select on the desired sign or magnitude of a scientific result.

Scientific settings not explicitly delegated here are immutable after run start.

---

## 1. Hard wall-clock policy

- Total wall time: `28,800 s`.
- S5 MUST begin by `21,600 s` elapsed.
- S6 MUST begin by `26,784 s` elapsed.
- At `24,480 s` elapsed, no new broad candidate or robustness experiment may start.
- At `25,920 s` elapsed, no new experiment may start. Running short confirmation work may finish if projected to complete before S6.
- At deadline, finish the current atomic artifact ingest and DB transaction, then terminate.

Stage targets:

| Stage | Start target | Hard latest exit |
|---|---:|---:|
| S0 | 00:00 | 00:30 |
| S1 | 00:30 | 00:55 |
| S2 | 00:55 | 01:15 |
| S3 | 01:15 | 04:20 |
| S4 | 04:20 | 06:00 |
| S5 | 06:00 | 07:26:24 |
| S6 | 07:26:24 | 08:00 |

---

## 2. A100 topology selection

### 2.1 Resource caps

- GPU memory: hard stop at `68 GiB` allocated/resident for simulator workers.
- CPU: simulator workers use at most `9` of `11` vCPU.
- RAM: simulator workers use at most `96 GiB`.
- Maximum simulator processes: `4`.
- No other DGCC training job may share the GPU.

### 2.2 Probe candidates

Probe in this order:

1. `1×1024`;
2. `1×2048`;
3. `2×1024`;
4. `3×512`;
5. `4×256`.

A topology is valid only if:

- two full reset+primitive rounds complete;
- non-finite incidents are zero;
- persistent invalid table count is zero;
- settle convergence is at least `0.95`;
- p99 round time is at most `120 s`;
- GPU/RAM/CPU caps are respected.

Choose the valid topology with highest aggregate valid action cells/s. If throughput differs by less than 5%, choose fewer processes. A topology OOM may be retried once only with the next smaller listed topology.

The topology choice is mechanical and does not alter scientific settings.

---

## 3. Throughput execution tier

Use aggregate valid action cells/s from the complete side-study pipeline, not primitive-only throughput.

| Tier | Throughput | Candidate plan |
|---|---:|---|
| `FULL` | `>= 10.0/s` | C0–C3, 96 dev states/task |
| `REDUCED` | `5.0–9.999/s` | C0–C3, 64 dev states/task |
| `MINIMAL` | `3.0–4.999/s` | C0 and C1, 64 dev states/task |
| `NO_GO` | `< 3.0/s` | no production science; Grade D |

The tier is selected once after S0 and recorded as a locked decision. Every retained candidate receives exactly the same states and action-cell count.

If the projected S3+S4 completion exceeds 5 hours despite the measured tier, step down one tier before production collection. After production collection begins, no tier change is allowed.

---

## 4. Candidate validity and pruning

### 4.1 Fixed priority

`C0 → C1 → C2 → C3`

### 4.2 Hard candidate guards

A candidate is `valid` only if all hold:

- reset placement error max `<= 1e-4`;
- no-op median absolute progress `<= 1e-3`;
- no-op p99 absolute progress `<= 5e-3`;
- repeatability median distance `<= 1e-4`;
- repeatability p99 distance `<= 1e-3`;
- tie-aware repeated top-action equivalence agreement `>= 0.99` with `1e-4` score tolerance;
- settle convergence `>= 0.95`;
- non-finite incident count `== 0` in qualification;
- clamp count `== 0`;
- persistent invalid state-table rate `<= 0.02`;
- complete action tables only.

A mechanical failure may be retried once with the identical scientific configuration. A second failure is terminal for that candidate.

### 4.3 Selection

- If `C0` passes all guards, select `C0`, regardless of effect size.
- If `C0` fails, select the first guard-valid candidate in fixed priority.
- A candidate with small or zero action effect remains valid; it is not replaced merely to obtain stronger results.
- All valid dev candidates are retained as robustness evidence.
- Primary effect estimates are never part of the selection score.

### 4.4 All candidates fail

1. Determine whether failures share one mechanical signature.
2. If yes, apply one predeclared topology fallback and rerun qualification only.
3. Do not change displacement, lift, settle threshold, task error, or action grid.
4. If no candidate then passes, stop experiments and emit Grade D `run_failure_report.md`.
5. If tables are mechanically valid but all have negligible range, treat as `valid_null_result` and emit Grade C, not Grade D.

---

## 5. State-table failure policy

- Any invalid cell invalidates the entire `state × candidate` table.
- Retry the whole table once with identical state, environment assignment permutation, and scientific config.
- A second failure is persistent.
- Do not replace a persistent post-action failure with a reserve state.
- Reserve states are allowed only for pre-action state-generation failure or failure to meet the preregistered eligibility threshold.
- If persistent invalid rate exceeds 2%, the candidate fails the guard.
- If invalidity is concentrated by contact or direction by more than 2 percentage points, block the causal Where/How claim for that candidate as Missing Not At Random.

---

## 6. Baseline and challenge analysis

S1 baseline is valid when:

- C0 qualification tables are complete;
- the random baseline \(v_0\) is computed;
- no-op and repeatability guards are evaluated;
- at least one nontrivial action table exists or a valid-null diagnosis is recorded.

S2 classifies findings as:

- `invalid_run`;
- `mechanical_failure`;
- `valid_null_result`;
- `informative_valid`.

Only `informative_valid` and `valid_null_result` proceed to scientific estimation. Invalid data are never merged with valid tables.

---

## 7. Reproduction and hidden confirmation

### 7.1 Clean reproduction

The selected candidate is rebuilt in a clean process/container and rerun on 32 states per task.

Reproduction passes when:

- every validity guard passes;
- task-level \(\Delta_{WH}\) differs from the dev estimate by no more than `0.02` absolute for preregistered non-null contrasts;
- interaction differs by no more than `0.02` absolute;
- tie-aware top-action equivalence agreement is at least `0.95` with `1e-4` score tolerance.

If reproduction fails once:

- classify the cause;
- one mechanical rerun is allowed with the same frozen tuple;
- no scientific retuning is allowed.

A second failure blocks hidden confirmation and downgrades to Grade C or D according to validity.

### 7.2 Hidden confirmation

- Exactly one hidden attempt.
- Verifier-only seed/state access.
- No method or metric change after reveal.
- A dev-supported directional claim is confirmed only when hidden has the same sign and absolute effect at least `0.01`.
- If hidden disagrees, reduce the claim to descriptive dev evidence and Grade B/C.
- Hidden failure never triggers retuning or a second hidden split use.

---

## 8. Scientific decision rules

### H1

Report \(\Delta_{WH}(t)\) for all tasks with simultaneous intervals.

Allowed labels:

- `Where-dominant`: lower CI bound `> 0` and estimate `>= 0.02`;
- `How-dominant`: upper CI bound `< 0` and estimate `<= -0.02`;
- `balanced/inconclusive`: otherwise.

A task-dependence claim additionally requires a preregistered task-pair difference with simultaneous CI excluding zero and absolute effect `>= 0.02`.

### H2

`positive interaction` is claimable for a task only if:

- estimate `>= 0.02`;
- simultaneous lower CI bound `> 0`;
- additive-reconstruction control shows nonzero residual energy;
- the direction repeats in reproduction or hidden confirmation.

Otherwise report interaction descriptively.

### H3

`t1c has stronger coupling than t1a` is claimable only if the difference estimate is `>= 0.02` and its 95% interval excludes zero.

No result is converted into a broader DLO-general claim.

---

## 9. Budget pressure

Mandatory evidence priority:

1. simulator qualification;
2. equal-cardinality primary tables;
3. selected-candidate reproduction;
4. one hidden confirmation;
5. deterministic metrics and evidence package;
6. simple controls;
7. optional robustness.

Drop order under pressure:

1. `R_realism`;
2. `R_resolution_16x16`;
3. `R_contact_density`;
4. reduce review to one loop;
5. reduce dev tier only through the locked tier rule before production starts.

Never drop:

- no-op control;
- repeatability;
- complete-table policy;
- hidden isolation;
- candidate parity;
- final audit reserve.

At 80% GPU-time budget, stop launching optional work. At 90%, finish only selected reproduction/hidden. At 95%, stop all experiment launch and finalize evidence.

---

## 10. Guard failure consequences

| Failure | Consequence |
|---|---|
| reset/no-op/repeatability failure | block causal attribution; Grade D if unresolved |
| settle `<0.95` | candidate invalid |
| non-finite qualification incident | candidate invalid pending one identical retry |
| clamp count `>0` | candidate invalid |
| persistent invalid tables `>2%` | candidate invalid |
| contact/direction-dependent invalidity | mechanism claim blocked |
| hidden confirmation failure | no retuning; claim reduction |
| evidence package incomplete | Grade A/B blocked |
| direct prior-art collision | reclassify contribution; do not erase valid evidence |

---

## 11. Direct prior-art collision

If R2 identifies direct collision:

- retain the experiment;
- reclassify contribution from novelty/method to `analysis`, `replication`, or `robustness`;
- remove “first”, “novel”, or exclusivity wording;
- add the colliding work and precise distinction;
- block Grade A until positioning is locked.

The experiment is not repeated solely because of a literature collision.

---

## 12. Evidence shortage and null results

- A valid null is preserved as Grade C `research_report.pdf`.
- Failure to meet minimum effect does not authorize metric substitution.
- Exploratory metrics remain labeled exploratory.
- If only one candidate is valid, report reduced search breadth and do not imply best-of-four selection.
- If sample count falls below 48 valid states per task on dev or 32 per task on hidden, block strong task-level claims.

---

## 13. ASK timeout

Default ASK timeout: `300 s`.

On timeout:

1. apply an existing deterministic clause;
2. otherwise choose the most reversible evidence-preserving option;
3. prefer stopping optional work over altering science;
4. record the question, options, timeout, and selected fallback.

No unattended ASK may silently become a scientific hyperparameter change.

---

## 14. Output-grade policy

- **Grade B / internal draft:** valid, reproduced, hidden-confirmed evidence sufficient for a conservative internal paper; active submission venue is not assumed.
- **Grade C / research report:** valid null, hidden disagreement, reduced sample, or mechanism evidence insufficient.
- **Grade D / failure report:** simulator/data validity not established or evidence lineage damaged.

This side study does not target automatic submission and MUST record `submission_performed=false`.
