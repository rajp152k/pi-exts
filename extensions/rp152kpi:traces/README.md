# rp152kpi:traces

Exposes the local `traces` CLI to Pi as `traces_search` and `traces_show`. It also routes trace links and requests for local/recent traces toward those tools before an answer is produced.

## Requirements

- The `traces` CLI must be available on `PATH` and authenticated/configured for the traces to inspect.

## Install

```bash
just install traces
```

Restart Pi after installation.

## Behavior

- `traces_search` lists recent local traces or searches locally indexed trace events.
- `traces_show` accepts a traces.com URL or bare trace ID and loads a bounded remote trace view.
- Both tools return at most Pi's standard tool-output limit (2,000 lines or 50KB).
- The extension only injects guidance; it does not upload or modify traces.
