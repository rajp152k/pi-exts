# pi-exts

Personal Pi extensions, organized under the `rp152kpi:<name>` namespace.

## Extensions

- [`rp152kpi:notify`](extensions/rp152kpi:notify): sends a Ghostty notification through tmux when Pi is ready for the next prompt.

## Install

Install one extension by its non-namespaced name:

```bash
just install notify
```

Install every extension:

```bash
just all
```

Both commands install the GitHub package with `pi install git:github.com/rajp152k/pi-exts`. The single-extension command then configures Pi to load only that extension.
