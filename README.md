# pi-exts

Personal Pi extensions, organized under the `rp152kpi:<name>` namespace.

## Plans

- [Firefox browser-agent integration](plans/firefox-browser-agent.md)

## Extensions

- [`rp152kpi:notify`](extensions/rp152kpi:notify): shows a top-right tmux popup when Pi is ready for the next prompt.
- [`rp152kpi:firefox`](extensions/rp152kpi:firefox): provides status and lifecycle controls for the live Firefox browser-agent integration.
- [`tmux-control`](skills/tmux-control): directs Pi to safely inspect and control local tmux sessions through the tmux CLI.

## Install

Install one extension by its non-namespaced name:

```bash
just install notify
```

Install the Firefox extension and skill:

```bash
just install firefox
```

Install the tmux-control skill:

```bash
just install tmux
```

Install every extension:

```bash
just all
```

## Firefox setup

The Firefox integration requires an automation-enabled Firefox process and MCPorter:

```bash
npm install --global mcporter@0.12.4
just firefox-launch
just firefox-doctor
```

See [the integration README](integrations/firefox/README.md) and the [implementation plan](plans/firefox-browser-agent.md) for operating details and limitations.

Both commands install the GitHub package with `pi install git:github.com/rajp152k/pi-exts`. A named install enables that integration's resources while preserving resources enabled by earlier named installs.

Update one installed extension:

```bash
just update notify
```

Update every installed extension:

```bash
just update-all
```
