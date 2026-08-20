# rp152kpi:notify

Shows a top-right tmux popup when Pi has fully settled and is ready for the next prompt. The popup stays open until you press any key.

The popup identifies the current tmux session, window index, and window name as `session:index.window-name`.

## Requirements

- tmux 3.2 or later (`display-popup` support)
- Pi running in TUI mode from a tmux pane (`TMUX` and `TMUX_PANE`)

## Install

From the repository root:

```bash
just install notify
```

This installs the package with Pi and selects `rp152kpi:notify`. Named bundle selections are additive; an existing full-package installation remains unfiltered. Restart Pi after installation.

## Test

Run this from Pi to send a notification immediately. Outside TUI mode it does nothing; in TUI mode outside tmux it shows a requirement warning. Automatic notifications are silently skipped outside TUI mode or when `TMUX`/`TMUX_PANE` is unavailable. Failed automatic popups do not interrupt a completed run:

```text
/notify-test
```
