# RESEARCH_SPEC.md

```yaml
problem:
  statement: "Under the same DLO state, goal, candidate cardinality, and simulator budget, how much one-step action quality is attributable to contact selection (where), motion-direction selection (how), and their interaction?"
  scope: "One-step, simulator-ground-truth, canonicalized quasi-static DLO states; tasks t1a_straighten, t1b_single_bend, t1c_endpoint_reposition; no RL training, no real-robot or long-horizon claims."

hypothesis:
  observed_failure: "Hybrid-action systems (HACMan-style, DGCC parent) jointly select contact and motion, so success does not reveal which factor carries the one-step decision value."
  causal_hypothesis: "The relative one-step value of contact vs motion-direction selection is task-dependent, and part of the attainable improvement exists only under joint selection (contact-motion interaction)."
  falsifier: "Action tables are not repeatable, no-op drift is comparable to action effects, or the action table has negligible dynamic range; a null or reversed result remains valid evidence."

baseline:
  name: "uniform-random factorial baseline v0"
  command: "uv run python scripts/where_vs_how_runner.py --mode collect --split dev --states-file /root/wvh/states_dev.json.gz --candidates C0 --n-envs 1024 --out /root/wvh"
  fairness_constraints:
    - "equal 8x8 contact/motion cardinality in the primary comparison"
    - "identical states, action grid, settle budget, and error metric across candidates"
    - "compute parity in executed action cells; runtime differences grant no extra samples"

metrics:
  primary: "where_minus_how_by_task"
  direction: maximize
  minimum_effect: 0.02
  guards:
    - name: "noop_abs_progress_median"
      operator: lte
      threshold: 0.001
    - name: "repeat_top_action_equivalence_agreement"
      operator: gte
      threshold: 0.99
    - name: "settle_convergence_rate"
      operator: gte
      threshold: 0.95
    - name: "persistent_invalid_state_table_rate"
      operator: lte
      threshold: 0.02

candidates:
  min: 2
  max: 4
  representation_alternative_considered: true

mechanism:
  prediction: "Observed tables exceed the additive row-plus-column reconstruction where contact and motion must be chosen jointly; T1c couples more than T1a."
  required_checks: [ablation, counterfactual]

budget:
  wall_clock_hours: 8
  provider_cost_cap_usd: 25
  compute_cap: "1x A100 80GB, simulator 9 vCPU cap in preregistered plan; executed host 96 vCPU"
```

The machine block above is the harness contract; the full preregistered prose
specification follows.

---

# RESEARCH_SPEC.md

## 0. Study identity

- **Study ID:** `where-vs-how-dlo-v1`
- **Working title:** *Where or How? A Factorial Intervention Study of Contact and Motion Direction in Quasi-static DLO Manipulation*
- **Contribution type:** `analysis` + `robustness`
- **Phase 2 wall-clock limit:** 8 hours (`28,800 s`)
- **Target compute:** NVIDIA A100 80 GB, 11 vCPU, 128 GB RAM
- **Primary codebase:** `jiminc77/DGCC`
- **Primary simulator:** DLO-Lab through `DLOLabEnv`
- **Scientific scope:** one-step, simulator-ground-truth, canonicalized quasi-static DLO states
- **Primary tasks:** `t1a_straighten`, `t1b_single_bend`, `t1c_endpoint_reposition`
- **Not in scope:** RL training, arbitrary trajectory hidden-state restoration, real-robot validation, obstacle tasks, long-horizon policy claims

This specification is the Phase 1 scientific contract. Phase 2 may change only choices explicitly delegated to `DECISION_POLICY.md`.

---

## 1. Problem and motivation

Hybrid contact actions have the form

\[
a=(p,u),
\]

where \(p\) is a contact location and \(u\) is a motion parameter. HACMan-style methods and the DGCC parent project jointly select both factors, but a successful action does not reveal whether performance came from selecting **where to act**, **how to move**, or a particular contact–motion pairing.

The research gap is therefore an attribution gap:

> Under the same DLO state, goal, candidate cardinality, and simulator budget, how much one-step action quality is attributable to contact selection, motion-direction selection, and their interaction?

This question is useful independently of DGCC. It determines whether future work should spend complexity on dense contact maps, motion generation, or explicit joint reasoning.

---

## 2. Falsifiable naive baseline

**Naive baseline:** choose one of eight contact candidates uniformly and one of eight planar motion directions uniformly, then execute the fixed grasp–move–release–settle primitive.

The baseline value for state \(s\) is

\[
v_0(s)=\mathbb{E}_{p,u}[Y_s(p,u)].
\]

The study fails to support any contact/motion attribution claim if action tables are not repeatable, if no-op drift is comparable to action effects, or if the action table has negligible dynamic range.

---

## 3. Failure hypothesis and observables

