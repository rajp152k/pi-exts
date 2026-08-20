# pi-exts

Personal Pi extensions, organized under the `rp152kpi:<name>` namespace.

## Plans

- [Coherence refactor deliberation](plans/coherence-refactor.md)

## Documentation

- [Documentation index](docs/README.md)
- [Package installation and maintenance](docs/package-guide.md)
- [Integrations and skills](docs/integrations.md)
- [Task-dispatch workflows](docs/task-dispatch.md)
- [Capability truth table](docs/capabilities.md)

## Capabilities

- [`rp152kpi:notify`](extensions/rp152kpi:notify): shows a dismissible top-right tmux popup with the current tmux location when Pi settles in TUI mode.
- [`rp152kpi:firefox`](extensions/rp152kpi:firefox): starts off and provides on, off, status, and restart controls for its Firefox MCP connection.
- [`tmux-control`](skills/tmux-control): directs Pi to safely inspect and control local tmux sessions through the tmux CLI.
- [`pi-task-dispatch`](skills/pi-task-dispatch): dispatches and monitors tmux-backed Pi workers, with SQLite-persisted dependency workflows, event observability, and a live board/Gantt watch.
- [`orchestrate`](skills/orchestrate): turns a goal and discovery todo corpus into a reviewed, safely parallel task-dispatch graph and observable execution.
- [`modelling`](skills/modelling): turns a context into a bounded, decision-relevant model specification with explicit uncertainty and validation.
- [`science`](skills/science): applies scientific-method thinking to critically question claims, learning, and software.
- [`rp152kpi:traces`](extensions/rp152kpi:traces): lists or searches local traces and loads trace IDs or traces.com links through the `traces` CLI.
- [`rp152kpi:tangent`](extensions/rp152kpi:tangent): opens an isolated Pi tangent in tmux and can catch up from its latest recorded response.

## Install

Install one named bundle:

```bash
just install notify
```

Install the Firefox extension and skill:

```bash
just install firefox
```

Install the tmux skills (`tmux-control`, `pi-task-dispatch`, and `orchestrate`):

```bash
just install tmux
```

Install the modelling skill:

```bash
just install modelling
```

Install the science skill:

```bash
just install science
```

Install the traces extension and skill:

```bash
just install traces
```

Install the tangent extension:

```bash
just install tangent
```

Install every extension and skill:

```bash
just all
```

`just install <bundle>` and `just all` install `git:github.com/rajp152k/pi-exts`. Named bundle selections are additive; a full-package installation remains unfiltered. Restart Pi after installing or changing loaded resources.

## Firefox setup

The Firefox integration requires Node 24+, MCPorter, and an automation-enabled Firefox process. The launcher defaults to `/Applications/Firefox.app/Contents/MacOS/firefox`; set `FIREFOX_BIN` for another Firefox executable:

```bash
npm install --global mcporter@0.12.4
just firefox-launch
just firefox-doctor
```

See [the integration README](integrations/firefox/README.md) and [Firefox skill](skills/firefox-browser/SKILL.md) for operating details and limitations.

Update one installed extension:

```bash
just update notify
```

Update every installed extension:

```bash
just update-all
```
