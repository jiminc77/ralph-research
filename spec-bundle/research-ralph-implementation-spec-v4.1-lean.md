# research-ralph — One-Shot Autonomous Research Harness
## Implementation Specification v4.1 — Lean Baseline

> **상태:** FINAL / implementation-ready / lean baseline  
> **기준일:** 2026-07-12  
> **대체 문서:** `research-ralph Implementation Specification v4.0`  
> **목표:** Phase 1에서 연구 명세를 확정한 뒤, 시작 승인 1회로 실험·검증·집필·Figure·Reviewer ×3·PDF 산출까지 수행하는 단일 사용자용 연구 harness

---

## 0. 최종 설계 원칙

### 0.1 Target threat model

Baseline 구현은 다음 환경을 전제로 함.

- 단일 신뢰 사용자
- private/local repository
- 한 repository당 active run 최대 1개
- worker 최대 병렬도 기본 2개
- 외부 사용자가 임의 task를 제출하지 않는 환경
- 연구 code가 완전히 악성이라고 가정하지 않음
- agent의 실수, 잘못된 command, secret 우발 노출, hidden split leakage는 방지 대상
- multi-tenant service, hostile code execution, regulated data enclave는 범위 밖

따라서 baseline은 **연구 무결성과 복구 가능성에 집중**하고, enterprise-grade isolation은 별도 Hardened profile로 분리함.

### 0.2 v4.0에서 제거하는 구현

| 제거 항목 | Lean 대체 |
|---|---|
| 별도 State Service process + UDS JSON-RPC + task token | Supervisor process 내부 `StateStore` class |
| event sourcing + projection rebuild | SQLite domain tables + append-only debug event table |
| transactional outbox + sidecar fleet | Supervisor의 idempotent local operation |
| content-addressed storage/CAS + object/reference 분리 | run-local artifact directory + SHA-256 manifest |
| task-local independent Git database + bundle import | standard `git worktree` + task branch |
| credential broker / secret sidecar | subprocess environment allowlist + redaction |
| deny-by-default network proxy | role-level tool policy; hardened mode에서만 proxy |
| mount policy engine | Claude Code sandbox + path callback + working directory 제한 |
| atomic multi-resource reservation ledger | single Supervisor의 simple admission check |
| lease epoch/fencing token | task status + attempt + atomic `result.json` |
| per-run template 73-file revalidation | archive hash 1회 확인 + setup-time extraction |
| 별도 VLM Figure checker | Figure controller self-check + Reviewer R3 검토 |
| dashboard/GitHub Pages/notification sidecars | CLI status + local log; notification optional |
| live venue deadline web verification | user-locked venue profile; final submission은 사람 책임 |
| 대규모 fault-injection matrix | 핵심 crash/retry/E2E test만 유지 |

### 0.3 반드시 유지하는 불변식

1. `builder != verifier`
2. search/dev와 hidden confirmation 분리
3. finalist freeze 이전 hidden confirmation 접근 금지
4. hidden result 확인 후 method/config tuning 금지
5. Writer의 raw ledger 접근 금지
6. claim/table/figure 수치는 verified evidence에서만 생성
7. Reviewer R1/R2/R3 모두 `claude-opus-4-8`, adaptive thinking, `effort=max`
8. 후보별 최근접 3편 gate 없음
9. finalist 대상 prior-art collision scan 1회
10. Lane A quantitative plot은 deterministic code
11. Lane B Figure는 Claude Design MCP + 제공된 PaperFigure template 우선
12. Claude Design 장애 시 local template renderer fallback
13. valid null result와 invalid run 분리
14. 결과 Grade A/B/C/D 분리
15. Harness가 conference portal에 직접 제출하지 않음

### 0.4 구현 규모 목표

Baseline implementation 권장 규모:

- Python package 25–40 source files
- SQLite table 9개
- long-running process 1개: Supervisor
- optional subprocess: workers, GJC, LaTeX, Chromium
- mandatory external services: model provider
- optional external service: Claude Design MCP
- required acceptance tests: 32개 이하

---

## 1. Product Contract

### 1.1 사용자 흐름

```text
Phase 1: /ideate 및 repository 편집
  → RESEARCH_SPEC.md
  → DECISION_POLICY.md
  → data_manifest.lock.json
  → statistical_protocol.lock.json
  → venue_profile.lock.yml
  → spec-lint
  → ./ralph start
  → preflight 요약
  → Enter 1회
  → Phase 2 unattended
  → paper/report + grade.json + evidence package
```

### 1.2 Phase 2 운영 command

```bash
./ralph status
./ralph logs [--task TASK_ID]
./ralph pause
./ralph resume
./ralph stop
./ralph kill
```

- `pause`: 신규 task dispatch 중단. 실행 중 task는 기본적으로 완료 허용.
- `resume`: locked scientific config 변경 없이 재개.
- `stop`: 신규 task 중단 후 현재 evidence로 finalization.
- `kill`: worker 즉시 종료. 다음 실행 시 recovery 수행.

### 1.3 기본 산출물

```text
runs/<run_id>/outputs/
├── grade.json
├── run-report.md
├── decisions.jsonl
├── evidence-package/
├── reproducibility-package/
└── one of:
    ├── paper.pdf
    ├── internal-draft.pdf
    ├── research-report.pdf
    └── run-failure-report.md
```

`paper.pdf` 생성 자체가 submission-ready를 의미하지 않음. 최종 상태는 `grade.json`의 `scientific_grade`, `venue_passed`, `submission_ready`로 판정함.

### 1.4 비목표

- academic acceptance 보증
- novelty 완전 증명
- 법적·윤리적 책임 자동 이전
- multi-user cloud service
- arbitrary hostile code 격리
- automatic conference submission
- zero-cost 또는 zero-failure 보증

---

## 2. Phase 1 Inputs and Preflight

### 2.1 필수 입력 파일

| 파일 | 역할 |
|---|---|
| `RESEARCH_SPEC.md` | problem, hypothesis, baseline, candidate family, metrics, mechanism prediction |
| `DECISION_POLICY.md` | 무인 선택·중단·fallback 규칙 |
| `ONE_LINER.md` | contribution sentence template |
| `references.bib` | seed references |
| `data/data_manifest.lock.json` | dataset identity와 split |
| `statistics/statistical_protocol.lock.json` | metric, seeds, aggregate, confirmation rule |
| `venue/venue_profile.lock.yml` | internal/submission/camera-ready format |
| `config.yml` | runtime/model/budget configuration |

### 2.2 `RESEARCH_SPEC.md` 최소 항목

```yaml
problem:
  statement: string
  scope: string

hypothesis:
  observed_failure: string
  causal_hypothesis: string
  falsifier: string

baseline:
  name: string
  command: string
  fairness_constraints: [string]

metrics:
  primary: string
  direction: maximize|minimize
  minimum_effect: number
  guards:
    - name: string
      operator: gte|lte
      threshold: number

candidates:
  min: 2
  max: 4
  representation_alternative_considered: true

mechanism:
  prediction: string
  required_checks: [ablation, counterfactual]
```

