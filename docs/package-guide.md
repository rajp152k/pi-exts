# Package installation and maintenance

## Layout

The root `package.json` exposes all `extensions/*/index.ts` files and `skills/*/SKILL.md` files as a Pi package. `resources.json` defines named bundles:

| Bundle | Resources |
| --- | --- |
| `notify` | `rp152kpi:notify` extension |
| `firefox` | `rp152kpi:firefox` extension and `firefox-browser` skill |
| `tmux` | `tmux-control`, `pi-task-dispatch`, and `orchestrate` skills |
| `modelling` | `modelling` skill |
| `science` | `science` skill |
| `traces` | `rp152kpi:traces` extension and `pi-traces` skill |
| `tangent` | `rp152kpi:tangent` extension |

Named installs are additive: the configuration script preserves already selected resources for the same package source.

## Install from Git

From the repository root:

```bash
just install notify
just install firefox
just install tmux
just install modelling
just install science
just install traces
just install tangent
just all
```

`just install NAME` runs `pi install git:github.com/rajp152k/pi-exts`, then configures the selected bundle in `~/.pi/agent/settings.json`. `just all` enables the complete package. Restart Pi after changing loaded resources.

## Local development

Use a local package source while iterating so Pi reads this checkout directly:

```bash
pi install /absolute/path/to/pi-exts
python3 scripts/configure-package.py /absolute/path/to/pi-exts tmux
```

The configuration script expects an existing valid `~/.pi/agent/settings.json`; `pi install` creates/updates the package entry first. For a full local install, omit the bundle argument from `configure-package.py`.

## Update

```bash
just update notify
just update-all
```

The named update refreshes the Git package then reapplies its resource filter. The all update enables all resources.

## How configuration works

For a named bundle, `scripts/configure-package.py` writes a filtered package object with exact `+path` filters. It merges filters from earlier named installs, removes old entries for the same source, and writes settings atomically. An all install stores the source without filters.

## Validation

```bash
just --list
python3 scripts/configure-package.py --help
pi list
```

Firefox-specific checks require the Firefox prerequisites described in [the integration guide](integrations.md#firefox):

```bash
just firefox-doctor
just firefox-tabs
just test-firefox
```
