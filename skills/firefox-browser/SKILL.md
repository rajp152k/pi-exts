---
name: firefox-browser
description: Operate an automation-enabled live Firefox session through firefoxctl. Use for observing open Firefox tabs, screenshots, semantic DOM snapshots, trusted browser actions, JavaScript evaluation, network, console, downloads, and navigation.
compatibility: Requires Firefox started with integrations/firefox/scripts/launch-firefox-agent, mcporter, Node 24+, and the Firefox integration installed.
---

# Firefox browser agent

Define `firefoxctl` from the installed package before using this skill. Override `PI_EXTS_ROOT` when developing from another checkout:

```bash
PI_EXTS_ROOT="${PI_EXTS_ROOT:-$HOME/.pi/agent/git/github.com/rajp152k/pi-exts}"
firefoxctl() { node "$PI_EXTS_ROOT/integrations/firefox/bin/firefoxctl.mjs" "$@"; }

firefoxctl doctor
firefoxctl tabs list
```

## Core workflow

1. List tabs and select the explicit tab index to operate on.
2. Observe before acting:

   ```bash
   node integrations/firefox/bin/firefoxctl.mjs observe 0
   ```

3. Read `snapshot.txt` for semantic state and use Pi's `read` tool on `viewport.png` for visual state.
4. Use snapshot UIDs with `click` and `fill`.
5. Re-observe after navigation or mutations. Do not reuse stale UIDs.

## Commands

```bash
firefoxctl tabs list
firefoxctl navigate <index> <url>
firefoxctl observe <index>
firefoxctl click <index> <uid>
firefoxctl fill <index> <uid> <text>
firefoxctl eval <index> --file script.js
firefoxctl screenshot <index> --save /tmp/page.png
firefoxctl network <index>
firefoxctl console <index>
```

Use `firefoxctl raw <tool> key=value` only when the documented wrapper command does not expose a Mozilla Firefox MCP capability.

## JavaScript

Prefer a file over shell-quoted code:

```bash
cat > /tmp/page-query.js <<'EOF'
() => ({ title: document.title, url: location.href })
EOF
firefoxctl eval 0 --file /tmp/page-query.js
```

The evaluated source must be a JavaScript function expression. Keep results bounded; write large values to files from page code or query them incrementally.

## Artifacts

`observe` writes a directory under `~/.cache/rp152kpi/firefox/`. Its `observation.json` identifies the screenshot and snapshot artifact paths. Do not paste large artifact contents into messages; inspect the exact files needed.

## Recovery

- `firefoxctl doctor` reports missing Firefox, MCPorter, or connection failures.
- `firefoxctl daemon restart` restarts MCPorter's persistent server transport.
- If Firefox is not automation-enabled, fully quit it and start it with `just firefox-launch`.
- If a UID fails, take a new snapshot or observation and select a current UID.
