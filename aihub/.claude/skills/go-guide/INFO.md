---
title: Go-Guide
pitch: Saves a conceptual guide into the project's knowledge folder
icon: 📖
category: knowledge
price: free
publish: true
order: 130
works_with:
  - id: ship-first
    why: On task closure through ship-first offers to record a guide
  - id: project-knowledge
    why: Guides become the source of truth for the routing table
---

## What problem it solves

You closed a complex task — found a mechanism, a pattern, a solution. A month later you hit a similar problem and **don't remember** you already figured it out. You solve it from scratch again.

Without recording conceptual guides, every serious discussion stays in the task, in the chat, in the commit. There's no shared knowledge you can reuse in another task.

## How it works

Three modes. **Interactive** — the user launches `/go-guide` manually, picks a project, topic, title, and text. **From-task** — `ship-first` after a fast-track offers to record a guide based on the task result (takes `user-note.md` + the latest `report-NN.md`). **From-epic** — the epic-closure command collects a guide from all epic `user-note.md` + the epic summary + the tech-spec.

Storage: a simple `.md` file under `project-knowledge/guides/{topic}/`, registered via git commit + push. No database, no admin panel — the file itself is the artifact, discoverable via the file tree or search.

## Result of the work

Conceptual knowledge accumulates as a reusable base — separate from tasks, separate from chats. A month later, on a similar problem, project knowledge points at the ready guide.

Long-term — the project becomes "learning": every serious decision stays as knowledge, doesn't get lost in the task stream.

## Skills it works with

| Skill | Why |
|---|---|
| ship-first | On task closure through ship-first offers to record a guide |
| project-knowledge | Guides become the source of truth for the routing table |
