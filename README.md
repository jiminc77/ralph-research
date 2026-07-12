# ralph-research

**어디를 잡을까, 어느 방향으로 움직일까?** — 흐물흐물한 로프(DLO)를 로봇이 다룰 때, 한 걸음의 성공은 *잡는 위치*에서 오는가, *미는 방향*에서 오는가, 아니면 둘의 *궁합*에서 오는가?

이 레포는 [Ralphthon](https://luma.com/hjuo7auc?tk=7F6B08) 해커톤에서 만든 결과물입니다. 두 가지로 이루어져 있습니다.

1. **자율 연구 하베스트(`research-ralph`)** — 사전등록 → 실험 → 통계 → 논문까지 무인으로 굴리는 에이전트 파이프라인의 lean 1차 구현.
2. **그 파이프라인이 실제로 산출한 연구** — *"Where to Act or Which Way to Move"*, ICML 2026 Track 1 심사 중인 사전등록 파일럿 연구.

---

## 📄 산출물 바로 보기

| | |
|---|---|
| 🖥️ **논문 쉽게 읽기 (인터랙티브 explainer)** | **[jiminc77.github.io/ralph-research](https://jiminc77.github.io/ralph-research/)** |
| 📑 **논문 PDF (polished)** | [where-to-act-or-which-way-to-move.pdf](docs/where-to-act-or-which-way-to-move.pdf) |
| 📊 **증거 리포트 · 채점** | [report.md](submissions/ralphthon-icml-track1/report.md) · [grade.json](submissions/ralphthon-icml-track1/grade.json) |
| 📦 **제출물 전체** | [submissions/](submissions/) |

> explainer는 논문의 내용을 한국어 한 페이지로 풀어낸 것으로, 히트맵·수식·인터랙티브 데모를 포함합니다. GitHub Pages로 호스팅됩니다.

---

## 한 줄 요약

> 같은 로프 상태·목표·후보 개수·시뮬레이터 예산에서, 한 걸음의 행동 가치는 **접촉 위치 선택(where)**, **모션 방향 선택(how)**, **둘의 상호작용** 중 무엇에 얼마나 귀속되는가?

새 알고리즘을 제안하지 않습니다. 대신 고전 통계의 **완전요인설계**를 액션 공간에 적용해, 각 상태에서 잡는 위치 8곳 × 미는 방향 8개 = **64조합을 전부 직접 실행**하고 개입 효과를 측정합니다.

### 핵심 결과 (dev-split 파일럿, C0)

| 과제 | Δ_WH = E[v_P − v_U] | 95% 동시구간 | 라벨 |
|---|---|---|---|
| t1a 곧게 펴기 | **+0.041** | [+0.029, +0.053] | **위치 우세** |
| t1b 한 번 접기 | −0.034 | [−0.073, +0.005] | 판정 유보 |
| t1c 끝점 옮기기 | **−0.130** | [−0.161, −0.100] | **방향 우세** |

- **인자의 중요도는 과제를 따라 뒤집힌다.** 곧게 펼 때는 위치가, 끝점을 옮길 때는 방향이 더 값졌습니다.
- **진짜 주인공은 "궁합(상호작용)".** t1a·t1b에서 상호작용이 표 분산의 각각 **86%·76%**를 차지 — 어느 단독 인자보다 큽니다.
- **주장 경계는 좁습니다.** 위치 인자는 로프 전체를 8등분해 커버하지만 방향 인자는 고정 크기 평면 8방향뿐이므로, 이 비교는 "where vs how" 일반론이 아니라 *"접촉 위치 선택 vs 고정 크기 평면 방향 선택"*입니다.

### 정직성 리포트 — 이건 "확정 결론"이 아닙니다

사전등록한 데이터 품질 가드(무효 테이블 비율 ≤ 0.02)를 **어떤 실행 조건도 통과하지 못했습니다** (192개 중 42개가 canonicalization 재배치 아티팩트로 무효). 그래서 논문은 모든 수치를 **서술적 파일럿 증거**로 스스로 강등했고, hidden-split 확정도 clean reproduction도 실행하지 않았습니다. 채점 결과는 **Grade C** (유효한 파일럿 증거, 축소 표본). 모든 무효 실행은 숨기지 않고 그대로 공개합니다.

---

## 저장소 구조

### 연구 하베스트 (`research-ralph` v4.1-lean)

| 경로 | 설명 |
|---|---|
| [`ralph_core/`](ralph_core/) | 에이전트 supervisor · preflight · guards · 스키마 · 복구 · CLI |
| [`schema/`](schema/) | 코어 SQLite 스키마 · 워커 결과 JSON 스키마 |
| [`spec-bundle/`](spec-bundle/) | FINAL 구현 스펙(v4.1-lean) · 검증 · 매니페스트 |
| [`venue/`](venue/) | 논문 venue 프로파일 · 구조 체크 |
| [`tests/`](tests/) | 헤르메틱 모듈 테스트 스위트 |
| [`DEFERRED.md`](DEFERRED.md) | lean 1차 pass에서 의도적으로 미룬 표면(마일스톤별) |

### 이번 연구 (`where-vs-how-dlo-v1`)

| 경로 | 설명 |
|---|---|
| [`RESEARCH_SPEC.md`](RESEARCH_SPEC.md) | 사전등록 연구 스펙(하네스 계약 + 산문 스펙) |
| [`DECISION_POLICY.md`](DECISION_POLICY.md) | 무인 Phase 2 의사결정 정책(월-클락·토폴로지·선택 규칙) |
| [`ONE_LINER.md`](ONE_LINER.md) | 연구 한 줄 정의 |
| [`submissions/`](submissions/) | ICML Track 1 제출물(논문·figures·repro·채점) |
| [`docs/`](docs/) | 인터랙티브 explainer + 논문 PDF (GitHub Pages) |

---

## 개발 환경

`research-ralph` 코어는 Python 3.12, [uv](https://github.com/astral-sh/uv) 기반입니다.

```bash
uv sync            # 의존성 설치
uv run pytest      # 헤르메틱 테스트 스위트 실행
```

> 참고: 실제 과학 파이프라인(시뮬레이터·GPU 실행·LaTeX 빌드)은 별도 워크스페이스(DGCC / DLO-Lab)에서 돌아갔으며, 재현 커맨드는 [report.md](submissions/ralphthon-icml-track1/report.md)에 있습니다. 이 레포의 테스트는 어댑터 seam을 `tests/fakes/*`로 대체한 모듈 단위 테스트입니다(상세: [`DEFERRED.md`](DEFERRED.md)).

---

## 라이선스

별도 명시 전까지 저자(jiminc77) 저작권. 인용/재사용 문의 환영합니다.
