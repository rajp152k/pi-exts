# Campaign usage guides

These are operating guides, not API references. They explain when to use `orchorch` versus `orchestrate`, how to keep campaigns evidence-led, and how to avoid creating a second scheduler or a process-heavy substitute for judgment.

- [Orchorch](orchorch.md): design, simulate, and operate multi-workflow campaigns.
- [Orchestrate](orchestrate.md): run one bounded child workflow safely.

Use the smallest layer that can safely solve the problem:

```text
one bounded workflow → /orchestrate
multiple workflows with phase gates/integration → /skill:orchorch
simple inspection or implementation → do not orchestrate
```
