# pi-exts usage guide

This is a practical guide for choosing the right level of coordination.

## Choose the smallest useful tool

| Need | Use |
| --- | --- |
| Inspect, edit, test, or answer one bounded question | Work directly with Pi and normal tools. |
| Inspect/control tmux safely | `tmux-control`. |
| Read repository/workflow/tmux/trace state without control | `/work-state`. |
| Run one bounded worker DAG with durable attempts/artifacts | `/orchestrate`. |
| Design or coordinate several independently gated workflows | `/skill:orchorch`. |
| Explore an isolated question without affecting the main conversation | `/tangent`, then `/catchup`. |

Do not orchestrate ordinary edits. Coordination has overhead; use it when evidence, isolation, approval, or recovery materially improves the outcome.

## One workflow: `/orchestrate`

Use for a small implementation/review/research workflow.

Before starting, require:

```text
outcome + acceptance checks
origin tmux session
bounded task contracts
writer isolation and write paths
monitoring cadence and deadline
```

For writers, use a managed worktree. Review and integrate the patch manually after the worker is terminal; a worker report, pane, or passing isolated test is not a merge decision.

After start, the board is mandatory. Pi should monitor until terminal, inspect SQLite/artifacts, run integration checks, then report.

## Several workflows: `/skill:orchorch`

Use a campaign when work has real phase boundaries:

```text
scout → implementation → integration → measurement/consolidation
```

Start with `campaign simulate`. It validates phase order, child workflow specs/hashes, gates, writer integration checkpoints, and required approvals without launching anything.

Campaign rules:

- Child workflow SQLite and artifacts remain authoritative.
- Git plus verification is authoritative for integrated behavior.
- The campaign ledger records phase intent, gates, observations, integration evidence, and consolidation.
- Missing/stale/mismatched child evidence blocks advancement.
- A writer phase does not advance on worker settlement alone.

Writer lifecycle:

```text
worker terminal → observe → propose integration → approve
→ apply/review → verify → record integration → next phase eligible
```

You are the default authority. This repository allows explicit, scoped, expiring delegation of campaign integration approval to the primary assistant. Dispatch, recording, and writer retries still require separate delegation.

## Attention and decisions

Treat only these as attention-worthy:

- decision needed;
- approval needed;
- integration ready;
- blocked/failed state;
- incident with a recovery action.

Routine worker completion and tool output should stay in the board/artifacts, not interrupt you.

## Practical habits

- Prefer a scout before a risky or unclear writer phase.
- Keep one integration owner for overlapping code paths.
- Name the authoritative evidence for every decision.
- Use bounded reports; raw logs remain in artifacts.
- Do not silently retry writers or silently substitute models.
- End campaigns with consolidation: outcome, evidence, incidents, opportunities, and one next action.

For detailed agent operating guidance, see `skills/orchorch/usage/`.
