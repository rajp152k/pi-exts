# rp152kpi:notify

Shows a top-right tmux popup when Pi has fully settled and is ready for the next prompt. The popup stays open until you press any key.

The popup identifies the current tmux session and window as `session:index.window`.

## Requirements

- tmux 3.2 or later (`display-popup` support)
- Pi running in TUI mode from a tmux pane (`TMUX` and `TMUX_PANE`)

## Install

From a clone of [`rajp152k/pi-exts`](https://github.com/rajp152k/pi-exts):

```bash
just install notify
```

This installs the package with Pi and selects `rp152kpi:notify`. Named bundle selections are additive; an existing full-package installation remains unfiltered. Restart Pi after installation.

## Test

Run this from Pi to send a notification immediately. Outside TUI mode or a tmux pane, it does nothing; failed automatic popups do not interrupt a completed run:

```text
/notify-test
```
