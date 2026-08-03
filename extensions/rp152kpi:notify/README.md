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

Register this directory in `~/.pi/agent/settings.json`:

```json
{
  "extensions": [
    "/absolute/path/to/pi-exts/extensions/rp152kpi:notify"
  ]
}
```

Restart Pi after changing global settings.
