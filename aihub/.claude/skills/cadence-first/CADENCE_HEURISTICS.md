---
type: cadence-manifest
version: 1.0.2
status: patched-y5-lib-first
updated: 2026-07-10
maintained_by: /cadence-first + humans
consumers:
  - /cadence-first (skill applying these rules)
  - /infra-mode-first + /backend-mode-first + /ui-mode-first + /arch-first + /audit-first (invoke cadence-first in Step 3.5 to bake `recommended_cadence` into generated blocks)
  - manual execution flows (executor reads pre-baked cadence from task_blocks)
sibling_manifests:
  - INFRA_MODES_MANIFEST.md (Wave 1 schema layer)
  - BACKEND_MODES_MANIFEST.md (Wave 2 endpoint layer)
  - UI_MODES_MANIFEST_SUMMARY.md (Wave 3 frontend layer)
---

# Cadence Heuristics — Radar OS / Platform Skills

Canonical specification of **per-block skill-chain cadence** — the decision of which sub-skills (flow-first / library-first / plan-first) execute before a task_blocks entry is performed.

Cadence-first is a **filter against redundancy**: it prunes sub-skills whose expected information gain is near-zero for a given block. NOT an orchestrator between many parts — a **right-sizer** of the preparation phase.

---

## §2 Purpose

### When to read this document

- Building `/cadence-first` skill implementation (source of behavioral rules)
- Adding a new block-generator skill that needs to invoke `/cadence-first` in its Step 3.5 hand-off
- Auditing why a specific block was assigned a particular cadence
- Debugging cadence drift ("all blocks flagged Tier 1 — is heuristic broken?")
- Onboarding a new agent to the per-block cadence discipline

### What this document IS

- Source of truth for tier definitions, decision questions, signals per Q, and anti-patterns
- Definition of the canonical output shape produced by `/cadence-first` skill
- Real-world calibration data (empirical ratios from 4 historical tasks)
- Legacy migration principles for retro-fitting cadence on existing tasks

### What this document IS NOT

- **Not the skill itself.** SKILL.md at `aihub/.claude/skills/cadence-first/SKILL.md` implements decision logic per these rules. Manifest = rulebook, SKILL = executor.
- **Not a substitute for flow-first / library-first / plan-first.** Cadence-first decides WHICH of these three to invoke, then chains into them. It does not do their work.
- **Not applicable to hot-fix / one-liner blocks.** Per plan-first Exceptions rule, those skip the whole chain including cadence-first.
- **Not a rigid rule.** Executor override supported when execution surfaces new information not visible at generation time. See §9 LM.4.

### How to update

Two paths:

1. **Metacognition path** — `/cadence-first` regression run (task 515 block 4 planned) discovers a pattern that this manifest doesn't capture → auditor flags proposal → next v1.0.x patch.
2. **Dedicated task path** — new tier introduced, new decision question needed, new anti-pattern surfaced → dedicated task touches manifest + skill in same commit.

Any change to §3 Golden Rule / §4 Anatomy / §5 Decision framework / §6 Anti-patterns / §8 Output format / §9 Legacy migration MUST land in the **same commit** as any SKILL.md changes reading those rules. Companion invariant — see §12.

---

## §3 Golden Rule

**Cadence is decided at block GENERATION time (session where blocks are written to task_blocks), not at EXECUTION time (session where blocks are performed). The generation session has the richest context — user intent, discussion nuance, landscape docs already produced adjacent to the block, sibling-block relationships — none of which is reconstructible from block title alone at execution.**

Consequence: `/cadence-first` is invoked from generator skills' Step 3.5 (after `task_blocks` INSERT, before hand-off). It writes `recommended_cadence` into a dedicated `task_blocks.recommended_cadence` column. Executor reads pre-baked value with option to override on new information.

**Absolutely forbidden:**

- Cadence decisions made silently in-agent-head without recording rationale (breaks audit trail per AP.9)
- Deferring cadence decision to execution time when block was generated in a rich-context session (violates Golden Rule — context lost)
- Tier assignment based on block LOC estimate or duration (invalid selector — see AP.6)
- Skip of any sub-skill without explicit rationale in the plan-first artifact of that block (AP.3 silent skill skip)

---

## §4 Anatomy — 3-tier gradient

All executable blocks map to exactly one of three tiers. Every tier chain terminates in `plan-first → execute → ship-first`; the differentiation is which pre-plan skills invoke.

### Tier 1 — Full cycle

