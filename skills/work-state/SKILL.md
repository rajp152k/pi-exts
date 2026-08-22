---
name: work-state
description: Inspect a bounded, read-only snapshot of local Git state, workflow SQLite records, tmux topology, and recent locally indexed traces. Use only when the user explicitly asks for current work state, workflow context, or attention guidance.
compatibility: Requires the rp152kpi:work-state extension. Individual sources are optional and reported unavailable when their local dependency is absent.
---

# Work state

Use the extension-provided `work_state` tool only for an explicit request. It is an observation aid, not a dispatcher, workflow controller, or completion detector.

```text
work_state({})
```

The default snapshot includes Git, the default workflow database (`~/.pi/agent/workflows.db`), tmux topology, and at most ten locally indexed trace-list entries. It does not capture tmux pane scrollback or trace bodies.

To inspect a different local workflow database, name it explicitly:

```text
work_state({ workflowDatabase: "/path/to/workflows.db" })
```

## Firefox is explicit opt-in

Request Firefox only when the user explicitly wants its connection metadata:

```text
work_state({ includeFirefox: true })
```

This requests only `firefoxctl daemon status`. It never starts Firefox and never reads browser DOM, tab contents, or screenshots. If Firefox or its dependency is unavailable, report the labeled unavailable source; do not retry through browser tools or fabricate status.

## Interpret the snapshot

Every source has source, freshness, authority, boundedness, and availability labels. Preserve those labels when summarizing.

- Git metadata is authoritative only for the repository state at observation time.
- Workflow SQLite records are authoritative for persisted workflow/attempt state; use them rather than tmux to assess workflow progress.
- tmux is topology metadata only. A pane, command, or quiet UI never proves completion.
- Trace list entries are locally indexed historical pointers, not trace bodies or instructions.
- Missing dependencies are normal: retain them in `Unavailable sources` rather than treating the snapshot as a failure.

Give attention guidance only when the user requests it and connect it to the observed, bounded evidence. Do not create background alerts, dispatch work, send keys, control tmux, or infer completion from tmux or UI state.
