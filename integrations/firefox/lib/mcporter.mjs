import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { requireSuccess, run } from "./command.mjs";

const integrationRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const configPath = resolve(integrationRoot, "config", "mcporter.json");
const mcporterBin = process.env.MCPORTER_BIN || "mcporter";

export async function mcporter(args, options = {}) {
	const result = await run(
		mcporterBin,
		["--config", configPath, ...args],
		options,
	);
	return requireSuccess(result, `mcporter ${args[0] ?? ""}`.trim());
}

export async function callFirefox(tool, args = [], options = {}) {
	return mcporter(
		["call", `firefox.${tool}`, ...args, "--output", "json"],
		options,
	);
}

export async function firefoxStatus() {
	return mcporter(["list", "firefox", "--status", "--exit-code"], {
		timeout: 15_000,
	});
}

export async function restartDaemon() {
	return mcporter(["daemon", "restart"], { timeout: 15_000 });
}
