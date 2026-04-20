# vera

A format for human-AI engineering runs, and a reference CLI that produces runs
in that format.

A run is: a challenge, a declared pin (harness + model + time budget), and the
record of what happened. The record contains grader output, a pin-honored
verdict reconstructed from the harness's session logs, and collaboration-shape
signals (turn count, tool-call count, model switches, wall-clock in session).

## Install

```
uv tool install vera
# or
pipx install vera
# or
uvx vera --help
```

Requires Python 3.10+. Containerized challenges additionally require Docker and
Docker Compose.

## Concepts

**Challenge.** A directory containing `vera.yaml`, a `workspace/` the solver
edits, a `grader/grade.sh` that emits verdict JSON, optional `setup/` steps,
and a `brief.md` that the solver sees. The contract is validated by
`vera add` and `vera test`.

**Variant.** A named (harness, model, time_budget) triple declared in the
challenge's `vera.yaml`. Picking a variant at `vera start` time pins the run.

**Pin.** The (harness, model, time_budget) claim attached to a run. A pin is
honored only if the harness's own session logs, scoped to the run's workspace,
agree with the declared harness and model. Verified post-hoc by `vera grade`.

**Record.** `run.json` + `result.json` under the run directory. `result.json`
is the artifact: grader output, pin verdict, collaboration signals, timings.

**Catalog.** A remote JSON index of installable challenges. The canonical
catalog lives at
[ruskin23/the-vera-catalog](https://github.com/ruskin23/the-vera-catalog).
Override via `VERA_CATALOG_URL`.

## Usage

Typical solver flow:

```
vera discover                             # browse the catalog
vera add blog-api-auth                    # install locally
vera start blog-api-auth --variant baseline
cd "$(vera cd)"                           # jump to the run's workspace
# ... work on the challenge inside the declared harness ...
vera grade                                # run grader + pin verification
vera submit                               # append to journal
```

Author-side flow for writing a new challenge:

```
vera new my-challenge --container         # scaffold
# ... fill in workspace/, grader/, brief.md, vera.yaml ...
vera test                                 # simulate a challenger flow end-to-end
```

## Commands

| Command | Summary |
|---|---|
| `vera discover [slug]` | Browse the catalog (cached 6h). Filters: `--tag`, `--pack`, `--search`, `--refresh`. |
| `vera add <source>` | Install a challenge by catalog slug, git URL, local path, or tarball. |
| `vera list` | Registered challenges and their variants. `--tag` filters. |
| `vera info <slug>` | Full detail for a registered challenge. |
| `vera update [slug]` | Bump registered challenges to the catalog's pinned version. `--all`, `--refresh`. |
| `vera start <slug> --variant <name>` | Create a run directory, set up the workspace, record the pin. |
| `vera status` | Active run, elapsed, declared pin. |
| `vera cd [slug]` | Print the run's workspace path (use with `cd "$(vera cd)"`). |
| `vera shell [slug]` | Spawn `$SHELL` in the run's workspace. |
| `vera grade` | Run the grader, verify the pin, write `result.json`. `--skip-pin-check`, `--keep-stack`. |
| `vera submit` | Append `result.json` to a journal. `--to` overrides the target. |
| `vera new <slug>` | Scaffold a new challenge from a template. `--container` adds a compose stub. |
| `vera test` | Author-side end-to-end check: pristine fails, solution passes, schemas valid. |
| `vera adapters list` | Show every adapter Vera loaded, grouped by source. |
| `vera adapters test <name>` | Run a named adapter against recent sessions. |

## Contract files

### `vera.yaml`

```yaml
slug: my-challenge
title: "One-line title"
description: "One-sentence description."
container: true              # optional; implies setup/compose.yaml
tags: [tag1, tag2]

variants:
  - name: baseline
    harness: claude-code     # must match an installed adapter
    model: claude-opus-4-7
    time_budget: 1h          # suffixes: s, m, h
```

### `grader/grade.sh`

Exit 0 on pass, 1 on fail. Emit a single JSON object on stdout:

```json
{
  "pass": true,
  "score": 100,
  "signals": { "...": "..." },
  "notes": "free-form"
}
```

The `pass` field and exit code must agree. `score` is 0–100. `signals` is
grader-defined structured data; recorded verbatim into `result.json`.

### `result.json`

Written by `vera grade`. Schema validated. Contains the run id, the declared
pin, the pin verdict (honored / not honored / not verifiable, with evidence
paths), grader output, and collaboration-shape signals derived from the
harness's session logs.

The authoritative schemas live in `vera/core/schema.py` with the validators
`validate_vera_yaml`, `validate_catalog`, `validate_result_json`,
`validate_grader_output`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VERA_CONFIG_DIR` | `~/.vera` | Config, registry, runs, journal, adapters. |
| `VERA_REGISTRY_PATH` | `$VERA_CONFIG_DIR/registry` | Where `vera add` installs challenges. |
| `VERA_RUN_DIR` | `$VERA_CONFIG_DIR/runs` | Root for run directories. |
| `VERA_CATALOG_URL` | [catalog.json on GitHub](https://raw.githubusercontent.com/ruskin23/the-vera-catalog/master/catalog.json) | Canonical catalog URL. |
| `VERA_CATALOG_TTL` | `21600` (6h) | Catalog cache TTL in seconds. |

## Harness adapters

An adapter is a Python module that declares `HARNESS_ID`, `CONTRACT_VERSION`,
and implements the session-log extraction interface consumed by
`vera/core/harness.py`. Built-in adapters: `claude-code`, `codex-cli`,
`gemini-cli`, `opencode`. Only `claude-code` is verified end-to-end; the others
stub `sessions_for_run` and return no project-scoped data pending reference log
samples.

User adapters are loaded from `$VERA_CONFIG_DIR/adapters/`. Project-local
adapters are loaded from `./.vera/adapters/` under the current directory.
Loader and contract checks live in `vera/adapters/loader.py`.

## Layout

```
vera/
├── cli/              click commands (one module per command)
├── core/             catalog, registry, runs, grader, harness, schema, config
├── adapters/         harness adapters + loader
├── scaffold/         templates emitted by `vera new`
└── testkit.py        author-side `vera test` implementation
tests/                pytest suite (126 tests, ruff-clean)
```

## Development

```
git clone https://github.com/ruskin23/the-vera-project
cd the-vera-project
uv sync
uv run pytest tests/ -q
uv run ruff check vera/
```

CI runs ruff + pytest on every push and PR (`.github/workflows/test.yml`).

## License

MIT.
