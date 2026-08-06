import { useState, useEffect } from "react";
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

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function CodeAgent() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"analysis" | "proposals" | "git">("analysis");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const headers = getAuthHeader();
      const [analysisRes, proposalsRes, gitRes] = await Promise.all([
        fetch("/api/v1/kudos/agent/analyze", { headers }),
        fetch("/api/v1/kudos/agent/proposals", { headers }),
        fetch("/api/v1/kudos/agent/git/status", { headers }),
      ]);
      if (analysisRes.ok) setAnalysis(await analysisRes.json());
      if (proposalsRes.ok) {
        const data = await proposalsRes.json();
        setProposals(data.proposals || []);
      }
      if (gitRes.ok) setGitStatus(await gitRes.json());
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
    const res = await fetch(`/api/v1/kudos/agent/proposals/${id}/commit`, {
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
    const res = await fetch("/api/v1/kudos/agent/push", {
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
      ) : (
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
      )}
    </Layout>
  );
}
