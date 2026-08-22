# Using Orchorch well

Use `/skill:orchorch` when an outcome needs several independently durable workflows, explicit phase boundaries, integration evidence, or a final campaign consolidation. It is not a reason to wrap ordinary work in a campaign.

## Start with design, not dispatch

A campaign design answers:

- What outcome, non-goals, and acceptance evidence matter?
- Which phases are genuinely ordered?
- Which child workflows can stand alone?
- Where must a human or delegated authority decide?
- What writer integration evidence is required before another phase can advance?

Run `campaign simulate` first. Treat its output as a dry run: review hashes, child specs, gates, integration declarations, and required approvals. Revise the plan rather than improvising dependencies after work has started.

## Use a scout phase for uncertainty

For a new or risky campaign, the first phase should be read-only discovery. Scouts should reduce a decision that changes scope, ownership, architecture, or safety; they should not merely produce more commentary.

A useful scout returns:

```text
observed facts
assumptions and unknowns
smallest viable implementation slice
acceptance checks
risks and required decisions
```

Do not start a writer phase because a scout settled. Observe the child SQLite authority, inspect its artifact, and record the appropriate campaign gate decision.

## Keep authority federated

The campaign ledger coordinates intent; it does not replace other authorities:

| Concern | Authority |
| --- | --- |
| Child task/attempt state | Child workflow SQLite |
| Worker evidence | Child artifact root |
| Integrated behavior | Git commit plus verification |
| Phase gates/integration record | Campaign ledger |

A stale, missing, unreadable, or revision/hash-mismatched child observation is a blocker. Tmux panes and boards are useful views, never proof of completion.

## Treat integration as a phase boundary

For a writer child, use this order:

```text
worker terminal → observe child → propose integration
→ approval → apply/review Git change → verify
→ record integration → open dependent phase
```

The record must identify the base and resulting commits, verification evidence, owner, integrator, authority, and timestamp. Never record an integration just because a patch exists or tests ran in an isolated worktree.

User approval is the default. This repository permits explicitly recorded, bounded delegation of `integrate` approval to the primary assistant. A delegation must remain scoped, expiring, and revocable; it does not authorize dispatch, recording, or writer retry unless those actions are separately delegated.

## Use phases sparingly

Create a phase only when it has a different outcome boundary, authority gate, integration checkpoint, or independent child workflow. Avoid phases that merely rename implementation steps.

Good:

```text
scout → implementation → verified integration → pilot measurement
```

Poor:

```text
read file → edit file → run test → commit
```

The latter is one normal implementation task.

## Keep pilots reversible

Wisdom, attention, and adaptive routing are measured pilots. Record source-linked observations and compare them to a baseline. Promote a pilot only if it reduces a measured problem; remove or defer it if it creates overhead without improving verified outcomes.

## Consolidate deliberately

End a campaign with a consolidation record, not just a completion label. Include outcome, phase evidence, incidents, unresolved decisions, opportunities, measured cost/rework/blocked time, and one recommended next action. Harvested wisdom is proposed knowledge only; workers do not promote policy.
