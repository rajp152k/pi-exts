# rp152kpi:work-state

Provides the read-only `work_state` Pi tool for an explicitly requested local work-state snapshot.

## Sources and limits

Each result labels its source, freshness, authority, boundedness, and availability.

- **Git:** branch plus no more than 100 porcelain status paths.
- **Workflow SQLite:** the 20 most recently updated workflows and 20 active attempts from a read-only immutable SQLite query. Its default path is `~/.pi/agent/workflows.db`; callers may name another local database.
- **tmux:** no more than 100 pane topology records (session, window/pane ID, active flag, current command, and working path). It never reads pane scrollback and is not evidence of workflow completion.
- **Traces:** no more than 10 entries from the local `traces list` index, with no trace bodies.
- **Firefox:** excluded unless `includeFirefox: true`; then it runs only `firefoxctl daemon status`, without starting Firefox or collecting browser DOM, tabs, screenshots, or content.

An unavailable executable, database, or integration is reported as an unavailable source rather than causing the whole snapshot to fail.

## Use

```text
work_state({})
work_state({ workflowDatabase: "/path/to/workflows.db" })
work_state({ includeFirefox: true })
```

The extension never dispatches or controls workflows, sends tmux input, or infers completion from tmux/UI state. Attention guidance is opt-in: the tool is offered only for explicit work-state or workflow-context requests and emits no background alerts.

## Offline checks

Fixture-only parser/provenance tests require no live Pi, tmux, traces, Firefox, or workflow database:

```bash
node --test test/work-state.test.mjs
./node_modules/.bin/tsc -p tsconfig.json
```
