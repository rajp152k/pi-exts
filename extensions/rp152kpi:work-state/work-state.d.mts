export type WorkStateSource = {
	id: string;
	source: string;
	freshness: string;
	authority: string;
	boundedness: string;
	available: boolean;
	detail: Record<string, unknown>;
};

export function sourceResult(
	input: Omit<WorkStateSource, "source" | "freshness"> & { freshness?: string },
): WorkStateSource;
export function unavailableSource(input: {
	id: string;
	authority: string;
	boundedness: string;
	reason: string;
}): WorkStateSource;
export function gitSummary(stdout: string): {
	branch: string;
	changes: string[];
	changeCount: number;
};
export function tmuxTopology(stdout: string): {
	panes: Array<{
		session: string;
		window: string;
		pane: string;
		active: boolean;
		command: string;
		path: string;
	}>;
	paneCount: number;
};
export function traceList(stdout: string): {
	entries: string[];
	entryCount: number;
};
export function renderWorkState(sources: WorkStateSource[]): string;
