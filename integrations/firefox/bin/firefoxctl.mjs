#!/usr/bin/env node

import { homedir } from "node:os";
import { join } from "node:path";
import {
	callFirefox,
	firefoxStatus,
	mcporter,
	restartDaemon,
} from "../lib/mcporter.mjs";
import { withFirefoxLock } from "../lib/lock.mjs";
import {
	createObservation,
	validateActionObservation,
} from "../lib/observation.mjs";

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
  firefoxctl click|hover <index> <uid> --observation <path> [--force]
  firefoxctl fill <index> <uid> <text> --observation <path> [--force]
  firefoxctl drag <index> <source-uid> <target-uid> --observation <path> [--force]
  firefoxctl upload <index> <uid> <file> --observation <path> [--force]
  firefoxctl select <index> <uid> <value> --observation <path> [--force]
  firefoxctl scroll <index> <x> <y>
  firefoxctl key <index> <key> [code]
  firefoxctl wait <index> (url|text|selector|ready) [value] [--timeout <ms>]
  firefoxctl viewport <index> <width> <height>
  firefoxctl history <index> (back|forward)
  firefoxctl downloads [list|clear|allow|deny|default]
  firefoxctl dialog accept [text]|dismiss
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

function safetyOptions(args) {
	const observationFlag = args.indexOf("--observation");
	return {
		force: args.includes("--force"),
		observationPath:
			observationFlag === -1 ? undefined : args[observationFlag + 1],
	};
}

