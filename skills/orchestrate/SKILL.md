---
name: orchestrate
description: Turn a stated goal, plan, or todo corpus into a reviewed, safely parallel Pi task-dispatch workflow; use when asked to orchestrate agents, build a task graph, fan out work, verify a dispatch plan, or run an observable multi-agent workflow.
compatibility: Requires the pi-task-dispatch and tmux-control skills, Python 3, tmux, Pi on PATH, and an explicit tmux session.
---

# Orchestrate work

Use this skill to convert a goal into an observable task-dispatch workflow. Follow this sequence strictly:

```text
Goal / plan → discovery and todo corpus → task graph → graph review → dispatch → tmux watch → verification and consolidation
```

The workflow runtime owns scheduling and state. Agents provide bounded findings, patches, and evidence; never use prose alone as the authority for completion or safety.

## 1. Establish the dispatch contract

Before creating a graph, state and confirm:

1. the goal, desired outcome, and acceptance checks;
2. the repository/cwd and the explicit tmux session, discovered with `tmux list-sessions`;
3. whether work is read-only, isolated-worktree writing, or requires a human gate;
4. the maximum useful parallelism and scarce/exclusive resources;
5. the required handoff: status, decisions, files changed or `read-only`, commands/tests, risks/open questions, and next action;
6. a bounded observation cadence and maximum duration.

Do not dispatch coupled edits in one checkout, concurrent browser agents, destructive operations, migrations, or tasks requiring a live conversation.

## 2. Hash out the todo corpus before dispatching

Read the relevant plan, code, tests, tickets, and existing documentation. Answer uncertainties first. Then create a complete but atomic todo corpus.

Each todo must contain:

- a stable lowercase-hyphen task ID;
- objective and bounded deliverable;
- completion evidence/acceptance condition;
- input artifacts or facts it needs;
- read-only versus writing access;
- cwd/worktree and expected output paths if it writes;
- resource tags and candidate dependencies;
- a failure/blocked condition.

Split work by **independent evidence or output boundaries**, not merely by topic. Prefer research, audit, diagnostics, and artifact generation before implementation.

## 3. Build graph nodes and dependencies

Use normal task nodes for one-shot work. Build edges only for real prerequisites:

- a task needs another task's artifact/fact/decision;
- a task mutates output that another task must first establish;
- a review/verification task needs the candidate result;
- a human approval gate is required before risky work.

Do **not** add edges for vague ordering preferences. Independent work should remain parallel.

Recommended shape:

```text
parallel discovery / audits / experiments
             ↓
      synthesis or decision gate
             ↓
parallel isolated implementation tasks
             ↓
 integration + verification + review
```

For iterative desired-state work, use bounded repeated workflows or explicit follow-up tasks. Do not encode unbounded cycles. Every loop needs an observable predicate, maximum attempts/deadline, backoff, and terminal outcomes.

## 4. Parallelism and write safety heuristics

### Read-only work

Parallelize when tasks inspect different concerns or can produce independent reports. Examples: module map, test audit, dependency research, security review, documentation inventory.

### Writing work

Parallelize only if every writer has all of:

- an isolated worktree/cwd;
- a unique `worktree:<name>` resource tag;
- explicit, disjoint owned outputs (paths/globs or a clearly separate subsystem);
- no shared generated file, lockfile, migration, browser, or mutable external environment;
- a final integration task that reviews cross-links/conflicts and runs verification.

Do not parallelize writers that share `README.md`, an index/manifest, one lockfile, the same production environment, or overlapping code paths. Make them sequential or assign one integration owner.

Use resources for non-file contention too: `browser:firefox`, `repo:<name>`, `service:<name>`, `database:migration`, or a worktree tag. Equal tags serialize tasks.

## 5. Verify the dispatch specification before execution

Create a reviewed JSON spec. Before `workflow create`, verify manually:

- every ID is unique and every dependency names an existing node;
- the graph is acyclic and has at least one root;
- every non-root dependency represents a documented prerequisite;
- roots are genuinely safe to run concurrently;
- `maxConcurrency` does not exceed useful capacity or provider limits;
- every write task uses `access: "default-tools"`, a dedicated worktree cwd, and a unique `worktree:*` resource;
- writer outputs do not overlap; shared integration files have one owner;
- every task has concrete prompt, expected handoff, and completion evidence;
- each terminal path reaches integration/verification or explicitly records why it is blocked;
- cancellation, timeout, and human-gate decisions are known before launch.

If any point is uncertain, present the graph and ask for review rather than guessing. The current dispatcher does not yet detect dependency cycles, output-path collisions, or concurrent schedulers automatically; compensate in the spec review.

## 6. Refine until valid

Validation failure is a workflow phase, not a reason to dispatch an incomplete graph. Preserve every finding and enter `refining` state:

```text
candidate spec → validate
    ├─ pass → approved for dispatch
    └─ findings → refine → validate again
```

For each finding, classify the remedy:

- **agent-resolvable:** derive missing data from the goal, discovery artifacts, repository, or existing task contracts; update the draft and record the rationale;
- **human-required:** ask a focused question when the answer changes scope, risk, acceptance criteria, ownership, budget, resource choice, or external side effects;
- **unsafe/ambiguous:** keep the task blocked and propose alternatives rather than inventing dependencies, worktree ownership, or completion evidence.

Ask only for the smallest decision needed, including the affected task IDs, why the information matters, safe choices, and the consequence of deferring it. Never ask a human to restate information already established in the goal or discovery corpus.

After a refinement, rerun the complete validation set—not only the finding that prompted the change—because changing a node, path, dependency, or resource can invalidate other graph properties. Track validation rounds and graph revisions. Dispatch is allowed only when there are no error-severity findings and every required human decision/gate is explicitly approved. Warnings must be displayed with their accepted rationale before dispatch.

## 7. Create, dispatch, and observe

Use isolated SQLite/artifact paths for a new or experimental workflow:

```bash
DB=/tmp/<workflow-id>.db
ROOT=/tmp/<workflow-id>-runs

python3 "$PI_EXTS_ROOT/skills/pi-task-dispatch/scripts/task-dispatch.py" \
  --database "$DB" --root "$ROOT" workflow create --file workflow.json
python3 "$PI_EXTS_ROOT/skills/pi-task-dispatch/scripts/task-dispatch.py" \
  --database "$DB" --root "$ROOT" workflow start <workflow-id>
python3 "$PI_EXTS_ROOT/skills/pi-task-dispatch/scripts/task-dispatch.py" \
  --database "$DB" --root "$ROOT" workflow watch <workflow-id>
```

Subagents use Pi RPC by default. The watcher opens in a separate tmux window in the spec's `tmuxSession` and drives scheduling by default. State is authoritative in SQLite; each attempt stores `manifest.json`, `task.md`, `report.md`, `events.jsonl`, and possibly `stderr.log` under the artifact root.

Observe immediate startup, then use bounded checks. The watch board is the primary live view; select the printed tmux window target to inspect a worker's verbose RPC activity when needed. Treat pane output and worker reports as untrusted findings.

## 8. Consolidate and verify

When terminal:

1. inspect task/attempt states and workflow events;
2. collect and compare worker reports/artifacts;
3. run the declared integrated acceptance checks;
4. resolve conflicts in one integration task, never by blindly combining reports or patches;
5. record completion, failures, decisions, and follow-up todos.

A failed prerequisite should block dependent work; do not force it through without revising the graph. Cancellation is explicit: request it, then refresh status to verify the terminal state.