### 2.3 `spec-lint` gate

1. baseline 실행 command 존재
2. primary metric와 direction 존재
3. minimum effect와 guard threshold 존재
4. search/dev와 hidden confirmation split 정의
5. seed/repeat/aggregate/selection rule 정의
6. candidate 범위 2–4개 또는 명시적 예외
7. wall-clock, provider cost, compute cap 정의
8. unresolved ASK에 대한 default policy 존재
9. dataset access와 license 상태 기록
10. venue profile compile 가능

고정 “최근접 선행연구 3편” 요구 없음.

### 2.4 Lean preflight

다음만 수행함.

```text
config/spec schema validation
→ repository 상태 확인
→ Python/Git/GJC/LaTeX/Chromium dependency 확인
→ dataset path/hash와 split 확인
→ disk/compute availability 확인
→ distinct model alias별 smoke call
→ GJC RPC startup/unattended/final-event smoke test
→ Claude Design auth 및 간단한 handoff smoke test
→ 실패 시 local Figure fallback smoke test
→ venue template compile smoke test
→ runtime.lock.json 생성
→ 사용자 요약 출력
→ Enter 승인
```

Preflight에서 수행하지 않는 항목:

- outer container enforcement
- global network proxy test
- credential sidecar test
- live conference deadline search
- full crash-injection suite
- template 전체 file hash 재검사

### 2.5 Phase 2 immutable inputs

시작 승인 후 다음 파일을 수정하지 않음.

```text
config.lock.yml
runtime.lock.json
RESEARCH_SPEC.md
DECISION_POLICY.md
ONE_LINER.md
data/data_manifest.lock.json
statistics/statistical_protocol.lock.json
venue/venue_profile.lock.yml
figures/paperfigure/source.lock.json
```

변경 필요 시 새 `run_id` 생성.

---

## 3. Lean Architecture

### 3.1 전체 구조

```text
┌──────────────────────────────────────────────────────────┐
│ ralph Supervisor                                        │
│ scheduler · StateStore · budget · recovery · stage flow │
└───────────────┬───────────────────────────┬──────────────┘
                │ subprocess/stdout         │ local files
        ┌───────▼──────────┐       ┌────────▼──────────────┐
        │ Role workers      │       │ runs/<run_id>/        │
        │ Agent SDK / GJC   │       │ state.db · worktrees  │
        │ verifier / writer │       │ artifacts · evidence  │
        └───────┬──────────┘       │ paper · logs          │
                │ atomic result     └───────────────────────┘
                ▼
        task/result.json
```

### 3.2 Components

| Component | 책임 |
|---|---|
| `Supervisor` | stage flow, task dispatch, recovery, budget, finalization |
| `StateStore` | SQLite read/write. Supervisor process 내부 단일 instance |
| `Scheduler` | dependency, parallelism, remaining budget 기준 dispatch |
| `RoleRunner` | Agent SDK session 실행과 structured result 수집 |
| `GJCAdapter` | JSONL RPC session, unattended gate, final event 처리 |
| `Verifier` | validity, reproduction, hidden confirmation, claim eligibility |
| `EvidenceCompiler` | verified result를 locked evidence files로 변환 |
| `PaperPipeline` | Writer, citations, tables, figures, LaTeX, review |
| `FigurePipeline` | Lane A deterministic plot, Lane B Claude Design/local fallback |

별도 daemon, sidecar, message broker 없음.

### 3.3 Truth sources

| 정보 | Truth |
|---|---|
| runtime/task state | `runs/<run_id>/state.db` |
| code provenance | Git commit |
| experiment files | `runs/<run_id>/artifacts/` + hash manifest |
| scientific claims | `runs/<run_id>/evidence/claims.lock.json` |
| paper source | `runs/<run_id>/paper/` |
| human-readable history | DB `events` + `logs/ralph.log` |

### 3.4 Single-writer rule

- Supervisor만 SQLite write 수행.
- Worker는 DB 접근 금지.
- Worker output은 자신의 workspace의 `result.json`과 artifact files뿐임.
- `ralph status`는 read-only SQLite connection 사용.
- 한 repository에 active Supervisor 1개만 허용. `flock` 기반 `runs/.active.lock` 사용.

---

## 4. Repository and Run Layout

```text
research-ralph/
├── ralph
├── pyproject.toml
├── uv.lock
├── config.yml
├── RESEARCH_SPEC.md
├── DECISION_POLICY.md
├── ONE_LINER.md
├── references.bib
├── data/
│   └── data_manifest.lock.json
├── statistics/
│   └── statistical_protocol.lock.json
├── venue/
│   ├── venue_profile.lock.yml
│   ├── templates/
│   └── check.py
├── ralph_core/
│   ├── cli.py
│   ├── supervisor.py
│   ├── state.py
│   ├── scheduler.py
│   ├── recovery.py
│   ├── budget.py
│   ├── schemas.py
│   ├── roles/
│   │   ├── orchestrator.py
│   │   ├── failure_analyst.py
│   │   ├── verifier.py
│   │   ├── writer.py
│   │   ├── prior_art.py
│   │   ├── figure.py
│   │   └── reviewer.py
│   ├── adapters/
│   │   ├── agent_sdk.py
│   │   ├── gjc_rpc.py
│   │   └── compute.py
│   ├── science/
│   │   ├── experiments.py
│   │   ├── statistics.py
│   │   └── evidence.py
│   └── paper/
│       ├── citations.py
│       ├── tables.py
│       ├── figures.py
│       ├── latex.py
│       └── grading.py
├── figures/
│   └── paperfigure/
│       ├── PaperFigure Design System (ICRAICLR)-handoff.zip
│       ├── source.lock.json
│       ├── vendor/
│       ├── local_renderer/
│       └── overrides/
├── schema/
│   ├── core-v4.1-lean.sql
│   └── worker-result.schema.json
├── tests/
└── runs/
    └── <run_id>/
        ├── state.db
        ├── runtime.lock.json
        ├── worktrees/
        ├── tasks/
        ├── artifacts/
        ├── evidence/
        ├── paper/
        ├── outputs/
        └── logs/
```

### 4.1 Workspace 규칙

- Builder task당 `git worktree` 1개.
- Analysis/Writer/Reviewer는 필요 시 일반 directory 사용.
- 모든 worker output은 `runs/<run_id>/tasks/<task_id>/` 또는 지정 worktree 내부에 작성.
- artifact ingest 후 task workspace 삭제 가능.
- task workspace 외부 write 금지.

---

## 5. Runtime State and Worker Protocol

### 5.1 SQLite 설정

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

정규 schema는 bundle의 `schema/core-v4.1-lean.sql` 사용.

### 5.2 Core tables

```text
runs
tasks
experiments
metrics
artifacts
decisions
model_calls
reviews
events
```

실제 table name은 모두 lowercase 사용.

제거된 table:

```text
leases
sessions
outbox_messages
artifact_objects
artifact_refs
budget_reservations
projection_offsets
asks
claims
citations
```

Claims와 citations는 final lock file로 관리하며 runtime DB에 중복 저장하지 않음.

### 5.3 Task lifecycle

