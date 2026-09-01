# Fixture input — plan-first / add endpoint

Run the `plan-first` protocol for the following block, then point the parity
runner at the log directory it produced.

**Block:** Add a `GET /api/health` endpoint returning service status and version.

**Context the agent may assume:**

- The service is a small HTTP API with existing routes under `api/`.
- There is no health endpoint yet.
- The block is part of a task already registered in `routing.db`.

Nothing else is provided on purpose: the fixture tests the shape of the plan,
not the correctness of a plan for a real codebase.
