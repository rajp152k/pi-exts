import { mkdir, open, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const lockPath = join(tmpdir(), "rp152kpi-firefox.lock");
const staleAfterMs = 120_000;

function sleep(milliseconds) {
	return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function removeStaleLock() {
	try {
		const lock = JSON.parse(await readFile(lockPath, "utf8"));
		if (Date.now() - lock.createdAt > staleAfterMs) {
			await rm(lockPath, { force: true });
		}
	} catch {
		await rm(lockPath, { force: true });
	}
}

export async function withFirefoxLock(work, { timeout = 30_000 } = {}) {
	const deadline = Date.now() + timeout;
	await mkdir(tmpdir(), { recursive: true });

	while (true) {
		try {
			const handle = await open(lockPath, "wx");
			try {
				await writeFile(
					handle,
					JSON.stringify({ pid: process.pid, createdAt: Date.now() }),
				);
				return await work();
			} finally {
				await handle.close();
				await rm(lockPath, { force: true });
			}
		} catch (error) {
			if (error?.code !== "EEXIST") throw error;
			await removeStaleLock();
			if (Date.now() >= deadline) {
				throw new Error("timed out waiting for Firefox operation lock");
			}
			await sleep(100);
		}
	}
}