```text
queued
→ running
→ completed

exception:
failed
interrupted
cancelled
blocked
```

- `completed`: worker `result.json` schema 통과와 required artifacts 확인 완료 상태.
- scientific experiment state는 task state와 별도.
- process exit code 0만으로 completed 처리 금지.

### 5.4 Worker result contract

Worker는 같은 directory에 먼저 `result.tmp.json`을 쓰고 `fsync` 후 `result.json`으로 atomic rename함.

```json
{
  "schema_version": "4.1",
  "task_id": "TASK-S3-C2",
  "status": "completed",
  "summary": "...",
  "source_commit": "<git-sha-or-null>",
  "experiments": [
    {
      "experiment_id": "EXP-0042",
      "purpose": "search",
      "status": "valid",
      "data_split": "search_dev",
      "config_hash": "sha256:...",
      "seeds": [11, 23, 37],
      "aggregate": {"primary": 0.72},
      "guards": {"latency": "passed"},
      "manifest": "artifacts/EXP-0042/manifest.json"
    }
  ],
  "artifacts": [
    {
      "kind": "metrics",
      "path": "out/metrics.json",
      "sha256": "..."
    }
  ],
  "findings": [],
  "limitations": [],
  "next_action": "continue|retry|stop|none"
}
```

Supervisor ingest 절차:

1. task ID와 status 검증
2. result path가 task directory 내부인지 확인
3. required artifact 존재와 hash 확인
4. Git commit 존재와 clean status 확인
5. SQLite transaction으로 task/experiment/metric/artifact 기록
6. ingest 완료 marker 생성

같은 task의 result를 재수집해도 unique key 기준 no-op 처리.

### 5.5 Artifact storage

```text
runs/<run_id>/artifacts/<experiment_id>/
├── manifest.json
├── metrics.json
├── stdout.log
├── stderr.log
└── selected files
```

`manifest.json` 필수 항목:

```json
{
  "experiment_id": "EXP-0042",
  "source_commit": "...",
  "command": ["python", "train.py", "--config", "..."],
  "environment": {
    "python": "3.12.x",
    "dependency_lock_sha256": "...",
    "hardware": "..."
  },
  "dataset_hash": "...",
  "split": "search_dev",
  "seeds": [11, 23, 37],
  "files": [
    {"path": "metrics.json", "sha256": "...", "size": 1234}
  ]
}
```

CAS와 deduplication 없음. 한 run 내 복사 비용을 단순성보다 우선하지 않음.

### 5.6 Crash recovery

Supervisor 재시작 시:

1. active lock 획득
2. run status와 stage load
3. `running` task를 `interrupted`로 변경
4. 각 task의 `result.json` 검사
5. valid complete result면 ingest 후 `completed`
6. 불완전 result면 attempt 증가 후 retry 또는 failed
7. Git worktree와 artifact partial file 정리
8. scheduler 재개

PID 재연결, lease epoch, fencing token 없음.

SSH/HPC adapter는 `external_job_id`가 있을 때만 scheduler/job status를 조회하고 살아 있는 job은 유지 가능.

---

## 6. Stage State Machine

### 6.1 Global states

```text
created
→ preflight
→ ready
→ running:S0..S5
→ finalizing
→ completed

branches:
paused
stopping
failed
killed
```

### 6.2 Stage overview

| Stage | 목적 | 기본 budget 비율 |
|---|---|---:|
| S0 | environment와 baseline smoke | 5% |
| S1 | naive baseline 실행 | 12% |
| S2 | failure analysis | 13% |
| S3 | candidate experiments | 40% |
| S4 | freeze, reproduce, confirm, evidence lock | 15% |
| S5 | prior art, paper, figures, review | 15% |

비율은 guide이며 hard reservation 아님.

### 6.3 S0 — Setup

필수 작업:

- dependency lock 확인
- dataset sample read
- metric instrumentation smoke
- baseline command short run
- result contract smoke
- Git worktree create/delete smoke

Exit:

- baseline launch 가능
- metric schema 유효
- data hash 일치
- artifact manifest 생성 가능

### 6.4 S1 — Baseline

필수 산출물:

- required seeds baseline metrics
- aggregate와 CI
- failure sample index
- resource usage
- validity verdict

Exit:

- baseline valid 또는 명시적 Grade D 종료
- S2가 읽을 수 있는 failure evidence 존재

### 6.5 S2 — Failure Analysis

Failure analyst 입력은 valid baseline evidence만 허용.

출력:

```json
{
  "cause_clusters": [],
  "instrumentation_risks": [],
  "candidates": [
    {
      "candidate_id": "C1",
      "cause_target": "...",
      "mechanism_prediction": "...",
      "falsifier": "...",
      "minimal_delta": "...",
      "estimated_cost": {},
      "required_checks": []
    }
  ],
  "representation_alternative_assessment": {}
}
```

Exit:

- candidate 2–4개
- 각 candidate가 cause cluster와 연결
- mechanism prediction/falsifier 존재
- representation alternative 검토 기록

이 단계에서 prior-art gate 없음.

### 6.6 S3 — Candidate Experiments

- candidate별 worktree와 GJC task 생성.
- 기본 병렬도 2.
- candidate별 동일한 compute fairness rule 적용.
- ranking은 aggregate 기반.
- best single seed 사용 금지.
- invalid run과 valid null result 분리.

Exit:

- finalist eligibility 후보 최소 1개, 또는
- 모든 후보가 valid null/guard failure여서 Grade C 경로 선택

### 6.7 S4 — Freeze, Reproduce, Confirm

순서 고정:

```text
search result validity 확정
→ finalist 선택
→ finalist.lock.json 생성
→ independent reproduction on search/dev
→ non-hidden ablation/counterfactual
→ claim family와 success criterion freeze
→ hidden confirmation 1회
→ evidence lock 생성
```

`finalist.lock.json`:

```json
{
  "candidate_id": "C2",
  "source_commit": "...",
  "config_hash": "...",
  "checkpoint_rule": "...",
  "seed_rule": "...",
  "claim_families": ["performance", "mechanism"],
  "success_criterion": "...",
  "frozen_at": "..."
}
```

Hidden confirmation 이후 허용:

- 동일 tuple의 mechanical retry
- wording 축소
- limitation 추가

Hidden confirmation 이후 금지:

- architecture 변경
- hyperparameter tuning
- checkpoint selection 변경
- seed selection 변경
- 더 강한 claim 추가

### 6.8 S5 — Positioning and Paper

```text
prior-art collision scan 1회
→ evidence-bound outline
→ Writer draft
→ Lane A plots
→ Lane B Figure
→ citation/table/claim lint
→ PDF build
→ Reviewer R1/R2/R3 round 1
→ targeted fix
→ 필요 시 round 2
→ final grade
```

---

## 7. Scientific Integrity

### 7.1 Data split contract

