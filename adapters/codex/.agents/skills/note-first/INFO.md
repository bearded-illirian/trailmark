---
title: Note-First
pitch: Saves the agent's last message as a note attached to the task
icon: 📝
category: session
price: free
publish: true
order: 120
works_with:
  - id: human-first
    why: Often what we save is exactly the plain-language explanation from human-first
  - id: project-knowledge
    why: Notes become a source for future routing
---

## What problem it solves

The agent just wrote a valuable answer — analysis, solution, options. But it's **in chat**: the session closes, it's gone. A week later "I remember we discussed something, but not what exactly".

Without saving important answers, every new session rebuilds context from scratch. Progress between sessions is lost.

## How it works

The skill takes the **last message** by the agent (the one right before `/note-first`). Saves it verbatim — no rewording, no truncation — as `note-NN.md` into the current task's folder.

Automatic numbering: the first note → `note-01.md`, next → `note-02.md`. Two-way linkage: an entry appears under `## Task files` in `task.md`.

`/note-first` is invoked manually — when you want to pin a specific answer.

## Result of the work

Valuable agent answers stay with the task — after the session closes and a week later they can still be read. The history of decisions is recorded.

Long-term — tasks become self-contained: open the folder → you see all the discussion context, no need to hunt down "what did we discuss in chat".

## Skills it works with

| Skill | Why |
|---|---|
| human-first | Often we save exactly the plain-language explanation |
| project-knowledge | Notes become a source for future routing |
