# Firefox integration

This directory adapts Mozilla's Firefox DevTools MCP server into Pi-friendly commands. It does not contain a browser server or Firefox add-on.

## Prerequisites

```bash
npm install --global mcporter@0.12.4
```

Fully quit Firefox, then start it with automation enabled:

```bash
just firefox-launch
```

This uses the normal Firefox profile and makes `navigator.webdriver` true while that Firefox process is running.

## Verify

```bash
just firefox-doctor
just firefox-tabs
```

`firefoxctl doctor` requires Firefox to have been launched with both Marionette and remote debugging enabled. It intentionally fails against an ordinary already-running Firefox.

## CLI

```bash
node integrations/firefox/bin/firefoxctl.mjs --help
```

The wrapper uses the pinned `@mozilla/firefox-devtools-mcp@0.9.15` process through MCPorter. It scopes browser actions to an explicit tab index and serializes multi-call operations with a local lock.
