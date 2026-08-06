import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Stats {
  total_documents: number;
  approved_documents: number;
  total_chunks: number;
  total_web_knowledge: number;
  total_conversations: number;
  total_messages: number;
}
interface PendingDoc {
  id: number;
  title: string;
  uploaded_by: number;
  chunks: number;
}
interface PendingWeb {
  id: number;
  url: string;
  title: string;
  learned_by: number;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosAdmin() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [pending, setPending] = useState<{ pending_documents: PendingDoc[]; pending_web: PendingWeb[] }>({
    pending_documents: [],
    pending_web: [],
  });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statsRes, pendingRes] = await Promise.all([
        fetch("/api/v1/kudos/admin/stats", { headers: getAuthHeader() }),
        fetch("/api/v1/kudos/admin/pending", {
          method: "POST",
          headers: getAuthHeader(),
        }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (pendingRes.ok) setPending(await pendingRes.json());
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const approveAllDocs = async () => {
    const res = await fetch("/api/v1/kudos/admin/approve-all-documents", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage(`✅ Approved ${data.approved} documents`);
      fetchAll();
    }
  };

  const approveAllWeb = async () => {
    const res = await fetch("/api/v1/kudos/admin/approve-all-web", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage(`✅ Approved ${data.approved} web pages`);
      fetchAll();
    }
  };

  const approveDoc = async (id: number) => {
    await fetch(`/api/v1/kudos/documents/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ is_approved: true }),
    });
    fetchAll();
  };

  const approveWeb = async (id: number) => {
    await fetch(`/api/v1/kudos/learn/web/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ is_approved: true }),
    });
    fetchAll();
  };

  const deleteDoc = async (id: number) => {
    if (!confirm("Delete this document from KUDOS's knowledge?")) return;
    await fetch(`/api/v1/kudos/documents/${id}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    fetchAll();
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">⚙️ KUDOS Admin Panel</h2>
      <p className="text-gray-600 mb-8">
        Superadmin controls — manage KUDOS&apos;s knowledge base, approve content, view stats
      </p>

      {message && (
        <div className="mb-6 p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          {message}
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
              {[
                { label: "Documents", value: stats.total_documents, icon: "📄" },
                { label: "Approved", value: stats.approved_documents, icon: "✅" },
                { label: "Chunks", value: stats.total_chunks, icon: "🧩" },
                { label: "Web Pages", value: stats.total_web_knowledge, icon: "🌐" },
                { label: "Conversations", value: stats.total_conversations, icon: "💬" },
                { label: "Messages", value: stats.total_messages, icon: "📨" },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-xl border p-4 text-center">
                  <p className="text-2xl mb-1">{s.icon}</p>
                  <p className="text-2xl font-bold text-primary">{s.value}</p>
                  <p className="text-xs text-gray-500">{s.label}</p>
                </div>
              ))}
            </div>
          )}

          {/* Quick actions */}
          <div className="flex gap-3 mb-8">
            <button
              onClick={approveAllDocs}
              className="bg-green-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-green-700 transition"
            >
              ✅ Approve All Documents
            </button>
            <button
              onClick={approveAllWeb}
              className="bg-green-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-green-700 transition"
            >
              ✅ Approve All Web Pages
            </button>
            <button
              onClick={fetchAll}
              className="bg-white border px-5 py-2 rounded-lg font-medium hover:bg-gray-50 transition"
            >
              🔄 Refresh
            </button>
          </div>

          {/* Pending documents */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold text-lg mb-4">
                📄 Pending Documents ({pending.pending_documents.length})
              </h3>
              {pending.pending_documents.length === 0 ? (
                <p className="text-gray-500 text-sm bg-white rounded-lg border p-4">
                  No pending documents ✨
                </p>
              ) : (
                <div className="space-y-3">
                  {pending.pending_documents.map((doc) => (
                    <div key={doc.id} className="bg-white rounded-lg border p-4 flex justify-between items-center">
                      <div>
                        <p className="font-medium">{doc.title}</p>
                        <p className="text-xs text-gray-400">
                          {doc.chunks} chunks • Uploaded by user #{doc.uploaded_by}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => approveDoc(doc.id)}
                          className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => deleteDoc(doc.id)}
                          className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="font-semibold text-lg mb-4">
                🌐 Pending Web Pages ({pending.pending_web.length})
              </h3>
              {pending.pending_web.length === 0 ? (
                <p className="text-gray-500 text-sm bg-white rounded-lg border p-4">
                  No pending web pages ✨
                </p>
              ) : (
                <div className="space-y-3">
                  {pending.pending_web.map((item) => (
                    <div key={item.id} className="bg-white rounded-lg border p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium">{item.title}</p>
                          <p className="text-xs text-gray-400 truncate">{item.url}</p>
                        </div>
                        <button
                          onClick={() => approveWeb(item.id)}
                          className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200 ml-2"
                        >
                          Approve
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </Layout>
  );
}
