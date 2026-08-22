import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import {
	gitSummary,
	renderWorkState,
	sourceResult,
	traceList,
	tmuxTopology,
	unavailableSource,
} from "./work-state.mjs";

const WORKFLOW_QUERY = String.raw`
import json, sqlite3, sys
path = sys.argv[1]
uri = f"file:{path}?mode=ro&immutable=1"
try:
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    workflows = [dict(row) for row in db.execute("SELECT id, state, updated_at FROM workflows ORDER BY updated_at DESC LIMIT 20")]
    attempts = [dict(row) for row in db.execute("SELECT workflow_id, task_id, id, state, started_at FROM attempts WHERE state IN ('in_progress', 'orphaned') ORDER BY started_at DESC LIMIT 20")]
    print(json.dumps({"workflows": workflows, "activeAttempts": attempts}))
except Exception as error:
    print(json.dumps({"error": str(error)}))
    sys.exit(2)
`;

const TMUX_FORMAT =
	"#{session_name}\t#{window_index}.#{pane_index}\t#{pane_id}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}";
const extensionDirectory = dirname(fileURLToPath(import.meta.url));

function failureText(result: {
	stderr: string;
	stdout: string;
	code: number;
}): string {
	return result.stderr.trim() || result.stdout.trim() || `exit ${result.code}`;
}

async function gitSource(pi: ExtensionAPI, cwd: string, signal?: AbortSignal) {
	try {
		const result = await pi.exec(
			"git",
			["status", "--porcelain=v1", "--branch"],
			{ cwd, signal, timeout: 3_000 },
		);
		if (result.code !== 0)
			return unavailableSource({
				id: "git",
				authority: "Git repository metadata",
				boundedness: "branch plus at most 100 changed paths",
				reason: failureText(result),
			});
		return sourceResult({
			id: "git",
			authority: "Git repository metadata",
			boundedness: "branch plus at most 100 changed paths",
			available: true,
			detail: gitSummary(result.stdout),
		});
	} catch (error) {
		return unavailableSource({
			id: "git",
			authority: "Git repository metadata",
			boundedness: "branch plus at most 100 changed paths",
			reason: error instanceof Error ? error.message : "git unavailable",
		});
	}
}

async function workflowSource(
	pi: ExtensionAPI,
	database: string,
	signal?: AbortSignal,
) {
	try {
		await access(database, constants.R_OK);
		const result = await pi.exec("python3", ["-c", WORKFLOW_QUERY, database], {
			signal,
			timeout: 3_000,
		});
		if (result.code !== 0)
			return unavailableSource({
				id: "workflow SQLite",
				authority: "workflow SQLite records",
				boundedness:
					"20 workflows and 20 active attempts; read-only immutable query",
				reason: failureText(result),
			});
		const detail = JSON.parse(result.stdout) as Record<string, unknown>;
		return sourceResult({
			id: "workflow SQLite",
			authority: "workflow SQLite records",
			boundedness:
				"20 workflows and 20 active attempts; read-only immutable query",
			available: true,
			detail,
		});
	} catch (error) {
		return unavailableSource({
			id: "workflow SQLite",
			authority: "workflow SQLite records",
			boundedness:
				"20 workflows and 20 active attempts; read-only immutable query",
			reason:
				error instanceof Error ? error.message : "workflow database unavailable",
		});
	}
}

async function tmuxSource(pi: ExtensionAPI, signal?: AbortSignal) {
	try {
		const result = await pi.exec(
			"tmux",
			["list-panes", "-a", "-F", TMUX_FORMAT],
			{ signal, timeout: 3_000 },
		);
		if (result.code !== 0)
			return unavailableSource({
				id: "tmux",
				authority: "tmux topology metadata, not workflow completion",
				boundedness: "at most 100 panes; no pane scrollback",
				reason: failureText(result),
			});
		return sourceResult({
			id: "tmux",
			authority: "tmux topology metadata, not workflow completion",
			boundedness: "at most 100 panes; no pane scrollback",
			available: true,
			detail: tmuxTopology(result.stdout),
		});
	} catch (error) {
		return unavailableSource({
			id: "tmux",
			authority: "tmux topology metadata, not workflow completion",
			boundedness: "at most 100 panes; no pane scrollback",
			reason: error instanceof Error ? error.message : "tmux unavailable",
		});
	}
}

