import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const TMUX_FORMAT = "#S:#I.#W";
const MAX_NOTIFICATION_TEXT_LENGTH = 200;

function sanitizeNotificationText(value: string): string {
	return value
		.replace(/[\x00-\x1f\x7f]/g, " ")
		.replace(/;/g, ",")
		.trim()
		.slice(0, MAX_NOTIFICATION_TEXT_LENGTH);
}

function notifyGhostty(title: string, body: string): void {
	// tmux passthrough: ESC P tmux; ESC ESC ] ... BEL ESC \\
	process.stdout.write(
		`\x1bPtmux;\x1b\x1b]777;notify;${title};${body}\x07\x1b\\`,
	);
}

async function getTmuxLocation(pi: ExtensionAPI): Promise<string | undefined> {
	const pane = process.env.TMUX_PANE;
	if (!pane) return undefined;

	const result = await pi.exec(
		"tmux",
		["display-message", "-p", "-t", pane, TMUX_FORMAT],
		{
			timeout: 1_000,
		},
	);
	if (result.code !== 0) return undefined;

	const location = sanitizeNotificationText(result.stdout);
	return location || undefined;
}

async function sendReadyNotification(pi: ExtensionAPI): Promise<boolean> {
	if (!process.env.TMUX || !process.env.TMUX_PANE) return false;

	const location = await getTmuxLocation(pi);
	notifyGhostty("Pi", location ? `Ready for input — ${location}` : "Ready for input");
	return true;
}

export default function (pi: ExtensionAPI) {
	pi.registerCommand("notify-test", {
		description: "Send a Ghostty notification through tmux",
		handler: async (_args, ctx) => {
			if (ctx.mode !== "tui") return;

			try {
				if (!await sendReadyNotification(pi)) {
					ctx.ui.notify("rp152kpi:notify requires tmux", "warning");
				}
			} catch {
				ctx.ui.notify("Could not send Ghostty notification", "error");
			}
		},
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (ctx.mode !== "tui") return;

		try {
			await sendReadyNotification(pi);
		} catch {
			// Notifications must never interfere with the completed agent run.
		}
	});
}
