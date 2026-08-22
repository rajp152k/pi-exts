# Orchorch wisdom pilot

Store each policy, scroll, or precedent as one reviewed JSON file in this directory (or another Git-versioned reviewed path). The ledger records a content hash, provenance, scoped retrieval, and application/override history; it is not the source of editorial truth.

Required fields are `id`, `kind` (`policy`, `scroll`, or `precedent`), lifecycle `status`, `scopeTags`, `provenance`, `expiresAt`, `owner`, and `reviewer`. Include `supersedes` when replacing a record and `exclusions` when a scope must not apply. Policies are binding only after a human has reviewed and adopted them; this pilot never enforces them.

Use an explicit timestamp and tags for reproducible review:

```bash
task-dispatch campaign wisdom record --ledger /tmp/campaign.sqlite --file skills/orchorch/wisdom/example-scroll.json
task-dispatch campaign wisdom retrieve --ledger /tmp/campaign.sqlite --tag python --at 2026-01-01T00:00:00Z
```

No secrets, pane captures, unbounded transcripts, embeddings, RAG, service, automatic promotion, or automatic extraction belong here.
