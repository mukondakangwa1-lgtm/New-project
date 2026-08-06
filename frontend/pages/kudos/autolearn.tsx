import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface LearnerStatus {
  running: boolean;
  interval_minutes: number;
  last_run: string | null;
  stats: {
    total_runs: number;
    total_items_learned: number;
    connectors_synced: number;
    archive_items: number;
    web_pages: number;
    social_items: number;
    search_queries_learned: number;
  };
  recent_log: { action: string; details: string; items: number; timestamp: string }[];
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AutoLearner() {
  const [status, setStatus] = useState<LearnerStatus | null>(null);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/v1/kudos/learn/status", { headers: getAuthHeader() });
      if (res.ok) setStatus(await res.json());
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchStatus(); const interval = setInterval(fetchStatus, 10000); return () => clearInterval(interval); }, []);

  const startLearner = async (minutes: number) => {
    const res = await fetch(`/api/v1/kudos/learn/start?interval_minutes=${minutes}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchStatus();
    }
  };

  const stopLearner = async () => {
    const res = await fetch("/api/v1/kudos/learn/stop", { method: "POST", headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchStatus();
    }
  };

  const triggerNow = async () => {
    setTriggering(true);
    setMessage({ text: "⏳ Learning cycle running... This may take a minute.", type: "success" });
    const res = await fetch("/api/v1/kudos/learn/trigger", { method: "POST", headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchStatus();
    }
    setTriggering(false);
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold">🚀 KUDOS Auto-Learner</h2>
          <p className="text-gray-600">Automatically learns from everything — connectors, web, archive, social, search</p>
        </div>
        <div className="flex gap-2">
          <button onClick={triggerNow} disabled={triggering}
            className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
            {triggering ? "⏳ Learning..." : "⚡ Learn Now"}
          </button>
          {status?.running ? (
            <button onClick={stopLearner} className="bg-red-100 text-red-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-200">
              ⏹ Stop Auto-Learning
            </button>
          ) : (
            <div className="flex gap-1">
              <button onClick={() => startLearner(30)} className="bg-green-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-green-700">
                ▶ Start (30m)
              </button>
              <button onClick={() => startLearner(60)} className="bg-green-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-green-600">
                ▶ Start (1h)
              </button>
            </div>
          )}
        </div>
      </div>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>{message.text}</div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : status && (
        <div className="space-y-6">
          {/* Status Banner */}
          <div className={`p-4 rounded-xl border ${status.running ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"}`}>
            <div className="flex justify-between items-center">
              <div>
                <p className={`font-semibold ${status.running ? "text-green-700" : "text-gray-500"}`}>
                  {status.running ? "🟢 Auto-Learner Active" : "⚪ Auto-Learner Stopped"}
                </p>
                {status.running && <p className="text-sm text-green-600">Learning every {status.interval_minutes} minutes from all sources</p>}
                {status.last_run && <p className="text-xs text-gray-500 mt-1">Last run: {new Date(status.last_run).toLocaleString()}</p>}
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold text-primary">{status.stats.total_items_learned}</p>
                <p className="text-xs text-gray-500">Total items learned</p>
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { label: "Total Runs", value: status.stats.total_runs, icon: "🔄", color: "text-blue-600" },
              { label: "Connectors", value: status.stats.connectors_synced, icon: "🔌", color: "text-green-600" },
              { label: "Web Pages", value: status.stats.web_pages, icon: "🌐", color: "text-purple-600" },
              { label: "Archive", value: status.stats.archive_items, icon: "🕰️", color: "text-amber-600" },
              { label: "Social", value: status.stats.social_items, icon: "🗣️", color: "text-pink-600" },
              { label: "Searches", value: status.stats.search_queries_learned, icon: "🔍", color: "text-cyan-600" },
            ].map((s) => (
              <div key={s.label} className="bg-white rounded-xl border shadow p-4 text-center">
                <p className="text-2xl mb-1">{s.icon}</p>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-gray-500">{s.label}</p>
              </div>
            ))}
          </div>

          {/* What KUDOS Learns From */}
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">🧠 What KUDOS Learns From</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { icon: "🔌", title: "Connectors", desc: "32 sources synced automatically" },
                { icon: "🌐", title: "Web Search", desc: "DuckDuckGo on trending topics" },
                { icon: "📚", title: "Wikipedia", desc: "Featured articles on key topics" },
                { icon: "🤖", title: "Reddit", desc: "Popular posts from 9 subreddits" },
                { icon: "🕰️", title: "Archive.org", desc: "Historical texts and documents" },
                { icon: "🗣️", title: "Social Skills", desc: "Conversation and empathy skills" },
                { icon: "🕷️", title: "Web Crawls", desc: "HN, DEV, Stack Overflow, Wikipedia" },
                { icon: "📊", title: "Search Queries", desc: "Learns from what users ask" },
              ].map((s) => (
                <div key={s.title} className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xl mb-1">{s.icon}</p>
                  <p className="font-medium text-sm">{s.title}</p>
                  <p className="text-xs text-gray-500">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Log */}
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">📋 Activity Log</h3>
            {status.recent_log.length === 0 ? (
              <p className="text-gray-500 text-sm">No activity yet. Start the auto-learner or trigger a manual cycle.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {status.recent_log.slice().reverse().map((entry, i) => (
                  <div key={i} className="flex justify-between items-center text-sm border-b pb-2">
                    <div>
                      <span className="font-mono bg-gray-100 px-2 py-0.5 rounded mr-2 text-xs">{entry.action}</span>
                      <span className="text-gray-600">{entry.details}</span>
                      {entry.items > 0 && <span className="text-green-600 ml-1">(+{entry.items})</span>}
                    </div>
                    <span className="text-xs text-gray-400">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
