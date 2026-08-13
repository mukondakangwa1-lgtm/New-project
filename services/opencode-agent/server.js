// KUDOS ↔ opencode bridge — tiny HTTP service that runs an opencode subagent
// (`opencode run --agent <agent> --format json …`) and returns the finished
// text. The backend asks for a subject; the agent researches it and writes a
// reference document.
//
// POST /learn   { prompt, agent?, model? }  -> { text, agent, session_id }
// GET  /health                              -> { ok: true }

"use strict";

const http = require("http");
const { spawn } = require("child_process");

const PORT = Number(process.env.PORT || 8090);
const MAX_CONCURRENT = Number(process.env.MAX_CONCURRENT || 2);
const DEFAULT_AGENT = process.env.DEFAULT_AGENT || "build";
const RUN_TIMEOUT_MS = Number(process.env.RUN_TIMEOUT_MS || 480000); // 8 min

let running = 0;
const queue = [];

function enqueue(task) {
  return new Promise((resolve, reject) => {
    queue.push({ task, resolve, reject });
    pump();
  });
}

function pump() {
  while (running < MAX_CONCURRENT && queue.length > 0) {
    const { task, resolve, reject } = queue.shift();
    running++;
    task()
      .then(resolve)
      .catch(reject)
      .finally(() => {
        running--;
        pump();
      });
  }
}

function runAgent(prompt, agent, model) {
  return enqueue(() => {
    return new Promise((resolve, reject) => {
      const args = ["run", "--agent", agent, "--format", "json"];
      if (model) {
        args.push("--model", model);
      }
      args.push("--title", `kudos-learn:${agent}:${Date.now()}`);
      args.push(prompt);

      const child = spawn("opencode", args, {
        env: { ...process.env, FORCE_COLOR: "0", CI: "true" },
      });

      let stdout = "";
      let stderr = "";
      const parts = [];
      let sessionId = null;

      const timer = setTimeout(() => {
        child.kill("SIGKILL");
      }, RUN_TIMEOUT_MS);

      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
        const lines = stdout.split("\n");
        stdout = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const evt = JSON.parse(line);
            if (evt.sessionID) sessionId = evt.sessionID;
            if (evt.type === "text" && evt.part && typeof evt.part.text === "string") {
              parts.push(evt.part.text);
            }
          } catch {
            // ignore non-JSON noise lines
          }
        }
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });

      child.on("error", (err) => {
        clearTimeout(timer);
        reject(new Error(`spawn failed: ${err.message}`));
      });

      child.on("close", (code) => {
        clearTimeout(timer);
        const text = parts.join("\n").trim();
        if (text) {
          resolve({ text, agent, session_id: sessionId });
        } else {
          reject(
            new Error(
              `opencode exited ${code} with no output. stderr: ${stderr.slice(-2000)}`
            )
          );
        }
      });
    });
  });
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (c) => {
      data += c;
      if (data.length > 2 * 1024 * 1024) {
        reject(new Error("body too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

function send(res, code, body) {
  const payload = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/health") {
      return send(res, 200, { ok: true, running, queued: queue.length });
    }

    if (req.method === "POST" && req.url === "/learn") {
      const raw = await readBody(req);
      let body;
      try {
        body = JSON.parse(raw || "{}");
      } catch {
        return send(res, 400, { error: "invalid JSON body" });
      }
      const prompt = String(body.prompt || "").trim();
      const agent = String(body.agent || DEFAULT_AGENT).trim();
      const model = body.model ? String(body.model).trim() : undefined;
      if (!prompt) {
        return send(res, 400, { error: "prompt is required" });
      }
      const result = await runAgent(prompt, agent, model);
      return send(res, 200, result);
    }

    return send(res, 404, { error: "not found" });
  } catch (err) {
    return send(res, 500, { error: String((err && err.message) || err).slice(0, 2000) });
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`opencode-agent sidecar listening on ${PORT}`);
});
