# rp152kpi:firefox

Thin Pi UI integration for the live Firefox browser-agent stack.

It contributes:

- `/firefox-on` to check and connect to Firefox on demand
- `/firefox-off` to stop MCPorter without closing Firefox
- `/firefox-status` to inspect status without starting MCPorter
- `/firefox-restart` to restart MCPorter's persistent Firefox transport
- a Pi status indicator that begins as `Firefox: off`

It performs no Firefox or MCPorter work during Pi startup.

Install the complete bundle from the repository root. It requires Node 24+ and MCPorter (`npm install --global mcporter@0.12.4`):

```bash
just install firefox
```

Start automation-enabled Firefox before using `/firefox-on`. The launcher defaults to `/Applications/Firefox.app/Contents/MacOS/firefox`; set `FIREFOX_BIN` for another Firefox executable:

```bash
just firefox-launch
# Or: FIREFOX_BIN=/path/to/firefox just firefox-launch
```
