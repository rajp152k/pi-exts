# rp152kpi:firefox

Thin Pi UI integration for the live Firefox browser-agent stack.

It contributes:

- `/firefox-status` to refresh connection status
- `/firefox-restart` to restart MCPorter's persistent Firefox transport
- a footer indicator showing whether `firefoxctl doctor` can reach Firefox

Install the complete bundle from the repository root:

```bash
just install firefox
```

Start automation-enabled Firefox before opening Pi:

```bash
just firefox-launch
```
