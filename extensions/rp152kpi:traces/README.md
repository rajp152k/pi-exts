# rp152kpi:traces

Exposes the local `traces` CLI to Pi as `traces_search` and `traces_show`. It adds guidance for trace links and recognized local/recent-trace requests before an answer is produced.

## Requirements

- The `traces` CLI must be available on `PATH` and configured for any traces to inspect.

## Install

```bash
just install traces
```

Restart Pi after installation.

## Behavior

- `traces_search` lists recent local traces or searches locally indexed trace events.
- `traces_show` accepts a traces.com URL or bare trace ID and returns the first 60 matching events (each capped at 6,000 characters), fetching remotely when the trace is not available locally.
- Both tools can include tool calls and results when requested.
- Successful CLI stdout is head-truncated at Pi's standard 2,000-line/50KB limit; a short notice is appended when material is omitted.
- The extension registers read-only search/show tools and injects guidance; it does not upload or modify traces.
