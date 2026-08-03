# Firefox browser-agent integration plan

## Status

**Planning only.** No Firefox integration has been implemented yet.

## Goal

Give Pi agentic, full-control access to a live Firefox session: tabs, navigation, trusted input, screenshots, semantic DOM state, arbitrary page JavaScript, network and console events, downloads, and browser artifacts. Pi should have access to all ordinary tabs in an automation-enabled Firefox profile by default.

The primary interaction loop is:

```text
list/select page → observe DOM + pixels → act/evaluate → wait → re-observe
```

## Decision record

### Use Firefox automation protocols, not a custom WebExtension bridge

A custom WebExtension plus WebSocket/native-messaging bridge can manipulate tabs and inject page scripts, but it would duplicate browser automation infrastructure and still falls short of trusted input. It would also require us to own its protocol, lifetime, screenshots, frame routing, permissions, and state consistency.

Use Mozilla's [`@mozilla/firefox-devtools-mcp`](https://github.com/mozilla/firefox-devtools-mcp) instead. It is a maintained implementation over Selenium WebDriver and WebDriver BiDi with support for:

- live-page and tab management
- semantic DOM snapshots and reusable UIDs
- screenshots
- click, hover, fill, drag, upload, and keyboard input
- page JavaScript evaluation
- network, console, download, dialog, and navigation operations

A WebExtension may be added later only for capabilities unavailable through BiDi, such as browser-specific UI or APIs. It is not the transport foundation.

### Use MCPorter as the persistent transport