```json
{
  "dataset": {
    "name": "...",
    "version": "...",
    "content_hash": "sha256:...",
    "license": "..."
  },
  "splits": {
    "train": {"path": "...", "manifest_hash": "..."},
    "search_dev": {"path": "...", "manifest_hash": "..."},
    "hidden_confirmation": {
      "path": "...",
      "manifest_hash": "...",
      "sealed": true
    }
  },
  "preprocessing": {
    "commit": "...",
    "config_hash": "..."
  }
}
```

### 7.2 Access rule

| Role | train | search/dev | hidden confirmation |
|---|---:|---:|---:|
| Builder/GJC | yes | yes | no |
| Failure analyst | derived evidence | yes | no |
| Orchestrator | aggregate only | aggregate only | final summary only |
| Verifier pre-confirmation | yes | yes | no |
| Verifier confirmation | no need | reference only | yes |
| Writer/Figure/Reviewer | no raw rows | no raw rows | no raw rows |

구현 방식:

- Builder subprocess environment와 task input에 hidden path를 포함하지 않음.
- Claude/Agent path permission callback이 task workspace와 approved search data만 허용.
- confirmation task 생성 시에만 Supervisor가 hidden path를 verifier command에 전달.
- 별도 credential broker 없음.

### 7.3 Statistical protocol

```json
{
  "primary_metric": "success_rate",
  "direction": "maximize",
  "minimum_effect": 0.03,
  "search": {
    "seeds": [11, 23, 37],
    "aggregate": "mean",
    "uncertainty": "bootstrap_ci_95",
    "selection": "highest_lower_ci_bound_subject_to_guards"
  },
  "confirmation": {
    "seeds": [101, 103, 107, 109, 113],
    "attempts": 1,
    "success_rule": "pre_registered"
  },
  "failed_seed_policy": "diagnose_then_apply_pre_registered_rule",
  "stopping_rule": "budget_or_futility"
}
```

### 7.4 Experiment lifecycle

```text
created
→ running
→ completed
→ valid
→ reproduced
→ confirmed
→ claim_eligible
```

Terminal states:

```text
invalid_run
mechanical_failure
optimization_failure
valid_null_result
cancelled
```

- `valid`: data/code/instrumentation가 의도한 experiment를 실행했다고 판정된 상태.
- `reproduced`: 별도 verifier task가 locked tuple을 재실행한 상태.
- `confirmed`: hidden protocol 통과 상태.
- `claim_eligible`: statistical/guard/mechanism requirement까지 통과한 상태.

### 7.5 Mechanism claims

Causal wording 허용 조건:

1. performance evidence 통과
2. preregistered ablation 통과
3. counterfactual 또는 perturbation 통과
4. 주요 alternative explanation 최소 1개 배제
5. claim wording가 setting 범위를 초과하지 않음

미충족 시 descriptive/performance claim으로 축소.

### 7.6 Prior-art collision scan

- S4 finalist freeze 후 정확히 1회.
- 고정 논문 수 없음.
- accepted archival paper와 public preprint/OpenReview 모두 검색.
- public preprint는 novelty collision 판단에는 사용 가능.
- preprint 결과를 scientific fact로 의존하려면 독립 evidence 필요.
- repository/blog는 implementation clue로만 사용.

결과:

```text
NO_DIRECT_COLLISION
POSSIBLE_OVERLAP
DIRECT_COLLISION
```

`DIRECT_COLLISION` 처리:

- 자동 후보 폐기 금지
- new-method claim 제거 가능
- mechanism insight, replication, robustness, bounded extension으로 contribution 재분류

---

## 8. Roles and Model Allocation

### 8.1 Default roles

| Role | Default model | Effort | 설명 |
|---|---|---|---|
| Orchestrator | `claude-fable-5` | high | stage decision와 task brief |
| Failure analyst | `claude-opus-4-8` | high | failure clustering와 candidate generation |
| Verifier | `claude-fable-5` | high | validity, reproduction, confirmation, claims |
| Prior-art positioner | `claude-opus-4-8` | high | finalist collision scan |
| Writer | `claude-fable-5` | high | locked evidence 기반 manuscript |
| Figure controller | `claude-opus-4-8` | max | Claude Design/local template orchestration |
| Citation checker | `claude-sonnet-5` | low | metadata와 support check |
| Reviewer R1 | `claude-opus-4-8` | max | soundness/statistics |
| Reviewer R2 | `claude-opus-4-8` | max | originality/significance |
| Reviewer R3 | `claude-opus-4-8` | max | clarity/Figure/venue/red-team |

Model alias는 `config.lock.yml`에서 override 가능. 단 Reviewer 3개 exact model/effort는 변경 금지 unless user explicitly revises specification.

### 8.2 Reviewer request contract

```yaml
model: claude-opus-4-8
thinking:
  type: adaptive
effort: max
max_tokens: 65536
sampling:
  use_provider_defaults: true
```

### 8.3 Session policy

- task별 fresh session 기본.
- Reviewer는 항상 cold-start.
- R1/R2/R3는 서로의 output 비공개.
- session이 context limit에 접근하면 current task summary를 `successor-packet.md`에 저장하고 새 session 1회 허용.
- 동일 task session rotation 2회 초과 시 blocked 처리.

### 8.4 Model logging

각 call에 다음 기록:

```text
role
resolved model name
effort
start/end
input/output tokens
estimated cost
stop reason
status
```

별도 Model Gateway 없음. SDK/CLI adapter가 직접 기록.

### 8.5 Fallback

- transient/rate-limit: 같은 model 최대 2회 retry.
- Orchestrator/Writer/Verifier: `config`에 정의된 fallback 허용.
- Reviewer: 다른 model fallback 금지. 실패 시 review incomplete 및 Grade A 차단.
- Figure controller: model failure 시 local template renderer로 전환 가능하나 Figure quality limitation 기록.

---

## 9. Git and Workspaces

### 9.1 Branch/worktree model

```text
base branch: main or configured base
builder branch: ralph/<run_id>/<task_id>
workspace: runs/<run_id>/worktrees/<task_id>/
```

Supervisor 동작:

```bash
git worktree add -b ralph/<run>/<task> <path> <base_commit>
```

Worker 동작:

- 지정 branch/worktree 내 edit와 commit 가능.
- `git push`, force push, remote 변경 금지.
- 다른 task branch를 수정하지 않음.

### 9.2 Merge rule

Finalist 또는 필요한 infrastructure patch만 Supervisor가 merge/cherry-pick함.

검사:

- expected base commit
- clean worktree
- changed path allowlist
- hidden data 또는 secret 포함 여부
- required tests
- verifier verdict

독립 Git DB, bundle export/import, signed commit 요구 없음.

Crash-safe local operation 규칙:

- worktree create 전 branch/path 존재 여부 확인
- merge/cherry-pick 전 target branch에 commit 포함 여부 확인
- artifact copy는 temporary file + hash + atomic rename
- output build는 temporary directory에서 완료 후 최종 path 교체

별도 outbox 없이 위 검사로 재실행 안전성 확보.

### 9.3 Reproducibility tuple

Valid experiment마다 기록:

```text
source commit
base commit
dependency lock hash
Python/runtime version
hardware summary
dataset/split hash
command argv
relevant environment values
random seeds
metric schema version
artifact hashes
```

---

