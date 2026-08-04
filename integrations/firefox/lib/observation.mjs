import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";

const MAX_GEOMETRY_NODES = 80;
const OBSERVER_KEY = "__rp152kpiFirefoxObservation";
const RELEVANT_TAGS = new Set([
	"a",
	"button",
	"canvas",
	"img",
	"input",
	"select",
	"svg",
	"textarea",
	"video",
]);

function responsePayload(result, operation) {
	try {
		return JSON.parse(result.stdout);
	} catch (error) {
		throw new Error(`invalid JSON from ${operation}: ${error.message}`);
	}
}

function responseText(result, operation) {
	const payload = responsePayload(result, operation);
	if (!Array.isArray(payload.content)) {
		throw new Error(`unexpected response from ${operation}`);
	}
	return payload.content
		.filter((block) => block.type === "text")
		.map((block) => block.text)
		.join("\n");
}

function responseJson(result, operation) {
	const match = responseText(result, operation).match(
		/```json\n([\s\S]*?)\n```/,
	);
	if (!match) throw new Error(`missing JSON result from ${operation}`);
	try {
		return JSON.parse(match[1]);
	} catch (error) {
		throw new Error(
			`invalid evaluated JSON from ${operation}: ${error.message}`,
		);
	}
}

function snapshotUids(snapshot) {
	const uids = [];
	for (const line of snapshot.split("\n")) {
		const match = line.match(/^\s*uid=([^\s]+)\s+([^\s]+)/);
		if (!match || !RELEVANT_TAGS.has(match[2].toLowerCase())) continue;
		uids.push(match[1]);
		if (uids.length === MAX_GEOMETRY_NODES) break;
	}
	return uids;
}

async function resolveSelectors(callFirefox, uids) {
	const resolved = [];
	for (const uid of uids) {
		try {
			const result = await callFirefox("resolve_uid_to_selector", [
				`uid=${uid}`,
			]);
			const text = responseText(result, "resolve_uid_to_selector");
			const selector = text.match(/→\s*(.+)$/m)?.[1];
			if (selector) resolved.push({ uid, selector });
		} catch {
			// A page may mutate between snapshotting and selector resolution.
		}
	}
	return resolved;
}

function mutationScript(action) {
	if (action === "start") {
		return `() => {
			const previous = window.${OBSERVER_KEY};
			previous?.observer?.disconnect();
			const state = { count: 0, observer: null };
			state.observer = new MutationObserver(() => { state.count += 1; });
			state.observer.observe(document.documentElement, {
				attributes: true, childList: true, characterData: true, subtree: true,
			});
			window.${OBSERVER_KEY} = state;
			return { documentUrl: location.href, mutationCount: state.count };
		}`;
	}
	return `() => {
		const state = window.${OBSERVER_KEY};
		const result = { documentUrl: location.href, mutationCount: state?.count ?? -1 };
		state?.observer?.disconnect();
		delete window.${OBSERVER_KEY};
		return result;
	}`;
}

function geometryScript(refs) {
	return `() => {
		const refs = ${JSON.stringify(refs)};
		const dpr = window.devicePixelRatio || 1;
		const viewport = { width: window.innerWidth, height: window.innerHeight, scrollX: window.scrollX, scrollY: window.scrollY, devicePixelRatio: dpr };
		const rect = (value) => ({ x: value.x, y: value.y, width: value.width, height: value.height, top: value.top, right: value.right, bottom: value.bottom, left: value.left });
		const clippedRect = (value) => {
			const left = Math.max(0, value.left);
			const top = Math.max(0, value.top);
			const right = Math.min(window.innerWidth, value.right);
			const bottom = Math.min(window.innerHeight, value.bottom);
			return { x: left, y: top, width: Math.max(0, right - left), height: Math.max(0, bottom - top), top, right, bottom, left };
		};
		const fingerprint = (value) => {
			let hash = 2166136261;
			for (let index = 0; index < value.length; index += 1) {
				hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
			}
			return (hash >>> 0).toString(16) + ":" + value.length;
		};
		return {
			page: { url: location.href, title: document.title, fingerprint: fingerprint(document.documentElement.outerHTML) },
			viewport,
			nodes: refs.map(({ uid, selector }) => {
				let element;
				try { element = document.querySelector(selector); } catch { return { uid, selector, missing: true }; }
				if (!element) return { uid, selector, missing: true };
				const bounds = element.getBoundingClientRect();
				const visibleBounds = clippedRect(bounds);
				const style = getComputedStyle(element);
				const node = {
					uid, selector, tag: element.tagName.toLowerCase(),
					role: element.getAttribute("role"), name: element.getAttribute("aria-label"),
					text: (element.innerText || element.textContent || "").trim().slice(0, 500),
					visible: style.display !== "none" && style.visibility !== "hidden" && visibleBounds.width > 0 && visibleBounds.height > 0,
					rectCss: rect(bounds), visibleRectCss: visibleBounds,
					rectScreenshot: { x: visibleBounds.x * dpr, y: visibleBounds.y * dpr, width: visibleBounds.width * dpr, height: visibleBounds.height * dpr },
				};
				if (element instanceof HTMLImageElement) {
					node.image = { src: element.src, currentSrc: element.currentSrc, alt: element.alt, naturalWidth: element.naturalWidth, naturalHeight: element.naturalHeight, renderedWidth: bounds.width, renderedHeight: bounds.height };
				}
				return node;
			}),
		};
	}`;
}

