# Task-dispatch improvements backlog

## 1. Workflow specification validation

- [x] Add `workflow validate --file workflow.json` before persistence and `workflow validate WORKFLOW_ID` for stored workflows.
- [x] Reject duplicate IDs, missing dependencies, dependency cycles, no-root graphs, invalid states, and unsupported dependency metadata.
- [x] Verify every task has a bounded objective, expected deliverable, completion evidence, access mode, and handoff contract.
- [x] Explain validation findings with task IDs, offending edges, severity, and a concrete remediation.
- [x] Make `workflow create` run validation by default; preserve warnings for explicit review before dispatch.
- [x] Add a `refining` workflow phase: rerun complete validation after revisions and block dispatch until errors are resolved and required approvals are recorded.
- [x] Persist graph revision, validation findings, refinement rationale, and revision-bound approvals so dispatch provenance is auditable.

## 2. Declared outputs and write-path ownership

- [x] Add task metadata for `inputs`, `outputs`, and `writePaths` (files/globs/subsystems).
- [x] Validate that concurrently eligible writer tasks do not claim overlapping output/write paths.
- [x] Require a single owner for shared integration files such as indexes, manifests, lockfiles, generated assets, and migrations.
- [x] Surface write-path conflicts as validation/scheduler blocking reasons and exported workflow projections.
- [x] Record actual changed paths after attempts and compare them with declared ownership.

## 3. Worktree lifecycle management

- [x] Add optional workflow-managed Git worktree creation for `default-tools` tasks.
- [x] Persist worktree path, branch, base revision, owner task, and cleanup policy in SQLite/artifacts.
- [x] Create a unique `worktree:<name>` resource lease automatically for each writer.
- [x] Add commands to inspect, preserve, clean, merge, or cherry-pick worktree results after review.
- [x] Refuse automatic merge when the worktree is dirty, diverged unexpectedly, has failed verification, or conflicts with another result.

## 4. Workflow-context and artifact injection

- [x] Include workflow ID, task ID, attempt ID, artifact root, cwd/worktree, declared inputs/outputs, and handoff contract in every worker prompt/manifest.
- [x] Materialize dependency reports/artifact references for child tasks instead of asking workers to search default task-run roots.
- [x] Add bounded artifact-selection rules so downstream prompts receive relevant reports, not unbounded history.
- [x] Preserve provenance: record which parent artifacts and decisions were supplied to each child attempt.

## 5. Retry, timeout, and budget policy

- [x] Add per-task retry count, retry classification, backoff, and retry eligibility.
- [x] Add wall-clock deadline, no-progress timeout, token budget, and cost budget policies at task level.
- [x] Distinguish retriable transport/provider failures from failed acceptance checks and unsafe side effects.
- [x] Record every policy decision as an event, including budget refusal and retry scheduling.
- [x] Ensure retries create new attempts and never overwrite a prior report or event history.

## 6. True Gantt, critical path, and observability UI

- [ ] Render proportional attempt bars instead of only a textual recent-attempt summary.
- [ ] Show task phase, elapsed duration, retries, current tool, resource leases, and cost/token usage where available.
- [ ] Highlight the critical path, current blockers, ready-but-unscheduled tasks, and scheduler deferral reasons.
- [ ] Add selectable task details: prompt, dependencies, artifacts, raw RPC event tail, report tail, and tmux target.
- [ ] Support filtering by task state/resource/agent and a noninteractive export of timeline/event data.

## 7. Human approval gates

- [x] Add first-class `gate` nodes for graph review, write dispatch, merge, migration, deployment, and external side effects.
- [x] Persist approver identity, decision, timestamp, rationale, and the graph/version approved.
- [x] Prevent a gate approval from silently applying after task-spec or dependency changes.
- [x] Show pending gates in CLI and permit explicit reject/revise actions.

## 8. Scheduler safety and recovery

- [x] Add a SQLite scheduler lease/lock so concurrent `tick`/`watch --drive` processes cannot dispatch the same task.
- [x] Use transactional outbox/reconciliation semantics around attempt creation, tmux launch, resource leasing, and manifest updates.
- [x] Detect orphaned tmux/RPC workers after crashes and reconcile to a durable terminal or recoverable state.
- [x] Release leases only after authoritative completion/reconciliation, including cancellation and worker loss.
- [x] Add restart/recovery tests for interrupted manifest/target/outbox recovery boundaries.

## 9. Graph authoring assistance

- [x] Add a `workflow draft` flow that converts a goal and discovery corpus into atomic todos, proposed dependencies, resource tags, and writer ownership.
- [x] Require an explicit reviewed graph before any write-capable task is dispatched.
- [x] Keep inferred edges distinct from user-approved edges and explain each inferred prerequisite.
- [x] Add graph versioning so changes after approval require revalidation and reapproval.

## 10. Test and verification coverage

- [x] Add unit tests for validation, dependency resolution, leasing, retries, cancellation, and recovery.
- [x] Mock tmux and RPC at process boundaries for deterministic scheduler tests.
- [x] Add end-to-end tests with a fake JSONL RPC agent, including streaming, settlement, malformed events, and process loss.
- [x] Add real opt-in Pi/tmux smoke tests with isolated database and artifact roots.
- [x] Define acceptance fixtures for parallel readers, isolated writers, shared-resource serialization, human gates, and integration verification.
