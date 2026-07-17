# Anti-Patterns This Framework Prevents

The README calls this framework «artifact-first» and claims it structurally
prevents a class of problems that plague AI-driven coding. This document is
the receipts.

Each anti-pattern below has three parts:

1. **What happens** — the failure mode as it looks in practice.
2. **Why it breaks work** — the downstream cost.
3. **Structural mechanism** — the specific step in a skill or a tooling
   script that prevents it. Every mechanism cites a concrete file, so you
   can inspect the enforcement code yourself.

The distinction from most agent-workflow guides: this is not «best
practices, please follow». It's «the protocol won't let the run continue
without the artifact».

---

## 1. Silent skill drift

**What happens.** A skill file in your workspace slowly diverges from the
upstream source (or from the manifest declaration). The agent invokes a
version of the skill that doesn't match what the docs claim. Six weeks
later a behavior mismatch surfaces and nobody can trace when the drift
started.

**Why it breaks work.** Every audit of past work becomes suspect — «did
we run the current protocol here or an earlier one?». Reproducibility of
old decisions vanishes.

**Structural mechanism.** `bin/sync-from-aihub.sh` runs a hardcode audit
on every sync (`grep` for known leak patterns across all skill files) and
writes a per-run log in `.sync-log/sync-{ISO}.log`. If a synced file
drifts from expected shape, the audit surfaces it during the next sync
run — you find out this session, not six weeks later. Additionally, each
skill's `SKILL.md` is fronted by a `name:` and `description:` frontmatter
that the linter (`bin/verify-contract.sh`, see
[`SKILL_CONTRACT.md`](./SKILL_CONTRACT.md)) checks against the manifest —
a rename or restructure fails contract check before the sync completes.

---

## 2. Missing artifacts

**What happens.** An agent completes work — writes code, makes a commit,
declares the task done — but no reasoning trail lands anywhere. What
alternatives did it consider? What did it decide against? Gone.

**Why it breaks work.** Reviewers can't audit. The next agent (or the
same agent in a new session) starts fresh with no prior context.
Regressions can't be attributed to a specific decision because there's
no record of any decision.

**Structural mechanism.** Every skill's protocol ends with an explicit
`Step 5 / Step 3.5` that writes a file to `{log_dir}` and inserts a row
into `routing.db.task_artifacts`. The write is not an afterthought —
it's the step that closes the skill's execution. No file + no DB row =
the skill didn't run. See `flow-first/SKILL.md` Step 5, `library-first`
Step 2.5, `plan-first` Step 1.5 + Step 3.5. If the row's missing, the
next skill in the chain refuses to proceed until it's created (chain
verification in Step 0.5 of each protocol skill).

---

## 3. Unlogged approvals

**What happens.** The user says «yeah, go ahead» in chat. The agent
proceeds. Later there's a question about scope: was that approval for
the whole plan or just the next step? Nobody remembers.

**Why it breaks work. **Scope creep becomes untraceable. «You approved
this» / «I didn't approve that» disputes have no ground truth.

**Structural mechanism.** `plan-first` Step 2 stops execution and
requires an explicit mode selection (`1. Autopilot / 2. Step-by-step /
3. Hybrid`). The choice is recorded in `plan-first-{N}.{R}.md` and via
`skill_invocations`. Autopilot doesn't mean «no approval» — it means
«single approval for the whole plan, logged once». Hybrid mode records
the exact step boundary where the user re-approves. Any handoff between
skills passes through a validation checkpoint (see `dev-auto-first`
protocol's per-skill validation rules) which is itself an artifact-emitting
step, so «what did the auto-approver check?» becomes answerable.

---

## 4. Ephemeral steps

**What happens.** The agent does something — a grep, a file read, a
quick edit — that doesn't fit any protocol step. It happens, produces
useful information, but leaves no trace. Later that information gets
rediscovered from scratch, or worse, forgotten.

**Why it breaks work.** Chat context is the only record. When the
session ends, the information is gone. When the context window compresses,
it's silently truncated.

**Structural mechanism.** The framework's stance is that chat is not
storage. Every skill's protocol steps are shaped so their output goes
into a file, not just chat. `flow-first` produces a 4×3 table (file).
`library-first` produces a LOC table (file). `plan-first` produces a
plan table (file). Reports and user-notes wrap up. If an agent finds
itself doing an operation that «doesn't fit anywhere» — that's a signal
to either invoke the right skill or use `note-first` to explicitly save
the output. See [`CONCEPTS.md`](./CONCEPTS.md) for the artifact taxonomy.

---

## 5. Hidden research inside a plan

**What happens.** The plan-first table contains rows like «study how X
works» or «check if there's an analog». The agent approves its own plan,
then spends the first three «steps» doing research it should have done
during flow-first.

**Why it breaks work.** The plan appears solid but the first several
steps are actually undecided exploration. Estimates blow out. What
looked like «5 steps, done in an hour» becomes «10 steps, done in a
day». Reviewers approving the plan don't realize they're approving
uncertainty.

**Structural mechanism.** `plan-first` has this exact anti-pattern
documented (see `plan-first/SKILL.md` Anti-patterns section, item
«Research steps in the plan table»). Rows containing «study» / «understand» /
«check if there's» are surfaced as a signal that `flow-first` was
skipped or done insufficiently. The protocol requires you to stop and
invoke `Skill('flow-first')` to close the research gap before the plan
is finalized. Plan-time discovery becomes flow-first-time discovery,
which is where discovery belongs.

---

## 6. Protocol inlining

**What happens.** The agent «knows how flow-first works» so it just
starts filling in the table from memory instead of invoking `Skill('flow-first')`.
Result: outdated protocol version, no artifact registration, no chain
verification.

**Why it breaks work.** Skills evolve. An agent running an inlined memory
of last month's version drifts from the current contract. Downstream
skills expect the current shape and either fail or silently accept the
wrong input.

**Structural mechanism.** Every skill's `SKILL.md` lists «Inlining the
skill instead of using the Skill() tool» in its Anti-patterns section
with an explicit rule («always launch via the `Skill('name')` tool»).
The Skill() invocation returns the current protocol text, guaranteeing
the agent runs the current version. It also registers the invocation in
`skill_invocations` — auditable proof that the skill actually ran and
which version. An inlined execution leaves no `skill_invocations` row,
so ship-first's aggregate report catches the gap.

---

## How this differs from other agent frameworks

Executable orchestrators (LangChain, CrewAI, others) let you build agent
graphs and run them, but treat artifacts as optional — a callback, a log
line, whatever you wire up. The registry is on you.

Prescriptive frameworks (documentation-first playbooks) describe the
discipline in prose and trust you to apply it. Nothing structurally
enforces the practice; it lives in the reviewer's memory.

This framework fits between the two: it ships opinionated skill files
(the prescription) *plus* the routing.db registry and mandatory
artifact-emitting steps (the enforcement). You can't accidentally skip
the discipline because the discipline is a step in the protocol, not a
comment in a wiki.

If you find yourself producing agent workflow output that doesn't land
in a file and register in a database, one of the anti-patterns above is
active. The fix is always in the same place: the skill whose Step N was
supposed to produce that artifact.