async function withFreshUids(index, uids, options, work) {
	if (!options.force && !options.observationPath) {
		throw new Error(
			"a guarded action requires --observation <observation.json> (or explicit --force)",
		);
	}
	return withSelectedTab(index, async () => {
		if (!options.force) {
			for (const uid of uids) {
				await validateActionObservation({
					callFirefox,
					observationPath: options.observationPath,
					uid,
				});
			}
		}
		return work();
	});
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

async function waitUntil(index, predicate, timeout) {
	const deadline = Date.now() + timeout;
	return withSelectedTab(index, async () => {
		while (Date.now() < deadline) {
			const result = await callFirefox("evaluate_script", [
				`function=${predicate}`,
			]);
			const text = parseJson(result.stdout, "wait evaluation")
				.content.filter((block) => block.type === "text")
				.map((block) => block.text)
				.join("\n");
			if (text.includes("```json\ntrue\n```")) return print(result);
			await new Promise((resolve) => setTimeout(resolve, 200));
		}
		throw new Error(`wait timed out after ${timeout}ms`);
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
	const observation = await withSelectedTab(index, () =>
		createObservation({
			callFirefox,
			directory: artifactDirectory(),
			tabIndex: index,
		}),
	);
	process.stdout.write(`${JSON.stringify(observation, null, 2)}\n`);
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

	if (["click", "hover", "fill", "upload", "select"].includes(command)) {
		const [index, uid, value] = args;
		const needsValue = ["fill", "upload", "select"].includes(command);
		if (!index || !uid || (needsValue && value === undefined)) {
			throw new Error(
				`${command} requires ${needsValue ? "<index> <uid> <value>" : "<index> <uid>"}`,
			);
		}
		return withFreshUids(
			parseIndex(index),
			[uid],
			safetyOptions(args),
			async () => {
				if (command === "click")
					return print(await callFirefox("click_by_uid", [`uid=${uid}`]));
				if (command === "hover")
					return print(await callFirefox("hover_by_uid", [`uid=${uid}`]));
				if (command === "fill")
					return print(
						await callFirefox("fill_by_uid", [`uid=${uid}`, `value=${value}`]),
					);
				if (command === "upload")
					return print(
						await callFirefox("upload_file_by_uid", [
							`uid=${uid}`,
							`filePath=${value}`,
						]),
					);
				const script = `(element) => {
				if (!(element instanceof HTMLSelectElement)) throw new Error("target is not a select element");
				element.value = ${JSON.stringify(value)};
				if (element.value !== ${JSON.stringify(value)}) throw new Error("option value was not found");
				element.dispatchEvent(new Event("input", { bubbles: true }));
				element.dispatchEvent(new Event("change", { bubbles: true }));
				return { value: element.value };
			}`;
				return print(
					await callFirefox("evaluate_script", [
						`function=${script}`,
						`args=[{"uid":"${uid}"}]`,
					]),
				);
			},
		);
	}

	if (command === "drag") {
		const [index, sourceUid, targetUid] = args;
		if (!index || !sourceUid || !targetUid)
			throw new Error("drag requires <index> <source-uid> <target-uid>");
		return withFreshUids(
			parseIndex(index),
			[sourceUid, targetUid],
			safetyOptions(args),
			async () =>
				print(
					await callFirefox("drag_by_uid_to_uid", [
						`fromUid=${sourceUid}`,
						`toUid=${targetUid}`,
					]),
				),
		);
	}

	if (command === "scroll") {
		const [index, x, y] = args;
		if (!index || x === undefined || y === undefined)
			throw new Error("scroll requires <index> <x> <y>");
		return withSelectedTab(parseIndex(index), async () =>
			print(
				await callFirefox("evaluate_script", [
					`function=() => { window.scrollTo(${Number(x)}, ${Number(y)}); return { x: window.scrollX, y: window.scrollY }; }`,
				]),
			),
		);
	}

	if (command === "key") {
		const [index, key, code] = args;
		if (!index || !key) throw new Error("key requires <index> <key> [code]");
		const script = `() => {
			const options = { key: ${JSON.stringify(key)}, code: ${JSON.stringify(code || "")}, bubbles: true, cancelable: true };
			document.activeElement?.dispatchEvent(new KeyboardEvent("keydown", options));
			document.activeElement?.dispatchEvent(new KeyboardEvent("keyup", options));
			return { activeElement: document.activeElement?.tagName || null };
		}`;
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("evaluate_script", [`function=${script}`])),
		);
	}

	if (command === "wait") {
		const [index, condition, value] = args;
		const timeoutFlag = args.indexOf("--timeout");
		const timeout = timeoutFlag === -1 ? 10_000 : Number(args[timeoutFlag + 1]);
		if (
			!index ||
			!["url", "text", "selector", "ready"].includes(condition) ||
			!Number.isFinite(timeout) ||
			timeout <= 0
		) {
			throw new Error(
				"wait requires <index> (url|text|selector|ready) [value] [--timeout <ms>]",
			);
		}
		if (condition !== "ready" && value === undefined)
			throw new Error(`wait ${condition} requires a value`);
		const predicates = {
			url: `() => location.href.includes(${JSON.stringify(value)})`,
			text: `() => document.body.innerText.includes(${JSON.stringify(value)})`,
			selector: `() => !!document.querySelector(${JSON.stringify(value)})`,
			ready: "() => document.readyState === 'complete'",
		};
		return waitUntil(parseIndex(index), predicates[condition], timeout);
	}

	if (command === "viewport") {
		const [index, width, height] = args;
		if (!index || !width || !height)
			throw new Error("viewport requires <index> <width> <height>");
		return withSelectedTab(parseIndex(index), async () =>
			print(
				await callFirefox("set_viewport_size", [
					`width=${Number(width)}`,
					`height=${Number(height)}`,
				]),
			),
		);
	}

	if (command === "history") {
		const [index, direction] = args;
		if (!index || !["back", "forward"].includes(direction))
			throw new Error("history requires <index> (back|forward)");
		return withSelectedTab(parseIndex(index), async () =>
			print(await callFirefox("navigate_history", [`direction=${direction}`])),
		);
	}

	if (command === "downloads") {
		const [action = "list"] = args;
		if (action === "list") return print(await callFirefox("list_downloads"));
		if (action === "clear") return print(await callFirefox("clear_downloads"));
		const behavior = { allow: "allowed", deny: "denied", default: "default" }[
			action
		];
		if (behavior)
			return print(
				await callFirefox("set_download_behavior", [`behavior=${behavior}`]),
			);
		throw new Error("downloads expects list, clear, allow, deny, or default");
	}

	if (command === "dialog") {
		const [action, promptText] = args;
		if (action === "accept")
			return print(
				await callFirefox(
					"accept_dialog",
					promptText === undefined ? [] : [`promptText=${promptText}`],
				),
			);
		if (action === "dismiss") return print(await callFirefox("dismiss_dialog"));
		throw new Error("dialog expects accept [text] or dismiss");
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
