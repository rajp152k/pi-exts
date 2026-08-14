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
- Successful CLI stdout is head-truncated at Pi's standard 2,000-line/50KB limit; a short notice is appended when material is omitted.
- The extension only injects guidance; it does not upload or modify traces.
