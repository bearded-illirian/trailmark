---
title: Human-First
pitch: Explains the agent's last message in plain language
icon: 💬
category: session
price: free
publish: true
order: 110
works_with:
  - id: note-first
    why: If the explanation is useful — save it as a note via note-first
---

## What problem it solves

The agent just wrote a technical answer — 200 lines mentioning 10 files and 5 patterns. A minute later you don't remember what was important. An hour later you re-read and still don't understand.

Without a human explanation you have to **decode** the agent's answer every time: what it actually proposes, why it beats the alternative, what it needs from you. Technical language smothers decisions.

## How it works

The skill takes the **last message** by the agent (the one right before `/human-first`). It extracts the 1-3 main ideas — what the agent was actually trying to say in essence, not the structure and not the details.

It explains in plain language: no jargon (replaces "UPSERT by name" with "updates existing or creates new"), with concrete examples and analogies. Ends with a one-sentence "so here's what matters next".

`/human-first` is invoked manually — when you didn't understand what the agent just wrote.

## Result of the work

After `/human-first` it's clear: what the agent proposes, why, what's required from you. You can immediately decide "yes / no / clarify" without parsing the technical text.

Long-term — fewer "lost" agent replies because of misunderstanding.

## Skills it works with

| Skill | Why |
|---|---|
| note-first | If the explanation is useful — save it as a note to the task |
