# Contributing

Thanks for wanting to help. This framework is deliberately small —
plain markdown, bash, sqlite — which makes contributions approachable.

Before you start, please skim [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).
By participating you agree to it.

---

## Ways to contribute

- **Report a bug** — open a [GitHub issue](../../issues) using the bug
  template. Include what you ran, what happened, and what you expected.
- **Ask a question** — open a
  [GitHub Discussion](../../discussions) in the Q&A category. Faster
  than an issue for open-ended questions.
- **Suggest an idea** — Discussion in the Ideas category. Once we agree
  it's worth building, we open an issue and link them.
- **Improve docs** — PR against any file in `docs/` or the top-level
  READMEs. Doc-only PRs merge fast.
- **Add or modify a skill** — see [Adding a skill](#adding-a-skill) below.
- **Improve tooling** — PR against `bin/` scripts, `bin/flow-ui/`, or
  `manifest.yml` semantics.

---

## Contribution flow

1. **Fork** the repo and clone your fork locally.
2. **Branch** from `main`. Naming: `<type>/<short-slug>` — e.g.
   `feat/skill-flow-first-anchor-detection` or `fix/bin-init-macos-bash-3.2`.
3. **Set up the workspace** locally — see
   [README first-run](./README.md#first-run).
4. **Make your change.** Small PRs review faster than big ones. If a
   change grows beyond ~200 lines diff, consider splitting.
5. **Verify** with the tooling described below.
6. **Commit** using our conventions (see [Commit messages](#commit-messages)).
7. **Open a PR** using the pull request template. Link related issue
   or Discussion.

---

## Adding a skill

Skills are the core unit of the framework. Each skill lives in
`aihub/.claude/skills/<name>/SKILL.md` and follows a strict contract.

**Read [`docs/SKILL_CONTRACT.md`](./docs/SKILL_CONTRACT.md) first.** It
defines the required frontmatter fields, the three body sections (Input
/ Output / Hands off to), and the acceptance criteria the linter checks.

**Local verification:**

```bash
bash bin/verify-contract.sh
```

This runs against every skill in the workspace. Your new/modified skill
must pass all required checks before opening a PR.

**Register in the manifest.** After you create the skill folder, add
an entry to `manifest.yml` in the appropriate tier
(`command` / `protocol` / `core`). Follow the existing entries as
templates. Then run `bash bin/gen-skills-map.sh` to regenerate the
skills map documentation.

**Test the sync.** Run `bash bin/sync-from-aihub.sh` and verify the
`.sync-log/` output shows your entry synced without warnings.

---

## Commit messages

We follow a light convention — no strict enforcement, but consistency
helps `git log` stay useful.

**Prefix** with one of: `feat` / `fix` / `docs` / `refactor` / `chore` /
`test`. Then a colon, then a short present-tense summary.

**Examples:**

```
feat: add auto-anchor detection to flow-first
fix: bin/init handles empty aihub_root default correctly
docs: clarify hub-and-spoke pattern in PROJECTS_GUIDE
chore: bump manifest version to v0.5.1
```

**Body (optional)** — bullet list of what changed and why. Wrap at 72
columns. Reference issues with `Closes #NN` or `Refs #NN`.

**Signed-off-by is not required.**

---

## Pull request requirements

Before requesting review:

- [ ] Branch is up to date with `main` (rebase or merge).
- [ ] `bash bin/verify-contract.sh` passes (if you touched a skill).
- [ ] `bash bin/gen-skills-map.sh` was rerun (if you added/removed a skill).
- [ ] Docs updated (README, relevant `docs/`) if behavior changed.
- [ ] Related issue or Discussion linked.

Small doc/typo PRs skip most of this — reviewers are lenient with
low-risk changes.

---

## Local development setup

You need what the [README](./README.md#requirements) lists plus (for
Flow UI development):

```bash
pip install -r bin/flow-ui/requirements.txt
```

To iterate on a skill and see it live:

```bash
# 1. Edit aihub/.claude/skills/<name>/SKILL.md
# 2. Sync to the workspace surface (no-op for local dev if you edit in
#    place, but validates the manifest)
bash bin/sync-from-aihub.sh
# 3. Run the skill via your agent
```

Flow UI shows artifacts as they land in `routing.db` — useful for
watching a skill produce its expected output.

---

## Getting help

- **Q&A** — [GitHub Discussions](../../discussions)
- **Bug reports** — [GitHub Issues](../../issues)
- **Security disclosures** — see [`SECURITY.md`](./SECURITY.md)

We aim to respond to Discussions within a few days and to issues
within a week. This is a small project — thank you for your patience.

---

## What we look for in a PR

- **Does it match the framework's spirit** — plain markdown, minimal
  dependencies, no runtime lock-in, artifacts stay first-class.
- **Is the change scoped** — one PR, one concern.
- **Is it documented** — new behavior needs a doc update.
- **Does it degrade gracefully** — new features shouldn't break
  existing skills that don't opt in.

We accept PRs that improve clarity even without new features. Renaming
a confusing section, tightening a docstring, fixing a broken link —
all welcome.
