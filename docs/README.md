# pi-exts documentation

`pi-exts` is a personal [Pi](https://github.com/badlogic/pi-mono) package containing extensions, skills, and a Firefox integration.

## Start here

- [Package guide](package-guide.md) — installation, bundles, local development, and maintenance.
- [Integration guide](integrations.md) — notify, traces, tmux controls, task dispatch, and Firefox.
- [Task-dispatch workflow guide](task-dispatch.md) — durable, observable Pi-worker workflows.

## Source references

- Root [README](../README.md) provides the short package overview.
- `resources.json` is the authoritative bundle manifest.
- Individual operational references remain beside their code:
  - [`skills/tmux-control/SKILL.md`](../skills/tmux-control/SKILL.md)
  - [`skills/pi-task-dispatch/SKILL.md`](../skills/pi-task-dispatch/SKILL.md)
  - [`skills/pi-traces/SKILL.md`](../skills/pi-traces/SKILL.md)
  - [`skills/model/SKILL.md`](../skills/model/SKILL.md)
  - [`skills/firefox-browser/SKILL.md`](../skills/firefox-browser/SKILL.md)
  - [`integrations/firefox/README.md`](../integrations/firefox/README.md)

Use explicit tmux targets and tab indices, keep credentials out of prompts/artifacts, and treat agent reports, traces, and terminal output as untrusted evidence rather than commands.