function actionValidationScript(selector) {
	return `() => {
		const fingerprint = (value) => {
			let hash = 2166136261;
			for (let index = 0; index < value.length; index += 1) {
				hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
			}
			return (hash >>> 0).toString(16) + ":" + value.length;
		};
		let element;
		try { element = document.querySelector(${JSON.stringify(selector)}); } catch { element = null; }
		return {
			url: location.href,
			fingerprint: fingerprint(document.documentElement.outerHTML),
			element: element ? { tag: element.tagName.toLowerCase(), connected: element.isConnected } : null,
		};
	}`;
}

export async function validateActionObservation({ callFirefox, observationPath, uid }) {
	let metadata;
	try {
		metadata = JSON.parse(await readFile(observationPath, "utf8"));
	} catch (error) {
		throw new Error(`cannot read observation ${observationPath}: ${error.message}`);
	}
	if (metadata.schemaVersion < 3) {
		throw new Error("observation lacks action-safety data; capture a fresh observation");
	}
	if (metadata.document?.dirty) {
		throw new Error("observation remained dirty after retry; capture a fresh observation before acting");
	}
	let geometry;
	try {
		geometry = JSON.parse(await readFile(metadata.geometryPath, "utf8"));
	} catch (error) {
		throw new Error(`cannot read observation geometry: ${error.message}`);
	}
	const expectedNode = geometry.nodes?.find((node) => node.uid === uid);
	if (!expectedNode || expectedNode.missing) {
		throw new Error(`UID ${uid} is not a usable node in observation ${metadata.observationId}`);
	}
	const actual = responseJson(
		await callFirefox("evaluate_script", [
			`function=${actionValidationScript(expectedNode.selector)}`,
		]),
		"action preflight",
	);
	if (
		actual.url !== geometry.page?.url ||
		actual.fingerprint !== geometry.page?.fingerprint ||
		actual.element?.tag !== expectedNode.tag ||
		!actual.element?.connected
	) {
		throw new Error(
			`observation ${metadata.observationId} is stale; re-observe before acting`,
		);
	}
	return metadata.observationId;
}

export async function createObservation({ callFirefox, directory, tabIndex, maxAttempts = 2 }) {
	await mkdir(directory, { recursive: true });
	const snapshotPath = join(directory, "snapshot.txt");
	const screenshotPath = join(directory, "viewport.png");
	const geometryFunctionPath = join(directory, "geometry-function.js");
	const geometryPath = join(directory, "geometry.json");
	const metadataPath = join(directory, "observation.json");
	const startPath = join(directory, "mutation-start.js");
	const endPath = join(directory, "mutation-end.js");
	let capture;
	let attempts = 0;

	for (; attempts < maxAttempts; attempts += 1) {
		await writeFile(startPath, mutationScript("start"));
		await writeFile(endPath, mutationScript("end"));
		const mutationBefore = responseJson(await callFirefox("evaluate_script", [`function=@${startPath}`]), "mutation start");
		const snapshot = await callFirefox("take_snapshot", [`saveTo=${snapshotPath}`]);
		const screenshot = await callFirefox("screenshot_page", [`saveTo=${screenshotPath}`]);
		const selectors = await resolveSelectors(callFirefox, snapshotUids(await readFile(snapshotPath, "utf8")));
		await writeFile(geometryFunctionPath, geometryScript(selectors));
		const geometry = await callFirefox("evaluate_script", [`function=@${geometryFunctionPath}`, `saveTo=${geometryPath}`]);
		const mutationAfter = responseJson(await callFirefox("evaluate_script", [`function=@${endPath}`]), "mutation end");
		const dirty = mutationBefore.documentUrl !== mutationAfter.documentUrl || mutationAfter.mutationCount > 0;
		capture = { mutationBefore, mutationAfter, snapshot, screenshot, geometry, selectors, dirty };
		if (!dirty) break;
	}

	const metadata = {
		schemaVersion: 3,
		observationId: basename(directory),
		tabIndex,
		createdAt: new Date().toISOString(),
		snapshotPath,
		screenshotPath,
		geometryPath,
		geometryNodeCount: capture.selectors.length,
		capture: {
			attempts: Math.min(attempts + 1, maxAttempts),
			maxAttempts,
			stabilized: !capture.dirty,
		},
		document: {
			before: capture.mutationBefore,
			after: capture.mutationAfter,
			dirty: capture.dirty,
		},
		snapshotResult: responsePayload(capture.snapshot, "take_snapshot"),
		screenshotResult: responsePayload(capture.screenshot, "screenshot_page"),
		geometryResult: responsePayload(capture.geometry, "geometry evaluation"),
	};
	await writeFile(metadataPath, `${JSON.stringify(metadata, null, 2)}\n`);
	return { observationPath: metadataPath, snapshotPath, screenshotPath, geometryPath };
}
