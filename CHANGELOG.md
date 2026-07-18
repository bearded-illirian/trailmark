# Changelog

All notable changes to this framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [0.7.0] — 2026-07-18

### Added

- **INFO.md pattern** — 16 EN `INFO.md` files (~44 lines each) ship
  alongside every `SKILL.md` in the manifest. Frontmatter contains
  `title`, `pitch`, `icon`, `category`, `works_with`. Body has four
  sections: What problem it solves / How it works / Result of the
  work / Skills it works with. Public consumers now see per-skill
  positioning without opening `SKILL.md`.
- **Two new INFO.md** for `cadence-first` and `decision-first` — these
  skills previously had no INFO. Now aligned with the rest of the
  MVP set.
- **v2.1 `info` profile** in `skill-public-check` — accepts
  `target_file=INFO.public.md`, skips pre-gate C8 (anti-patterns)
  and C10 (Step 99) since INFO is descriptive metadata, not a
  protocol with a bash template. Full 8-D scoring unchanged.

### Changed

- `bin/sync-from-aihub.sh` — added a second rename pass
  (`INFO.public.md → INFO.md`) parallel to the existing SKILL pass.
  External users see canonical `INFO.md`; internal RU `INFO.md` stays
  upstream only.
- `manifest.yml` `sync_rules.exclude_patterns` — added `INFO.md` so
  the internal RU metadata doesn't leak into the public tree during
  rsync.
- `skill-public-check` (`SKILL.md`) — Step 1 documents `target_file`
  parameter; Step 2 adds source-file mapping table; Step 4 report
  header carries `Profile: standard|info`.

## [0.6.0] — 2026-07-17

### Added

- **cadence-first** (core) — meta-orchestrator that assigns Tier 1/2/3
  cadence per block via Q1-Q6 rules. Runs before `plan-first` to
  right-size the skill chain per block scope.
- **arch-map** (core) — auto-links artifacts to project architecture
  elements. Two modes: file-mode (by file paths) and feature-mode
  (by artifact text). Propagates arch_ref up the epic → spec → brief
  chain.
- **check-first** (core) — coverage validation before an approval gate.
  Reads requirements from any structured document and matches them
  against proposed decomposition units (blocks, epics, tasks).
- **go-guide** (core) — captures a conceptual guide into
  `project-knowledge/guides/{topic}/`. Three modes: interactive,
  from-task (ship-first hook), from-epic. Fallback-only storage (no
  DB required).

### Changed

- Manifest grew from 15 to 19 entries: 2 commands + 4 protocol +
  **12 core** (was 8) + 1 tool.
- README: `Status` line + `Architecture` ASCII tree updated to new
  counts.

## [1.0.0-mvp] — TBD

The first public release. Contents are the accumulated result of two
internal tasks (498 assembly, 594 release-prep) — see previous versions
below for the incremental history.

### Added

- Public release under MIT License.
- GitHub Actions CI (`.github/workflows/verify-contract.yml`) — runs
  `verify-contract.sh` and skills-map drift check on every PR.
- Release tag `v1.0.0-mvp` and GitHub release notes.

## [0.5.0] — 2026-07-17

### Added

- **New manifest tier `tool`** — for executable code trees synced from
  external repos alongside skills. First consumer: Flow UI.
- **Flow UI** — local web browser over `routing.db` (`bin/flow-ui/`,
  FastAPI + SQLite, `127.0.0.1:8765`). Read-only view of tasks, blocks,
  artifacts, deploys, and skill-usage analytics.
- **Sample populated project** — `bin/init-sample` seeds a `sample-app`
  project with one completed task and full artifact chain, so Flow UI
  has content on first serve. `bin/archive-sample` undoes it.
- **OSS scaffolding** — `CODE_OF_CONDUCT.md`, `SECURITY.md`, this
  `CHANGELOG.md`, `FAQ.md`, `CONTRIBUTING.md`.
- **README v2** — artifact-first positioning, comparison table vs
  prescriptive frameworks / executable-without-artifacts orchestrators /
  raw agent-code tools; persona table; Flow UI section; RU translation
  with language switcher.
- **AUTO_DEPLOY_RECIPE.md** — opt-in guide for git-push auto-deploy
  (bare repo + post-receive hook + snapshot backups).

### Changed

- `sync-from-aihub.sh` — parser emits `source_root` (default aihub;
  `external` for tool tier). Main loop resolves tool sources via
  `expanduser()`. Hardcode audit scope updated to actual layout
  (`aihub/.claude/{skills,commands}` + `bin/flow-ui/`).
- Skills catalog endpoint in Flow UI is now configurable via
  `paths.aihub_api_url` (default `null` → empty state, no outbound HTTP).
- Auth reference implementation in Flow UI is now optional (`app/auth.py`
  excluded from public sync; contract documented in `AUTH.md`).

### Fixed

- Skills endpoint gracefully degrades on empty `task_artifacts` table
  (fresh install no longer 500s).

## [0.4.0] — 2026-07-17

### Added

- **Workspace layout restructure** (`vasechka-workspace` pattern).
  Consolidated to `aihub/`, `projects/`, `tasks/`, `bin/`, `docs/` top-level.
  Skills live under `aihub/.claude/skills/{name}/` (flat, no tier subdirs).
- `bin/init` (3-question wizard) and `bin/new-project` (project registration).
- `dev-auto-first` skill (14th skill in MVP) — autopilot orchestrator for
  per-block cycles.

### Changed

- Removed derived paths from `framework.yml` prompts (bin/init reduced
  from 7 to 3 questions).

## [0.3.0] — 2026-07-16

### Added

- `commands/go-fast.public.md` renamed on destination for external users.
- Post-rsync rename: `SKILL.public.md → SKILL.md` (external users see
  canonical filename).

## [0.2.0] — 2026-07-16

### Added

- `sync-from-aihub.sh` consumes `SKILL.public.md` as source (validated by
  `skill-public-check` v2.0 for zero secrets/refs).

## [0.1.0] — 2026-07-15

### Added

- Initial internal MVP: 13 skills (2 commands + 4 protocol + 7 core) +
  tooling scaffolding + `manifest.yml`.

[Unreleased]: https://github.com/bearded-illirian/framework/compare/v1.0.0-mvp...HEAD
[1.0.0-mvp]: https://github.com/bearded-illirian/framework/releases/tag/v1.0.0-mvp
[0.5.0]: https://github.com/bearded-illirian/framework/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/bearded-illirian/framework/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/bearded-illirian/framework/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bearded-illirian/framework/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bearded-illirian/framework/releases/tag/v0.1.0
