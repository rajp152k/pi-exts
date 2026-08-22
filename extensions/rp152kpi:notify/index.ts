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

async function showTmuxPopup(
	pi: ExtensionAPI,
	pane: string,
	message: string,
): Promise<void> {
	const result = await pi.exec(
		"tmux",
		[
			"display-popup",
			"-t",
			pane,
			"-E",
			"-w",
			"50",
			"-h",
			"5",
			"-x",
			"R",
			"-y",
			"0",
			"-T",
			"Pi",
			"-e",
			`RP152KPI_NOTIFY_MESSAGE=${message}`,
			"printf '%s\\n\\nPress any key to dismiss.' \"$RP152KPI_NOTIFY_MESSAGE\"; old_stty=$(stty -g); trap 'stty \"$old_stty\"' EXIT HUP INT TERM; stty -icanon -echo min 1 time 0; dd bs=1 count=1 >/dev/null 2>&1;",
		],
		{ timeout: 1_000 },
	);
	if (result.code !== 0) throw new Error(result.stderr);
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
	const pane = process.env.TMUX_PANE;
	if (!process.env.TMUX || !pane) return false;

	const location = await getTmuxLocation(pi);
	const message = location ? `Ready for input — ${location}` : "Ready for input";
	await showTmuxPopup(pi, pane, sanitizeNotificationText(message));
	return true;
}

export default function (pi: ExtensionAPI) {
	pi.registerCommand("notify-test", {
		description: "Show a tmux notification popup",
		handler: async (_args, ctx) => {
			if (ctx.mode !== "tui") return;

			try {
				if (!(await sendReadyNotification(pi))) {
					ctx.ui.notify("rp152kpi:notify requires tmux", "warning");
				}
			} catch {
				ctx.ui.notify("Could not send Ghostty notification", "error");
			}
		},
	});

	// Deliberately manual: routine settlement is not an actionable attention event
	// and must not steal focus. Campaign attention is recorded separately in its
	// ledger and never invokes a global popup.
}
