import { spawn } from "node:child_process";

export async function run(command, args, options = {}) {
	const { cwd, env, timeout = 60_000 } = options;
	return new Promise((resolve, reject) => {
		const child = spawn(command, args, {
			cwd,
			env: { ...process.env, ...env },
			stdio: ["ignore", "pipe", "pipe"],
		});
		let stdout = "";
		let stderr = "";
		let timedOut = false;
		const timer = setTimeout(() => {
			timedOut = true;
			child.kill("SIGTERM");
		}, timeout);

		child.stdout.on("data", (chunk) => {
			stdout += chunk;
		});
		child.stderr.on("data", (chunk) => {
			stderr += chunk;
		});
		child.on("error", (error) => {
			clearTimeout(timer);
			reject(error);
		});
		child.on("close", (code, signal) => {
			clearTimeout(timer);
			resolve({ code: code ?? 1, signal, stdout, stderr, timedOut });
		});
	});
}

export function requireSuccess(result, description) {
	if (result.code === 0 && !result.timedOut) return result;
	const detail = result.timedOut
		? "timed out"
		: result.stderr.trim() || `exited with status ${result.code}`;
	throw new Error(`${description}: ${detail}`);
}
