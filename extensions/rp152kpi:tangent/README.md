# rp152kpi:tangent

Adds `/tangent <query>`, which starts an interactive Pi tangent with an isolated context window.

## Behavior

- Seeds the tangent with the supplied query, then the most recent and penultimate visible assistant text responses from the active branch, each in explicit handoff tags.
- Starts the tangent in a new tmux window in the current session and working directory.
- Inherits the current Pi model and thinking level.
- When Pi is not running inside tmux, starts a detached `tangent-…` tmux session and prints the command needed to attach to it.
- Does not send a model request or add context to the originating Pi session.

The seed is written to a mode-`0600` temporary file. The tangent process removes it when it exits; a launch failure removes it immediately.

## Requirements

- `tmux` on `PATH` (3.2+ for `new-window -e`)
- `pi` on `PATH`
- A configured current Pi model; its credentials must also be available to a newly launched Pi process

## Install

From a clone of [`rajp152k/pi-exts`](https://github.com/rajp152k/pi-exts):

```bash
just install tangent
```

Restart Pi after installation.

## Usage

```text
/tangent Investigate why the last proposed approach may fail.
```

When invoked outside tmux, attach to the reported detached session:

```bash
tmux attach-session -t tangent-…
```
