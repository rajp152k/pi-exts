# rp152kpi:notify

Sends a Ghostty desktop notification when Pi has fully settled and is ready for the next prompt.

The notification subtitle identifies the current tmux session and window as `session:index.window`.

## Requirements

- Ghostty
- tmux with passthrough enabled:

  ```tmux
  set -g allow-passthrough on
  ```

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