### H1 — Task-dependent Where-versus-How contribution

The relative value of contact and motion-direction selection is not constant across T1 tasks.

**Observable:** for each task \(t\),

\[
\Delta_{WH}(t)=\mathbb{E}_{s\mid t}[v_P(s)-v_U(s)].
\]

Positive values indicate a larger contact-selection contribution; negative values indicate a larger motion-direction contribution.

### H2 — Contact–motion interaction

Some improvement is available only when the contact and direction are selected jointly.

**Observable:**

\[
I(t)=\mathbb{E}_{s\mid t}[v_{PU}-v_P-v_U+v_0].
\]

### H3 — Endpoint relocation is more coupled

`t1c_endpoint_reposition` is expected to have larger interaction than `t1a_straighten`, because both the acted endpoint and the displacement direction must be appropriate.

**Observable:**

\[
I_{\mathrm{T1c}}-I_{\mathrm{T1a}}.
\]

### Hypothesis-to-observable map

| Hypothesis | Direct observable | Minimum meaningful effect |
|---|---|---:|
| H1 | task-specific \(\Delta_{WH}(t)\) and pairwise task differences | `0.02` normalized progress |
| H2 | task-specific \(I(t)\) | `0.02` normalized progress |
| H3 | \(I_{\mathrm{T1c}}-I_{\mathrm{T1a}}\) | `0.02` normalized progress |

A null or reversed result remains valid evidence.

---

## 4. Experimental unit and action-quality target

### 4.1 State

A state is a **canonicalized quasi-static centerline state** created by placing an explicit DLO centerline, zeroing velocity, rebuilding edge/frame/twist state, and settling. It is not claimed to be an exact restoration of an arbitrary evolved simulator state.

### 4.2 Goal error

`D_task(X,G)` MUST call the exact scalar T1 task-error implementation from the locked DGCC commit. Its source file and function hash MUST be recorded at intake.

The following reference components MUST also be stored:

- correspondence-L2 shape error;
- anchor error;
- success threshold;
- task-specific orientation/anchor handling.

The side study MUST NOT redefine the reward or success metric after data collection starts.

### 4.3 One-step normalized progress

