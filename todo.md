# Task-dispatch improvements backlog

## 1. Workflow specification validation

- [x] Add `workflow validate --file workflow.json` before persistence and `workflow validate WORKFLOW_ID` for stored workflows.
- [ ] Reject duplicate IDs, missing dependencies, dependency cycles, no-root graphs, unreachable nodes, invalid states, and impossible dependency expressions.
- [ ] Verify every task has a bounded objective, expected deliverable, completion evidence, access mode, and handoff contract.
- [x] Explain validation findings with task IDs, offending edges, severity, and a concrete remediation.
- [ ] Make `workflow create` run validation by default; provide an explicit, recorded override only for deliberate exceptions.
- [ ] Add a `refining` workflow phase: classify each validation finding as agent-resolvable, human-required, or unsafe/ambiguous; apply safe refinements or ask focused human questions; rerun complete validation after every revision; block dispatch until errors are resolved and required approvals are recorded.
- [ ] Persist graph revision, validation round, findings, refinement rationale, human answers, and accepted warning rationale so dispatch provenance is auditable.

## 2. Declared outputs and write-path ownership

- [ ] Add task metadata for `inputs`, `outputs`, and `writePaths` (files/globs/subsystems).
- [ ] Validate that concurrently eligible writer tasks do not claim overlapping output/write paths.
- [ ] Require a single owner for shared integration files such as indexes, manifests, lockfiles, generated assets, and migrations.
- [ ] Surface write-path conflicts as scheduler blocking reasons and in the TUI.
- [ ] Record actual changed paths after attempts and compare them with declared ownership.

## 3. Worktree lifecycle management

- [ ] Add optional workflow-managed Git worktree creation for `default-tools` tasks.
- [ ] Persist worktree path, branch, base revision, owner task, and cleanup policy in SQLite/artifacts.
- [ ] Create a unique `worktree:<name>` resource lease automatically for each writer.
- [ ] Add commands to inspect, preserve, clean, merge, or cherry-pick worktree results after review.
- [ ] Refuse automatic merge when the worktree is dirty, diverged unexpectedly, has failed verification, or conflicts with another result.

## 4. Workflow-context and artifact injection

- [ ] Include workflow ID, task ID, attempt ID, artifact root, cwd/worktree, declared inputs/outputs, and handoff contract in every worker prompt/manifest.
- [ ] Materialize dependency reports/artifact references for child tasks instead of asking workers to search default task-run roots.
- [ ] Add bounded artifact-selection rules so downstream prompts receive relevant reports, not unbounded history.
- [ ] Preserve provenance: record which parent artifacts and decisions were supplied to each child attempt.

## 5. Retry, timeout, and budget policy

- [ ] Add per-task retry count, retry classification, backoff/jitter, and retry eligibility.
- [ ] Add wall-clock deadline, no-progress timeout, token budget, and cost budget policies at workflow and task levels.
- [ ] Distinguish retriable transport/provider failures from failed acceptance checks and unsafe side effects.
- [ ] Record every policy decision as an event, including budget refusal and retry scheduling.
- [ ] Ensure retries create new attempts and never overwrite a prior report or event history.

## 6. True Gantt, critical path, and observability UI

- [ ] Render proportional attempt bars instead of only a textual recent-attempt summary.
- [ ] Show task phase, elapsed duration, retries, current tool, resource leases, and cost/token usage where available.
- [ ] Highlight the critical path, current blockers, ready-but-unscheduled tasks, and scheduler deferral reasons.
- [ ] Add selectable task details: prompt, dependencies, artifacts, raw RPC event tail, report tail, and tmux target.
- [ ] Support filtering by task state/resource/agent and a noninteractive export of timeline/event data.

## 7. Human approval gates

- [ ] Add first-class `gate` nodes for graph review, write dispatch, merge, migration, deployment, and external side effects.
- [ ] Persist approver identity, decision, timestamp, rationale, and the graph/version approved.
- [ ] Prevent a gate approval from silently applying after task-spec, branch, artifact, or dependency changes.
- [ ] Show pending gates prominently in CLI/TUI and permit explicit reject/cancel/revise actions.

## 8. Scheduler safety and recovery

- [x] Add a SQLite scheduler lease/lock so concurrent `tick`/`watch --drive` processes cannot dispatch the same task.
- [x] Use transactional outbox/reconciliation semantics around attempt creation, tmux launch, resource leasing, and manifest updates.
- [ ] Detect orphaned tmux/RPC workers after crashes and reconcile to a durable terminal or recoverable state.
- [ ] Release leases only after authoritative completion/reconciliation, including cancellation and worker loss.
- [ ] Add restart/recovery tests for interruption at every dispatch lifecycle boundary.

## 9. Graph authoring assistance

- [ ] Add a `workflow draft` flow that converts a goal and discovery corpus into atomic todos, proposed dependencies, resource tags, and writer ownership.
- [ ] Require an explicit reviewed graph before any write-capable task is dispatched.
- [ ] Keep inferred edges distinct from user-approved edges and explain each inferred prerequisite.
- [ ] Add graph diff/versioning so changes after approval require targeted revalidation and, when needed, reapproval.

## 10. Test and verification coverage

- [ ] Add unit tests for validation, dependency resolution, leasing, retries, cancellation, and recovery.
- [ ] Mock tmux and RPC at process boundaries for deterministic scheduler tests.
- [ ] Add end-to-end tests with a fake JSONL RPC agent, including streaming, settlement, abort, malformed events, and process loss.
- [ ] Add real opt-in Pi/tmux smoke tests with isolated database and artifact roots.
- [ ] Define acceptance fixtures for parallel readers, isolated writers, shared-resource serialization, human gates, and integration verification.
