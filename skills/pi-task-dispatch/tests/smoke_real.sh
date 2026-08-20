#!/bin/sh
# Opt-in integration smoke: never runs in the default test suite.
set -eu
[ "${TASK_DISPATCH_SMOKE:-}" = 1 ] || {
	echo 'set TASK_DISPATCH_SMOKE=1 to run'
	exit 0
}
command -v pi >/dev/null
command -v tmux >/dev/null
command -v uv >/dev/null
base=$(mktemp -d "${TMPDIR:-/tmp}/task-dispatch-smoke.XXXXXX")
trap 'rm -rf "$base"' EXIT
session="task-dispatch-smoke-$$"
tmux new-session -d -s "$session"
trap 'tmux kill-session -t "$session" 2>/dev/null || true; rm -rf "$base"' EXIT
script=$(CDPATH= cd -- "$(dirname -- "$0")/../scripts" && pwd)/task-dispatch
"$script" --database "$base/workflow.db" --root "$base/runs" dispatch \
	--id smoke --tmux-session "$session" --cwd "$base" --read-only \
	--task 'Reply with a compact handoff; do not modify files.'
echo "smoke worker launched; inspect the printed run directory before cleanup"