\[
Y_s(p,u)=
\frac{D_{\mathrm{task}}(X_s,G_s)-D_{\mathrm{task}}(X'_{s,p,u},G_s)}
{\max(D_{\mathrm{task}}(X_s,G_s),10^{-8})}.
\]

Interpretation:

- \(Y>0\): action moved toward the goal;
- \(Y=0\): no change;
- \(Y<0\): action moved away from the goal.

Only states with pre-action error at least twice the task success threshold are eligible. Eligibility is checked before any candidate action is executed.

---

## 5. Factorial action grid

### 5.1 Contact factor

Eight candidates at normalized arc-length positions

\[
\sigma_i=i/7,\quad i=0,\dots,7.
\]

Each \(\sigma_i\) is mapped to the nearest native rod vertex. Both endpoints are included.

### 5.2 Motion factor

Eight planar directions

\[
\theta_j=j\pi/4,\quad j=0,\dots,7,
\]

with displacement

\[
\Delta_j=m[\cos\theta_j,\sin\theta_j,0]^\top.
\]

### 5.3 Equal-cardinality rule

The primary grid is always `8 contacts × 8 directions`. This gives Where and How the same best-of-eight search cardinality. A candidate with unequal factor cardinalities is not eligible for the primary comparison.

### 5.4 Fixed simulator settings

- `vel_threshold = 1e-3`
- `max_steps = 10000` for every settle-bearing call
- `grasp_realism = false`
- plasticity disabled
- no action-cell deletion
- no per-candidate change to task states, action count, settle budget, or error metric

The code defaults of `light_reset` and `step_primitive_batch` MUST NOT be relied on; `max_steps=10000` MUST be passed explicitly.

---

## 6. Parallel scientific candidates

Four primitive regimes are executed on the same dev states and the same `8×8` grid.

| ID | Displacement magnitude | Lift | Primary role |
|---|---:|---|---|
| `C0` | `0.10 m` | `low` | preregistered primary |
| `C1` | `0.05 m` | `low` | lower-energy fallback / robustness |
| `C2` | `0.10 m` | `high` | lift robustness |
| `C3` | `0.05 m` | `high` | combined conservative fallback |

Selection is **not** based on the sign, significance, or magnitude of \(\Delta_{WH}\) or \(I\).

Selection order:

1. use `C0` if all hard validity guards pass;
2. otherwise use the first guard-valid candidate in fixed order `C1 → C2 → C3`;
3. retain and report every valid candidate as a robustness result;
4. if a guard-valid candidate has negligible action-table range, keep it as a valid null rather than replacing it for a stronger effect.

This preserves Phase 2 pruning while preventing effect-driven cherry-picking.

---

## 7. State suite and data split

### 7.1 Split sizes

| Split | States per task | Total states | Access |
|---|---:|---:|---|
| `train` / qualification | 16 | 48 | Builder + Verifier |
| `dev_search` | 96 | 288 | Builder + Verifier |
| `confirmation_hidden` | 64 | 192 | Verifier only |
| clean reproduction | 32 | 96 | Verifier, selected candidate only |

Primary dev action cells:

\[
4\text{ candidates}\times288\text{ states}\times64=73{,}728.
\]

Selected-candidate hidden action cells:

\[
192\times64=12{,}288.
\]

The full mandatory run, including qualification and reproduction, is approximately `105k` primitive cells before small no-op/repeat controls.

### 7.2 Initial-shape strata

- `t1a_straighten`: `u_bend`, `s_curve`, `random_smooth`; straight starts excluded as trivial.
- `t1b_single_bend`: `straight`, `u_bend`, `s_curve`, `random_smooth`.
- `t1c_endpoint_reposition`: `straight`, `u_bend`, `s_curve`, `random_smooth`.

`dev_search` is exactly balanced within each applicable stratum. Hidden counts differ by at most one state where exact balance is impossible.

### 7.3 Hidden discipline

- Hidden seed material is generated and mounted only by the Verifier.
- Builder code receives only state tensors and opaque `state_id`s during confirmation.
- Hidden confirmation occurs at most once.
- No candidate, metric, threshold, action grid, or implementation change is allowed after hidden results are revealed.

---

## 8. Factorial estimands

For each complete action table \(Y_s\):

\[
v_0=\mathbb{E}_{p,u}[Y(p,u)]
\]

\[
v_P=\max_p\mathbb{E}_{u}[Y(p,u)]
\]

\[
v_U=\max_u\mathbb{E}_{p}[Y(p,u)]
\]

\[
v_{PU}=\max_{p,u}Y(p,u).
\]

Derived quantities:

\[
A_{\mathrm{where}}=v_P-v_0,\qquad
A_{\mathrm{how}}=v_U-v_0
\]

\[
\Delta_{WH}=A_{\mathrm{where}}-A_{\mathrm{how}}=v_P-v_U
\]

\[
I=v_{PU}-v_P-v_U+v_0.
\]

Two-player Shapley contributions MAY be reported:

\[
S_P=\tfrac12[(v_P-v_0)+(v_{PU}-v_U)]
\]

\[
S_U=\tfrac12[(v_U-v_0)+(v_{PU}-v_P)].
\]

The primary Where-versus-How contrast is unchanged: \(S_P-S_U=v_P-v_U\).

A two-way variance decomposition MUST also be reported to show whether table variation is dominated by contact, motion, or interaction rather than a single extreme cell.

---

## 9. Required simple controls

All controls use the same collected tables unless stated otherwise.

1. uniform random contact + uniform random direction;
2. endpoint contact + nearest goal-residual direction;
3. midpoint contact + nearest goal-residual direction;
4. maximum pointwise goal-discrepancy contact + local residual direction;
5. maximum-curvature contact + local-normal direction;
6. joint grid oracle;
7. no-op displacement control;
8. additive-table reconstruction control:
   \[
   Y_{\mathrm{add}}=\bar Y_{p\cdot}+\bar Y_{\cdot u}-\bar Y.
   \]

The additive control distinguishes true contact–motion coupling from independent row and column effects.

---

## 10. Representation consideration

The following representation alternatives were considered:

- raw/native centerline;
- normalized arc-length centerline;
- DCT/modal representation used by the DGCC parent study;
- learned latent representation.

**Decision:** use the normalized centerline and task-native point-space error for the primary study. Do not learn or substitute a representation.

**Reason:** the research question is causal attribution between two action factors. A learned or modal bottleneck would introduce representation error and optimization as additional causes. DCT features MAY be used only for a secondary descriptive visualization and MUST NOT define the primary metric, candidate selection, or hidden-confirmation decision.

---

## 11. Simulator qualification requirements

Production collection starts only after all of the following pass:

1. repository tests pass;
2. `supports_per_env_grasp() == true`;
3. reset placement error `max <= 1e-4`;
4. no-op drift: median absolute normalized progress `<= 1e-3`, p99 `<= 5e-3`;
5. repeatability: median pairwise final-state distance `<= 1e-4`, p99 `<= 1e-3`, tie-aware top-action equivalence agreement `>= 0.99` (cells within `1e-4` of the table maximum are equivalent);
6. non-finite incidents `== 0` in the qualification probe;
7. settle convergence `>= 0.95`;
8. displacement clamp count `== 0`;
9. persistent invalid state-table rate `<= 0.02`;
10. aggregate valid throughput sufficient for the locked execution tier.

A failed action cell invalidates its entire state table. The whole table may be retried once under the identical frozen configuration.

---

## 12. A100 resource plan

### 12.1 Resource ceilings

- GPU memory reservation ceiling: `68 GiB`
- simulator CPU ceiling: `9 vCPU`
- control/verification reserve: `2 vCPU`
- process RAM ceiling: `96 GiB` aggregate
- filesystem/output reserve: `32 GiB` RAM-equivalent headroom
- maximum simulator processes: `4`
- environment count MUST be a multiple of `64`

### 12.2 Topology probe

The attended/preflight probe evaluates, in order:

1. `1 process × 1024 envs`;
2. `1 × 2048`;
3. `2 × 1024`;
4. `3 × 512`;
5. `4 × 256`.

Each topology runs at least two full `light_reset + 8×8 table` rounds. The scheduler chooses the highest aggregate **valid action cells per second** satisfying all memory, NaN, settle, and p99 round-time guards. Ties prefer fewer processes.

Candidates and state tables are packed into the environment dimension. One `2048-env` process can evaluate 32 complete `8×8` tables in one round.

### 12.3 Thread policy

- `OMP_NUM_THREADS` is allocated so total simulator threads do not exceed 9;
- `MKL_NUM_THREADS=1`;
- `OPENBLAS_NUM_THREADS=1`;
- no concurrent DGCC training job on the same GPU;
- no runtime package installation.

---

## 13. Eight-hour execution envelope

| Stage | Hard latest completion | Work |
|---|---:|---|
| S0 preflight | `00:30` | lock, tests, topology, guards |
| S1 baseline | `00:55` | C0 qualification, no-op, random baseline |
| S2 challenge analysis | `01:15` | classify mechanical vs valid-null risks |
| S3 candidate exploration | `04:20` | C0–C3 dev tables in parallel |
| S4 reproduction + hidden | `06:00` | fixed-priority selection, clean reproduction, one hidden confirmation |
| S5 evidence/report | `07:26:24` | evidence lock, deterministic figures, report/review |
| S6 audit/package | `08:00` | starts by `07:26:24`; hashes, manifest, final grade |

No new broad experiment may start after `06:48` elapsed. No new experiment of any kind may start after `07:12`. S5 starts no later than 6 hours elapsed; S6 starts no later than 7 hours 26 minutes elapsed.

---

## 14. Optional experiments

Optional work starts only after mandatory hidden confirmation and evidence ingest are complete, with at least 75 minutes remaining.

- `R_resolution_16x16`: 16 contacts × 16 directions on 16 states per task; equal-cardinality robustness only.
- `R_realism`: `grasp_realism=true` on 16 states per task; descriptive execution robustness.
- `R_contact_density`: recover dense-oracle performance from contact subsets `{4, 6, 8, 16}`.

Optional results cannot modify the primary candidate, threshold, or claim wording unless they weaken a claim.

---

## 15. Forbidden shortcuts

- selecting a candidate because Where or How “wins” more strongly;
- unequal contact/motion cardinality in the primary comparison;
- reporting the best state, seed block, or candidate as the aggregate;
- deleting only failed cells from a table;
- reducing `max_steps` for faster candidates;
- changing task states across candidates;
- using Chamfer as the primary task error;
- enabling grasp stochasticity in the primary condition;
- retuning after hidden confirmation;
- claiming exact full-state causal intervention;
- claiming long-horizon, obstacle, or real-robot generality;
- converting a valid null into a mechanical failure;
- adding learned representations during Phase 2.

---

## 16. Expected evidence and claim boundary

### Evidence expected

- complete action-table dataset with provenance;
- task-specific \(\Delta_{WH}\), \(I\), Shapley contributions, and variance shares;
- simultaneous confidence intervals;
- heuristic control regret;
- validity, no-op, repeatability, settle, and invalid-rate tables;
- selected-candidate clean reproduction;
- one hidden confirmation;
- deterministic result figures.

### Maximum allowed claim

> In the tested canonicalized quasi-static T1 regimes and a fixed grasp–move–release–settle primitive, the one-step decision value of contact and planar motion-direction selection can be decomposed, and their relative contributions and interaction are task-dependent or task-invariant as supported by the preregistered estimates.

No broader claim is allowed without a new run and new specification.

---

## 17. Source basis

- DGCC parent plan: contact and motion are the hybrid action factors; DLO-Lab is the selected primary simulator.
- DGCC repository reports: P0 simulator validation, 10,000-step settle decision, P1 throughput, and P1 training-failure diagnosis.
- Research-Ralph v4: Phase 1 deliverable, split, compute-parity, hidden-confirmation, evidence-lock, and output-grade contracts.
- Scientific seed literature is listed in `references.seed.bib`.
