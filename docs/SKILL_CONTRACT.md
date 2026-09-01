# Skill Contract

Authoring standard for every skill in the framework. Any file under
`core/`, `protocols/`, or `commands/` that ends in `SKILL.md` (or
`{name}.md` for commands) is expected to conform. The linter
`bin/verify-contract.sh` checks the contract mechanically.

Reader path: [`CONCEPTS.md`](./CONCEPTS.md) defines what a "skill" is;
this file describes the shape every skill file must take;
[`AGENT_CONTRACT.md`](./AGENT_CONTRACT.md) describes what the runtime
executing that file must be able to do.

## Frontmatter

Every skill starts with a YAML frontmatter block delimited by `---`.

**Required fields:**

- `name` — the string the runtime uses to invoke the skill explicitly.
  Must match the folder name (e.g. `core/flow-first/` → `name: flow-first`).
  The invocation syntax is runtime-specific — `Skill('name')` on Claude Code,
  `$name` on Codex; see [`AGENT_CONTRACT.md`](./AGENT_CONTRACT.md) capability R2.
- `description` — multi-line string with three parts:
  1. **Role line** (opening sentence) — one clause describing what the
     skill does.
  2. **Principle** — one line starting with `Principle:` stating the
     core rule the skill enforces.
  3. **Use when** — list of triggers (auto-invoke context, manual
     command aliases, natural-language triggers).

**Example:**

```yaml
---
name: flow-first
description: |
  Understanding-alignment protocol before library-first.
  ...
  Principle: library-first without landscape understanding is built on guesses.

  Use when: automatically in /go-fast as Step 3.5; manually before any
  task that needs an understanding check; "flow-first", "/flow-first".
---
```

## Body sections

Three sections MUST appear in the body, in this order:

### Input

What the skill consumes — files, arguments, prior artifacts, session
context. One paragraph or bullet list.

> Example (flow-first): "The block's task description, plus 2-3 anchors
> (file / table / route) from the user."

### Output

What the skill produces — the concrete artifact the reader will see
after a successful run. Reference the `artifact` term from
`CONCEPTS.md`.

> Example (library-first): "A LOC table (5 columns) plus Watchpoints and
> Out-of-scope blocks, saved as `library-first-{N}.{R}.md`."

### Hands off to

Which skill the framework invokes next in the chain. If none (terminal
skill), write `— (terminal)`.

> Example (flow-first): "library-first (auto-invoked after user
> approval)."
>
> Example (ship-first): "— (terminal)."

## Optional sections

- **Anti-patterns** — bulleted list of behaviors the skill must NOT
  do, each with a short rationale.
- **Step 99 — Log invocation** — auto-hook block that inserts one row
  into `skill_invocations` for auditability.

Skills MAY include additional protocol steps (Step 0..N) between
Frontmatter and Body sections. The contract does not restrict internal
structure — only the presence of the required elements above.

## Acceptance criteria for the verifier

`bin/verify-contract.sh` (see Block 24) walks each SKILL.md and checks:

- [ ] `---` delimited frontmatter block present at the top of the file.
- [ ] `name:` field present in frontmatter.
- [ ] `description:` field present with `Use when` substring inside it.
- [ ] Body contains a heading matching `## Input` (case-insensitive).
- [ ] Body contains a heading matching `## Output` (case-insensitive).
- [ ] Body contains a heading matching `## Hands off to` (case-insensitive).

Each failed check is reported per file. The verifier exits non-zero
only when at least one skill has a failed **required** check;
individual failures are always logged.

## Migration path

The 13 skills currently shipped predate this contract. They have
compliant Frontmatter but may lack explicit `## Input`, `## Output`,
`## Hands off to` headings in the body.

The verifier reports these gaps as **non-compliant** without blocking
the sync pipeline. A follow-up block adds the missing sections to each
skill (deferred pending strategy decision on skill-file edits).

Until then, readers can infer Input/Output/Hands off to from the
skill's step-by-step protocol (usually the first Step 0..2 describes
Input, the artifact-write step describes Output, and the last Step
describes hand-off).

Populate cleanly via:

```bash
./bin/verify-contract.sh
```

Re-run whenever a skill is added, removed, or restructured.
