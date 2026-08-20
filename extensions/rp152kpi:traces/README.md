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

- `traces_search` lists recent local traces or searches locally indexed trace events. A query is case-insensitive regex text; `limit` defaults to 20, permits at most 50 results, and searches at most 100 events per trace.
- `traces_show` accepts a traces.com URL or bare trace ID, requests remote access for every show, and returns events 1–60 (each capped at 6,000 characters). By default it selects only user messages and agent text.
- `includeTools: true` adds tool calls and results to `traces_show` and query-mode `traces_search`; it has no effect when `traces_search` lists recent traces.
- Successful CLI stdout is head-truncated at Pi's standard 2,000-line/50KB limit; a short notice is appended when material is omitted.
- The extension registers read-only search/show tools and injects guidance; it does not upload or modify traces.
