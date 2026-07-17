---
title: Decision-First
pitch: Formally records an architectural decision as an atomic decision-NN.md artifact
icon: 🎯
category: development
price: free
publish: true
order: 55
works_with:
  - id: arch-first
    why: On an architectural fork inside an arch-first block, decision-first writes a formal decision-NN.md instead of leaving the choice buried in chat
  - id: plan-first
    why: When plan-first Steps require a choice between options — decision-first records the choice with rationale
  - id: ship-first
    why: On task closure ship-first includes all decisions in the overall summary — the history of choices survives
---

## What problem it solves

Architectural decisions taken "in chat" are unknown two weeks later. A developer comes back to the same question, reopens the discussion, and makes the opposite choice — because the context of the first decision is lost.

Without a formal record, every decision is paid for twice: first in the discussion, then in the reopening. Plus — new agents in another session can't tell "why X was chosen over Y" — the rationale exists only in the original conversation.

## How it works

The skill takes an architectural question → produces the answer itself via a five-part model rather than asking the user each time. Structure: **🎯 Decision** (what was chosen) / **Why** (2-3 concrete reasons) / **🛡 Safety** (what won't break) / **📈 Scalability** (how it behaves under growth) / **Alternatives** (what was rejected and why). Plus **Plain-language** (one sentence for a non-technical reader).

Each decision is an atomic artifact `decision-NN.md` in the task's `{log_dir}`. A link to the decision goes into the task.md header via `> 🎯 Decision NN: decision-NN.md`. Formally: 1 question = 1 file, don't mix multiple decisions into one artifact.

## Result of the work

Every architectural decision becomes a first-class artifact with explicit rationale. Future readers (including the same author a month later) see the choice + reasons + rejected alternatives. Reopening a discussion becomes informed, not from scratch.

Plus — decision-first makes the decision itself, without asking the user every time. The user can override, but the default is: the agent decides via the five-part model with rationale. Fewer pauses in the workflow, more audit trail.

## Skills it works with

| Skill | Why |
|---|---|
| arch-first | On an architectural fork inside a block — decision-first formally records the choice |
| plan-first | When a plan Step requires a choice — decision-first captures the rationale |
| ship-first | Task finalization includes all decisions in the summary |
