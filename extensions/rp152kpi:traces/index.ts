import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
	DEFAULT_MAX_BYTES,
	DEFAULT_MAX_LINES,
	formatSize,
	truncateHead,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const TRACE_URL = /https?:\/\/(?:www\.)?traces\.com\/[^\s<>"')\]]+/gi;
const TRACE_ID =
	/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;

function traceId(reference: string): string {
	const decoded = decodeURIComponent(reference);
	const uuid = decoded.match(TRACE_ID)?.[0];
	if (uuid) return uuid;

	try {
		const url = new URL(reference);
		for (const key of ["traceId", "trace_id", "id"]) {
			const value = url.searchParams.get(key);
			if (value) return value;
		}
		const segments = url.pathname.split("/").filter(Boolean);
		const lastSegment = segments.at(-1);
		if (lastSegment) return lastSegment;
	} catch {
		// A bare trace ID is also accepted.
	}

	const bare = reference.trim();
	if (/^[A-Za-z0-9_-]+$/.test(bare)) return bare;
	throw new Error(`Could not extract a trace ID from: ${reference}`);
}

function truncatedOutput(
	output: string,
	label: string,
): { text: string; truncated: boolean } {
	const truncation = truncateHead(output, {
		maxLines: DEFAULT_MAX_LINES,
		maxBytes: DEFAULT_MAX_BYTES,
	});
	let text = truncation.content;
	if (truncation.truncated) {
		text += `\n\n[${label} truncated: showing ${truncation.outputLines}/${truncation.totalLines} lines (${formatSize(truncation.outputBytes)}/${formatSize(truncation.totalBytes)}).]`;
	}
	return { text, truncated: truncation.truncated };
}

function registerTraceShowTool(pi: ExtensionAPI) {
	pi.registerTool({
		name: "traces_show",
		label: "Traces",
		description: `Load a particular agent trace through the traces CLI. Accepts a traces.com link or bare trace ID. Returns user and agent messages by default, bounded to 60 events and truncated to ${DEFAULT_MAX_LINES} lines or ${formatSize(DEFAULT_MAX_BYTES)}.`,
		promptSnippet: "Load a traces.com trace link or trace ID using the traces CLI",
		promptGuidelines: [
			"Use traces_show whenever the user pastes a traces.com link or supplies a trace ID. Do not use fetch_content or web tools for trace links.",
			"When the user asks about a local, recent, previous, or current trace without supplying a link or ID, use traces_search first, then traces_show on the matching trace ID when its full conversation is needed.",
		],
		parameters: Type.Object({
			reference: Type.String({
				description: "A traces.com URL or bare trace ID",
			}),
			includeTools: Type.Optional(
				Type.Boolean({
					description:
						"Include tool calls/results when implementation evidence is needed",
				}),
			),
		}),
		async execute(_toolCallId, params, signal) {
			const id = traceId(params.reference);
			const eventTypes = params.includeTools
				? "user_message,agent_text,tool_call,tool_result"
				: "user_message,agent_text";
			const result = await pi.exec(
				"traces",
				[
					"show",
					id,
					"--remote",
					"--markdown",
					"--event-type",
					eventTypes,
					"--offset",
					"1",
					"--limit",
					"60",
					"--max-event-chars",
					"6000",
				],
				{ signal, timeout: 30_000 },
			);

			if (result.code !== 0) {
				throw new Error(
					result.stderr.trim() ||
						result.stdout.trim() ||
						`traces show failed (${result.code})`,
				);
			}

			const output = truncatedOutput(result.stdout, "Trace output");
			return {
				content: [{ type: "text", text: output.text }],
				details: {
					traceId: id,
					reference: params.reference,
					eventTypes,
					truncated: output.truncated,
				},
			};
		},
	});
}

function registerTraceSearchTool(pi: ExtensionAPI) {
	pi.registerTool({
		name: "traces_search",
		label: "Search Traces",
		description: `Search locally indexed agent traces through the traces CLI. Omit query to list recent local traces. Returns bounded output truncated to ${DEFAULT_MAX_LINES} lines or ${formatSize(DEFAULT_MAX_BYTES)}.`,
		promptSnippet:
			"Search local agent traces by text, or list recent traces when no query is available",
		promptGuidelines: [
			"Use traces_search when the user refers to a local, recent, previous, or current trace/session without providing a trace link or ID. Use the returned trace ID with traces_show when the full conversation is needed.",
		],
		parameters: Type.Object({
			query: Type.Optional(
				Type.String({
					description:
						"Text or case-insensitive regex to search for. Omit to list recent traces.",
				}),
			),
			includeTools: Type.Optional(
				Type.Boolean({
					description:
						"Include tool calls/results in searched event text",
				}),
			),
			limit: Type.Optional(
				Type.Integer({
					minimum: 1,
					maximum: 50,
					description: "Maximum matches or recent traces (default 20)",
				}),
			),
		}),
		async execute(_toolCallId, params, signal) {
			const limit = String(params.limit ?? 20);
			const query = params.query?.trim();
			const eventTypes = params.includeTools
				? "user_message,agent_text,tool_call,tool_result"
				: "user_message,agent_text";
			const args = query
				? [
						"search",
						query,
						"--source",
						"event",
						"--event-type",
						eventTypes,
						"--result-level",
						"event",
						"--limit",
						limit,
						"--scan-events-per-trace",
						"100",
					]
				: ["list", "--limit", limit];
			const result = await pi.exec("traces", args, {
				signal,
				timeout: 30_000,
			});

			if (result.code !== 0) {
				throw new Error(
					result.stderr.trim() ||
						result.stdout.trim() ||
						`traces ${query ? "search" : "list"} failed (${result.code})`,
				);
			}

			const output = truncatedOutput(
				result.stdout,
				query ? "Trace search output" : "Trace list output",
			);
			return {
				content: [{ type: "text", text: output.text }],
				details: {
					mode: query ? "search" : "list",
					query,
					includeTools: params.includeTools ?? false,
					limit: Number(limit),
					truncated: output.truncated,
				},
			};
		},
	});
}

export default function piTraces(pi: ExtensionAPI) {
	registerTraceShowTool(pi);
	registerTraceSearchTool(pi);

	pi.on("input", (event) => {
		if (event.source === "extension") return { action: "continue" };
		const links = event.text.match(TRACE_URL);
		if (links?.length) {
			return {
				action: "transform",
				text: `${event.text}\n\n[pi-traces: Inspect ${links.join(", ")} with traces_show before answering.]`,
			};
		}

		const asksForLocalTrace =
			/\b(?:trace|traces)\b/i.test(event.text) &&
			/\b(?:search|find|inspect|open|read|look|investigate|evaluate|local|recent|previous|current|this|last)\b/i.test(
				event.text,
			);
		if (!asksForLocalTrace) return { action: "continue" };

		return {
			action: "transform",
			text: `${event.text}\n\n[pi-traces: No trace link was supplied. Search locally indexed traces with traces_search before answering; use traces_show on the matching trace ID if details are needed.]`,
		};
	});
}
