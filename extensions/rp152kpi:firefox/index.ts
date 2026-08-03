import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const extensionDirectory = dirname(fileURLToPath(import.meta.url));
const firefoxctl = resolve(
	extensionDirectory,
	"../../integrations/firefox/bin/firefoxctl.mjs",
);

async function updateStatus(pi: ExtensionAPI, ctx: ExtensionContext) {
	try {
		const result = await pi.exec("node", [firefoxctl, "doctor"], { timeout: 10_000 });
		ctx.ui.setStatus(
			"rp152kpi:firefox",
			result.code === 0 ? "Firefox: connected" : "Firefox: unavailable",
		);
	} catch {
		ctx.ui.setStatus("rp152kpi:firefox", "Firefox: unavailable");
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		await updateStatus(pi, ctx);
	});

	pi.registerCommand("firefox-status", {
		description: "Check the Firefox browser-agent connection",
		handler: async (_args, ctx) => {
			await updateStatus(pi, ctx);
			ctx.ui.notify("Firefox status refreshed", "info");
		},
	});

	pi.registerCommand("firefox-restart", {
		description: "Restart the persistent Firefox MCP connection",
		handler: async (_args, ctx) => {
			try {
				const result = await pi.exec("node", [firefoxctl, "daemon", "restart"], { timeout: 15_000 });
				if (result.code !== 0) throw new Error("daemon restart failed");
				await updateStatus(pi, ctx);
				ctx.ui.notify("Firefox MCP connection restarted", "info");
			} catch {
				ctx.ui.notify("Could not restart Firefox MCP connection", "error");
			}
		},
	});
}
