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

## [1.0.0] — 2026-07-18

**First stable public release** as **Trailmark** — the artifact-first
agent framework. Repo public, brand identity fixed, full docs parity
EN/RU, CI wired.

### Added

- **Public release** under MIT License at `github.com/bearded-illirian/trailmark`.
- **Product name: Trailmark** (rebranded from working title «The Framework»).
- **GitHub Actions CI** (`.github/workflows/verify-contract.yml`) — runs
  `verify-contract.sh` + `manifest.yml` parse check on every push/PR to main.
- **Social preview poster** (`docs/assets/og-poster.png`) — 1280×640, Flow UI
  brand palette (bg `#04070d`, accent `#F4A300`). Uploaded via Settings.
- **Before/after diagram** (`docs/assets/before-after.png`) — 1200×600
  visual comparison «chat-only agent vs artifact-first agent» embedded
  in README hero.
- **README badges cluster** — MIT / Manifest / Skills / Stars / Issues.
- **README «Star history»** section via star-history.com.
- **10 GitHub topics** for discoverability (ai-framework, claude-code,
  agent-orchestration, artifact-first, etc.).
- **Repository description** with core value prop hook.
- **`.github` templates** — bug report, feature request, discussion
  templates (Q&A, ideas, show-and-tell) with Trailmark branding.

### Changed

- **README** — full rewrite to `Trailmark` identity, contrast-card
  «Why artifact-first» (bullets vs wall-of-text), inline glosses for
  key terms (block, report, skill, chain, gate), star history embed,
  homework section with `/tutorial-check` reference.
- **README.ru.md** — full parity with English v1.0.0 content (was
  stale v0.5.0 snapshot).
- **Install flow** — 3 commands (`init` → `init-demo` → `new-project`),
  was 4 commands with deprecated `bin/init-sample`.
- **Security** — removed all `/Users/viktor/` path leaks from
  `manifest.yml` + `bin/sync-from-aihub.sh` (author's absolute paths
  now use dynamic `${HOME}` / `${AIHUB_ROOT}` patterns).

### Removed

- «MVP» label everywhere (product is stable now, not a work-in-progress
  preview). FAQ scope phrasing + Status section reworded.
- Deprecated `bin/init-sample` + `bin/archive-sample` (replaced by
  `bin/init-demo` + `bin/archive-demo` with 3-marker safety).

## [0.8.0] — 2026-07-18

**Onboarding closure + Trailmark rebrand foundation.** Added the
`tutorial-check` skill (20th shipped item) and cleaned demo lifecycle.

### Added

- **`tutorial-check`** (core) — homework validator that runs 5 SQL/file
  checks against user's workspace after they complete QUICKSTART § 5.
  Reports ✅/❌ per step with one-line remediation. Ships as SKILL.md +
  SKILL.public.md + INFO.md + INFO.public.md.
- **`bin/init-demo`** (377 LOC) — populates workspace with 3 demo
  projects × 2 tasks × 5 artifacts (123 rows total). Every row marked
  `is_demo=1` + tracked in `tasks/.demo-manifest.json`.
- **`bin/archive-demo`** (200 LOC) — surgical safe remove with 3-marker
  safety (is_demo=1 AND project LIKE 'demo-%' AND id IN manifest).
- **`bin/restore-demo-backup`** — full round-trip recovery from tar.gz
  + routing.db snapshot.
- **`docs/DEMO_DATA.md`** — full guide to demo dataset with safety
  guarantees + FAQ.
- **`docs/TROUBLESHOOTING.md`** — top 7 failure modes + fixes.
- **QUICKSTART.md rewrite** — 5-minute walkthrough under init-demo flow
  with homework 5-step checklist for `/tutorial-check` validation.

### Changed

- Manifest grew from 19 to 20 entries (13 core skills, was 12).
- **Flow UI paths in README fixed** — `bin/flow-ui/serve` →
  `bin/flow-ui/bin/serve` (5 broken references).
- **`PROJECTS_GUIDE.md`** — added Advanced section on project-local
  skill overrides.

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

[Unreleased]: https://github.com/bearded-illirian/trailmark/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/bearded-illirian/trailmark/releases/tag/v1.0.0
[0.8.0]: https://github.com/bearded-illirian/trailmark/compare/v0.5.0...v1.0.0
[0.7.0]: https://github.com/bearded-illirian/trailmark/releases/tag/v0.7.0
[0.6.0]: https://github.com/bearded-illirian/trailmark/releases/tag/v0.6.0
[0.5.0]: https://github.com/bearded-illirian/trailmark/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/bearded-illirian/trailmark/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/bearded-illirian/trailmark/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bearded-illirian/trailmark/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bearded-illirian/trailmark/releases/tag/v0.1.0
