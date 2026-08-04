# rp152kpi:firefox

Thin Pi UI integration for the live Firefox browser-agent stack.

It contributes:

- `/firefox-on` to start MCPorter and connect to Firefox on demand
- `/firefox-off` to stop MCPorter without closing Firefox
- `/firefox-status` to inspect status without starting MCPorter
- `/firefox-restart` to restart MCPorter's persistent Firefox transport
- a footer indicator that begins as `Firefox: off`

It performs no Firefox or MCPorter work during Pi startup.

Install the complete bundle from the repository root:

```bash
just install firefox
```

Start automation-enabled Firefox before opening Pi:

```bash
just firefox-launch
```
