# Using Orchestrate well

Use `/orchestrate` for one bounded workflow: a small DAG of independent scouts, an isolated writer, or a defined implementation/review job. Use it when durable attempts, tmux observation, artifacts, and dependency-aware execution improve safety or speed.

Do not use it for a one-file edit, a question answerable by direct inspection, coupled writers in one checkout, or work that requires a live back-and-forth conversation.

## Before creating a workflow

State the outcome, acceptance checks, cwd, originating tmux session, execution session, writer isolation model, resources, handoff, monitoring cadence, and deadline. Discover the originating session from `$TMUX_PANE`; never select a convenient attached session.

Split tasks by independent evidence or output boundaries. A task needs a concrete objective, deliverable, completion evidence, handoff, access scope, and blocked condition. Prefer parallel read-only scouts before a writer; use only one writer when paths overlap.

## Writers

Use managed worktrees whenever possible. Declare every writable path. Keep the source checkout clean and avoid concurrent changes in it while a managed writer runs. A worker patch is evidence, not an instruction to merge.

For a writer, the primary agent must:

```text
inspect terminal workflow state
review declared changed paths and diff
apply/review in an integration checkout
run acceptance checks
commit/push only after verification
```

## Monitoring is part of execution

Immediately after `workflow start`:

1. open `workflow watch` in the session-affine tmux session;
2. record the board target;
3. begin bounded authoritative `status --refresh` monitoring in the same turn;
4. do not send a normal response while any task is nonterminal.

Only a declared timeout or blocker justifies an interim response. At terminal state, inspect the workflow/task/attempt/events/artifacts before reporting. Pane silence, a worker exit code, or a board card is not sufficient evidence.

## Escalate cleanly

When a child result changes scope, authority, or safety, stop and ask a focused decision. Do not auto-retry a substantive failure. Infrastructure retries must be declared and bounded; writer retries additionally require idempotency and approval for the exact failed attempt/revision.

If one workflow grows into several independently gated workflows, stop using `/orchestrate` as the parent mechanism and design an Orchorch campaign instead.