## 10. GJC RPC Integration

### 10.1 Pinning

- GJC git ref 또는 package version을 `runtime.lock.json`에 기록.
- exact commit pin 권장이나 development에서는 version tag 허용.
- protocol major mismatch 시 start 실패.

### 10.2 Minimum contract

Adapter가 지원해야 할 동작:

1. process startup와 `ready`
2. unattended negotiation
3. prompt send와 immediate acknowledgment 분리
4. event sequence 수신
5. final `agent_end` 관찰
6. workflow gate를 `DECISION_POLICY`로 resolve
7. cancel/terminate
8. stdout JSONL 이외 로그를 stderr로 분리

Prompt acknowledgment를 task completion으로 처리하지 않음.

### 10.3 Minimal smoke test

```text
start GJC
→ negotiate unattended
→ trivial read/edit/test task
→ receive prompt ack
→ receive agent_end
→ validate result files
→ terminate cleanly
```

Full protocol fuzzing, reconnect sequence reconciliation, bridge ownership test는 baseline 필수 아님.

### 10.4 GJC role defaults

```yaml
main:      claude-fable-5/high
planner:   claude-fable-5/high
architect: gpt-5.6-sol/xhigh
executor:  gpt-5.6-terra/low
critic:    gpt-5.6-sol/high
```

`gpt-5.6-sol`, `gpt-5.6-terra`는 project-specific alias. Resolve 실패 시 해당 role을 configured alternative로 대체하거나 preflight fail.

### 10.5 Completion boundary

GJC의 “done”은 Ralph에서 다음을 모두 통과해야 `completed`임.

- `agent_end`
- required file 존재
- test exit status
- `result.json` schema
- artifact hash
- commit cleanliness

---

## 11. Lean Security Baseline

### 11.1 Mandatory controls

Baseline에서 다음 7개만 필수.

1. non-root user 실행
2. Claude Code sandbox 사용
3. unsandboxed fallback 금지
4. worker cwd와 file-tool path boundary 제한
5. subprocess environment allowlist와 log redaction
6. Builder hidden split path 비공개
7. automatic `git push` 및 destructive remote operation 금지

### 11.2 Claude Code sandbox

권장 설정:

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "allowUnsandboxedCommands": false
  }
}
```

추가 custom network proxy, managed setting deployment, Unix socket filter는 baseline 요구 아님.

### 11.3 Agent SDK options

```python
ClaudeAgentOptions(
    cwd=task_workspace,
    setting_sources=[],
    strict_mcp_config=True,
    allowed_tools=role_allowed_tools,
    disallowed_tools=role_denied_tools,
    can_use_tool=path_and_command_guard,
)
```

`allowed_tools`만으로 restriction이 완성된다고 가정하지 않음. `disallowed_tools`와 path guard 사용.

Figure controller는 user `.mcp.json` discovery에 의존하지 않고 Claude Design endpoint를 `mcp_servers`에 명시적으로 전달함. `strict_mcp_config=True` 상태에서 해당 server만 사용.

최소 path guard:

- read/write path가 task workspace 또는 명시적 input root 내부인지 확인
- hidden confirmation root는 confirmation verifier 외 거부
- `~/.ssh`, `~/.aws`, `~/.config/gcloud`, `.env`, repository credential file 거부
- `git push`, `gh auth`, destructive filesystem root command 거부

### 11.4 Environment handling

Worker environment는 allowlist로 생성.

기본 허용 예시:

```text
PATH
HOME
TMPDIR
LANG
LC_ALL
CUDA_VISIBLE_DEVICES
provider authentication required by the selected adapter
explicit dataset/cache variables
```

기본 제거 예시:

```text
GITHUB_TOKEN
GH_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
GOOGLE_APPLICATION_CREDENTIALS
SSH_AUTH_SOCK
KUBECONFIG
```

Provider credential이 worker 자체에 필요하면 해당 role에만 전달하고 stdout/stderr redaction 적용.

### 11.5 Network

Baseline은 OS-level deny-by-default proxy를 구현하지 않음.

- Builder: dependency 설치는 preflight에서 수행. task 중 network 사용 최소화.
- Prior-art/Citation: web/API 사용 허용.
- Figure controller: Claude Design MCP 사용 허용.
- Writer/Reviewer: model service 외 별도 browsing은 rubric에 명시되지 않으면 사용 금지.

민감 data, shared host, untrusted repository인 경우 optional Hardened profile 사용.

### 11.6 Explicitly out of baseline

```text
outer container mandatory enforcement
credential sidecar
short-lived bearer token
network egress proxy
per-role mount namespace
CAS isolation
canonical .git concealment
TLS inspection
multi-tenant ACL
```

### 11.7 Optional Hardened profile trigger

다음 조건이면 baseline 대신 별도 profile 필요.

- third-party untrusted code 실행
- restricted/regulated dataset
- shared multi-user compute node
- public service 형태
- organization credential가 같은 host에 존재
- arbitrary MCP/plugin 허용

Hardened profile은 container, network allowlist, read-only mounts, secret broker를 추가할 수 있으나 v4.1 Definition of Done 범위 밖.

---

## 12. Failure, Retry, Recovery, and Budget

### 12.1 Failure taxonomy

```text
invalid_run
  code_error | data_error | environment_error | instrumentation_error

mechanical_failure
  OOM | timeout | process_crash | disk_exhaustion | provider_error

optimization_failure
  divergence | instability | non_convergence

valid_null_result
  no_improvement | guard_failure | mechanism_prediction_failed
