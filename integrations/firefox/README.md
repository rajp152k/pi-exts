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
just test-firefox
```

`firefoxctl doctor` requires Firefox to have been launched with both Marionette and remote debugging enabled. It intentionally fails against an ordinary already-running Firefox.

## CLI

```bash
node integrations/firefox/bin/firefoxctl.mjs --help
```

The wrapper uses the pinned `@mozilla/firefox-devtools-mcp@0.9.15` process through MCPorter. Commands that operate on a page require an explicit tab index; daemon, raw-tool, download, and dialog commands are global. It serializes multi-call page operations with a local lock.

`just test-firefox` opens disposable local fixture pages, verifies observation geometry, guarded fill/select/click actions, synthetic keys, waits, stale-action rejection, dirty-observation retry, and closes its test tabs.
