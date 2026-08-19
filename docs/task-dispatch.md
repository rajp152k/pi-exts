# Task-dispatch workflows

`pi-task-dispatch` orchestrates independent Pi RPC workers through tmux. SQLite is authoritative for workflow state; per-attempt files preserve prompts, reports, and raw RPC events.

## Preconditions

- Python 3, `pi`, and `tmux` are on `PATH`.
- Install the Textual UI dependency: `python3 -m pip install -r "$PI_EXTS_ROOT/skills/pi-task-dispatch/requirements.txt"`.
- Install the `tmux` bundle and restart Pi.
- Discover the explicit tmux session before dispatching:

  ```bash
  tmux list-sessions -F '#{session_name}: attached=#{session_attached}'
  ```

For development from this checkout:

```bash
export PI_EXTS_ROOT=/absolute/path/to/pi-exts
task-dispatch() {
  python3 "$PI_EXTS_ROOT/skills/pi-task-dispatch/scripts/task-dispatch.py" "$@"
}
```

## First isolated workflow

Use temporary state for a first run. Review the JSON before creating the workflow.

```json
{
  "id": "repo-scouts",
  "name": "Repository scouts",
  "cwd": "/absolute/path/to/repo",
  "tmuxSession": "your-session",
  "maxConcurrency": 2,
  "tasks": [
    {
      "id": "map-source",
      "prompt": "Map the source modules. Do not modify files. Return a compact handoff.",
      "access": "read-only"
    },
    {
      "id": "review-tests",
      "prompt": "Review test coverage. Do not modify files. Return a compact handoff.",
      "access": "read-only"
    },
    {
      "id": "synthesize",
      "prompt": "Read the two worker reports and summarize findings. Do not modify files.",
      "access": "read-only",
      "dependsOn": ["map-source", "review-tests"]
    }
  ]
}
```

```bash
DB=/tmp/repo-scouts.db
ROOT=/tmp/repo-scouts-runs

# Create and dispatch ready tasks.
task-dispatch --database "$DB" --root "$ROOT" workflow create --file workflow.json
task-dispatch --database "$DB" --root "$ROOT" workflow start repo-scouts

# Mandatory after every workflow start unless the user explicitly declines tmux UI observation.
# This opens a separate tmux window in `tmuxSession`; it ticks every second.
task-dispatch --database "$DB" --root "$ROOT" workflow watch repo-scouts
```

The board is the required observable execution record, including for short workflows. It is a Textual application. Record and report the exact `tmux select-window` command that the watcher prints. Its default board has four equal-width bordered columns: **Queued**, **Ready**, **In progress**, and **Terminated**. Terminal cards retain their state tag (`DONE`, `FAILED`, `CANCELLED`, `BLOCKED`, `ORPHANED`, or `LOST`); cards word-wrap phase, elapsed time, retry count, resource leases, and known tool/token/cost data. Critical-path, blocked, and ready-deferral annotations are visible on cards.

The board scrolls vertically with arrow keys, Page Up/Down, Home/End, or the mouse wheel, so all task cards remain reachable when they exceed terminal height. Controls are deliberately display-only except for `r`: `j`/`k` select, `d` shows bounded prompt/dependency/artifact/report/RPC/tmux details, `s`/`f`/`a` cycle state/resource/agent filters, `x` hides terminal cards for this screen only, and `0` restores them. `g` switches to the retained proportional Gantt attempt view. `r` performs an immediate tick and `q` exits. Hiding/resetting never deletes SQLite records or artifacts; use `workflow export` and `workflow events --jsonl` to preserve or export durable history. Pass `--no-drive` to observe without scheduling.

Workflow workers run one per tmux window in a derived detached session named `eph-<tmuxSession>` (for example, `eph-pi-exts`). This keeps worker geometry separate from the user's session and avoids tmux's minimum-pane-size limit. The workflow board remains in `tmuxSession`; attempt manifests record the derived worker session and its window/pane IDs. The legacy `dispatch` command still opens one window per worker in its requested session. A failed tmux session/window creation is recorded by normal outbox reconciliation rather than being treated as a successful launch.

## Draft a workflow from a goal

Generate a **JSON-only**, editable draft without creating a database record or launching a worker:

```bash
task-dispatch workflow draft --goal "Understand retry behavior" \
  --discovery skills/pi-task-dispatch/scripts/task-dispatch.py \
  --discovery skills/pi-task-dispatch/tests > workflow-draft.json
```

The draft keeps `inferredDependencies` (with rationale) separate from
`approvedDependencies` and task `dependsOn`. Inferred edges are not scheduling
edges: a reviewer must explicitly copy approved dependencies into `dependsOn`
before `workflow create`.

## Validation and refinement

Validate either a draft file or a stored workflow before dispatch:

