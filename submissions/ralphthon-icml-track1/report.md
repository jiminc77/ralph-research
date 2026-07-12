# Ralphthon Track 1 evidence report: where-vs-how-dlo-v1 (pilot)

- Generated: 2026-07-12T04:54:04Z
- Grade: **C** — Valid pilot evidence at reduced sample (dev split only, {'t1a_straighten': 13, 't1b_single_bend': 14, 't1c_endpoint_reposition': 15} states/task vs registered 96/64); hidden confirmation and clean reproduction not executed, so Grade B is blocked by policy (DECISION_POLICY.md section 14). Dev-split effects exceed the preregistered minimum for at least one task. No candidate is formally selectable: the 0.02 invalid-table-rate guard is unsatisfiable at pilot n (placement-artifact tables are quarantined; all estimates descriptive C0). Registered full-set noop guard failed on state(s) excluded from all used tables; used-state noop passes (see guards).
- Claim scope: contact-location choice vs fixed-magnitude planar-direction choice, one quasi-static primitive, DLOLabEnv only
- DGCC commit: `2f9652754f94c28abe602094655c0a18d4b168cb`
- DLO-Lab commit: `c5026a9416b03c6bc5186eba13cd4ffd4c0e7796`
- Selected candidate: **None** via fixed_priority_after_hard_validity C0->C1->C2->C3 (none selectable; C0 reported descriptively)
- Throughput: 5.42 valid cells/s @ 512 envs (A100-80GB)

## Scale (pilot vs registered)

- Executed rows: 12,288; valid tables: 150; invalid tables: 42
- Valid states/task: {'t1a_straighten': 13, 't1b_single_bend': 14, 't1c_endpoint_reposition': 15}
- Registered scale (96 dev states/task, hidden 64, reproduction 32) NOT run; every number below is dev-split pilot evidence.
- Invalid runs are reported separately from valid null results (complete-table-or-invalid; no cell deletion).

## Primary contrast per task (candidate C0)

| task | n | dWH = E[vP-vU] | simultaneous 95% CI | label |
|---|---|---|---|---|
| t1a straighten | 12 | +0.0413 | [+0.0294, +0.0532] | where_dominant |
| t1b single bend | 13 | -0.0344 | [-0.0735, +0.0046] | balanced_or_inconclusive |
| t1c endpoint reposition | 15 | -0.1304 | [-0.1610, -0.0997] | how_dominant |

## Secondary estimands (candidate C0)

| task | v0 | where main | how main | interaction | oracle gain |
|---|---|---|---|---|---|
| t1a straighten | -0.1513 | +0.0781 | +0.0368 | +0.2282 [+0.2170,+0.2392] | +0.3431 |
| t1b single bend | -0.1421 | +0.1042 | +0.1387 | +0.1536 [+0.1379,+0.1679] | +0.3965 |
| t1c endpoint reposition | -0.0657 | +0.0833 | +0.2137 | +0.0074 [-0.0072,+0.0197] | +0.3044 |

## Cross-task contrasts (shared strata {u_bend,s_curve,random_smooth}, equal weights — review correction C-S2)

- where_minus_how t1b_single_bend_minus_t1a_straighten: -0.0224 [-0.0708, +0.0242]
- where_minus_how t1c_endpoint_reposition_minus_t1a_straighten: -0.1520 [-0.1817, -0.1257]
- where_minus_how t1c_endpoint_reposition_minus_t1b_single_bend: -0.1295 [-0.1813, -0.0774]
- interaction t1b_single_bend_minus_t1a_straighten: -0.0324 [-0.0571, -0.0081]
- interaction t1c_endpoint_reposition_minus_t1a_straighten: -0.1802 [-0.2014, -0.1599]
- interaction t1c_endpoint_reposition_minus_t1b_single_bend: -0.1478 [-0.1715, -0.1234]

## Guards

| guard | value | status |
|---|---|---|
| reset_placement_error_max | 7.782e-05 | pass |
| noop_abs_progress_median | 1.009e-08 | pass |
| noop_abs_progress_p99 | 9.101e-03 | FAIL |
| repeat_final_distance_median | 3.567e-07 | pass |
| repeat_final_distance_p99 | 2.047e-05 | pass |
| repeat_top_action_equivalence_agreement | 1.000e+00 | pass |
| settle_convergence_rate | 9.957e-01 | pass |
| nonfinite_incidents | 0 | pass |
| persistent_invalid_state_table_rate | 2.188e-01 | FAIL |
| factor_dependent_invalidity_gap | 9.766e-03 | pass |
| zerodelta_abs_Y_median (info) | 1.374e-03 | info |
| zerodelta_abs_Y_p99 (info) | 3.053e-03 | info |
| task_dependent_invalidity_gap (info) | 2.344e-01 | info |
| repeat_tables_compared (info) | 6 | info |

## Reproduction commands (from /workspace/DGCC, branch ralphthon-track1)

```bash
# smoke
.venv/bin/python scripts/where_vs_how_runner.py --mode smoke --n-envs 384 --out <dir>
# pilot (states + controls + C0..C3 + repeat, one process)
.venv/bin/python scripts/where_vs_how_pilot_driver.py --split dev \
    --states-per-task 16 --n-envs 512 --out <dir>
# one-time mechanical retry of invalid tables + second noop pass
.venv/bin/python scripts/where_vs_how_retry_driver.py --split dev --n-envs 512 --out <dir>
# analysis / figures / paper / packaging
.venv/bin/python scripts/where_vs_how_analysis.py --data-dir <dir> --split dev \
    --out <outputs> --n-boot 10000 --label pilot
.venv/bin/python scripts/where_vs_how_figures.py --analysis <outputs>/analysis_dev.json --out <outputs>/figures
.venv/bin/python scripts/where_vs_how_paper.py --analysis <outputs>/analysis_dev.json \
    --figures <outputs>/figures --out <outputs>/paper --cellsps <measured>
.venv/bin/python scripts/where_vs_how_package.py --analysis <outputs>/analysis_dev.json \
    --figures <outputs>/figures --paper <outputs>/paper --out <outputs>
```

Master seed 20260712; all state/goal/exec seeds derived via sha256 of (study_id, role, task, stratum, index, master_seed).
