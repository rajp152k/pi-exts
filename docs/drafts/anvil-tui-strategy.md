# Draft: Anvil strategy vector and terminal-native operating experience

**Status:** Paused exploration. This is a product/design sketch, not an implementation commitment.

## Intent

Create an ignored local planning surface that helps a human and Pi maintain near-term direction without turning into a task database, a second workflow engine, or an autonomous controller.

- `anvil/TODO.md`: unstructured candidate-work/debt inbox.
- `anvil/anvil.md`: concise, agent-maintained strategy vector for the current worktree/task.

Anvil is advisory. Direct user instructions, explicit workflow approvals, and checked-in project policy always take precedence.

## The strategy-vector idea

The vector is a rolling tactical control loop:

```text
current position → next evidence-producing move → conditional follow-on → decision gate
```

The “next 2.5 moves” heuristic deliberately avoids two failure modes:

- **One-move myopia:** acting without knowing what evidence would determine the next choice.
- **Long-horizon fiction:** treating a speculative multi-step plan as settled fact.

### Proposed fields

```md
# Anvil
schema: 1
revision: <n>
updated: <ISO-8601>
basis: head:<sha> todo:<digest>

## Current position
<one outcome-oriented sentence; facts, uncertainty, constraint>

## Next 2.5 moves
1. <smallest viable next action; completion/evidence criterion>
2. <likely follow-on only if move 1 produces expected evidence>
2.5. If <observable condition>, then <branch, stop, or ask>

## Invariants
- <safety/scope/ownership/evidence boundary>

## Evidence needed
- [ ] <authoritative observation, test, or inspection>

## Viable next move
<one currently executable, bounded action; preconditions; confidence>
```

A “gate” needs a condition, authoritative evidence, threshold/interpretation, alternative action, and decision owner. Confidence never substitutes for provenance.

### What it is not

| Artifact | Question answered |
| --- | --- |
| TODO | What candidate work exists? |
| Plan | How might the objective unfold over phases? |
| Workflow DAG | Who does what, with what dependencies/resources/gates? |
| Anvil vector | Given current evidence, what should happen now and what changes that choice? |

## Terminal-native product direction

Keep the CLI and tmux as the control plane. Do not build a browser cockpit for this phase.

### Roles

- **Pi home:** human judgment, conversation, and consolidation.
- **Task-dispatch board:** durable schedule, blockers, gates, and workflow attention.
- **Worker panes:** bounded diagnostic transport only; never completion evidence.
- **SQLite/artifacts/session history:** recovery material and source of truth, not scrollback.

### Suggested tmux convention

One tmux session per repository/context:

1. `home` — primary Pi conversation.
2. `workflow-<id>` — one active workflow board.
3. `rpc-<id>` — task-dispatch worker transport.
4. `scratch` — optional human shell/editor/tests.

Default worker concurrency should be two, exceptionally three. Worker panes can exhaust available terminal space; durable reports must outlive any pane cleanup.

## Attention model

The interface should be calm and explicit about when the human is needed:

- **Working:** passive footer signal.
- **Ready:** quiet return to home; no routine popup.
- **Needs decision:** coalesced notification.
- **Blocked/failed:** coalesced notification with a recovery-oriented next action.

Never notify for each tool result, worker completion, or settled turn. The workflow board is the attention queue; Pi is the place where the human decides.

The existing generic “ready for input” popup could eventually become contextual and rate-limited. It must not consume the next intended keypress.

## Pi TUI interaction system

Prefer existing Pi primitives and retain default chrome:

- `setStatus`: terse keyed footer state such as `workflow: 1 gate` or `anvil: move ready`.
- `setWidget(..., aboveEditor)`: one small, temporary card only when it answers “what should I do now?”
- `notify`: concise warning/error feedback, not routine progress.
- Slash commands before custom shortcuts.
- Overlay only on explicit inspection; never persistent or focus-stealing.
- Compact successful tool results; make current/failed tools prominent and preserve normal expansion.

Avoid a custom global footer/header/editor, a pane wall, mouse-first control, status animation clutter, or a second workflow source of truth.

## Anvil TUI interaction model

Anvil should appear as a quiet **candidate proposal**, not a demand:

```text
ANVIL · candidate · current branch
Now  Known position and active uncertainty.
1    Viable next move; done when <observable criterion>.
2    Likely follow-on if 1 succeeds.
2½   If <condition>, then <response>.
→ Inspect /anvil
```

### Appearance rules

Show only when Pi is settled/idle, material evidence changed, one concrete move exists, and the same proposal was not deferred or dismissed. Do not show it while streaming, during tools, after every turn, during real clarification, or when the next move is generic/speculative/unsafe.

Use `agent_settled` for any eventual surfacing; use `turn_end` only to accumulate evidence. `agent_end` is too early because retries, compaction recovery, and queued follow-ups can still occur.

### Controls

- `/anvil`: inspect evidence, assumptions, freshness, stop condition, and up to three alternatives.
- `/anvil accept`: copy Move 1 into the regular editor; do **not** auto-submit.
- `/anvil revise`: edit a proposal explicitly.
- `/anvil defer` / `/anvil dismiss`: suppress the proposal fingerprint without nagging.
- `/anvil refresh`: explicitly recompute/reconcile.

An accepted or user-edited move is never silently replaced. New user input, tool outcomes, branch/session changes, compaction, and model changes make an old proposal review-needed.

## Native implementation path

1. **Convention/skill pilot:** ignored files and an explicit review ritual.
2. **Manual TUI prototype:** opt-in status + passive card + read-only `/anvil` + accept-to-editor.
3. **Validated suggest mode:** freshness checks, revision-checked updates, explicit proposal lifecycle.
4. **Only if proven useful:** guarded boundary surfacing and richer inspection.

Do not automate dispatch, execution, commits, merges, external actions, or Anvil writes from task-dispatch workers. Workers return evidence; the primary session consolidates it.

## Safeguards

- Treat TODO content as untrusted and potentially sensitive.
- Bind vector freshness to worktree/branch/HEAD, TODO digest, revision, and provenance.
- Mark stale or conflicting state; never overwrite blindly.
- Keep Anvil disabled or read-only in RPC/print/JSON worker contexts.
- Use durable task-dispatch state and artifacts for workflow truth.
- Do not recover workflow facts from terminal scrollback.
- Add `anvil/` to local ignore policy before creating local state in a repository.

## Product questions to revisit

1. Is a vector scoped to a user task, a worktree, or both with a coordinator-level vector?
2. What is the explicit semantic-task boundary protocol?
3. What evidence/provenance is mandatory before surfacing a viable move?
4. Should Anvil persist only in files, or also retain branch-local UI audit entries?
5. After a real-use pilot, is reliable surfacing/freshness actually the bottleneck worth extension complexity?

## First prototype when resumed

Build a project-local, opt-in extension that does only:

1. One keyed footer status for activity/attention.
2. One temporary above-editor next-human-action card.
3. Read-only/manual `/anvil` inspection and `/anvil accept` that pastes editable text.

Evaluate it over 5–7 real tasks. Measure re-orientation time after interruption, ignored/deferred cards, accepted/revised moves, stale proposals, and unwanted alerts.
