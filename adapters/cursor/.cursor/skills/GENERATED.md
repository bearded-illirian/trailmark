# This tree is generated

Every file here is produced by `bin/build-adapter.sh cursor` from the skills
in `aihub/.claude/skills/` and `aihub/.claude/commands/`. Nothing in this folder
is edited by hand.

**An edit made here does not survive.** The next rebuild overwrites it, and
because a rebuild prints no warning about what it replaced, the change simply
disappears. The tree is committed so the port stays browsable and usable where
the bash generator cannot run — not because it is a source.

## Where to make the change instead

| You want to change | Edit |
|---|---|
| What a skill does | `aihub/.claude/skills/{name}/SKILL.md` |
| An entry point | `aihub/.claude/commands/{name}` |
| How Cursor differs from other runtimes — invocation syntax, paths, invocation policy | the `cursor` profile in `bin/build-adapter.sh` |

Then rebuild:

```bash
bash bin/build-adapter.sh cursor
```

## This is enforced, not merely requested

`bash bin/build-adapter.sh cursor --check` compares this tree against what
the generator would produce right now. It runs in two places:

- **CI** — `.github/workflows/verify-contract.yml`, on every push and pull request to `main`
- **Publication** — `bin/sync-to-github.sh` refuses to publish a tree that has drifted

So a hand edit here fails a build rather than vanishing quietly. That is the
point: the failure mode this guards against is silent, and silent losses are
the ones nobody learns from.

See `../../README.md` for the adapter itself, and `docs/AGENT_CONTRACT.md` for
what a runtime has to provide.
