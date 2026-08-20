# Coherence refactor: findings and execution plan

**Status:** Phase 0 and the first scheduler-recovery proof are implemented, verified, and merged to `main`.

## Evidence-based direction

Keep `pi-exts` as a small set of Pi-facing capabilities, not a terminal-product framework. Preserve the existing boundary:

```text
Pi extension (optional UI/lifecycle adapter)
→ skill (selection and operating procedure)
→ CLI/local runtime (durable protocol/state)
→ external system
```

One authority per concern:

| Concern | Authority | Views/derivatives |
| --- | --- | --- |
| Product behavior | Git + targeted tests | plans, worker reports |
| Workflow execution | SQLite events/attempts | tmux board/panes, notifications |
| Worker evidence | versioned attempt artifacts | board/card rendering |
| Install bundles | `resources.json` | package globs, docs |
| Capability metadata | **new Phase-0 manifest** | README/docs/validation table |
| Attention | authoritative artifact/board link | status/widget/notification |

## Discovery findings

### Capability and documentation

- `package.json` exposes all resource paths; `resources.json` defines named install bundles; `scripts/configure-package.py` implements selection. The audit found no bundle-path mismatch.
- The repository advertises four extensions and seven skills, but lacks a canonical capability manifest, maturity/support vocabulary, compatibility table, docs truth table, root validation command, and CI entry point.
- `docs/README.md` does not link the `orchestrate` and `science` skill contracts; `docs/integrations.md` likewise omits them. Root `README.md` does advertise both.
- Extension-local TypeScript configs exist, but no root typecheck recipe exists. `tsc` was unavailable in the scout environment.

### TUI and attention

- `notify` uses `agent_settled` and opens a dismissible tmux popup (`extensions/rp152kpi:notify/index.ts`). It is an attention view, never workflow authority.
- Task-dispatch’s board is a separate Textual view; SQLite/artifacts remain authoritative (`docs/task-dispatch.md`).
- The paused Anvil sketch proposes quieter, opt-in status/cards and explicitly avoids focus-stealing or routine notifications (`docs/drafts/anvil-tui-strategy.md`). It is not approved implementation scope.
- The current popup behavior, Anvil’s proposed calm-attention model, and no shared attention/status-key contract are in tension. Decide the intended notification posture before modifying a TUI extension.

### Task-dispatch runtime

Treat these as proof obligations, not confirmed defects:

1. Cancellation must have one defined terminal meaning across task state, manifest, attempt, events, and lease release.
2. No-progress timeouts need a precise qualifying-progress definition.
3. Orphaned attempts need an explicit capacity/lease policy.
4. Writers must not automatically retry without explicit idempotency and human-approved policy.
5. Attempts/artifacts should pin the workflow revision/hash that authorized them.
6. Managed-worktree and `eph-*` tmux-session lifecycles need reproducible retention/cleanup semantics.
7. Artifact, event, export, and board observations need a bounded provenance/schema contract.

The deterministic task-dispatch suite ran **39 tests: 38 passed, 1 failed**: `test_missing_manifest_and_target_is_durably_failed_and_releases_lease_once` expected one `window_exists` call and observed two. Reproduce and decide intended pending-outbox semantics before treating this as a runtime defect.

## Recommended dependency graph

```text
human semantic decisions
        ↓
Phase 0: capability/authority contract ───────────┐
Phase 1: runtime invariant reproductions/tests ───┤
        ↓                                         ↓
Phase 2: validation + compatibility discipline ←──┘
        ↓
Phase 3: optional read-only work-state / attention adapter
        ↓
Phase 4: demand-proven additions (including any filesystem tool)
```

## Execution plan

### Gate A — human decisions (before writers)

1. Is task-dispatch a supported local runtime, or explicitly experimental?
2. What do cancellation, orphan capacity, revision changes, and writer retries mean?
3. Is attention opt-in/contextual and quiet, or should the current ready popup remain?
4. Confirm `pi-exts` is not funding a general terminal navigator yet; name a repeated unsolved filesystem job first.

### Phase 0 — legibility, isolated documentation/data change

#### Deliverables

- A machine-readable capability manifest covering the eleven advertised capabilities.
- Maturity/support and compatibility vocabulary.
- Generated or maintained documentation truth table.
- Offline manifest ↔ `resources.json` ↔ `package.json` consistency checker.
- Per-capability validation recipes and a root validation command.

**Acceptance:** each advertised capability has one owner layer, install source, prerequisites, maturity claim, authority, side-effect class, boundedness rule, and validation command.

**Writer isolation:** one managed worktree; own the manifest, checker, root validation entry point, and generated/derived documentation together. Do not combine with runtime state-machine changes.

### Phase 1 — runtime proof before migration

Create one deterministic reproduction/test per invariant, then make only the smallest behavior/documentation change justified by that test. Order: cancellation → heartbeat → orphan/capacity → writer retry → revision pinning → worktree/ephemeral-session lifecycle → artifact/export schema.

**Acceptance:** each resolved claim has a test, explicit chosen semantics, durable event/attempt evidence, and an updated operational contract.

### Phase 2 — operational discipline

Add CI only after the existing Python failure is triaged. Separate offline tests from opt-in live Firefox/real-worker smoke checks; declare supported Python, Node, Pi, tmux, and platform assumptions.

### Phase 3 — composition, not a new control plane

Only after Phases 0–2, consider a read-only `/work-state` and a shared, opt-in rate-limited attention adapter. It must label freshness/source, link to authority, never scrape browser DOM/pane content by default, and never claim completion.

### Phase 4 — demand-proven additions

Do not build a filesystem navigator from this plan. If repeated evidence warrants it, prototype the narrow independent flow `inspect → bounded render → reviewed mutation plan → explicit apply`; keep it non-recursive by default, symlink-safe, and non-authoritative.

## Discovery workflow record

A read-only workflow, `coherence-refactor-discovery`, ran in tmux session `pi-exts` with three independent tasks: `tui-overview`, `runtime-invariant-audit`, and `capability-contract-inventory`. Its specification validated with no findings; all three attempts completed. Artifacts are under `/tmp/coherence-refactor-discovery-runs/` and the isolated SQLite database is `/tmp/coherence-refactor-discovery.db`.

The initial `workflow watch` attempts returned targets `pi-exts:@284` and `pi-exts:@287` but exited because the active Homebrew Python lacked Textual and its Expat linkage was broken. This was repaired without modifying the repository: Homebrew `expat` was installed and Textual was installed in `/tmp/pi-exts-task-dispatch-venv`. The board is now live in `pi-exts:@293` (`tmux select-window -t 'pi-exts:@293'`) and shows all three tasks as `DONE`. A final `workflow tick` recorded the workflow as completed.

## Source evidence

- `plans/coherence-refactor.md`
- `docs/drafts/anvil-tui-strategy.md`
- `docs/task-dispatch.md`
- `skills/orchestrate/SKILL.md`
- `skills/pi-task-dispatch/SKILL.md`
- `skills/pi-task-dispatch/scripts/task-dispatch.py`
- `skills/pi-task-dispatch/tests/test_{scheduler_recovery,scheduler_safety,workflow_policy,workflow_revisions_gates,managed_worktrees,workflow_context,observability}.py`
- `extensions/rp152kpi:notify/index.ts`
- `package.json`, `resources.json`, `scripts/configure-package.py`, `justfile`

## Next action

Continue Phase 1 with cancellation semantics first: desired versus observed workflow state, durable cancellation intent/acknowledgment events, and crash-boundary recovery tests. Then address heartbeat, orphan capacity, writer retry, revision pinning, worktree/session lifecycle, and artifact/export schema.
