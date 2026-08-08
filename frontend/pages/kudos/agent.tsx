import { useState, useEffect } from "react";
import { getAuthHeader } from "@/lib/api";
import Layout from "@/components/Layout";

interface Analysis {
  stats: { files: number; lines: number; functions: number; classes: number };
  issues: { type: string; file: string; line: number; text: string }[];
  issue_count: number;
  suggestions: { title: string; description: string; category: string; impact: string; files: string[]; auto_fixable: boolean }[];
}

interface Proposal {
  id: number;
  title: string;
  description: string;
  category: string;
  status: string;
  files_changed: { file: string }[];
  created_at: string;
  reviewed_at: string | null;
  commit_hash: string | null;
}

interface GitStatus {
  branch: string;
  status: string;
  recent_commits: string[];
  diff_stat: string;
}

interface ArchIndex {
  summary: string;
  stats: { files: number; lines_of_code: number; functions: number; classes: number; by_extension: Record<string, number> };
  features: { name: string; files: number; examples: string[] }[];
  modules: { path: string; kind: string; symbols?: string[] }[];
}

interface AgentTask {
  id: number;
  task_type: string;
  status: string;
  error: string;
  result: { exit_code?: number; output?: string };
  created_at: string | null;
  finished_at: string | null;
}

interface SandboxLog {
  id: number;
  workspace: string | null;
  operation: string;
  command: string;
  status: string;
  exit_code: number | null;
  output: string;
  created_at: string | null;
}