**Chain:** `flow-first → library-first → plan-first → execute → ship-first`

**When it fires:**
- Block changes production code / prod DB state / prod runtime configuration
- Block introduces novel idiom, integration surface, or first-of-its-kind pattern
- Block operates on multi-integration cross-cutting surface (schema migration + N skill files touched simultaneously)
- Block explicitly tagged HIGH-risk in roadmap / task.md

**Purpose of each pre-plan skill:**
- **flow-first** aligns understanding across UI / DB / Integrations with 4×3 landscape table — "do we all agree what changes and where?"
- **library-first** produces the LOC atomization table with reuse decisions — "what do we mirror vs write new, at what cost?"
- **plan-first** orders steps — "in what sequence, with what risks?"

**Live example (task 497 block 601):** Write BACKEND_MODES_MANIFEST v1.0. New source-of-truth document. Silent-failure risk HIGH — if manifest wrong, all downstream `/backend-check-modes` runs produce wrong compliance reports. flow-first captured which templates apply (INFRA precedent); library-first identified section-by-section mirror candidates; plan-first sequenced compose + Write + register + verify. Full cycle justified.

### Tier 2 — Partial cycle

**Chain:** `library-first → plan-first → execute → ship-first`

**When it fires:**
- Landscape is already captured in an existing artifact (`plan-{code}.md` from a `/{layer}-mode-first`, prior flow-first-*.md < 1 hour old, note-N.md explicitly describing landscape)
- Block writes new code but the pattern requires audit against an etalon (first-of-its-kind sibling of a family)
- Block includes new library-vs-scratch decision (which template mirror? which shared module reuse?)
- Block is a mechanical prod batch (N identical file edits on prod, cleanup of old keys after replacement wave). See §5 Q1 escape hatch.

**Live example (task 497 block 601):** landscape came from note-14.md (block 600 output). flow-first redundant. But library-first needed — template choice between INFRA MANIFEST (verbose) and UI SUMMARY (minimal). Tier 2 correct.

### Tier 3 — Plan-focused

**Chain:** `plan-first → execute → ship-first`

**When it fires:**
- Deliverable is a document / note / spec / comparison (research output)
- Deliverable is a diagnostic / verification report (smoke test, compliance audit output)
- Block is a mechanical batch (N identical file edits, catalog registration, trivial mkdir + touch)
- Block is task finalization / closure ceremony

**Rationale:** flow-first's 4×3 landscape table for a note-writing block becomes all "not involved" cells — no signal. library-first's LOC table for a 3-line catalog addition is 1 row of "reuse Edit tool, 0 LOC" — no reuse decision. Both are ceremony without insight.

**Live example (task 497 block 606):** Wave finalize — mark blocks done + commit + push + sync. All mechanical. Tier 3.

### Never — Zero pre-plan cycle

**Chain:** `execute` only (skip plan-first entirely)

**When it fires:** hot-fix per plan-first Exceptions rule — one-line edit, opaque typo fix, known repro of known bug. Cadence-first NOT invoked for hot-fix — `/idea-first` hot-fix branch handles this.

Zero-cycle blocks bypass the whole framework including cadence-first. Not part of the 3-tier gradient.

---

## §5 Decision framework — Q1 through Q5

Ask five questions in order. First "yes" locks the tier per the mapping below. If Q5 fires, it overrides all prior answers.

### Q1 — Does the block change PRODUCTION code / state?

- **YES** → **Tier 1 Full cycle** locked (unless Q5 override forces same)
- **NO** → continue to Q2

**Signals FOR "yes":**
- `git push origin main` where deploy dir = `/srv/*` on prod VDS
- DB migration ALTER TABLE / CREATE TABLE / DROP on `mode_library.sqlite`, `routing.db`, per-tenant `radar.sqlite`
- Config file edit on `.env` / systemd service / nginx snippet
- Catalog INSERT / UPDATE affecting downstream skill behavior across projects (e.g. `skills-catalog.yml` write that sync-agents.sh will propagate)
- Schema migration + cross-cutting SKILL.md edits (block combines both — Tier 1 without doubt)

