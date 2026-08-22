# Task-dispatch workflows

`pi-task-dispatch` orchestrates independent Pi RPC workers through tmux. SQLite is authoritative for workflow state; per-attempt files preserve prompts, reports, and raw RPC events.

## Preconditions

- `uv`, `pi`, and `tmux` are on `PATH`.
- The checked-in uv script lock provisions the managed Python and Textual environment; no system Python or `pip install` is required.
- Install the `tmux` bundle and restart Pi.
- Discover the explicit tmux session before dispatching:

  ```bash
  tmux list-sessions -F '#{session_name}: attached=#{session_attached}'
  ```

For development from this checkout:

```bash
export PI_EXTS_ROOT=/absolute/path/to/pi-exts
task-dispatch() {
  "$PI_EXTS_ROOT/skills/pi-task-dispatch/scripts/task-dispatch" "$@"
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

The watcher is the required observable execution record, including for short workflows. It is a Textual application. Record and report the exact `tmux select-window` command that it prints. Its default is a compact **one-row-per-task Gantt**: every row has an explicit stage tag and one adaptive bar spanning that task's observed attempts (completed attempts use `=`, an active attempt uses `#`). It shows elapsed/recorded time only—it does not invent a completion estimate. This keeps retries on the same row instead of consuming a card.

Press `g` to switch between that Gantt and an explicit dependency **DAG** (`dependency [stage] → dependent [stage]`); this provides a whole-workflow dependency view using the same filters. Press `v` to cycle Gantt, DAG, and the legacy four-column **Queued / Ready / In progress / Terminated** card board. Terminal tasks retain their state tag (`DONE`, `FAILED`, `CANCELLED`, `BLOCKED`, `ORPHANED`, or `LOST`). The view scrolls vertically with arrow keys, Page Up/Down, Home/End, or the mouse wheel. Controls are deliberately display-only except for `r`: `j`/`k` select, `d` shows bounded prompt/dependency/artifact/report/RPC/tmux details, `s`/`f`/`a` cycle state/resource/agent filters, `x` hides terminal tasks for this screen only, and `0` restores them. `r` performs an immediate tick and `q` exits. Hiding/resetting never deletes SQLite records or artifacts; use `workflow export` and `workflow events --jsonl` to preserve or export durable history. Pass `--no-drive` to observe without scheduling.

Workflow workers run one per tmux window in a workflow-scoped detached session named `eph-<tmuxSession>-<workflowId>`. SQLite persists a unique ownership marker; an existing unmarked or differently marked session is rejected rather than adopted. This keeps worker geometry separate from the user's session. The workflow board remains in `tmuxSession`; manifests record the derived worker session and window/pane IDs. No automatic destructive tmux/worktree cleanup is performed; cleanup remains a manual operator action.

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

`workflow refine` records a `refining` state and reports current findings. Warning overrides and persisted refinement-round or human-answer records are not implemented; resolve ambiguity in the reviewed spec and its handoff.

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

## Campaign ledger (explicit, no dispatch)

Campaign intent is stored only when an operator names a separate ledger file; it never uses `--database` or alters a child workflow database:

```bash
task-dispatch campaign create --ledger /tmp/release-ledger.sqlite --file campaign.json
task-dispatch campaign inspect --ledger /tmp/release-ledger.sqlite release-prep
```

Use explicit `campaign gate`, `observe`, `propose-integration`, `approve-integration`, `record-integration`, `pause`, `resume`, and `consolidate` operations. Observation opens the named child SQLite authority read-only and fails closed for missing or revision/hash-mismatched authority. Recording integration requires fresh matching authority, approved phase/proposal decisions, commit and verification evidence, recorder attestation, and authorization. The runtime accepts the user directly, or an unexpired delegation JSON whose named authority has the relevant action and a scope containing the campaign ID. It does not validate path scope, required checks, or revocation conditions; record and review those operational constraints separately. These commands never start a child workflow, retry work, merge/apply a patch, infer state from tmux, or copy child runtime records.

### Display-only campaign overview

```bash
task-dispatch campaign status --ledger /tmp/release-ledger.sqlite release-prep
# `watch` is an alias for the same one-shot, display-only JSON overview.
task-dispatch campaign watch --ledger /tmp/release-ledger.sqlite release-prep
```

The overview reads the ledger plus its child authority locators without writing either database. It shows each declared phase, authoritative child workflow state, observation freshness, board (`workflow watch --no-drive`) and artifact links, gate decisions, integration proposal/commit evidence, recorded incidents, and a conservative next action. A missing observation, stale observation, unreadable child database, or revision/hash mismatch is explicitly labeled **BLOCKED**; it makes no completion or advancement claim and cannot schedule, retry, integrate, or refresh an observation.

### Constrained campaign pilots

`campaign consolidate` emits a deterministic report from ledger references: planned-versus-observed phases, authority-linked integration evidence, incidents, outstanding decisions, opportunities, and counts. An optional reviewed file may add only proposed wisdom candidates; it cannot promote them.

`campaign wisdom record/retrieve/apply` stores human-reviewed policy, scroll, or precedent JSON records. Retrieval is deterministic tag intersection at an explicit timestamp and returns only reviewed/adopted, non-expired records. Records carry provenance, expiry, scope, lifecycle, owner/reviewer, and any application or override is separately attributed. Keep record files in Git for review. This is not a service, RAG, automatic extraction/promotion, or policy enforcement mechanism.

`campaign attention record` is opt-in and records only actionable `decision`, `approval`, `integration`, `blocked`, or `incident` events with authority, impact, options, recommendation, confidence, and source. Its deterministic fingerprint coalesces an open duplicate; `attention resolve` closes that lifecycle. It sends no popup and must not be used for routine settled information.

`campaign route-preflight` compares one explicit `{provider, model, thinking}` JSON route to an operator-supplied availability JSON list. It fails closed when the exact provider-qualified model/thinking combination is unavailable and never substitutes or dispatches a model. A successful invocation records the supplied task locator, route, escalation source, cost, latency, and outcome for later comparison.

## Opt-in real smoke test

The default Python suite uses a fake JSONL RPC command and requires neither Pi
nor tmux. To launch one isolated real worker, explicitly opt in:

```bash
TASK_DISPATCH_SMOKE=1 skills/pi-task-dispatch/tests/smoke_real.sh
```

It creates a temporary database/root and tmux session and cleans both up. It
only verifies launch; inspect the printed run before treating any output as a
result.

## Runtime safety semantics

Attempts pin the workflow revision hash and task snapshot at creation. Dependency reports are injected only when their completed attempt has the current matching revision; revising a workflow therefore invalidates old completed dependency artifacts. Git/worktree command failures and audit failures fail closed. Scheduler status projection runs under its lease fence; no-progress time advances only when a newly observed valid RPC event or worker heartbeat is persisted, never from polling or tmux liveness. A `default-tools` retry additionally requires declared `idempotency: true` and a durable approval for that exact failed attempt and revision (`workflow retry-approve <workflow> <attempt> --approver <user>`); retries are otherwise refused.

## Current limits

This is a practical local workflow tool, not a production workflow service. Avoid dependency cycles, concurrent scheduler/watch processes, and relying on crash recovery for critical work. A dispatch interruption can leave orphaned tmux workers; cancellation and resource leases are reconciled on a tick, but tmux sessions and managed worktrees are deliberately never destructively cleaned up automatically. Keep a human responsible for manual cleanup, reviewing workflow specs, approving write retries, and consolidating worker findings.

For the agent-facing operational contract, see [`skills/pi-task-dispatch/SKILL.md`](../skills/pi-task-dispatch/SKILL.md).
