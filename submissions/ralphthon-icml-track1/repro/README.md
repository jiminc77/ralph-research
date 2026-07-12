# DGCC reproduction patch

- DGCC branch: `ralphthon-track1`
- Base commit: `3ac95fe`
- Phase 2 pipeline commit: `8985575`
- Patch: `0001-Finalize-Ralphthon-Track-1-pilot-pipeline.patch`
- Patch SHA-256: `68d014094eed513a4f83f01a0ba57b1c6762eaa84597d790685b876a46f5eb0b`
- Verification: `116 passed` in the DGCC test suite; `142 passed` in the ralph-research test suite.

Apply from a DGCC checkout at the base commit:

```bash
git am 0001-Finalize-Ralphthon-Track-1-pilot-pipeline.patch
```

The committed pipeline contains the strict candidate-local validity analysis,
deterministic bootstrap seeding, official anonymous ICML 2026 paper build, and
submission packaging. The paper reports the dev experiment as descriptive
because no candidate passed the preregistered invalid-table-rate guard.
