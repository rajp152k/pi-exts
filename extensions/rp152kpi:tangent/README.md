# rp152kpi:tangent

Adds `/tangent <query>` for an isolated Pi tangent and `/catchup` to bring its latest recorded findings back.

## Behavior

- Seeds the tangent with the supplied query, then the most recent and penultimate visible assistant text responses from the active branch, each in explicit handoff tags.
- Starts the tangent in a new tmux window in the current session and working directory.
- Inherits the current Pi model and thinking level.
- When Pi is not running inside tmux, starts a detached `tangent-…` tmux session and prints the command needed to attach to it.
- Does not send a model request or add context to the originating Pi session.
- Persists each tmux Pi pane's latest finalized assistant response locally, so `/catchup 2 ; update docs` sends that response to the current session. Targets may name a window (`session.window`) or a specific pane (`session.window.pane`, for example `pi-exts.0.1`). `/catchup <window>` requires the receiving Pi to run inside tmux; otherwise use an explicit session target. If no validated persisted response exists, `/catchup` stops with a warning rather than silently sending scrollback. Use `/catchup <target> --capture` to explicitly send the last 2,000 captured pane lines; Pi labels that source as a bounded tmux capture.

The seed is written to a mode-`0600` temporary file. The tangent process removes it when it exits; a launch failure removes it immediately.

## Requirements

- `tmux` on `PATH` (3.2+ for `new-window -e`)
- `pi` on `PATH`
- A configured current Pi model; its credentials must also be available to a newly launched Pi process

## Install

From the repository root:

```bash
just install tangent
```

Restart Pi after installation.

## Usage

```text
/tangent Investigate why the last proposed approach may fail.
/catchup 2 ; summarize the findings
/catchup tangent-session.2 --capture ; inspect the bounded pane capture
/catchup pi-exts.0.1 ; catch up from one explicit pane
```

When invoked outside tmux, attach to the reported detached session:

```bash
tmux attach-session -t tangent-…
```
