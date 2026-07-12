# Deferred Surfaces — research-ralph v4.1-lean first pass

This repository contains the approved fast-track first pass of the v4.1-lean
baseline (plan: ralplan stage-04 revision, milestones M1–M2 plus M3 safeguard
subset). Everything below is intentionally deferred, with the owning plan
milestone noted. The spec remains
`spec-bundle/research-ralph-implementation-spec-v4.1-lean.md` (FINAL).

## Deferred to later milestones

| Surface | Plan owner | Notes |
|---|---|---|
| Git/GJC/Agent SDK adapters (`ralph_core/adapters/`) | M3 | `config.yml` already names the final dotted paths; `schemas.load_adapter` syntax-validates and defers import, so the modules are absent by design until M3. |
| Worktree manager, merge rule (§9.2), `build_task_brief` split-access seam | M3 | PathGuard / env-allowlist safeguards shipped now; brief/worktree plumbing deferred. |
| Scientific pipeline S2–S5 depth (experiments, statistics, evidence locks, S4 predecessor graph, `verify_seal`) | M4 | Schema tables and experiment/metric ingest exist; stage logic deferred. |
| Paper pipeline (writer, citations, tables, LaTeX/PDF build) | M5 | `venue/` profile + structural `venue/check.py` shipped; TeX execution deferred. |
| PaperFigure import, Claude Design MCP lane, local figure renderer | M6 | Bundle assets remain under `spec-bundle/paperfigure/` unextracted; hardened import per plan M6. |
| Reviewer ensemble R1/R2/R3, grading, output packaging | M7 | Reviewer alias resolution (`claude-opus-4-8` exact-match, exit 3 otherwise) already enforced in preflight. |
| Acceptance manifest, `@pytest.mark.acceptance` lifecycle plugin, DoD container (`ci/Dockerfile.dod`, uv 0.7.13 pin), e2e positive/null runs, `scripts/check_acceptance.py` | M8 | Current suite is hermetic module tests only; the 32-test acceptance matrix is not yet mapped. |
| Live-service smokes as real calls (provider, GJC, Claude Design, TeX, Chromium) | M3/M5/M6/M8 | Preflight executes these checks through adapter seams; hermetic tests use `tests/fakes/*`. Real runs will fail preflight (exit 3) until M3+ adapters exist — by design. |
| Scheduler and budget admission caps (`scheduler.py`, `budget.py`; acceptance test 7) | M2 depth | Admission-cap enforcement is deferred. |
| Ingest git-commit existence/clean verification and authoritative `runs/<id>/artifacts` store materialization | M2/M3 | Ingest validation and artifact-store authority remain deferred. |
| Recovery worktree and partial-artifact cleanup beyond `*.tmp` | M3 | Lean baseline only removes temporary files. |
| Tamper-evident `runtime.lock.json` signing | Hardening | Out of the lean baseline. |
| Runtime lock design-handoff status and template-archive hash fields | M6 | Extended runtime lock metadata is deferred. |

## Documented deviations from the plan (fast-track)

- `pyproject.toml` omits `matplotlib` and `claude-agent-sdk` (plan M1 pins them
  at M1). They belong to deferred surfaces (M4 figures / M3 SDK adapter) and
  will be added with those milestones as a recorded plan amendment.
- Host toolchain: this machine has git 2.34 (< plan's 2.40 gate) and no
  TeX/Chromium; the hermetic suite does not depend on them. `make check-tools`
  / `scripts/check_prereqs.py` and the pinned DoD container are deferred to
  M8 alongside their consumers.
- `resume` performs the immutable-input drift check (exit 6) and control-file
  write; full supervisor re-entry/scheduler resume semantics land with M2+
  scheduler depth.

## Security refusals

Policy (plan §2 global execution policy): any security-related model refusal
is recorded and skipped, never retried. Refusals recorded during this first
pass: none.
