import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import {
	gitSummary,
	renderWorkState,
	sourceResult,
	traceList,
	tmuxTopology,
	unavailableSource,
} from "../work-state.mjs";

const fixture = JSON.parse(
	await readFile(
		fileURLToPath(new URL("./fixtures.json", import.meta.url)),
		"utf8",
	),
);

test("summarizes bounded fixture metadata without pane or trace bodies", () => {
	assert.deepEqual(gitSummary(fixture.git), {
		branch: "feature/work-state...origin/feature/work-state",
		changes: [" M README.md", "?? skills/work-state/SKILL.md"],
		changeCount: 2,
	});
	assert.deepEqual(tmuxTopology(fixture.tmux), {
		panes: [
			{
				session: "main",
				window: "1.0",
				pane: "%1",
				active: true,
				command: "pi",
				path: "/tmp/project",
			},
			{
				session: "workflow",
				window: "2.1",
				pane: "%2",
				active: false,
				command: "python",
				path: "/tmp/worker",
			},
		],
		paneCount: 2,
	});
	assert.deepEqual(traceList(fixture.traces), {
		entries: ["trace-a recent local trace", "trace-b older local trace"],
		entryCount: 2,
	});
});

test("renders provenance labels and unavailable sources", () => {
	const text = renderWorkState([
		sourceResult({
			id: "git",
			authority: "Git",
			boundedness: "one branch",
			available: true,
			detail: { branch: "main" },
		}),
		unavailableSource({
			id: "Firefox",
			authority: "firefoxctl",
			boundedness: "status only",
			reason: "not installed",
		}),
	]);
	for (const label of [
		"source: git",
		"freshness: observed now",
		"authority: Git",
		"boundedness: one branch",
		"Unavailable sources: Firefox",
	]) {
		assert.match(text, new RegExp(label));
	}
	assert.match(text, /availability: unavailable/);
});