[`mcporter`](https://github.com/openclaw/mcporter) runs the stdio MCP server as a keep-alive daemon. This avoids reconnecting on every Pi command and preserves the Firefox session, event buffers, and snapshot state across CLI calls.

Pi will invoke a local CLI rather than receiving the MCP server's large tool schema in every prompt. This aligns with Pi's CLI/skill progressive-disclosure model.

### Keep this repository an integration package

`pi-exts` owns Pi-facing tooling and workflow—not a general browser automation framework and not a vendored Firefox MCP server.

| Owned here | Owned externally |
| --- | --- |
| Pi extension, skill, CLI wrapper, configuration, artifacts, locking, observation normalization | Firefox, WebDriver BiDi, Marionette, Mozilla Firefox DevTools MCP, MCPorter |

If the custom observation layer becomes independently useful as a general browser protocol, extract it later; keep the Pi adapter and skill in this repository.

## Technology choices

| Concern | Decision |
| --- | --- |
| Browser | Local, visible Firefox running the user's actual profile |
| Browser protocol | WebDriver BiDi plus Marionette |
| Firefox adapter | `@mozilla/firefox-devtools-mcp@0.9.15` |
| MCP lifecycle | `mcporter@0.12.4` with `"keep-alive"` lifecycle |
| Runtime | Node.js 24+ and ESM JavaScript |
| Pi control surface | `firefoxctl` CLI and an on-demand Pi skill |
| Pi UI | Thin `rp152kpi:firefox` extension; native multimodal observation later |
| Package management | npm/npx with exact version pins |
| Task runner | `just` |
| Tests | Node/Vitest unit tests plus opt-in real-Firefox integration tests |

Do not use `@latest` in committed configuration. Do not vendor Mozilla's MCP implementation. Do not build a custom browser WebSocket protocol for the initial integration.

## Firefox launch and connection

Firefox must be fully quit, then started with automation enabled:

```bash
/Applications/Firefox.app/Contents/MacOS/firefox \
  --marionette \
  --remote-debugging-port 9222
```

The Mozilla MCP server connects to this existing session with `--connect-existing` and Marionette port `2828`.

```text
Firefox
  ├─ Marionette (default port 2828)
  └─ Remote Agent / WebDriver BiDi
        │
        ▼
Mozilla Firefox DevTools MCP
        │ stdio MCP
        ▼
MCPorter keep-alive daemon
        │ local daemon socket
        ▼
firefoxctl → Pi skill / Pi extension
```

### Operational trade-off

Marionette makes `navigator.webdriver` true and changes automation-related browser fingerprinting. Some bot-protected sites can detect this. This is accepted for the requested full-control, real-profile mode. Firefox cannot be retrofitted with these flags after it has already started normally.

## Proposed repository layout

```text
pi-exts/
├── extensions/
│   ├── rp152kpi:notify/
│   └── rp152kpi:firefox/
│       └── index.ts
├── skills/
│   └── firefox-browser/
│       ├── SKILL.md
│       └── references/
├── integrations/
│   └── firefox/
│       ├── bin/firefoxctl.mjs
│       ├── lib/
│       │   ├── mcporter.mjs
│       │   ├── observe.mjs
│       │   ├── artifacts.mjs
│       │   ├── locks.mjs
│       │   └── refs.mjs
│       ├── config/mcporter.json
│       ├── scripts/launch-firefox-agent
│       └── test/
├── resources.json
├── justfile
└── package.json
```

Do not put Node/npm work inside colon-named extension directories. Tooling such as `npx` can misbehave when its working directory contains `:`.

## Package resources and installation

The package must describe installable integration bundles declaratively:

```json
{
  "notify": {
    "extensions": ["extensions/rp152kpi:notify/index.ts"]
  },
  "firefox": {
    "extensions": ["extensions/rp152kpi:firefox/index.ts"],
    "skills": ["skills/firefox-browser/SKILL.md"]
  }
}
```

The existing installer should be generalized to consume this file. Intended commands:

```bash
just install firefox
just update firefox
just all
just update-all
```

`just install firefox` loads only the Firefox integration's extension and skill.

## MCPorter configuration

The committed config will pin the adapter and keep it warm:

```json
{
  "mcpServers": {
    "firefox": {
      "command": "npx",
      "args": [
        "--yes",
        "@mozilla/firefox-devtools-mcp@0.9.15",
        "--connect-existing",
        "--marionette-port",
        "2828",
        "--tool-preset",
        "developer"
      ],
      "lifecycle": "keep-alive"
    }
  }
}
```

The `developer` preset is required for arbitrary page JavaScript and debugging, in addition to the standard page, snapshot, input, screenshot, network, console, download, and utility modules.

`firefoxctl doctor` must verify:

- Node and MCPorter versions
- Firefox executable and automation ports
- MCPorter daemon status
- Firefox MCP tool availability
- ability to list pages, capture a screenshot, and evaluate a harmless expression

## Public CLI contract

Pi should learn only the wrapper, not raw MCP tool names:

```bash
firefoxctl doctor

firefoxctl tabs list
firefoxctl tabs open <url>
firefoxctl tabs close <tab-id>
firefoxctl navigate <tab-id> <url>

firefoxctl observe <tab-id>
firefoxctl query <tab-id> --role button --name Submit
firefoxctl node <tab-id> <ref>
firefoxctl crop <tab-id> <ref>

firefoxctl click <tab-id> <ref>
firefoxctl fill <tab-id> <ref> <text>
firefoxctl key <tab-id> <key>
firefoxctl scroll <tab-id> ...
firefoxctl drag <tab-id> <source-ref> <target-ref>

firefoxctl eval <tab-id> --file script.js
firefoxctl eval <tab-id> --expr 'document.title'
firefoxctl wait <tab-id> ...

firefoxctl screenshot <tab-id>
firefoxctl network list <tab-id>
firefoxctl network get <request-id>
firefoxctl console list <tab-id>
```

Rules:

- JSON only on stdout; human diagnostics only on stderr.
- Every operation is explicitly tab/page-scoped.
- Prefer `eval --file` over shell-quoted source.
- Large results must be saved as artifacts and returned by path plus metadata.
- The wrapper is the compatibility boundary for MCP tool/API changes.

## Concurrency and reference validity

The underlying MCP server has selected-page and snapshot state that can be global to the persistent process. Multiple Pi sessions must not select or mutate the wrong tab.

`firefoxctl` will use an interprocess lock for transactions:

```text
acquire lock → select requested page → perform action → collect result → release lock
```

Implement a Node lock file with exclusive create, PID/timestamp metadata, timeout, and stale-lock recovery. Do not rely on macOS `flock`.

References need explicit context:

```text
page:<id>/document:<id>/snapshot:<id>/uid:<uid>
```

Mutating operations should optionally require the expected document/snapshot version and reject stale references after a navigation or materially changed document.

## Composite visual/DOM observation

Mozilla's snapshot output is a semantic DOM representation, not a complete browser accessibility tree, and it does not alone encode all visual geometry required for screenshot-directed reasoning.

`firefoxctl observe` is the main custom feature. It combines:

1. semantic snapshot / UIDs
2. page screenshot
3. page-side JavaScript for viewport, scroll, DPR, element geometry, and image metadata
4. pre/post mutation revision checks

It writes a single observation artifact:

```text
~/.cache/rp152kpi/firefox/<pi-session>/<observation-id>/
├── observation.json
├── snapshot.txt
└── viewport.png
```

Example shape:

```json
{
  "schemaVersion": 1,
  "observationId": "...",
  "page": { "id": "...", "url": "...", "title": "..." },
  "document": {
    "id": "...",
    "mutationBefore": 42,
    "mutationAfter": 42,
    "dirty": false
  },
  "viewport": {
    "width": 1440,
    "height": 900,
    "scrollX": 0,
    "scrollY": 320,
    "devicePixelRatio": 2,
    "screenshotWidth": 2880,
    "screenshotHeight": 1800
  },
  "nodes": []
}
```

Each node should carry:

- snapshot UID/ref, document and frame identity
- tag, semantic role, accessible name, text, selected attributes
- visibility, focusability, enabled/editable state
- CSS-pixel and screenshot-pixel rectangles
- clipping/transformation state
- link/form metadata where relevant
- image metadata for `<img>`, `<picture>`, SVG, canvas/video, and CSS background images

For images: include source/current source, alt text, natural and rendered dimensions, and screenshot crop coordinates.

DOM/pixel capture is not atomic. Record a mutation revision before and after capture; retry a bounded number of times on change, otherwise mark the observation `dirty: true`.

## Pi skill and extension

### Skill: `firefox-browser`

The skill provides progressive disclosure and teaches:

- setup and `doctor`
- tab selection
- observe → act → re-observe discipline
- artifact inspection with Pi's image-capable `read` tool
- stale-ref recovery
- query versus full observation
- arbitrary JavaScript via temporary files
- bounded output and network/console inspection

### Extension: `rp152kpi:firefox`

Keep it thin:

- `/firefox-status`
- `/firefox-restart`
- footer connection status
- optional future `firefox_observe` tool that returns both concise semantic text and a native image attachment

The extension must not start long-lived resources during its factory. It may check/warm MCPorter during `session_start`, and must clean up only resources it itself owns during `session_shutdown`.

## Testing

### Unit tests

- CLI parsing and JSON output
- MCP result normalization
- artifact paths, truncation, and cleanup
- geometry conversion and screenshot coordinate mapping
- mutation consistency behavior
- stale-reference validation
- lock acquisition, timeout, and stale recovery

### Browser fixtures

Create local test pages covering:

- forms and editable controls
- nested and cross-origin iframes
- open and closed shadow DOM
- images, picture elements, SVG, canvas, video, CSS backgrounds
- transforms, clipping, fixed/sticky elements, browser zoom
- fast DOM mutation and navigation
- dialogs, downloads, and uploads

### Opt-in integration tests

```bash
just test-firefox
```

They validate the entire chain:

```text
firefoxctl → MCPorter daemon → Mozilla Firefox MCP → BiDi/Marionette → Firefox
```

## Phased implementation

1. Add `resources.json`; refactor `just install/update` around bundles.
2. Add Firefox launcher, MCPorter config, `firefoxctl doctor`, and connection smoke test.
3. Implement page listing, navigation, screenshot capture, and JavaScript evaluation.
4. Add `firefox-browser` skill and `rp152kpi:firefox` connection status.
5. Implement disk-backed composite observations.
6. Add UID actions, waits, console/network/download artifacts, and stale-ref enforcement.
7. Add fixture and real-browser integration suites.

## References

- [Pi packages](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/packages.md)
- [Pi skills](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/skills.md)
- [Pi extensions](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/extensions.md)
- [Mozilla Firefox DevTools MCP](https://github.com/mozilla/firefox-devtools-mcp)
- [Mozilla MCP: connect to existing Firefox](https://github.com/mozilla/firefox-devtools-mcp#connect-to-existing-firefox)
- [MCPorter keep-alive daemon](https://mcporter.sh/daemon.html)
- [MDN: WebDriver BiDi](https://developer.mozilla.org/en-US/docs/Web/WebDriver/Reference/BiDi)
- [MDN: `scripting.executeScript`](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript)
