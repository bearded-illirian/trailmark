# Fixture input — decision-first / storage choice

Run the `decision-first` protocol for the following fork, then point the parity
runner at the log directory it produced.

**Fork:** the task needs to persist a few thousand rows of structured task
history. Choose between SQLite in the repository and a hosted Postgres.

The fixture tests that the agent records a decision with its rationale and
rejected alternatives — not which option it picks. Either answer passes.