```bash
task-dispatch workflow validate --file workflow.json
task-dispatch --database "$DB" workflow validate repo-scouts
```

The command prints JSON findings with severity, task IDs, affected edges where relevant, and remediation. `workflow create` rejects error findings. The current validator checks task IDs and metadata types, dependencies/cycles/roots, access/state values, writer worktree resources, and concurrent writer path collisions. It preserves prompt-only legacy specs but reports missing objective, deliverable, completion-evidence, or handoff fields as warnings.

Use the refinement loop: validate; resolve agent-safe findings in the spec; ask a focused human question for scope, ownership, authorization, or other unsafe ambiguity; then rerun the complete validation set. Do not dispatch with errors. Review warnings before dispatch.

> **Current limit:** recorded warning overrides, persisted refinement rounds/human answers, and a first-class `refining` state are not implemented yet.

## Graph and scheduling rules

- Dependencies have all-success semantics: a child becomes ready after every parent is done.
- A failed, blocked, or cancelled parent blocks its child.
- `maxConcurrency` caps simultaneous attempts.
- Resource leases support `read:<name>` (shared) and `write:<name>` (exclusive); a writer conflicts with every read/write lease of the same name. Untagged legacy resources, including `worktree:<name>`, remain exclusive.
- A task cannot declare both `read:<name>` and `write:<name>` for the same name.
- `read-only` is the default safe mode for discovery/review. Every RPC worker, including a read-only worker, receives `bash` for bounded inspection, diagnostics, and test commands; its task contract still prohibits file modifications.
- A `default-tools` task must use a dedicated worktree and declare a `worktree:<name>` resource. Do not dispatch coupled writers in one checkout.
- The Markdown importer accepts `- [ ]` items and only recognizes dependencies written as `<!-- depends: task-id -->`; it does not infer graph edges from prose.

## Observe, inspect, and collect

Observe dispatched workflows through `workflow watch` at a bounded cadence. Supplement the board with the following machine-readable commands; they do not replace it. Only when the user explicitly declines tmux UI observation may bounded CLI polling substitute for the board.

```bash
task-dispatch --database "$DB" workflow status repo-scouts --refresh
task-dispatch --database "$DB" workflow inspect repo-scouts map-source
task-dispatch --database "$DB" workflow events repo-scouts --jsonl
task-dispatch --database "$DB" workflow export repo-scouts > read-model.json
```

When the user has explicitly declined tmux UI observation, use a bounded shell loop for CLI-only monitoring; do not leave unbounded polling running:

```bash
for n in $(seq 1 30); do
  task-dispatch --database "$DB" --root "$ROOT" workflow tick repo-scouts
  task-dispatch --database "$DB" workflow status repo-scouts --refresh
  sleep 2
done
```

SQLite defaults to `~/.pi/agent/workflows.db`. Attempt artifacts default to `~/.pi/agent/task-runs/<timestamp>-<task>-<suffix>/`:

```text
manifest.json  transport/lifecycle snapshot
task.md        dispatched prompt
report.md      final assistant text
events.jsonl   raw Pi RPC lifecycle, message, and tool events
stderr.log     only if Pi wrote stderr
```

## Cancellation

```bash
task-dispatch --database "$DB" workflow cancel repo-scouts map-source
task-dispatch --database "$DB" workflow status repo-scouts --refresh
```

Omit the task ID to cancel the workflow. RPC workers observe the cancellation request, send Pi an RPC `abort`, then escalate after a short grace period. Always run a post-cancellation status refresh before drawing conclusions.

`events --jsonl` emits stable one-record-per-line event objects, including IDs,
timestamp, type, task/attempt IDs, and decoded detail. `workflow export` emits
a stable read model with task state/phase, dependencies, attempts, resources,
retries, blockers, and deferrals. Both are observation-only and never dispatch.

## Opt-in real smoke test

The default Python suite uses a fake JSONL RPC command and requires neither Pi
nor tmux. To launch one isolated real worker, explicitly opt in:

```bash
TASK_DISPATCH_SMOKE=1 skills/pi-task-dispatch/tests/smoke_real.sh
```

It creates a temporary database/root and tmux session and cleans both up. It
only verifies launch; inspect the printed run before treating any output as a
result.

## Current limits

This is a practical local workflow tool, not a production workflow service. Avoid dependency cycles, concurrent scheduler/watch processes, and relying on crash recovery for critical work. A dispatch interruption can leave orphaned tmux workers; cancellation and resource-lease cleanup are eventually reconciled on a tick. Keep a human responsible for reviewing workflow specs, approving write tasks, and consolidating worker findings.

For the agent-facing operational contract, see [`skills/pi-task-dispatch/SKILL.md`](../skills/pi-task-dispatch/SKILL.md).
