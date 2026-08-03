# rp152kpi:notify

Shows a short-lived tmux popup in the top-right corner when Pi has fully settled and is ready for the next prompt.

The popup identifies the current tmux session and window as `session:index.window`.

## Requirements

- tmux 3.2 or later (`display-popup` support)

## Install

From a clone of [`rajp152k/pi-exts`](https://github.com/rajp152k/pi-exts):

```bash
just install notify
```

This installs the package globally with Pi and configures it to load only `rp152kpi:notify`. Restart Pi after installation.

## Test

Run this from Pi to send a notification immediately:

```text
/notify-test
```