**Signals AGAINST (looks like prod but isn't):**
- SQL INSERT on demo tenant that is verification-only synthetic data (throwaway → treat as Tier 3 diagnostic per §5 490 note-09 edge case 1, BUT elevate to Tier 2 if UNIQUE/FK constraints matter)
- Writing to `{{ config.paths.log_dir_base }}/` markdown artifacts — user-facing but not runtime state
- Writing to per-task documentation — no downstream code effect

**Q1 escape hatch — mechanical prod batch:**

When Q1 YES fires BUT block is also N identical mechanical edits on prod (Q4 signals YES for "N identical file edits" fire simultaneously) → treat as **Tier 2 batch cycle**, not Tier 1 lock. Legitimate downgrade because:

- Landscape is same for all N (already captured for the family)
- Library-first is minimal (no library-vs-scratch choice — each edit is same pattern)
- Plan-first stays full (execution is the risky part)
- Ship-first batched within-block (one commit covering N mechanical edits, not N commits)

Canonical example: task 499 block 4008b (11 downstream migrations one commit) + 4008c (drop old keys cleanup after 4008b established replacements). Both Q1 YES + Q4 YES → Tier 2, not Tier 1. Cross-link: §4 Tier 2 «prod mechanical batch» trigger.

### Q2 — Is the LANDSCAPE captured in an existing artifact?

- **YES** → skip flow-first, minimum Tier 2
- **NO** → landscape fresh needed → Tier 1 Full cycle

**Signals landscape IS captured (skip flow legitimately):**
- Explicit plan artifact from `/{layer}-mode-first` exists: `infra-plan-{code}.md`, `backend-plan-{code}.md`, `ui-plan-{code}.md`
- Recent flow-first artifact for adjacent block ≤ 1 hour old whose landscape covers current block's scope
- Note-N.md explicitly documenting landscape (e.g. `note-14.md` in task 497 block 600 captured landscape for blocks 601-606)
- Wave 2/3 blocks where prior wave's plan artifact + roadmap describes surface exhaustively

**Signals landscape is NOT captured (flow-first mandatory):**
- First time touching this subsystem in the task
- Recent architectural change / rollback that shifted meaning
- User's request is unclear about scope ("fix the notification thing" — which one?)
- Multiple candidate approaches without explicit choice
- >2 days elapsed since last work in this area (memory decay per §5 edge case 2, task 490)

### Q3 — Does the block introduce a NEW library-vs-scratch decision?

- **YES** → keep library-first (Tier 2 minimum)
- **NO** → library-first skippable (Tier 3 candidate — pending Q4)

**Signals YES (library-first has value):**
- Writing first-of-its-kind endpoint / component / skill in a family — need to choose which etalon to mirror
- New integration pattern with subtle failure modes (fire-and-forget async, multipart upload semantics, transaction rollback structure)
- Reference exemplar exists for pattern (e.g. universal atoms like `digital_check_blocklist` per task 499 note-13) — audit picks which
- Cross-mode helper introduction — decide which shared module reuse

**Signals NO (library-first is ceremony without insight):**
- Sibling of already-audited block in same wave — mirrors known pattern with different fields (e.g. `items_delete.php` after `items_create.php` audit per task 511 note-08)
- Trivial mechanical edit whose shape is universal (catalog YAML addition, one-line grep-replace)
- Documentation / arch docs writing — no code pattern involved
- Skill invocation orchestration where the skill owns the pattern

### Q4 — Is the deliverable a DOCUMENT / DIAGNOSTIC / MECHANICAL BATCH?

- **YES** → Tier 3 Plan-focused
- **NO** → Tier 2 default (or Tier 1 if Q1 fired)

**Signals YES (Tier 3 warranted):**
- Deliverable is a note-N.md / spec.md / comparison.md
- Deliverable is smoke test report / compliance audit output / diagnostic markdown
- Block is N identical file edits (e.g. task 499 block 4008b — 11 mechanical downstream migrations)
- Block is catalog registration (single-line YAML addition)
- Block is task finalization ceremony (mark done + commit + sync)
- Documentation edit (README section update, arch docs typo fix)
- Block writes code that mirrors an already-audited sibling in same wave (pattern encoded from library-first watchpoints of the first-of-its-kind block) — the code work IS mechanical extrapolation even though line count is non-trivial. Canonical: task 511 Wave 3 Backend items_create.php audited (Tier 2 first-of-kind) → items_update / items_delete / items_fire / items_reset_password all Tier 3 plan-only mirroring the audited transaction pattern. Cross-link: §6 AP.8 fix language + §5 Q3 signals NO sibling entry.

**Signals NO (elevation from Tier 3 to Tier 2 minimum):**
- Research block that involves grep across N tools + writing a *library reuse map* (borderline — task 490 note-09 edge case 3)
- Diagnostic block with any INSERT / UPDATE on prod tables (elevate — task 490 edge case 1)
- Documentation writing where the doc IS the source of truth (like this manifest itself) — Tier 2 minimum, likely Tier 1 for first version

### Q5 — HIGH-risk override

- **YES** → **Tier 1 Full cycle** regardless of Q1-Q4 answers
- **NO** → tier stands per Q1-Q4

**Signals YES:**
- Roadmap or task.md explicitly tags block as HIGH-risk
- Silent failure mode identified (agent thinks "if this is wrong, nothing crashes but everything is subtly broken") — silent failures ALWAYS Tier 1 per task 511 note-08 «silent failures MUST be audited, loud failures can be plan-first only»
- Block touches ≥3 integration surfaces simultaneously
- Discovery-heavy work (data model unknowns, first-time work with new external service)
- Rollback path complex (multi-step revert, DB state entangled with prod)

### Q6 — Does this block CREATE a lib primitive that downstream blocks CONSUME?

- **YES** → **Tier 1 Full cycle** (producer captures design landscape) AND block_num sequence MUST place producer BEFORE consumers
- **NO** → tier stands per Q1-Q5

**Signals YES (producer block — lib-first anchor):**
- Block creates new file in `lib/` (CSS / JS helper / composition wrapper / partial) that another block in same task imports/references by name
- Block extracts classes / functions from monolith (e.g. `team.css`) to reusable primitive per memory `feedback_no_monolith_css`
- First-of-kind visual/structural primitive (card grid, custom Slider variant, new picker composition, extracted atom) where downstream blocks name the classes/functions
- New PHP helper file (`_shared/foo.php`) consumed by ≥2 sibling endpoints in same wave

**Signals NO (consumer or standalone block):**
- Block uses classes/functions defined by a producer block in same wave — this is the **consumer**, sits Tier 2 sibling of producer's landscape
- Block writes mode-internal helpers not exposed to lib/ (inline `_renderFoo` in page.js — mode-specific, not lib primitive)
- Block reuses existing lib primitive without extending it (mechanical consumption)

**Cadence-first FLAG:** if plan places consumer `block_num` < producer `block_num`, warn user with concrete swap suggestion. Producer must run first so consumers can reference its classes/functions.

**Living reference:** task `radar-os--547-notes-mode-unified` blocks 3050 / 3055 swap 2026-07-10 — original plan had `_renderNoteCard` render (3050) BEFORE `.notes-grid` CSS extract in `lib/notes-card.css` (3055). Consumer would execute with undefined classes → either broken landing OR inline styles diverge from later extraction. User caught. Fixed via swap: 3050 = CSS extract (Tier 1 lib-first anchor) → 3055 = render (Tier 2 consumer sibling).

---

## §6 Anti-patterns — AP.1 through AP.12

Consolidated from 4 empirical sources: task 511 note-08, task 490 note-09, task 499 note-13, task 497 inline decisions. Each pattern present = 🚨 red in `/cadence-first` audit + retro-fit prohibition.

### AP.1 — Uniform full cycle regardless of block type

**Definition:** running Tier 1 on every block "for consistency" without applying Q1-Q5 framework.

**Why bad:** consumes context, produces low-value artifacts (library-first for a verification block), creates fatigue leading to silent shortcuts on genuine HIGH-risk blocks. In a 14-block series (task 499 chain 48), full cycle × 14 exhausts context before HIGH-risk blocks reached.

**Fix:** apply Q1-Q5 explicitly per block. Record classification in task.md before any skill invocation.

**Source:** task 499 note-13 §Anti-pattern 1.

### AP.2 — Downgrading Tier 1 blocks under time pressure

**Definition:** "Block N is under deadline, let's skip library-first and go straight to plan-first because we already know the atom."

**Why bad:** the "we know the atom" assumption is exactly what library-first challenges. Skipping misses reference exemplars that could have made the block 30% smaller LOC. Time pressure is argument FOR full cycle, not against.

**Fix:** Tier 1 classification is non-negotiable for HIGH-risk / prod-code-changing blocks. If deadline pressure — negotiate scope, not skill depth.

**Source:** task 499 note-13 §Anti-pattern 2.

### AP.3 — Silent skill skip (no justification in plan-first)

**Definition:** running Tier 2/3 without explicit rationale in the plan-first artifact.

**Why bad:** future auditors can't distinguish intentional skip from accidental forgetting. Undermines the whole per-block cadence discipline.

**Fix:** any Tier 2/Tier 3 skill skip must include one-line rationale in plan-first: "library-first: skipped per §5 Q3 — no library-vs-scratch decision, pattern audited in block N". Auditability of the skip decision itself.

**Source:** task 499 note-13 §Anti-pattern 5.

### AP.4 — Cross-block ship-first batching

**Definition:** running blocks A + B + C back-to-back and doing one ship-first at end covering all three.

**Why bad:** each block deserves distinct commit-worthy scope. Cross-block batching means one big commit hard to revert selectively. Breaks task_blocks status granularity.

**Distinction:** within-block batching (e.g. task 499 block 4008b processes 11 downstreams internally with one ship-first) is fine — same block, one commit, one status close. **Cross-block** batching is the anti-pattern.

**Fix:** one ship-first per block, always.

**Source:** task 499 note-13 §Anti-pattern 4.

### AP.5 — Retro-fitting tier classification mid-execution

**Definition:** starting a block as Tier 1, hitting difficulty, silently downgrading to Tier 2 to "save time".

**Why bad:** Tier classification is a hypothesis about block characteristics decided BEFORE flow-first per §Golden Rule. Retro-fitting under pressure is how HIGH-risk shortcuts sneak in.

**Fix:** if block turns out simpler than initially classified, note observation and finish current tier. Apply learning to future blocks. Do NOT downgrade current block mid-way.

**Source:** task 499 note-13 §Anti-pattern 6.

### AP.6 — LOC / duration-based tier selection

**Definition:** "block is 200 LOC → Tier 1" or "block will take 3 hours → Tier 1".

**Why bad:** duration and LOC are symptoms, not signals. A 250-LOC block mirroring already-audited pattern (like `items_update.php` after `items_create.php` audit) does NOT need library-first. A 40-LOC block introducing subtle timing idiom (`render()` fire-and-forget) DOES need library-first.

**Fix:** classify based on *novelty of idiom* and *silent-failure risk*, not size.

**Source:** task 490 note-09 §Anti-pattern 3 + task 511 note-08 §AP.1.

### AP.7 — Skipping plan-first because "obvious"

**Definition:** "It's just cp + git add + push — plan-first overkill."

**Why bad:** sequencing errors are #1 cause of `.git/index.lock` incidents, foreign-file captures, rollback confusion. plan-first table forces staging verification and rollback-safe step identification.

**Fix:** any block that writes a file gets plan-first, no exceptions. Only one-line edits and pure diagnostic bash get skipped per plan-first Exceptions.

**Source:** task 511 note-08 §AP.3 + task 499 note-13 §Anti-pattern 3.

### AP.8 — Running library-first per block "for safety"

**Definition:** "Better to be thorough — do full cycle for every code block."

**Why bad:** ~15 min per block × 7 blocks = ~100 min lost per wave on already-known patterns. Reduces velocity, dilutes attention on the two blocks where audit actually matters.

**Fix:** first-of-its-kind gets library-first; siblings get plan-first only. Task 511 Wave 3 Backend applied this — 2 lib+plan for BE.1/BE.2 firsts + 6 plan-only for siblings.

**Source:** task 511 note-08 §AP.2.

### AP.9 — Not recording tier decisions in task.md

**Definition:** decided skill map for a wave, never fixed it in task.md.

**Why bad:** two sessions later you (or fresh Claude session) has no idea why block A got library-first but block B didn't. Wave becomes inconsistent.

**Fix:** after deciding skill map, fix it in `task.md` under a "Skill map per block" table with one-line rationale per block. Both Wave 2 UI and Wave 3 Backend of task 511 have this table.

**Source:** task 511 note-08 §AP.5.

### AP.10 — Inline write instead of Skill() invocation

**Definition:** writing plan-first artifact directly via Write tool instead of `Skill('plan-first')`.

**Why bad:** bypasses skill-managed bookkeeping (round numbers, artifact registration, task_blocks INSERT for sub-blocks). Even for plan-only Tier 3, invoke the skill.

**Fix:** always through `Skill('*')` tool. Inline write bypasses routing.db state and creates drift.

**Source:** task 490 note-09 §Anti-pattern 2 + AP.10 in note-01.

### AP.11 — Skipping flow-first because "I already know this code"

**Definition:** "I finished block N 20 minutes ago in the same area — skip flow-first for block N+1."

**Why bad:** real case in task 490 block 217.b — landscape was well-known, skipped flow-first felt safe. Reality: the flow-first that ran anyway (as auto-invoke) captured 3 non-obvious risks (push policy, cron alignment, broadcast callers regression).

**Fix:** even when landscape seems fresh, running flow-first is cheap insurance. If prior flow-first artifact genuinely covers current block's landscape at same fidelity — cite it explicitly in library-first "chain" header and skip legitimately per Q2. Otherwise let auto-invoke fire.

**Source:** task 490 note-09 §Anti-pattern 1.

### AP.12 — Consumer block before producer block (lib-first violation)

**Definition:** plan places consumer block that references a lib primitive (CSS classes / JS helpers / extracted partial) with a lower `block_num` than the producer block that CREATES that primitive. Consumer executes with undefined classes/functions.

**Why bad:** two failure modes, both silent:
1. Consumer lands broken — references classes that don't exist yet → visual glitch or runtime error only caught on smoke test
2. Consumer inlines styles/functions as workaround → producer's later extraction diverges from consumer's inline copy → dead code + drift between two "sources of truth" for same primitive

**Distinction from AP.4 (cross-block batching):** AP.4 is about ship-first granularity. AP.12 is about `block_num` sequence for producer→consumer dependencies. Both can coexist in same plan.

**Fix:** swap `block_num` so producer (lib primitive creation) comes first + producer becomes **Tier 1 anchor** per Q6 + consumer becomes **Tier 2 sibling** of producer's design landscape. Cadence-first `/cadence-first` skill FLAGs this ordering violation before task_blocks INSERT.

**Living reference:** task `radar-os--547-notes-mode-unified` blocks 3050 / 3055 swap 2026-07-10. Original plan: 3050 `_renderNoteCard()` (consumer of `.notes-grid` CSS) → 3055 CSS extract to `lib/notes-card.css` (producer). User caught the ordering violation before execute. Fixed via swap: producer 3050 first (Tier 1), consumer 3055 after (Tier 2).

**Source:** task 547 block 3050/3055 swap incident + memory `feedback_no_monolith_css.md`.

---

## §7 Real-world ratios (empirical calibration)

Data from 4 tasks aggregated. `/cadence-first` uses these as sanity check for output distribution across a task's blocks.

| Task / Wave | Blocks | Tier 1 Full | Tier 2 Partial | Tier 3 Plan-only |
|---|:-:|:-:|:-:|:-:|
| task 511 Wave 2 UI | 10 | 0 | 3 | 7 |
| task 511 Wave 3 Backend | 9 | 0 | 2 | 7 (incl. 1 retro-downgrade) |
| task 497 Backend wave | 7 | 3 | 2 | 2 |
| task 499 chain 48 series | 14 | 8 | 3 | 3 |
| task 547 Wave 1 Infra | 12 | 1 | 6 | 5 |
| task 547 Wave 2 Backend | 9 | 1 | 7 | 1 |
| task 547 Wave 3 UI | 13 | 2 | 8 | 3 (Q6 lib-first anchor 3050 CSS + AsyncPicker composition 3060) |
| **Aggregate (74 blocks)** | 74 | 15 | 26 | 33 |

**Observed distribution:** ~20% Tier 1 / ~35% Tier 2 / ~45% Tier 3.

**Skill calibration guidance:**
- Median tier across tasks = **Tier 2**. Default recommendation when Q1-Q5 signal is ambiguous = Tier 2 (median), NOT Tier 1 (per task 490 note-09 «default to fuller» conservatism, WHICH we override with observed ratios).
- If a task's cadence distribution outputs >70% Tier 1 → likely AP.1 uniform-cycle bias. Skill should surface warning.
- If a task's cadence distribution outputs >80% Tier 3 → likely under-classification. Skill should elevate at least manifest-writing / SKILL-writing blocks to Tier 2 minimum.

**Task-type modifiers (informal — refine in v1.0.x after regression):**
- Multi-tier COMPLEX mode Wave 1 infra → skew Tier 3 (mechanical schema work)
- Skill-writing tasks → skew Tier 2 (template audits)
- Prod migration series → skew Tier 1 (silent-failure risk)
- Documentation refresh tasks → skew Tier 3 (mechanical)

---

## §8 Output format contract

Skill `/cadence-first` invocation produces exactly this shape. Consumers (executors, downstream skills, audit tooling) rely on this being canonical. Do not deviate.

### Output shape (verbatim from task.md 515 canonical spec)

```markdown
## Cadence decisions — {task_slug}

| # | Block title | Flow | Library | Plan |
|:-:|---|:-:|:-:|:-:|
| 1 | Write CADENCE_HEURISTICS.md | ✗ | ✓ | ✓ |
| 2 | Write SKILL.md | ✗ | ✓ | ✓ |
| 3 | Register в catalog | ✗ | ✗ | ✓ |
| 4 | Regression | ✗ | ✓ | ✓ |
| 5 | Deep integration | ✓ | ✓ | ✓ |
| 6 | Finalize | ✗ | ✗ | ✓ |

### Rationale per block

**Block 1 — Write CADENCE_HEURISTICS.md:** {краткое обоснование на основе Q-триггеров, 1-2 предложения}
**Block 2 — Write SKILL.md:** {rationale}
**Block 3 — Register в catalog:** {rationale}
...
```

### Mandatory elements

1. Table with 5 columns: `#`, `Block title`, `Flow`, `Library`, `Plan` — each boolean with ✓ or ✗
2. Rationale block per every block below table — short (1-3 sentences) grounded in Q-triggers from §5
3. Optional aggregate row at end if overall pattern emerges (e.g. "all blocks skip flow-first because landscape captured in note-N.md")

### Storage requirements

- Output returned to chat for user visibility
- Simultaneously written to `task_blocks.recommended_cadence` column (text — enum string `flow+lib+plan` / `lib+plan` / `plan` / `full`) per row
- Rationale strings saved as separate artifact `cadence-decisions-{N}.md` in task's log_dir for audit trail
- Registered in `task_artifacts` with `artifact_type='cadence-decision'`

### Reference for skill implementation

SKILL.md (in task 515 block 2) uses this shape verbatim. Do not reinvent template — copy from here as canonical form. Any deviation breaks consumer expectations.

---

## §9 Legacy Migration Principles — LM.1 through LM.5

For retro-fitting `/cadence-first` on existing tasks that generated blocks pre-cadence-first. Constraints, not step-by-step recipe.

**LM.1** — Existing tasks with completed blocks (status=done) do NOT get retroactive cadence assigned. Their `recommended_cadence` column stays NULL. Historical cadence is captured in `plan-first-*.md` artifacts and task.md skill-map tables where present.

**LM.2** — Existing tasks with pending blocks (status=pending or open) may get cadence assigned by manual `/cadence-first` invocation with `task_id + block_num=[list]`. Standalone mode supported for this exact use.

**LM.3** — Mid-execution downgrade is prohibited (see AP.5). If executor observes tier misclassification during execution — finish current tier, note observation in ship-first report as "cadence-observation: block executed as Tier N but would have benefited from Tier N-1". Next similar block gets adjusted classification.

**LM.4** — Executor override supported. If executor at execution time sees new information not visible at generation time (e.g. block description omitted a critical integration surface discovered during flow-first) — executor may override `recommended_cadence` and document override in the block's plan-first artifact. Override rate should be < 10% for a well-calibrated skill. Higher rate = signal to review manifest.

**LM.5** — Regression testing (task 515 block 4) runs `/cadence-first` on historical blocks and compares recommendations to manual decisions in source notes. Target accuracy ≥90%. Below 90% = manifest v1.0.x patch cycle triggered.

---

## §10 Cross-references

### Empirical sources

- `{{ config.paths.log_dir_base }}/2026-07-02-radar-os--511-employees-mode/note-08.md` — skill map framework, 19 worked examples, silent-vs-loud failure insight
- `{{ config.paths.log_dir_base }}/2026-07-02-radar-os--490-questions-e2e-on-new-atoms/note-09.md` — 3 tiers with deliverable-type selector, 5 best practices, 6 anti-patterns, 3 edge cases
- `{{ config.paths.log_dir_base }}/2026-07-02-radar-os--499-scenario-pack-executor/note-13.md` — matrix committed early, Q1-Q4 framework, context exhaustion argument
- Task 497 blocks 600-606 inline decisions in `plan-first-*.md` artifacts
- `{{ config.paths.log_dir_base }}/2026-07-10-radar-os--547-notes-mode-unified/cadence-decisions-3.md` — Q6 lib-first ordering (producer→consumer) empirical evidence: block 3050 CSS extract MUST precede 3055 consumer render. User caught ordering violation before execute.

### Related memory

- `feedback_no_monolith_css.md` — motivating memory для Q6 lib-first signal (CSS не в monolith team.css, каждый primitive = свой `lib/*.css`). Producer→consumer sequencing enforced by Q6.

### Synthesis of the above

- `{{ config.paths.log_dir_base }}/2026-07-04-radar-os--515-cadence-first/note-01.md` — distilled synthesis + cross-refs (READ FIRST for navigation to sources)

### Sibling manifests (Mode Launch Framework)

- `radar/arch/modes/_shared/INFRA_MODES_MANIFEST.md` v1.0.2 — Wave 1 schema
- `radar/arch/modes/_shared/BACKEND_MODES_MANIFEST.md` v1.0.1 — Wave 2 endpoint
- `radar/arch/modes/UI_MODES_MANIFEST_SUMMARY.md` v1.0 — Wave 3 frontend (index over 8 arch docs)

### Task ID

`radar-os--515-cadence-first` — this task, creating cadence-first skill + manifest.

---

## §11 Update History

- **2026-07-04 v1.0 initial** — created in task `radar-os--515-cadence-first` block 1. Content synthesized from 4 empirical sources (511 note-08 + 490 note-09 + 499 note-13 + 497 inline decisions). Structural template mirrored from BACKEND_MODES_MANIFEST v1.0.1 (12 sections, Golden Rule + Anatomy + Anti-patterns + Legacy Migration + Update history + Companion invariant pattern). Content-specific sections adapted: §4 semantically shifted from BACKEND «endpoint shape signature» to CADENCE «3-tier gradient»; §5 from BACKEND «Baseline per Mode Type» to CADENCE «Decision framework Q1-Q5»; §8 introduced as new section «Output format contract» (BACKEND had no equivalent).
- **2026-07-04 v1.0.1 patched-y1-y2** — Y1+Y2 patches from task 515 block 4 regression (v1.0 accuracy 73.7% below 90% target per LM.5). **Y1**: §5 Q4 signals YES gains «sibling of already-audited block» entry (source: §6 AP.8 fix language). §5 Q3 signals NO already contained sibling entry from v1.0 — real gap was Q4 not elevating siblings to Tier 3. **Y2**: §5 Q1 gains new escape hatch sub-section «Q1 YES + Q4 YES mechanical prod batch → Tier 2 batch cycle» + §4 Tier 2 «When it fires» gains matching trigger. Companion SKILL.md updated same commit per §12 (Step 3.1 escape note + Step 3.4 Q4 sibling signal + Step 3.6 new consolidation rule). Y3 (research-deliverable Q reorder) + Y4 (retro-downgrade) deferred — Y3 structural, dedicated design task; Y4 folds into Y1 sibling signal.
- **2026-07-10 v1.0.2 patched-y5-lib-first** — Y5 patch from task `radar-os--547-notes-mode-unified` Wave 3 UI block 3050/3055 swap incident. **New §5 Q6** «Lib primitive producer/consumer ordering» — YES → Tier 1 anchor + producer must precede consumers in block_num sequence. **New §6 AP.12** «Consumer block before producer block (lib-first violation)» with two silent failure modes documented. §7 empirical calibration expanded with 3 rows from task 547 (Wave 1 Infra / Wave 2 Backend / Wave 3 UI) — aggregate now 74 blocks across 7 waves. §10 cross-references gain link to task 547 cadence-decisions-3.md + memory `feedback_no_monolith_css.md`. Companion SKILL.md needs Step 3.4 sync (add Q6 signal detection to `/cadence-first` invocation logic — flag ordering violation before task_blocks INSERT).

**v1.0.x planned patches:**
- Y3 (research/landscape-deliverable Q reorder) — §5 Q2 NO branch misfires for research blocks whose deliverable IS landscape exploration. Structural change (Q order or new signal AGAINST). Deferred until post-block-5 integration lands.

---

## §12 Companion invariant

Any change to this manifest that touches rules — **§3 Golden Rule, §4 Anatomy (tier definitions), §5 Decision framework (Q1-Q5 + signals), §6 Anti-patterns, §8 Output format contract, §9 Legacy Migration** — MUST land in the **same commit** as any dependent SKILL.md changes in `aihub/.claude/skills/cadence-first/SKILL.md`.

**Note (v1.0):** no SUMMARY / YAML companion files exist for cadence manifest. Single-file colocated pattern per task 515 D01 R2 decision (manifest is skill-specific, single consumer). If future orchestration-domain manifests emerge → consider shared location refactor + companion invariant expansion. YAGNI now.

Drift between manifest and SKILL.md = bug. `/cadence-first` self-audits at invocation time — if manifest version differs from expected version in SKILL frontmatter, warn user.

---

**End of manifest.**