```

NaN/Inf는 diagnosis 후 분류.

### 12.2 Retry policy

| Failure | 자동 retry | 조건 |
|---|---:|---|
| provider transient/rate limit | 2 | same request |
| process crash | 1 | same task |
| OOM | 1 | preregistered batch reduction만 |
| timeout | 1 | bounded extension |
| invalid code/instrumentation | 최대 2 fix loop | 새 experiment ID |
| optimization failure | policy에 따름 | preregistered fallback만 |
| valid null result | 0 | 다음 candidate로 진행 |
| hidden confirmation | 0 | same-tuple mechanical retry만 |

### 12.3 Simple budget accounting

Supervisor가 다음 값만 관리.

```text
wall-clock deadline
provider cost cap
GPU-hour cap
max parallel tasks
minimum finalization reserve
```

Dispatch 전:

```text
estimated task cost <= remaining cost - finalization reserve
estimated GPU hours <= remaining GPU hours
current parallel tasks < max parallel
current time < deadline - finalization reserve
```

Single Supervisor이므로 DB reservation transaction 불필요.

동시 실행 task의 estimate 합계는 in-memory `committed_budget`으로 차감. Supervisor restart 시 running task를 interrupted로 간주하고 committed amount를 재계산.

실제 사용량이 cap을 넘으면:

- 실제 usage 기록
- 신규 experiment 중단
- active task는 policy에 따라 종료
- S5 또는 partial finalization 진입

### 12.4 Wind-down

기본 finalization reserve:

```text
max(30 minutes, total wall-clock의 10%)
provider cost cap의 10%
```

Reserve 진입 시:

- 신규 candidate 금지
- 완료 가능한 active task만 유지
- current evidence lock
- Grade B/C/D라도 output 생성

---

## 13. Evidence, Writer, Tables, and Citations

### 13.1 Evidence files

S4 종료 시 다음 생성.

```text
evidence/
├── claims.lock.json
├── tables.lock.json
├── figures.lock.json
├── citations.lock.json
├── finalist.lock.json
└── reproducibility.lock.json
```

### 13.2 Claim schema

```json
{
  "claim_id": "C-007",
  "type": "performance|mechanism|robustness|negative|limitation",
  "status": "eligible|restricted|blocked",
  "canonical_text": "...",
  "scope": "...",
  "evidence": [
    {
      "experiment_id": "EXP-0042",
      "metric": "success_rate",
      "effect": 0.041,
      "ci95": [0.018, 0.063],
      "comparison": "BASE-01"
    }
  ],
  "confirmation": "confirmed|reproduced_only|search_only",
  "mechanism": "passed|not_passed|not_required",
  "limitations": []
}
```

### 13.3 Writer boundary

Writer 허용 입력:

```text
RESEARCH_SPEC.md
ONE_LINER.md
claims.lock.json
tables.lock.json
figures.lock.json
citations.lock.json
prior-art-positioning.json
venue profile
```

Writer 금지 입력:

```text
state.db
raw experiments table
per-seed unapproved metrics
hidden rows
failed/invalid raw outputs
Reviewer future prompts
```

추가 evidence 필요 시 `evidence-gap.json` 생성. Verifier가 lock file을 수정하거나 거부.

### 13.4 Table generation

- `tables.lock.json`의 값만 사용.
- TeX table은 deterministic generator로 생성.
- manual number transcription 금지.
- rounding, CI, bolding rule 고정.
- invalid/missing result는 명시적 marker 사용.

### 13.5 Citation lifecycle

간소화된 상태:

```text
pending
verified
uncertain
rejected
```

`verified` 조건:

- title/author/year/identifier 확인
- source 존재
- cited sentence와 source support 정합

`uncertain`은 문장 완화 또는 source 교체. `rejected`는 claim/citation 수정.

Citation checker가 모든 paper를 완전 검증한다고 주장하지 않음.

### 13.6 Claim lint

차단 대상:

- best seed를 aggregate처럼 표현
- search/dev를 hidden confirmation처럼 표현
- mechanism evidence 없이 causal wording
- evidence 범위를 넘는 universal claim
- support 없는 `first`, `state-of-the-art`, `consistently`

---

## 14. Figure System and Claude Design

### 14.1 Two lanes

| Lane | 대상 | 생성 |
|---|---|---|
| Lane A | line/bar/scatter/heatmap/quantitative result | deterministic Python/Matplotlib/PGFPlots |
| Lane B | method/architecture/influence diagram | Claude Design MCP 우선, local PaperFigure fallback |

LLM이 Lane A data, scale, error bar, value를 변경하는 행위 금지.

### 14.2 Provided PaperFigure template

사용 archive:

```text
PaperFigure Design System (ICRAICLR)-handoff.zip
SHA-256: d4cb4667d0c014871a0271a107f337bd4be97e0382a06a493f013a19a2909ba6
```

Setup 시:

1. archive hash 확인
2. `figures/paperfigure/vendor/`에 extract
3. source archive와 `source.lock.json` 보존
4. generated override만 `overrides/`에 작성
5. original vendor file 직접 수정 금지

매 run마다 73개 file 전체 재hash하지 않음. Setup 또는 CI에서만 companion manifest 검증.

### 14.3 Claude Design MCP setup

```bash
claude mcp add \
  --scope user \
  --transport http \
  claude-design \
  https://api.anthropic.com/v1/design/mcp
```

초기 사용자 인증:

```text
/design-login
```

Template/design system 연결은 `/design-sync` 또는 MCP가 실제 제공하는 import/handoff flow 사용. Agent SDK Figure controller에서는 user configuration을 자동 load하지 않고 다음 endpoint를 explicit MCP config로 전달함.

```yaml
mcp_servers:
  claude-design:
    type: http
    url: https://api.anthropic.com/v1/design/mcp
strict_mcp_config: true
```

Preflight 최소 확인:

- authentication 성공
- create/edit tool 호출 가능
- PaperFigure context 전달 가능
- 결과를 local code/handoff 형태로 회수 가능

Machine-readable handoff가 없거나 quota/service failure이면 즉시 local fallback. 별도 `design_capabilities.lock.json` 없음. 상태는 `runtime.lock.json`에 다음만 기록.

```json
{
  "claude_design": {
    "status": "available|fallback",
    "checked_at": "...",
    "handoff": "code|html|zip|none"
  }
}
```

### 14.4 Figure controller contract

Figure controller:

```text
model: claude-opus-4-8
effort: max
input: figure-spec.json + PaperFigure template + verified facts
output: raw handoff + normalized PDF/SVG/PNG + figure-report.json
```

Claude Design 내부 model/version은 Ralph가 주장하지 않음.

### 14.5 `figure-spec.json`

```json
{
  "figure_id": "FIG-02",
  "lane": "B",
  "purpose": "method_overview",
  "claim_ids": ["C-001", "C-004"],
  "template": "paperfigure/architecture-figure",
  "target": {
    "width": "two-column",
    "aspect_ratio": 1.65,
    "min_text_pt": 8.5
  },
  "nodes": [
    {"id": "N1", "label": "Observation Encoder", "fact_ids": ["F-019"]}
  ],
  "edges": [
    {"from": "N1", "to": "N2", "label": "latent state", "fact_ids": ["F-023"]}
  ],
  "forbidden": ["unverified metric", "new module", "decorative imagery"],
  "caption": "..."
}
```

### 14.6 Claude Design path

```text
figure-spec
→ Figure controller
→ Claude Design MCP create/edit
→ code/HTML/handoff 회수
→ local normalization
→ figure.pdf + preview.png
→ deterministic checks
→ paper include
```

Direct SVG/PDF export를 전제하지 않음.

### 14.7 Local fallback

Fallback renderer는 제공된 PaperFigure component와 CSS token을 사용하여 standalone HTML 또는 SVG 생성.

```text
figure-spec
→ Jinja/React-free local renderer
→ standalone HTML/SVG
→ Chromium 또는 vector converter
→ PDF + PNG preview
```

Baseline fallback 요구:

- network 없이 render
- system/embedded approved font
- external JavaScript dependency 없음
- same node/edge/caption content 유지

### 14.8 Figure checks

필수:

- file render 성공
- clipping/overflow 없음
- minimum font size
- caption 존재
- node/edge가 `figure-spec`과 일치
- claim/fact ID trace 가능
- Lane A source data hash 일치
- grayscale에서도 구조 구분 가능
- final PDF에서 font/render 오류 없음

별도 VLM checker 없음. Semantic/visual reject risk는 Reviewer R3가 확인.

### 14.9 Template rights note

Template은 user-provided private asset으로 취급. Public repository에 original archive/reference PNG를 재배포하기 전 사용자가 권리 상태 확인. Runtime hard gate 아님.

---

## 15. Independent Reviewer Ensemble

### 15.1 Shared contract

- R1/R2/R3 전부 `claude-opus-4-8`
- adaptive thinking
- `effort=max`
- cold-start
- 다른 Reviewer output 비공개
- frozen PDF와 reviewer별 evidence bundle 사용
- structured JSON output

Finding schema:

```json
{
  "finding_id": "R1-005",
  "severity": "fatal|major|minor|suggestion",
  "location": "p.4 §3.2",
  "claim_id": "C-007|null",
  "issue": "...",
  "evidence": "...",
  "required_action": "...",
  "confidence": 4
}
```

### 15.2 R1 — Soundness and Statistics

검토:

- leakage
- baseline fairness
- aggregate/CI/test
- reproducibility
- causal/mechanism support
- invalid run 처리

### 15.3 R2 — Originality and Significance

검토:

- collision scan coverage
- closest overlap
- contribution scope
- accepted/preprint positioning
- significance와 likely reviewer objection

### 15.4 R3 — Clarity, Figure, Venue, Red-team

검토:

- argument flow
- missing assumptions
- Figure-caption-method consistency
- unsupported wording
- venue/anonymity/format issues
- strongest reject rationale

### 15.5 Review rounds

- Round 1: 항상 R1/R2/R3 전부 실행.
- fatal/major 0개: final gate 진행.
- fatal/major 존재: targeted fix + affected verifier/lint rerun.
- Round 2: 수정 후 budget과 time이 충분하면 R1/R2/R3 전부 재실행.
- Round 2를 수행하지 못하고 unresolved major가 남으면 Grade A 금지.
- 최대 2 rounds.

별도 meta-review model 없음. Supervisor가 deterministic severity rule로 disposition.

---

## 16. Paper, Venue, and Grading

### 16.1 Venue profile

```yaml
name: generic-research-report-v1
mode: internal
active: false
latex_template: venue/templates/generic
page_size: letter
main_page_limit: null
file_size_mb: 20
anonymous: false
required_sections:
  - limitations
