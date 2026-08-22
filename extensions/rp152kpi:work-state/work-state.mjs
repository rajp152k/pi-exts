export const OBSERVED_AT = "observed now";

export function sourceResult({
	id,
	authority,
	boundedness,
	available,
	detail,
	freshness = OBSERVED_AT,
}) {
	return {
		id,
		source: id,
		freshness,
		authority,
		boundedness,
		available,
		detail,
	};
}

export function unavailableSource({ id, authority, boundedness, reason }) {
	return sourceResult({
		id,
		authority,
		boundedness,
		available: false,
		detail: { unavailable: reason },
	});
}

export function gitSummary(stdout) {
	const lines = stdout.split(/\r?\n/).filter(Boolean);
	const branch =
		lines.find((line) => line.startsWith("## "))?.slice(3) ?? "unknown";
	const changes = lines.filter((line) => !line.startsWith("## "));
	return { branch, changes: changes.slice(0, 100), changeCount: changes.length };
}

export function tmuxTopology(stdout) {
	const panes = stdout
		.split(/\r?\n/)
		.filter(Boolean)
		.map((line) => {
			const [session, window, pane, active, command, path] = line.split("\t");
			return { session, window, pane, active: active === "1", command, path };
		});
	return { panes: panes.slice(0, 100), paneCount: panes.length };
}

export function traceList(stdout) {
	const lines = stdout.split(/\r?\n/).filter(Boolean);
	return { entries: lines.slice(0, 10), entryCount: lines.length };
}

function printable(value) {
	if (value === undefined || value === null) return "none";
	if (typeof value === "string") return value;
	return JSON.stringify(value);
}

export function renderWorkState(sources) {
	const lines = ["# Work state", ""];
	for (const item of sources) {
		lines.push(`## ${item.source}`);
		lines.push(`- source: ${item.source}`);
		lines.push(`- freshness: ${item.freshness}`);
		lines.push(`- authority: ${item.authority}`);
		lines.push(`- boundedness: ${item.boundedness}`);
		lines.push(`- availability: ${item.available ? "available" : "unavailable"}`);
		for (const [key, value] of Object.entries(item.detail)) {
			lines.push(`- ${key}: ${printable(value)}`);
		}
		lines.push("");
	}
	const unavailable = sources
		.filter((item) => !item.available)
		.map((item) => item.source);
	lines.push(
		`Unavailable sources: ${unavailable.length ? unavailable.join(", ") : "none"}`,
	);
	return lines.join("\n");
}
