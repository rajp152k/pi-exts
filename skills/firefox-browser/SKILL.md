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

3. Read `snapshot.txt` for semantic state, `geometry.json` for UID-to-rectangle/image mappings, and use Pi's `read` tool on `viewport.png` for visual state.
4. Check `observation.json`: capture retries once when it detects mutations. Do not act from an observation whose `document.dirty` remains true.
5. Use snapshot UIDs with `click` and `fill`, always passing the matching `observation.json`. The wrapper rejects a changed document or a stale target before it acts.
6. Re-observe after navigation or mutations. Do not reuse stale UIDs.

## Commands

```bash
firefoxctl tabs list
firefoxctl navigate <index> <url>
firefoxctl observe <index>
firefoxctl click <index> <uid> --observation <observation.json>
firefoxctl hover <index> <uid> --observation <observation.json>
firefoxctl fill <index> <uid> <text> --observation <observation.json>
firefoxctl select <index> <uid> <value> --observation <observation.json>
firefoxctl drag <index> <source-uid> <target-uid> --observation <observation.json>
firefoxctl upload <index> <uid> <file> --observation <observation.json>
firefoxctl scroll <index> <x> <y>
firefoxctl key <index> Enter
firefoxctl wait <index> selector '#ready' --timeout 10000
firefoxctl wait <index> text 'Finished'
firefoxctl wait <index> url '/account'
firefoxctl wait <index> ready
firefoxctl viewport <index> <width> <height>
firefoxctl history <index> back
firefoxctl downloads allow
firefoxctl downloads list
firefoxctl dialog accept
firefoxctl eval <index> --file script.js
firefoxctl screenshot <index> --save /tmp/page.png
firefoxctl network <index>
firefoxctl console <index>
```

`scroll`, `viewport`, and history navigation deliberately change page state: observe again before using UID actions. `key` dispatches synthetic DOM keyboard events to the focused page element; Firefox DevTools MCP 0.9.15 does not expose trusted native keyboard injection or cross-origin iframe targeting. Use `eval` or `raw` only when the documented wrapper does not expose a Mozilla capability.

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

`observe` writes a directory under `~/.firefox-devtools-mcp/rp152kpi/`, which is the Mozilla MCP server's allowed artifact location. Its `observation.json` identifies the screenshot, snapshot, and geometry artifact paths. Do not paste large artifact contents into messages; inspect the exact files needed.

## Recovery

- `firefoxctl doctor` reports missing Firefox, MCPorter, or connection failures.
- `firefoxctl daemon restart` restarts MCPorter's persistent server transport.
- If Firefox is not automation-enabled, fully quit it and start it with `just firefox-launch`.
- If an action reports a dirty or stale observation, take a new observation and select a current UID. `--force` is an explicit escape hatch and bypasses the safety check.
