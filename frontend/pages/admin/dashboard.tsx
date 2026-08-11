import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { getAuthHeader } from "@/lib/api";
import Layout from "@/components/Layout";
import { ProgressBar, useLongProcess } from "@/components/ProgressBar";

function fmtBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function SuperadminDashboard() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [brainLog, setBrainLog] = useState<any[]>([]);
  const [brainThoughts, setBrainThoughts] = useState<any[]>([]);
  const [chatMessages, setChatMessages] = useState<{from: string; message: string; action?: string}[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [pendingUsers, setPendingUsers] = useState<any[]>([]);
  const [pendingStudents, setPendingStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [chatSending, setChatSending] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);
  const chatProgress = useLongProcess();

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight);
  }, [chatMessages]);

  const fetchAll = async () => {
    try {
      const [dashRes, logRes, thoughtsRes, pendingRes, studentsRes] = await Promise.all([
        fetch("/api/v1/superadmin/dashboard", { headers: getAuthHeader() }),
        fetch("/api/v1/superadmin/brain/log?limit=20", { headers: getAuthHeader() }),
        fetch("/api/v1/superadmin/brain/thoughts?limit=15", { headers: getAuthHeader() }),
        fetch("/api/v1/superadmin/users/pending", { headers: getAuthHeader() }),
        fetch("/api/v1/superadmin/students/pending", { headers: getAuthHeader() }),
      ]);
      if (dashRes.ok) setDashboard(await dashRes.json());
      else setDashboard(null);
      if (pendingRes.ok) setPendingUsers(await pendingRes.json());
      if (studentsRes.ok) setPendingStudents(await studentsRes.json());
      if (logRes.ok) {
        const d = await logRes.json();
        setBrainLog(d.log || []);
      }
      if (thoughtsRes.ok) {
        const d = await thoughtsRes.json();
        setBrainThoughts(d.thoughts || []);
      }
    } catch {}
    setLoading(false);
  };

  const approveUser = async (userId: number) => {
    const headers = getAuthHeader();
    const res = await fetch(`/api/v1/superadmin/users/${userId}/approve`, {
      method: "POST",
      headers,
    });
    if (res.ok) fetchAll();
  };

  const approveStudent = async (userId: number) => {
    await fetch(`/api/v1/superadmin/students/${userId}/approve`, { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  const rejectStudent = async (userId: number) => {
    await fetch(`/api/v1/superadmin/students/${userId}/reject`, { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatSending) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatSending(true);
    chatProgress.start("Asking KUDOS…");
    setChatMessages((prev) => [...prev, { from: "Superadmin", message: msg }]);

    try {
      const res = await fetch("/api/v1/superadmin/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ message: msg }),
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages((prev) => [...prev, { from: data.from || "KUDOS", message: data.message, action: data.action }]);
        fetchAll();
      }
    } finally {
      chatProgress.stop();
      setChatSending(false);
    }
  };

  const activateBrain = async () => {
    await fetch("/api/v1/superadmin/brain/start", { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  const deactivateBrain = async () => {
    await fetch("/api/v1/superadmin/brain/stop", { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  const startAutoLearn = async () => {
    await fetch("/api/v1/superadmin/auto-learn/start?interval_minutes=30", { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  const triggerLearn = async () => {
    await fetch("/api/v1/superadmin/auto-learn/trigger", { method: "POST", headers: getAuthHeader() });
    fetchAll();
  };

  if (loading) return <Layout><p className="text-gray-500">Loading superadmin dashboard...</p></Layout>;

  if (!dashboard) {
    return (
      <Layout>
        <div className="text-center py-16">
          <p className="text-6xl mb-4">🔒</p>
          <h2 className="text-2xl font-bold mb-2">Superadmin Access Required</h2>
          <p className="text-gray-600 mb-6">Please login as admin to access the dashboard</p>
          <a href="/login" className="bg-primary text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-800 inline-block">
            Login as Superadmin
          </a>
        </div>
      </Layout>
    );
  }

  const identity = dashboard?.identity;
  const brain = dashboard?.brain;
  const platform = dashboard?.platform;
  const storage = dashboard?.storage;
  const autoLearn = dashboard?.auto_learner;

  return (
    <Layout>
      <div className="mb-6">
        <h2 className="text-2xl md:text-3xl font-bold">👑 Superadmin Dashboard</h2>
        <p className="text-gray-600 text-sm">Complete control over {identity?.name || "KUDOS"} and the platform</p>
      </div>

      <div className="space-y-6">
        {/* Pending registrations */}
        {pendingUsers.length > 0 && (
          <div className="bg-white rounded-xl border p-4 md:p-5">
            <h3 className="font-semibold mb-3">
              🕐 Pending approvals ({pendingUsers.length})
            </h3>
            <div className="space-y-2">
              {pendingUsers.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center justify-between gap-4 text-sm border-b last:border-0 pb-2"
                >
                  <div>
                    <p className="font-medium">{u.full_name}</p>
                    <p className="text-gray-500">{u.email}</p>
                  </div>
                  <button
                    onClick={() => approveUser(u.id)}
                    className="bg-primary text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-blue-800 transition"
                  >
                    Approve
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Student approvals */}
        {pendingStudents.length > 0 && (
          <div className="bg-white rounded-xl border p-4 md:p-5">
            <h3 className="font-semibold mb-3">
              🎓 Student approvals ({pendingStudents.length})
            </h3>
            <p className="text-xs text-gray-500 mb-3">
              Approve to unlock Courses &amp; Register for this student&apos;s dashboard.
            </p>
            <div className="space-y-2">
              {pendingStudents.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center justify-between gap-4 text-sm border-b last:border-0 pb-2"
                >
                  <div>
                    <p className="font-medium">{u.full_name}</p>
                    <p className="text-gray-500">{u.email}</p>
                    <p className="text-xs text-purple-600">🏫 {u.school}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => rejectStudent(u.id)}
                      className="border border-gray-300 text-gray-600 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-50 transition"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => approveStudent(u.id)}
                      className="bg-primary text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-blue-800 transition"
                    >
                      Approve
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KUDOS Identity Banner */}
        {identity && (
          <div className="bg-gradient-to-r from-purple-900 to-indigo-900 rounded-xl p-4 md:p-6 text-white">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <h3 className="text-2xl md:text-3xl font-bold">🤖 {identity.name}</h3>
                <p className="text-purple-200 text-sm">{identity.full_name}</p>
                <p className="text-purple-300 text-xs mt-1">"{identity.motto}"</p>
              </div>
              <div className="flex gap-2">
                {brain?.active ? (
                  <button onClick={deactivateBrain} className="bg-red-500/20 hover:bg-red-500/30 px-4 py-2 rounded text-sm font-medium">
                    🧠 Stop Brain
                  </button>
                ) : (
                  <button onClick={activateBrain} className="bg-green-500/20 hover:bg-green-500/30 px-4 py-2 rounded text-sm font-medium">
                    🧠 Activate Brain
                  </button>
                )}
                <button onClick={startAutoLearn} className="bg-blue-500/20 hover:bg-blue-500/30 px-4 py-2 rounded text-sm font-medium">
                  🚀 Auto-Learn
                </button>
                <button onClick={triggerLearn} className="bg-yellow-500/20 hover:bg-yellow-500/30 px-4 py-2 rounded text-sm font-medium">
                  ⚡ Learn Now
                </button>
              </div>
            </div>

            {/* Body Parts */}
            {identity.body && (
              <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mt-4">
                {Object.entries(identity.body).map(([part, info]: [string, any]) => (
                  <div key={part} className="bg-white/10 rounded-lg p-2 text-center">
                    <p className="text-lg">{part === "brain" ? "🧠" : part === "eyes" ? "👁️" : part === "ears" ? "👂" : part === "mouth" ? "👄" : part === "hands" ? "🤲" : part === "legs" ? "🦵" : part === "heart" ? "❤️" : "✨"}</p>
                    <p className="text-xs text-purple-200 capitalize">{part}</p>
                    <span className={`w-1.5 h-1.5 rounded-full inline-block ${info.status === "active" ? "bg-green-400" : "bg-red-400"}`} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Platform Stats */}
        {platform && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {[
              { label: "Users", value: platform.users, icon: "👥" },
              { label: "Courses", value: platform.courses, icon: "📚" },
              { label: "Sessions", value: platform.sessions, icon: "📋" },
              { label: "Documents", value: platform.documents, icon: "📄" },
              { label: "Knowledge", value: platform.web_knowledge, icon: "🌐" },
              { label: "Conversations", value: platform.conversations, icon: "💬" },
              { label: "Messages", value: platform.messages, icon: "📨" },
              { label: "Assignments", value: platform.assignments, icon: "📝" },
              { label: "Submissions", value: platform.submissions, icon: "📤" },
              { label: "Exam Attempts", value: platform.exam_attempts, icon: "🎓" },
              { label: "Notifications", value: platform.notifications, icon: "🔔" },
              { label: "Attendance", value: platform.attendance_records, icon: "✅" },
            ].map((s) => (
              <div key={s.label} className="bg-white rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">{s.icon}</p>
                <p className="text-lg font-bold text-primary">{s.value}</p>
                <p className="text-xs text-gray-500">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Storage Usage */}
        {storage && (
          <div className="bg-white rounded-xl border p-4 md:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h3 className="font-semibold">💾 Storage Usage</h3>
              <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-500">
                backend: {storage.usage?.backend || "unknown"}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">🗄️</p>
                <p className="text-lg font-bold text-primary">{fmtBytes(storage.usage?.total_bytes || 0)}</p>
                <p className="text-xs text-gray-500">Objects used</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">🗂️</p>
                <p className="text-lg font-bold text-primary">{storage.usage?.total_objects || 0}</p>
                <p className="text-xs text-gray-500">Total objects</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">📦</p>
                <p className="text-lg font-bold text-primary">{fmtBytes(storage.db_size_bytes || 0)}</p>
                <p className="text-xs text-gray-500">Database size</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">📄</p>
                <p className="text-lg font-bold text-primary">{storage.usage?.by_prefix?.["docs/"]?.objects || 0}</p>
                <p className="text-xs text-gray-500">Documents</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">🎙️</p>
                <p className="text-lg font-bold text-primary">{storage.usage?.by_prefix?.["audio/"]?.objects || 0}</p>
                <p className="text-xs text-gray-500">Audio files</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">👤</p>
                <p className="text-lg font-bold text-primary">{storage.usage?.by_prefix?.["avatars/"]?.objects || 0}</p>
                <p className="text-xs text-gray-500">Avatars</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">🛟</p>
                <p className="text-lg font-bold text-primary">{storage.usage?.by_prefix?.["backups/"]?.objects || 0}</p>
                <p className="text-xs text-gray-500">Backups</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">💽</p>
                <p className="text-lg font-bold text-primary">{fmtBytes(storage.usage?.by_prefix?.["docs/"]?.bytes || 0)}</p>
                <p className="text-xs text-gray-500">Docs storage</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-xl mb-1">🎧</p>
                <p className="text-lg font-bold text-primary">{fmtBytes(storage.usage?.by_prefix?.["audio/"]?.bytes || 0)}</p>
                <p className="text-xs text-gray-500">Audio storage</p>
              </div>
            </div>
          </div>
        )}

        {/* Brain Status + Secure Chat */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Brain Activity */}
          <div className="bg-white rounded-xl border shadow p-4 md:p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-lg">🧠 Brain Activity</h3>
              <span className={`text-xs px-2 py-1 rounded ${brain?.active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {brain?.active ? "Active" : "Inactive"} • {brain?.cycles || 0} cycles
              </span>
            </div>

            {/* Recent Thoughts */}
            <div className="space-y-2 max-h-48 overflow-y-auto mb-4">
              {brainThoughts.length === 0 ? (
                <p className="text-gray-500 text-sm">No thoughts yet. Activate the brain!</p>
              ) : (
                brainThoughts.slice().reverse().map((t, i) => (
                  <div key={i} className="text-xs border-b pb-1">
                    <span className="font-mono bg-purple-50 text-purple-700 px-1 rounded">{t.category}</span>
                    <span className="ml-2 text-gray-600">{t.thought}</span>
                  </div>
                ))
              )}
            </div>

            {/* Activity Log */}
            <h4 className="font-medium text-sm mb-2 text-gray-500">Activity Log</h4>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {brainLog.slice().reverse().map((l, i) => (
                <div key={i} className="text-xs text-gray-500">
                  <span className="font-mono">{l.action}</span>: {l.thought}
                </div>
              ))}
            </div>
          </div>

          {/* Secure Chat */}
          <div className="bg-gray-900 rounded-xl overflow-hidden flex flex-col">
            <div className="bg-gray-800 px-4 py-3 flex justify-between items-center">
              <div>
                <p className="text-green-400 font-mono text-sm font-semibold">🔒 Secure Channel: Superadmin ↔ {identity?.name || "KUDOS"}</p>
                <p className="text-gray-500 text-xs">End-to-end • Admin-only • Logged</p>
              </div>
              <span className="w-3 h-3 bg-green-400 rounded-full animate-pulse" />
            </div>

            <div ref={chatRef} className="flex-1 p-4 overflow-y-auto max-h-80 space-y-3">
              {chatMessages.length === 0 && (
                <div className="text-center text-gray-500 py-8">
                  <p className="text-3xl mb-2">🔒</p>
                  <p className="text-sm">Secure channel established</p>
                  <p className="text-xs mt-1">Type a message to {identity?.name || "KUDOS"}</p>
                  <p className="text-xs mt-2 text-gray-600">Try: &quot;start learning&quot; • &quot;status&quot; • &quot;help&quot;</p>
                </div>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.from === "Superadmin" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.from === "Superadmin"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-green-400"
                  }`}>
                    <p className="text-xs font-bold mb-1 opacity-70">{msg.from}</p>
                    <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                    {msg.action && <p className="text-xs mt-1 opacity-50">[{msg.action}]</p>}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex border-t border-gray-700">
              <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendChat()}
                className="flex-1 bg-transparent text-green-400 font-mono text-sm px-4 py-3 outline-none"
                placeholder={`Message ${identity?.name || "KUDOS"}...`}
                disabled={chatSending} />
              <button onClick={sendChat} disabled={chatSending}
                className="bg-green-600 text-white px-6 py-3 text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                {chatSending ? "Thinking..." : "Send"}
              </button>
            </div>
            {chatProgress.active && (
              <div className="border-t border-gray-700 px-4 py-2">
                <ProgressBar label={chatProgress.label} elapsed={chatProgress.elapsed} />
              </div>
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { href: "/kudos/guardian", icon: "🛡️", label: "Guardian" },
            { href: "/kudos/agent", icon: "🤖", label: "Code Agent" },
            { href: "/kudos/autolearn", icon: "🚀", label: "Auto-Learner" },
            { href: "/kudos/maps", icon: "🗺️", label: "Maps" },
            { href: "/kudos/networks", icon: "📡", label: "Networks" },
            { href: "/kudos/llm", icon: "✨", label: "LLM Config" },
            { href: "/kudos/connect", icon: "🔌", label: "Connectors" },
            { href: "/kudos/archive", icon: "🕰️", label: "Archive" },
            { href: "/root", icon: "👑", label: "Root Terminal" },
          ].map((link) => (
            <a key={link.href} href={link.href}
              className="bg-white rounded-lg border p-4 text-center hover:shadow-md transition block">
              <p className="text-2xl mb-1">{link.icon}</p>
              <p className="text-sm font-medium">{link.label}</p>
            </a>
          ))}
        </div>
      </div>
    </Layout>
  );
}