export default function CodeAgent() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [arch, setArch] = useState<ArchIndex | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [logs, setLogs] = useState<SandboxLog[]>([]);
  const [taskForm, setTaskForm] = useState({ command: "", workspace: "", timeout: 120 });
  const [runningTask, setRunningTask] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"analysis" | "proposals" | "git" | "arch" | "tasks">("analysis");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const headers = getAuthHeader();
      const [analysisRes, proposalsRes, gitRes, archRes, tasksRes, logsRes] = await Promise.all([
        fetch("/api/v1/kudos/agent/analyze", { headers }),
        fetch("/api/v1/kudos/agent/proposals", { headers }),
        fetch("/api/v1/kudos/agent/git/status", { headers }),
        fetch("/api/v1/kudos/agent/architecture", { headers }),
        fetch("/api/v1/kudos/agent/tasks", { headers }),
        fetch("/api/v1/kudos/agent/tasks/logs", { headers }),
      ]);
      if (analysisRes.ok) setAnalysis(await analysisRes.json());
      if (proposalsRes.ok) {
        const data = await proposalsRes.json();
        setProposals(data.proposals || []);
      }
      if (gitRes.ok) setGitStatus(await gitRes.json());
      if (archRes.ok) setArch(await archRes.json());
      if (tasksRes.ok) {
        const data = await tasksRes.json();
        setTasks(data.tasks || []);
      }
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs || []);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const generateProposals = async () => {
    setMessage({ text: "", type: "" });
    const res = await fetch("/api/v1/kudos/agent/auto-improvement/generate", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchAll();
    }
  };

  const approveProposal = async (id: number) => {
    const res = await fetch(`/api/v1/kudos/agent/proposals/${id}/approve`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setMessage({ text: "✅ Proposal approved!", type: "success" });
      fetchAll();
    }
  };

  const rejectProposal = async (id: number) => {
    const res = await fetch(`/api/v1/kudos/agent/proposals/${id}/reject`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setMessage({ text: "❌ Proposal rejected", type: "error" });
      fetchAll();
    }
  };

  const commitProposal = async (id: number) => {
    const res = await fetch(`/api/v1/kudos/agent/proposals/${id}/commit?approve=true`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchAll();
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const pushChanges = async () => {
    const res = await fetch("/api/v1/kudos/agent/push?approved=true", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ Pushed to ${data.branch}!`, type: "success" });
      fetchAll();
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const runTask = async () => {
    if (!taskForm.command.trim()) {
      setMessage({ text: "❌ Enter a command to run", type: "error" });
      return;
    }
    setRunningTask(true);
    setMessage({ text: "", type: "" });
    const res = await fetch("/api/v1/kudos/agent/tasks", {
      method: "POST",
      headers: getAuthHeader(),
      body: JSON.stringify({
        task_type: "run_command",
        command: taskForm.command,
        workspace: taskForm.workspace || undefined,
        timeout: taskForm.timeout,
      }),
    });
    setRunningTask(false);
    if (res.ok) {
      const data = await res.json();
      const outcome = data.status === "done" ? "succeeded" : `failed: ${data.error || "exit " + data.exit_code}`;
      setMessage({ text: `⚙️ Task #${data.task_id} ${outcome}`, type: data.status === "done" ? "success" : "error" });
      fetchAll();
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const STATUS_COLORS: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-700",
    approved: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    committed: "bg-blue-100 text-blue-700",
  };

  const CATEGORY_ICONS: Record<string, string> = {
    feature: "✨",
    fix: "🔧",
    improvement: "📈",
    security: "🔒",
    performance: "⚡",
    cleanup: "🧹",
  };

  const IMPACT_COLORS: Record<string, string> = {
    high: "text-red-600",
    medium: "text-yellow-600",
    low: "text-green-600",
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold">🤖 KUDOS Code Agent</h2>
          <p className="text-gray-600">Autonomous code improvement — analyzes, proposes, waits for your approval</p>
        </div>
        <div className="flex gap-2">
          <button onClick={generateProposals} className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700">
            🔍 Analyze & Propose
          </button>
          <button onClick={pushChanges} className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700">
            🚀 Push to GitHub
          </button>
        </div>
      </div>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>{message.text}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-6">
        {[
          { id: "analysis" as const, label: "📊 Analysis", count: analysis?.issue_count || 0 },
          { id: "proposals" as const, label: "📋 Proposals", count: proposals.length },
          { id: "git" as const, label: "🔀 Git", count: 0 },
          { id: "arch" as const, label: "🏗️ Architecture", count: 0 },
          { id: "tasks" as const, label: "⚙️ Tasks", count: tasks.filter((t) => t.status === "running").length },
        ].map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${activeTab === t.id ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"}`}>
            {t.label} {t.count > 0 && `(${t.count})`}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500">Analyzing codebase...</p>
      ) : activeTab === "analysis" ? (
        <div className="space-y-6">
          {/* Stats */}
          {analysis && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Files", value: analysis.stats.files, icon: "📄" },
                { label: "Lines", value: analysis.stats.lines, icon: "📝" },
                { label: "Functions", value: analysis.stats.functions, icon: "⚡" },
                { label: "Classes", value: analysis.stats.classes, icon: "🏗️" },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-xl border shadow p-4 text-center">
                  <p className="text-2xl mb-1">{s.icon}</p>
                  <p className="text-2xl font-bold text-primary">{s.value.toLocaleString()}</p>
                  <p className="text-xs text-gray-500">{s.label}</p>
                </div>
              ))}
            </div>
          )}

          {/* Suggestions */}
          {analysis?.suggestions && analysis.suggestions.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-3">💡 Improvement Suggestions</h3>
              <div className="space-y-3">
                {analysis.suggestions.map((s, i) => (
                  <div key={i} className="bg-white rounded-xl border shadow p-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-semibold">{CATEGORY_ICONS[s.category] || "💡"} {s.title}</h4>
                        <p className="text-sm text-gray-500 mt-1">{s.description}</p>
                        <div className="flex gap-3 mt-2 text-xs">
                          <span className={`font-medium ${IMPACT_COLORS[s.impact]}`}>Impact: {s.impact}</span>
                          {s.auto_fixable && <span className="text-green-600">Auto-fixable ✅</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Issues */}
          {analysis?.issues && analysis.issues.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-3">🔍 Issues Found ({analysis.issue_count})</h3>
              <div className="bg-white rounded-xl border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left">
                    <tr>
                      <th className="px-4 py-2">Type</th>
                      <th className="px-4 py-2">File</th>
                      <th className="px-4 py-2">Line</th>
                      <th className="px-4 py-2">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.issues.slice(0, 20).map((issue, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-4 py-2"><span className="text-xs bg-gray-100 px-2 py-0.5 rounded">{issue.type}</span></td>
                        <td className="px-4 py-2 font-mono text-xs">{issue.file}</td>
                        <td className="px-4 py-2">{issue.line}</td>
                        <td className="px-4 py-2 text-gray-600">{issue.text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : activeTab === "proposals" ? (
        <div className="space-y-4">
          {proposals.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-xl border">
              <p className="text-5xl mb-3">📋</p>
              <p className="text-xl text-gray-600 mb-2">No proposals yet</p>
              <p className="text-gray-500">Click "Analyze & Propose" to generate improvement proposals</p>
            </div>
          ) : (
            proposals.map((p) => (
              <div key={p.id} className="bg-white rounded-xl border shadow p-5">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-semibold">{CATEGORY_ICONS[p.category] || "💡"} {p.title}</h4>
                    <p className="text-sm text-gray-500 mt-1">{p.description}</p>
                    <p className="text-xs text-gray-400 mt-2">Created: {new Date(p.created_at).toLocaleString()}</p>
                    {p.commit_hash && <p className="text-xs font-mono text-blue-600 mt-1">Commit: {p.commit_hash.substring(0, 8)}</p>}
                  </div>
                  <div className="flex gap-2 items-center">
                    <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[p.status]}`}>{p.status}</span>
                    {p.status === "pending" && (
                      <>
                        <button onClick={() => approveProposal(p.id)} className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200">✅ Approve</button>
                        <button onClick={() => rejectProposal(p.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200">❌ Reject</button>
                      </>
                    )}
                    {p.status === "approved" && (
                      <button onClick={() => commitProposal(p.id)} className="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded hover:bg-blue-200">💾 Commit</button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : activeTab === "git" ? (
        /* Git tab */
        <div className="space-y-6">
          {gitStatus && (
            <div className="bg-white rounded-xl border shadow p-6">
              <h3 className="font-semibold text-lg mb-4">🔀 Git Status</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-sm text-gray-500">Branch</p>
                  <p className="font-mono font-semibold">{gitStatus.branch}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <p className="font-mono text-sm">{gitStatus.status || "Clean"}</p>
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-2">Recent Commits</p>
                <div className="space-y-1">
                  {gitStatus.recent_commits.map((c, i) => (
                    <p key={i} className="font-mono text-xs text-gray-600">{c}</p>
                  ))}
                </div>
              </div>
            </div>
          )}

          <button onClick={pushChanges} className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700">
            🚀 Push All Committed Changes to GitHub
          </button>
        </div>
      ) : activeTab === "tasks" ? (
        /* Tasks tab */
        <div className="space-y-6">
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-3">⚙️ Run Task</h3>
            <div className="flex flex-col md:flex-row gap-3 mb-3">
              <input
                value={taskForm.command}
                onChange={(e) => setTaskForm({ ...taskForm, command: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && runTask()}
                placeholder="Command to run in a workspace, e.g. npm test"
                className="flex-1 px-3 py-2 border rounded-lg text-sm"
              />
              <input
                value={taskForm.workspace}
                onChange={(e) => setTaskForm({ ...taskForm, workspace: e.target.value })}
                placeholder="Workspace path (defaults to repo root)"
                className="flex-1 px-3 py-2 border rounded-lg text-sm"
              />
              <input
                type="number"
                value={taskForm.timeout}
                onChange={(e) => setTaskForm({ ...taskForm, timeout: Number(e.target.value) })}
                placeholder="Timeout (s)"
                className="w-28 px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <button
              onClick={runTask}
              disabled={runningTask}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-white hover:opacity-90 disabled:opacity-50">
              {runningTask ? "Running..." : "▶️ Run Task"}
            </button>
          </div>

          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-3">📜 Recent Tasks</h3>
            <div className="space-y-3 max-h-[28rem] overflow-y-auto">
              {tasks.length === 0 ? (
                <p className="text-sm text-gray-400">No tasks yet. Run one above.</p>
              ) : (
                tasks.map((t) => (
                  <div key={t.id} className="border border-gray-100 rounded-lg p-3">
                    <div className="flex items-center gap-3 text-sm mb-1">
                      <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">#{t.id}</span>
                      <span className="font-medium">{t.task_type}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        t.status === "done" ? "bg-green-50 text-green-700" :
                        t.status === "failed" ? "bg-red-50 text-red-700" :
                        "bg-yellow-50 text-yellow-700"
                      }`}>{t.status}</span>
                      {t.error && <span className="text-xs text-red-600 truncate">{t.error}</span>}
                      <span className="ml-auto text-xs text-gray-400">
                        {t.finished_at ? new Date(t.finished_at).toLocaleString() : t.created_at ? new Date(t.created_at).toLocaleString() : "—"}
                      </span>
                    </div>
                    {t.status === "failed" && t.result?.output && (
                      <pre className="text-xs bg-red-50 border border-red-100 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                        {t.result.output.slice(0, 500)}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-3">🛡️ Sandbox Activity</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {logs.length === 0 ? (
                <p className="text-sm text-gray-400">No sandbox activity yet.</p>
              ) : (
                logs.map((l) => (
                  <div key={l.id} className="flex items-start gap-3 text-sm border-b border-gray-100 pb-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                      l.status === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
                    }`}>{l.status}</span>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">{l.operation}{l.workspace ? ` · ${l.workspace}` : ""}</p>
                      <code className="text-xs font-mono text-gray-700 break-all">{l.command}</code>
                    </div>
                    <span className="ml-auto text-xs text-gray-400 shrink-0">{l.created_at ? new Date(l.created_at).toLocaleString() : "—"}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Architecture tab */
        <div className="space-y-6">
          {arch && (
            <>
              <div className="bg-white rounded-xl border shadow p-6">
                <h3 className="font-semibold text-lg mb-3">🏗️ Architecture Index</h3>
                <p className="text-sm text-gray-600 mb-4">{arch.summary}</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "Files", value: arch.stats.files, icon: "📄" },
                    { label: "LOC", value: arch.stats.lines_of_code, icon: "📝" },
                    { label: "Functions", value: arch.stats.functions, icon: "⚡" },
                    { label: "Classes", value: arch.stats.classes, icon: "🏗️" },
                  ].map((s) => (
                    <div key={s.label} className="bg-gray-50 rounded-lg border p-4 text-center">
                      <p className="text-2xl mb-1">{s.icon}</p>
                      <p className="text-2xl font-bold text-primary">{s.value.toLocaleString()}</p>
                      <p className="text-xs text-gray-500">{s.label}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border shadow p-6">
                <h4 className="font-semibold mb-3">🧩 Feature Areas</h4>
                <div className="flex flex-wrap gap-2">
                  {arch.features.map((f) => (
                    <span key={f.name} className="text-xs bg-purple-50 text-purple-700 border border-purple-200 px-3 py-1 rounded-full">
                      {f.name} ({f.files})
                    </span>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border shadow p-6">
                <h4 className="font-semibold mb-3">🗂️ Modules</h4>
                <div className="max-h-96 overflow-y-auto">
                  {arch.modules.map((m) => (
                    <div key={m.path} className="flex justify-between items-start py-1.5 border-b border-gray-100 text-sm">
                      <span className="font-mono text-xs text-gray-700">{m.path}</span>
                      {m.symbols && m.symbols.length > 0 && (
                        <span className="text-xs text-gray-400 ml-4">{m.symbols.slice(0, 5).join(", ")}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </Layout>
  );
}
