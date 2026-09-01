# Parity fixtures

A fixture is a frozen scenario plus the contract its output must satisfy. It
exists to answer one question: **did this runtime produce the same shape of work
as the reference one?**

```
fixtures/{skill}/{case}/
  input.md     # the task statement handed to the agent
  expect.yml   # what must be true afterwards
```

## Structure, never text

Assertions describe **shape**: a file exists, the sections it must contain, the
row it must register, the gate it must carry. They never compare prose.

Two agents will not word a plan the same way, and neither will the same agent on
two runs. A fixture that compares text is red from the first day, and a test that
is always red stops being read — which is worse than having no test at all.

## Running

The runner does **not** drive the agent. There is no way for a shell script to
make Claude Code or Codex execute a protocol; that part is yours.

1. Read `input.md`, hand it to the agent under test, let the chain run.
2. Point the runner at the log directory that run produced:

```bash
bash bin/parity-run fixtures/plan-first/001-add-endpoint /path/to/log-dir
```

To check every fixture against the same run — the question an adapter actually
has to answer — use `--all`:

```bash
bash bin/parity-run --all /path/to/log-dir
```

It prints a row per fixture and exits non-zero if any of them failed. A run that
exercised only one skill will legitimately fail the fixtures for the others; read
the table, not just the exit code.

Add `--verbose` to either form when a failure needs explaining. It shows what the
artifact actually contains — which headings are there, which files sit in the
directory, which artifact types the task registered — so a red line is a finding
rather than the start of a manual investigation. The flag adds lines and changes
none, so a quiet run stays byte-identical.

The runner reports ✅/❌ per assertion and exits non-zero if any fail.

## expect.yml

| Key | Meaning |
|---|---|
| `artifact` | filename glob the run must have produced |
| `artifact_type` | value expected in `task_artifacts.artifact_type` |
| `sections` | markdown headings that must be present |
| `gate` | substring proving an approval gate was offered |
| `min_table_rows` | minimum rows in the first markdown table (optional) |

Adding a fixture means adding a directory. Nothing registers it centrally — the
runner takes the path.
