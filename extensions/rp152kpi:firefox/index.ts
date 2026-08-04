import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type {
	ExtensionAPI,
	ExtensionContext,
} from "@earendil-works/pi-coding-agent";

const extensionDirectory = dirname(fileURLToPath(import.meta.url));
const firefoxctl = resolve(
	extensionDirectory,
	"../../integrations/firefox/bin/firefoxctl.mjs",
);

type StatusRequest = {
	extension: ExtensionAPI;
	context: ExtensionContext;
};

async function startAndUpdateStatus({ extension, context }: StatusRequest) {
	try {
		const result = await extension.exec("node", [firefoxctl, "doctor"], {
			timeout: 15_000,
		});
		context.ui.setStatus(
			"rp152kpi:firefox",
			result.code === 0 ? "Firefox: connected" : "Firefox: unavailable",
		);
		return result.code === 0;
	} catch {
		context.ui.setStatus("rp152kpi:firefox", "Firefox: unavailable");
		return false;
	}
}

async function updatePassiveStatus({ extension, context }: StatusRequest) {
	try {
		const result = await extension.exec(
			"node",
			[firefoxctl, "daemon", "status"],
			{
				timeout: 2_000,
			},
		);
		context.ui.setStatus(
			"rp152kpi:firefox",
			result.code === 0 && /firefox: connected/.test(result.stdout)
				? "Firefox: connected"
				: "Firefox: off",
		);
	} catch {
		context.ui.setStatus("rp152kpi:firefox", "Firefox: off");
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", (...parameters) => {
		const [, sessionContext] = parameters;
		sessionContext.ui.setStatus("rp152kpi:firefox", "Firefox: off");
	});

	pi.registerCommand("firefox-on", {
		description: "Start the Firefox MCP connection for this Pi session",
		handler: async (...parameters) => {
			const [, commandContext] = parameters;
			const connected = await startAndUpdateStatus({
				extension: pi,
				context: commandContext,
			});
			commandContext.ui.notify(
				connected
					? "Firefox MCP connection started"
					: "Could not connect to Firefox",
				connected ? "info" : "error",
			);
		},
	});

	pi.registerCommand("firefox-off", {
		description: "Stop the Firefox MCP connection without closing Firefox",
		handler: async (...parameters) => {
			const [, commandContext] = parameters;
			try {
				await pi.exec("node", [firefoxctl, "daemon", "stop"], {
					timeout: 5_000,
				});
			} finally {
				commandContext.ui.setStatus("rp152kpi:firefox", "Firefox: off");
			}
			commandContext.ui.notify("Firefox MCP connection stopped", "info");
		},
	});

	pi.registerCommand("firefox-status", {
		description: "Show Firefox MCP status without starting it",
		handler: async (...parameters) => {
			const [, commandContext] = parameters;
			await updatePassiveStatus({ extension: pi, context: commandContext });
			commandContext.ui.notify(
				"Firefox status refreshed without starting it",
				"info",
			);
		},
	});

	pi.registerCommand("firefox-restart", {
		description: "Restart the persistent Firefox MCP connection",
		handler: async (...parameters) => {
			const [, commandContext] = parameters;
			try {
				const result = await pi.exec(
					"node",
					[firefoxctl, "daemon", "restart"],
					{ timeout: 15_000 },
				);
				if (result.code !== 0) throw new Error("daemon restart failed");
				await startAndUpdateStatus({ extension: pi, context: commandContext });
				commandContext.ui.notify("Firefox MCP connection restarted", "info");
			} catch {
				commandContext.ui.notify(
					"Could not restart Firefox MCP connection",
					"error",
				);
			}
		},
	});
}
