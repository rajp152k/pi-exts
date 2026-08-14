# pi-exts

Personal Pi extensions, organized under the `rp152kpi:<name>` namespace.

## Plans

- [Firefox browser-agent integration](plans/firefox-browser-agent.md)

## Documentation

- [Documentation index](docs/README.md)
- [Package installation and maintenance](docs/package-guide.md)
- [Integrations and skills](docs/integrations.md)
- [Task-dispatch workflows](docs/task-dispatch.md)

## Extensions

- [`rp152kpi:notify`](extensions/rp152kpi:notify): shows a top-right tmux popup when Pi is ready for the next prompt.
- [`rp152kpi:firefox`](extensions/rp152kpi:firefox): provides status and lifecycle controls for the live Firefox browser-agent integration.
- [`tmux-control`](skills/tmux-control): directs Pi to safely inspect and control local tmux sessions through the tmux CLI.
- [`pi-task-dispatch`](skills/pi-task-dispatch): dispatches and monitors tmux-backed Pi workers, with SQLite-persisted dependency workflows, event observability, and a live board/Gantt watch.
- [`orchestrate`](skills/orchestrate): turns a goal and discovery todo corpus into a reviewed, safely parallel task-dispatch graph and observable execution.
- [`modelling`](skills/modelling): turns a context into a bounded, decision-relevant model specification with explicit uncertainty and validation.
- [`rp152kpi:traces`](extensions/rp152kpi:traces): searches local trace indexes and loads bounded trace views through the `traces` CLI.

## Install

Install one extension by its non-namespaced name:

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

Install the traces extension and skill:

```bash
just install traces
```

Install every extension and skill:

```bash
just all
```

`just install <bundle>` and `just all` install `git:github.com/rajp152k/pi-exts`. Named bundle selections are additive; a full-package installation remains unfiltered.

## Firefox setup

The Firefox integration requires an automation-enabled Firefox process and MCPorter:

```bash
npm install --global mcporter@0.12.4
just firefox-launch
just firefox-doctor
```

See [the integration README](integrations/firefox/README.md) and [Firefox skill](skills/firefox-browser/SKILL.md) for operating details and limitations. The [implementation plan](plans/firefox-browser-agent.md) is historical.

Update one installed extension:

```bash
just update notify
```

Update every installed extension:

```bash
just update-all
```
