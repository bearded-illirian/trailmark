# Skills Map

An at-a-glance table of every shipped skill: what tier it lives in, what
it does, which other skills it invokes, and which other skills invoke it.
This file is populated by `bin/gen-skills-map.sh` — the schema below
describes what each column means and where its value comes from.

Reader path: [`CONCEPTS.md`](./CONCEPTS.md) defines what a "skill" is; this
map lists the concrete ones.

## Columns

### Skill

Short identifier used to invoke the skill (`Skill('flow-first')`).
**Derived from:** `name:` field in `SKILL.md` frontmatter.

### Tier

Which layer of the framework the skill belongs to — `core` (universal
per-block cycle), `protocol` (opinionated methodology), or `command`
(user-facing entry point).
**Derived from:** `tier:` field of the skill's entry in `manifest.yml`.

### Role

One-sentence purpose, extracted so a reader can scan the table without
opening every SKILL.md.
**Derived from:** first paragraph of the `description:` field in the
skill's frontmatter, truncated at the first newline or ~100 characters.

### Invokes

List of skills this skill calls via `Skill('X')` during its own steps.
Chain-forming information.
**Derived from:** regex `Skill\('([a-z-]+)'\)` scan of the skill body,
unique names, comma-joined.

### Invoked by

Reverse of Invokes — which skills reference this one. Reveals who
"depends on" the skill and helps assess blast radius of changes.
**Derived from:** two-pass build over all skills' Invokes; each skill
lists the ones that named it.

### Delivers

The concrete artifact the skill produces per run (a table, a report file,
a decision doc). Answers "what will I get if I run this?".
**Derived from:** curated per-skill — no easy frontmatter extraction.
Populate manually or add an `output:` field to frontmatter in a future
schema bump.

## Table

| Skill | Tier | Role | Invokes | Invoked by | Delivers |
|---|---|---|---|---|---|
| go-start | command | Session startup skill. Reads platform docs (README, WORKFLOW, DEPLOY, PLATFORM_KNOWLEDGE,… | go-fast | — (independent) | TODO |
| idea-first | protocol | Точка входа самоорганизующейся цепочки скиллов. Запускается из go-fast после создания задачи.… | ship-first | arch-first, audit-first | TODO |
| arch-first | protocol | Протокол архитектурно-чистого исполнения сложных многоблочных задач. Декомпозиция в блоки →… | audit-first, idea-first, flow-first, dev-auto-first, library-first, plan-first, ship-first | audit-first | TODO |
| audit-first | protocol | Протокол аудита перед фиксом — сначала найти все дыры по 6 плоскостям, приоритизировать,… | arch-first, idea-first, flow-first, dev-auto-first | arch-first | TODO |
| ui-ai-first | protocol | Финальный аудит крупной задачи перед закрытием — выясняет какие операции доступны только через код… | — (leaf) | — (independent) | TODO |
| human-first | core | Берёт последнее сообщение агента и объясняет его простым языком — без технического жаргона, с… | — (leaf) | — (independent) | TODO |
| flow-first | core | Understanding-alignment protocol before library-first. Asks the user for 2-3 anchors (file, table,… | — (leaf) | arch-first, audit-first, library-first, ship-first | TODO |
| library-first | core | Mandatory protocol before executing any Fast-track task. Analyzes the task, builds a table: what we… | flow-first | arch-first, plan-first | TODO |
| plan-first | core | Mandatory protocol before any document creation, code writing, refactoring, DB migration, test… | library-first | arch-first | TODO |
| ship-first | core | Final task completion protocol: report → user-note → deploy → smoke test → close? → guide? →… | flow-first, arch-map, name | arch-first, idea-first | TODO |
| decision-first | core | Принимает архитектурное/проектное решение по 5-частной модели ВМЕСТО того чтобы задавать вопрос… | — (leaf) | — (independent) | TODO |
| note-first | core | Сохраняет последнее сообщение Клода как заметку к текущей задаче. Авто-нумерация (note-01,… | — (leaf) | — (independent) | TODO |


## Populating

Do not hand-edit rows below the schema. Run:

```bash
./bin/gen-skills-map.sh
```

The script walks every entry in `manifest.yml`, reads its `SKILL.md`,
builds the reverse-lookup graph across all skills, and overwrites the
`## Table` section in this file. Re-run whenever a skill is added,
removed, or has its frontmatter changed.