llm_disclosure: optional
```

Submission/camera-ready profile은 별도 file로 제공 가능.

Live deadline verification 없음. `active` 값은 사용자가 Phase 1에서 lock.

### 16.2 Deterministic PDF gates

- LaTeX compile 성공
- missing reference/citation 0개
- page size와 page limit
- file size
- font embedding/render error
- figure overflow
- table overflow
- profile 요구 시 anonymity scan
- profile required section 존재
- claim/table/figure IDs가 lock file에 존재

### 16.3 Scientific grades

#### Grade A

- valid baseline과 finalist
- independent reproduction
- hidden confirmation 통과
- required mechanism checks 또는 claim 축소
- evidence locks 완성
- Reviewer unresolved fatal/major 0개
- PDF gates 통과

#### Grade B

- coherent/reproduced evidence가 있으나 다음 중 하나 존재:
  - hidden confirmation 부재/미통과
  - unresolved major review
  - citation/venue limitation
  - Reviewer incomplete

#### Grade C

- valid null result, guard failure, mechanism falsification, inconclusive evidence
- scientific report는 작성 가능
- performance contribution paper로 표기 금지

#### Grade D

- baseline/data/instrumentation validity 확보 실패
- reliable scientific conclusion 불가

### 16.4 Output mapping

| Grade | File |
|---|---|
| A | `paper.pdf` |
| B | `internal-draft.pdf` |
| C | `research-report.pdf` |
| D | `run-failure-report.md` |

### 16.5 `grade.json`

```json
{
  "run_id": "RUN-...",
  "scientific_grade": "A",
  "confirmed": true,
  "review_complete": true,
  "unresolved_fatal": 0,
  "unresolved_major": 0,
  "venue_passed": true,
  "submission_ready": false,
  "submission_ready_reason": "human final review required",
  "output": "paper.pdf",
  "limitations": []
}
```

`submission_ready`는 profile이 active이고 deterministic gate를 통과해도 기본 false. 사람의 final review 후 외부에서 변경 가능.

---

## 17. Configuration

### 17.1 `config.yml`

```yaml
schema_version: "4.1"

run:
  name: example
  wall_clock_hours: 8
  provider_cost_cap_usd: 100
  gpu_hour_cap: 12
  max_parallel_tasks: 2
  finalization_reserve_minutes: 30

repository:
  base_branch: main
  require_clean_start: true
  allow_worker_commit: true
  allow_git_push: false

models:
  orchestrator: claude-fable-5
  verifier: claude-fable-5
  writer: claude-fable-5
  failure_analyst: claude-opus-4-8
  prior_art: claude-opus-4-8
  figure_controller: claude-opus-4-8
  reviewer: claude-opus-4-8

review:
  reviewers: [R1, R2, R3]
  effort: max
  max_tokens: 65536
  max_rounds: 2

experiments:
  min_candidates: 2
  max_candidates: 4
  max_parallel: 2
  hidden_confirmation_attempts: 1

security:
  profile: lean
  sandbox_required: true
  allow_unsandboxed_commands: false
  setting_sources: []
  strict_mcp_config: true
  scrub_environment: true
  allow_network_proxy: false

figures:
  lane_a: deterministic
  lane_b:
    provider: claude-design-mcp
    template: paperfigure-v1
    fallback: local-paperfigure-renderer
    require_direct_svg: false

venue:
  profile: generic-research-report-v1
  mode: internal

monitoring:
  local_log: true
  dashboard: false
  notifications: false
