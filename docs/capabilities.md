# Capability truth table

This generated table is checked by `just check`. `capabilities.json` is the capability metadata authority; `resources.json` remains authoritative for install bundles.

| ID | State | Maturity | Owner | Bundle | Prerequisites | Offline validation | Live / opt-in validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| notify | implemented | personal | Pi extension | notify | tmux | `just check` | `manual Pi TUI session` |
| firefox | implemented | personal | Pi extension + CLI + skill | firefox | Node 24+; MCPorter; automation-enabled Firefox | `just check` | `just test-firefox` |
| tmux-control | implemented | personal | skill | tmux | tmux | `just check` | `manual tmux session` |
| task-dispatch | implemented | supported-local | skill + local Python runtime | tmux | uv; tmux; Pi | `just check` | `TASK_DISPATCH_SMOKE=1 skills/pi-task-dispatch/tests/smoke_real.sh` |
| orchestrate | implemented | personal | skill | tmux | task-dispatch prerequisites | `just check` | `manual reviewed workflow` |
| modelling | implemented | personal | skill | modelling | Pi | `just check` | `manual Pi session` |
| science | implemented | personal | skill | science | Pi | `just check` | `manual Pi session` |
| traces | implemented | personal | Pi extension + skill | traces | traces CLI | `just check` | `manual trace query` |
| tangent | implemented | experimental | Pi extension | tangent | tmux; Pi | `just check` | `manual tangent session` |

State is the user-facing truth claim. Maturity describes support posture: `personal` is maintained for this collection, `supported-local` has a local compatibility commitment, and `experimental` may change without compatibility guarantees.