async function tracesSource(pi: ExtensionAPI, signal?: AbortSignal) {
	try {
		const result = await pi.exec("traces", ["list", "--limit", "10"], {
			signal,
			timeout: 5_000,
		});
		if (result.code !== 0)
			return unavailableSource({
				id: "traces",
				authority: "local traces CLI index",
				boundedness: "10 recent local trace-list entries; no trace bodies",
				reason: failureText(result),
			});
		return sourceResult({
			id: "traces",
			authority: "local traces CLI index",
			boundedness: "10 recent local trace-list entries; no trace bodies",
			available: true,
			detail: traceList(result.stdout),
		});
	} catch (error) {
		return unavailableSource({
			id: "traces",
			authority: "local traces CLI index",
			boundedness: "10 recent local trace-list entries; no trace bodies",
			reason: error instanceof Error ? error.message : "traces CLI unavailable",
		});
	}
}

async function firefoxSource(pi: ExtensionAPI, signal?: AbortSignal) {
	try {
		const result = await pi.exec(
			"node",
			[
				join(extensionDirectory, "../../integrations/firefox/bin/firefoxctl.mjs"),
				"daemon",
				"status",
			],
			{ signal, timeout: 3_000 },
		);
		if (result.code !== 0)
			return unavailableSource({
				id: "Firefox",
				authority: "firefoxctl daemon status metadata",
				boundedness: "explicit opt-in status only; no browser DOM or tab content",
				reason: failureText(result),
			});
		return sourceResult({
			id: "Firefox",
			authority: "firefoxctl daemon status metadata",
			boundedness: "explicit opt-in status only; no browser DOM or tab content",
			available: true,
			detail: { status: result.stdout.trim() || "reported available" },
		});
	} catch (error) {
		return unavailableSource({
			id: "Firefox",
			authority: "firefoxctl daemon status metadata",
			boundedness: "explicit opt-in status only; no browser DOM or tab content",
			reason: error instanceof Error ? error.message : "Firefox unavailable",
		});
	}
}

export default function workStateExtension(pi: ExtensionAPI) {
	pi.registerTool({
		name: "work_state",
		label: "Work State",
		description:
			"Read-only snapshot of Git state, workflow SQLite records, tmux topology, and locally indexed recent traces. Firefox status metadata is included only when explicitly requested. Every source is freshness-, authority-, and boundedness-labeled.",
		promptSnippet:
			"Summarize bounded, read-only local work state when explicitly requested",
		promptGuidelines: [
			"Use work_state only when the user explicitly asks for current local work state, workflow context, or attention guidance. Treat tmux as topology only; never infer workflow completion from it.",
		],
		parameters: Type.Object({
			includeFirefox: Type.Optional(
				Type.Boolean({
					description:
						"Explicitly include Firefox daemon status metadata only; never captures browser DOM.",
				}),
			),
			workflowDatabase: Type.Optional(
				Type.String({
					description:
						"Read-only workflow SQLite database path (default ~/.pi/agent/workflows.db).",
				}),
			),
		}),
		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			const database =
				params.workflowDatabase ?? join(homedir(), ".pi", "agent", "workflows.db");
			const sources = await Promise.all([
				gitSource(pi, ctx.cwd, signal),
				workflowSource(pi, database, signal),
				tmuxSource(pi, signal),
				tracesSource(pi, signal),
				...(params.includeFirefox ? [firefoxSource(pi, signal)] : []),
			]);
			return {
				content: [{ type: "text", text: renderWorkState(sources) }],
				details: {
					sources,
					unavailableSources: sources
						.filter((source) => !source.available)
						.map((source) => source.source),
					firefoxRequested: params.includeFirefox ?? false,
				},
			};
		},
	});
}