```

### 17.2 `runtime.lock.json`

```json
{
  "created_at": "...",
  "python": "...",
  "git": "...",
  "claude_code": "...",
  "agent_sdk": "...",
  "gjc": {"version": "...", "protocol": 2},
  "models": {
    "claude-fable-5": "resolved-id",
    "claude-opus-4-8": "resolved-id",
    "claude-sonnet-5": "resolved-id"
  },
  "claude_design": {
    "status": "available|fallback",
    "handoff": "code|html|zip|none"
  },
  "template_archive_sha256": "d4cb4667d0c014871a0271a107f337bd4be97e0382a06a493f013a19a2909ba6",
  "dependency_lock_sha256": "..."
}
```

Exact software version을 specification에 hard-code하지 않고, 설치된 version과 smoke-test result를 runtime lock에 기록.

---

## 18. Decision Policy

### 18.1 Precedence

```text
scientific integrity invariant
> config.lock.yml
> statistical protocol
> DECISION_POLICY.md
> stage policy
> Orchestrator recommendation
```

### 18.2 Unattended question handling

Phase 2에서 사람 질문을 기다리지 않음.

Resolution 순서:

1. `DECISION_POLICY.md` rule match
2. conservative default
3. scope 축소
4. task blocked 후 partial finalization

ASK UI, durable gate broker, timeout notification 없음.

GJC `workflow_gate`는 위 resolver가 즉시 machine response 생성.

### 18.3 Decision log

```json
{
  "decision_id": "DEC-...",
  "stage": "S3",
  "kind": "candidate_selection",
  "choice": "C2",
  "rationale": "highest lower CI bound subject to guards",
  "evidence": ["EXP-0042", "EXP-0045"],
  "created_at": "..."
}
```

DB와 `outputs/decisions.jsonl`에 기록.

---

## 19. Acceptance Tests

### 19.1 Runtime — 7 tests

1. single active Supervisor lock 동작
2. concurrent worker 2개 result ingest 시 DB 손상 없음
3. worker exit 0 + missing result가 completed 처리되지 않음
4. `result.json` duplicate ingest가 duplicate row를 만들지 않음
5. Supervisor kill 후 running task가 interrupted/retry로 복구
6. partial artifact/hash mismatch 검출
7. wall-clock/cost cap에서 신규 task dispatch 중단

### 19.2 Scientific integrity — 8 tests

8. Builder task input/environment에 hidden path 없음
9. path guard가 Builder의 hidden root access 거부
10. finalist freeze 전 confirmation task 생성 거부
11. hidden result 후 config 변경 시 Grade A 거부
12. best seed 값이 claim/table aggregate로 진입하지 못함
13. invalid run이 valid null result로 처리되지 않음
14. mechanism check 실패 시 causal wording 차단
15. hidden confirmation 없는 run이 Grade A 생성 불가

### 19.3 Security — 5 tests

16. sandbox unavailable + required=true이면 start 실패
17. unsandboxed fallback request 거부
18. common secret env가 worker에서 제거됨
19. `git push` command 거부
20. Writer가 `state.db`와 raw experiment files에 접근하지 못함

### 19.4 GJC and models — 5 tests

21. GJC ready/unattended/prompt ack/agent_end smoke 통과
22. GJC acknowledgment가 completion으로 오인되지 않음
23. R1/R2/R3 model=`claude-opus-4-8`, effort=max 확인
24. Reviewer session 상호 output 비공개 확인
25. Reviewer failure 시 Grade A 차단

### 19.5 Figure and paper — 5 tests

26. PaperFigure archive hash 확인과 extraction 성공
27. Claude Design available path에서 local handoff 회수
28. Claude Design unavailable 시 local fallback 성공
29. Lane A plotted values가 source metrics와 일치
30. PDF compile/citation/page/anonymity profile gate 통과

### 19.6 End-to-end — 2 tests

31. positive synthetic run → Grade A `paper.pdf`
32. valid null synthetic run → Grade C `research-report.pdf`

### 19.7 Definition of Done

- 32 tests 통과
- clean Linux/macOS/WSL2 supported environment에서 bootstrap → run → output 재현
- one-shot command로 full flow 수행
- claim에서 experiment/metric/commit/artifact까지 추적 가능
- Reviewer ×3와 Claude Design fallback 동작
- v4.0 제거 항목이 baseline dependency로 다시 유입되지 않음

---

## 20. One-Shot Implementation Order

### Step 1 — Skeleton and schemas

- package layout
- config/spec models
- SQLite schema
- CLI

### Step 2 — Supervisor kernel

- active lock
- StateStore
- task scheduler
- process runner
- atomic result ingest
- recovery
- simple budget

### Step 3 — Git/GJC/Agent adapters

- worktree manager
- GJC RPC minimum contract
- Agent SDK role runner
- path/command guard
- model logging

### Step 4 — Scientific pipeline

- baseline/candidate experiment records
- statistical aggregate
- failure analysis
- finalist freeze
- verifier/reproduction/confirmation
- evidence compiler

### Step 5 — Paper pipeline

- prior-art scan
- citation checker
- Writer
- deterministic tables/plots
- claim lint
- LaTeX build

### Step 6 — Figure pipeline

- PaperFigure archive import
- Claude Design MCP adapter
- local fallback renderer
- figure checks

### Step 7 — Review and grading

- R1/R2/R3 independent runners
- fix loop
- venue gates
- Grade A/B/C/D
- output package

### Step 8 — Acceptance suite

- 32 required tests
- positive/null E2E
- clean-machine smoke

위 순서대로 구현하되 각 Step 완료 시 바로 다음 Step에 필요한 최소 integration test 수행.

---

## Appendix A. Minimal Role Permissions

### Builder/GJC

```text
Read/Write/Edit/Bash: task worktree, task tmp, train/search data
Denied: hidden confirmation, outputs/evidence locks, git push, home secrets
Network: normally unnecessary after preflight
```

### Verifier

```text
Read/Bash: selected commit, search data
Confirmation task only: hidden data
Write: verifier task directory, evidence staging
Denied: builder branch mutation
```

### Writer

```text
Read: evidence locks, venue template, approved references
Write: paper directory
Denied: state.db, raw experiments, hidden data, Bash network tools
```

### Figure controller

```text
Read: figure spec, PaperFigure template, approved images
Write: figure task directory
MCP: Claude Design only
Denied: raw data, arbitrary MCP
```

### Reviewer

```text
Read: frozen PDF, reviewer-specific evidence packet
Write: review JSON only
Denied: code edit, paper edit, other Reviewer output
```

---

## Appendix B. Experiment Validity Checklist

Verifier는 `valid` 판정 전 다음 확인.

```text
expected source commit
clean worktree
expected dataset and split hash
expected command/config
required seeds accounted for
metric schema valid
NaN/Inf diagnosis
required logs and manifest
no hidden split in search experiment
resource usage plausible
```

---

## Appendix C. Lean vs Hardened Boundary

Lean baseline만으로 충분한 경우:

- 개인 연구 workstation
- private repo
- known dependencies
- public/non-sensitive dataset
- trusted model provider account

Hardened profile이 필요한 경우:

- unknown third-party repository 실행
- secret-rich production workstation
- shared lab cluster에서 다른 사용자와 동일 account
- restricted human data
- public task submission

Hardened 기능은 별도 milestone로 구현:

```text
container isolation
read-only mounts
network allowlist/proxy
secret broker
independent Git clone
CAS
stronger audit/event replay
```

Baseline code가 Hardened 기능을 선제 구현하거나 dependency로 요구하지 않음.

---

## Appendix D. External Contract Notes

- Claude Code sandbox는 baseline의 Bash isolation 수단. `allowUnsandboxedCommands=false` 사용.
- Agent SDK는 programmatic tools, `strict_mcp_config`, `setting_sources=[]`, path guard 사용.
- Claude Design은 Claude Code에서 MCP server로 연결하고 `/design-login`으로 인증.
- Claude Design export/handoff capability는 preflight에서 실제 확인하며 format을 추정하지 않음.
- GJC RPC prompt acknowledgment와 final `agent_end`를 분리.
- software version은 `runtime.lock.json`에 기록하고 smoke test로 검증.

---

## Final Implementation Rule

구현자는 v4.0의 enterprise-style runtime/security infrastructure를 재도입하지 않음. Baseline의 우선순위는 다음 순서임.

```text
scientific integrity
> recoverable one-shot execution
> evidence-bound writing
> Reviewer ×3 quality gate
> Figure quality
> operational hardening
```

추가 infrastructure는 실제 failure 또는 deployment threat가 확인된 이후에만 도입.
