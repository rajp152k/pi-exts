import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { run, requireSuccess } from "../lib/command.mjs";

const integrationRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const firefoxctl = resolve(integrationRoot, "bin", "firefoxctl.mjs");
const fixtureHtml = `<!doctype html>
<title>Pi Firefox Fixture</title>
<label>Name <input id="name" aria-label="Name"></label>
<button id="submit" onclick="document.querySelector('#result').textContent = document.querySelector('#name').value">Submit</button>
<p id="result"></p>`;
const mutatingHtml = `${fixtureHtml}<script>setInterval(() => { document.querySelector('#result').textContent = Date.now(); }, 10)</script>`;

async function firefox(...args) {
	const result = await run("node", [firefoxctl, ...args], { timeout: 180_000 });
	return requireSuccess(result, `firefoxctl ${args.join(" ")}`);
}

function pageIndex(result) {
	const match = result.stdout.match(/new page \[(\d+)]/);
	assert.ok(match, `could not find page index in: ${result.stdout}`);
	return match[1];
}

function uid(snapshot, tag) {
	const match = snapshot.match(new RegExp(`uid=([^ ]+) ${tag}`));
	assert.ok(match, `could not find ${tag} UID in snapshot`);
	return match[1];
}

const server = createServer((request, response) => {
	response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
	response.end(request.url === "/mutating" ? mutatingHtml : fixtureHtml);
});

await new Promise((resolveServer) =>
	server.listen(0, "127.0.0.1", resolveServer),
);
const address = server.address();
assert.ok(address && typeof address !== "string");
const url = `http://127.0.0.1:${address.port}/`;
let tabIndex;
let mutatingTabIndex;

try {
	await firefox("doctor");
	tabIndex = pageIndex(await firefox("tabs", "open", url));
	const observation = JSON.parse((await firefox("observe", tabIndex)).stdout);
	const snapshot = await readFile(observation.snapshotPath, "utf8");
	const inputUid = uid(snapshot, "input");
	const geometry = JSON.parse(await readFile(observation.geometryPath, "utf8"));
	const inputNode = geometry.nodes.find((node) => node.uid === inputUid);
	assert.ok(
		inputNode && !inputNode.missing,
		"input should have visual geometry",
	);
	assert.ok(
		inputNode.rectScreenshot.width > 0,
		"input should map to screenshot pixels",
	);

	await firefox(
		"fill",
		tabIndex,
		inputUid,
		"Agentic",
		"--observation",
		observation.observationPath,
	);
	const buttonUid = uid(snapshot, 'button "Submit"');
	await firefox(
		"click",
		tabIndex,
		buttonUid,
		"--observation",
		observation.observationPath,
	);
	const staleAction = await run(
		"node",
		[
			firefoxctl,
			"click",
			tabIndex,
			buttonUid,
			"--observation",
			observation.observationPath,
		],
		{ timeout: 180_000 },
	);
	assert.notEqual(staleAction.code, 0, "stale actions must be rejected");
	assert.match(staleAction.stderr, /is stale/);
	const result = await firefox(
		"eval",
		tabIndex,
		"--expr",
		'() => document.querySelector("#result").textContent',
	);
	assert.match(result.stdout, /Agentic/);

	mutatingTabIndex = pageIndex(await firefox("tabs", "open", `${url}mutating`));
	const unstableObservation = JSON.parse(
		(await firefox("observe", mutatingTabIndex)).stdout,
	);
	const unstableMetadata = JSON.parse(
		await readFile(unstableObservation.observationPath, "utf8"),
	);
	assert.equal(unstableMetadata.capture.attempts, 2, "dirty captures retry once");
	assert.equal(unstableMetadata.document.dirty, true, "mutating page stays dirty");
	const unstableSnapshot = await readFile(unstableObservation.snapshotPath, "utf8");
	const dirtyAction = await run(
		"node",
		[
			firefoxctl,
			"click",
			mutatingTabIndex,
			uid(unstableSnapshot, 'button "Submit"'),
			"--observation",
			unstableObservation.observationPath,
		],
		{ timeout: 180_000 },
	);
	assert.notEqual(dirtyAction.code, 0, "dirty observations must reject actions");
	assert.match(dirtyAction.stderr, /remained dirty/);
	await firefox("tabs", "close", mutatingTabIndex);
	mutatingTabIndex = undefined;
	process.stdout.write("Firefox smoke test passed.\n");
} finally {
	if (mutatingTabIndex) {
		try {
			await firefox("tabs", "close", mutatingTabIndex);
		} catch {
			// Preserve the original test failure while attempting cleanup.
		}
	}
	if (tabIndex) {
		try {
			await firefox("tabs", "close", tabIndex);
		} catch {
			// Preserve the original test failure while attempting cleanup.
		}
	}
	await new Promise((resolveServer) => server.close(resolveServer));
}
