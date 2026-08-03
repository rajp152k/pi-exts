#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import {
	callFirefox,
	firefoxStatus,
	mcporter,
	restartDaemon,
} from "../lib/mcporter.mjs";
import { withFirefoxLock } from "../lib/lock.mjs";

function usage() {
	return `Usage:
  firefoxctl doctor
  firefoxctl daemon restart
  firefoxctl tools
  firefoxctl raw <tool> [key=value ...]
  firefoxctl tabs list|open <url>|close <index>|select <index>
  firefoxctl navigate <index> <url>
  firefoxctl snapshot <index> [--save <path>]
  firefoxctl screenshot <index> [--save <path>]
  firefoxctl observe <index>
  firefoxctl click <index> <uid>
  firefoxctl fill <index> <uid> <text>
  firefoxctl eval <index> (--expr <function> | --file <path>)
  firefoxctl network <index>
  firefoxctl console <index>`;
}

function print(result) {
	process.stdout.write(result.stdout);
}

function parseJson(value, description) {
	try {
		return JSON.parse(value);
	} catch (error) {
		throw new Error(`invalid JSON from ${description}: ${error.message}`);
	}
}

function parseIndex(value) {
	const index = Number.parseInt(value, 10);
	if (!Number.isInteger(index) || index < 0) {
		throw new Error(`invalid tab index: ${value}`);
	}
	return index;
}

async function withSelectedTab(index, work) {
	return withFirefoxLock(async () => {
		await callFirefox("select_page", [`pageIdx=${index}`]);
		return work();
	});
}

function artifactDirectory() {
	const observationId = `${new Date().toISOString().replace(/[:.]/g, "-")}-${process.pid}`;
	return join(homedir(), ".firefox-devtools-mcp", "rp152kpi", observationId);
}

async function doctor() {
	const version = await mcporter(["--version"]);
	const status = await firefoxStatus();
	const pages = await callFirefox("list_pages");
	process.stdout.write(
		`${JSON.stringify(
			{
				mcporter: version.stdout.trim(),
				status: status.stdout.trim(),
				pages: parseJson(pages.stdout, "list_pages"),
			},
			null,
			2,
		)}\n`,
	);
}

async function observe(index) {
	const directory = artifactDirectory();
	await mkdir(directory, { recursive: true });
	const snapshotPath = join(directory, "snapshot.txt");
	const screenshotPath = join(directory, "viewport.png");
	const metadataPath = join(directory, "observation.json");

	await withSelectedTab(index, async () => {
		const snapshot = await callFirefox("take_snapshot", [
			`saveTo=${snapshotPath}`,
		]);
		const screenshot = await callFirefox("screenshot_page", [
			`saveTo=${screenshotPath}`,
		]);
		await writeFile(
			metadataPath,
			`${JSON.stringify(
				{
					schemaVersion: 1,
					tabIndex: index,
					createdAt: new Date().toISOString(),
					snapshotPath,
					screenshotPath,
					snapshotResult: parseJson(snapshot.stdout, "take_snapshot"),
					screenshotResult: parseJson(screenshot.stdout, "screenshot_page"),
				},
				null,
				2,
			)}\n`,
		);
	});

	process.stdout.write(
		`${JSON.stringify(
			{ observationPath: metadataPath, snapshotPath, screenshotPath },
			null,
			2,
		)}\n`,
	);
}

async function main(argv) {
	const [command, ...args] = argv;
	if (!command || command === "help" || command === "--help") {
		process.stdout.write(`${usage()}\n`);
		return;
	}

	if (command === "doctor") return doctor();
	if (command === "tools")
		return print(await mcporter(["list", "firefox", "--json"]));
	if (command === "daemon" && args[0] === "restart")
		return print(await restartDaemon());
	if (command === "raw") {
		const [tool, ...toolArguments] = args;
		if (!tool) throw new Error("raw requires an MCP tool name");
		return print(await callFirefox(tool, toolArguments));
	}

	if (command === "tabs") {
		const [action, value] = args;
		if (action === "list") return print(await callFirefox("list_pages"));
		if (action === "open" && value)
			return print(await callFirefox("new_page", [`url=${value}`]));
		if (action === "close" && value) {
			return withFirefoxLock(async () =>
				print(
					await callFirefox("close_page", [`pageIdx=${parseIndex(value)}`]),
				),
			);
		}
		if (action === "select" && value) {
			return withFirefoxLock(async () =>
				print(
					await callFirefox("select_page", [`pageIdx=${parseIndex(value)}`]),
				),
			);
		}
		throw new Error(
			"tabs expects list, open <url>, close <index>, or select <index>",
		);
	}

	if (command === "navigate") {
		const [index, url] = args;
		if (!index || !url) throw new Error("navigate requires <index> <url>");
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("navigate_page", [`url=${url}`])),
		);
	}

	if (command === "snapshot" || command === "screenshot") {
		const [index, flag, savePath] = args;
		if (!index) throw new Error(`${command} requires <index>`);
		const tool = command === "snapshot" ? "take_snapshot" : "screenshot_page";
		const toolArguments =
			flag === "--save" && savePath ? [`saveTo=${savePath}`] : [];
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox(tool, toolArguments)),
		);
	}

	if (command === "observe") {
		const [index] = args;
		if (!index) throw new Error("observe requires <index>");
		return observe(parseIndex(index));
	}

	if (command === "click") {
		const [index, uid] = args;
		if (!index || !uid) throw new Error("click requires <index> <uid>");
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("click_by_uid", [`uid=${uid}`])),
		);
	}

	if (command === "fill") {
		const [index, uid, text] = args;
		if (!index || !uid || text === undefined)
			throw new Error("fill requires <index> <uid> <text>");
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("fill_by_uid", [`uid=${uid}`, `value=${text}`])),
		);
	}

	if (command === "eval") {
		const [index, mode, value] = args;
		if (!index || !mode || !value || !["--expr", "--file"].includes(mode)) {
			throw new Error(
				"eval requires <index> (--expr <function> | --file <path>)",
			);
		}
		const functionArgument =
			mode === "--file" ? `function=@${value}` : `function=${value}`;
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("evaluate_script", [functionArgument])),
		);
	}

	if (command === "network" || command === "console") {
		const [index] = args;
		if (!index) throw new Error(`${command} requires <index>`);
		const tool =
			command === "network" ? "list_network_requests" : "list_console_messages";
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox(tool)),
		);
	}

	throw new Error(`unknown command: ${command}`);
}

main(process.argv.slice(2)).catch((error) => {
	process.stderr.write(`firefoxctl: ${error.message}\n`);
	process.exitCode = 1;
});
