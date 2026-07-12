# research-ralph v4.1 Lean Implementation Bundle

Implementation entrypoint:

1. Read `research-ralph-implementation-spec-v4.1-lean.md`.
2. Create package layout in Section 4.
3. Apply `schema/core-v4.1-lean.sql`.
4. Validate worker outputs with `schema/worker-result.schema.json`.
5. Import the PaperFigure archive using `paperfigure/source.lock.json`.
6. Implement in the order defined in Section 20.
7. Release only after the 32 acceptance tests pass.

This bundle intentionally excludes the v4.0 State Service daemon, UDS RPC, event-sourcing projections, transactional outbox, CAS, sidecar fleet, independent Git databases, and network-policy engine.
