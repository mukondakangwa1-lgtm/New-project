import { useState, useRef, FormEvent } from "react";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosUpload() {
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<any[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useState(() => {
    fetch("/api/v1/kudos/documents", { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && setDocs(d))
      .catch(() => {});
  });

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!fileRef.current?.files?.[0]) return;
    setLoading(true);
    setMessage({ text: "", type: "" });

    const formData = new FormData();
    formData.append("title", title);
    formData.append("tags", tags);
    formData.append("file", fileRef.current.files[0]);

    try {
      const res = await fetch("/api/v1/kudos/documents/upload", {
        method: "POST",
        headers: getAuthHeader(),
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setMessage({
          text: `✅ Uploaded "${data.title}" — ${data.chunk_count} chunks created. ${data.is_approved ? "Auto-approved." : "Pending admin approval."}`,
          type: "success",
        });
        setTitle("");
        setTags("");
        if (fileRef.current) fileRef.current.value = "";

        // Refresh list
        const listRes = await fetch("/api/v1/kudos/documents", { headers: getAuthHeader() });
        if (listRes.ok) setDocs(await listRes.json());
      } else {
        const data = await res.json();
        setMessage({ text: `❌ ${data.detail}`, type: "error" });
      }
    } catch (err: any) {
      setMessage({ text: `❌ ${err.message}`, type: "error" });
    }
    setLoading(false);
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">📄 Teach KUDOS — Upload Document</h2>
      <p className="text-gray-600 mb-8">
        Upload text, PDF, or Word documents. KUDOS will read, chunk, and learn from them.
      </p>

      {message.text && (
        <div
          className={`mb-6 p-4 rounded-lg text-sm ${
            message.type === "success"
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-red-50 border border-red-200 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold text-lg mb-4">Upload New Document</h3>
          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Document Title *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                placeholder="e.g. CS101 Lecture Notes Week 3"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">File *</label>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.md,.pdf,.docx,.doc,.csv,.json,.py,.js,.html,.css"
                className="w-full rounded border px-3 py-2 text-sm"
                required
              />
              <p className="text-xs text-gray-400 mt-1">
                Supported: .txt, .md, .pdf, .docx, .csv, .json, .py, .js (max 10MB)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm"
                placeholder="cs101, lecture, week3"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-white py-2 rounded-lg font-medium hover:bg-blue-800 disabled:opacity-50"
            >
              {loading ? "Processing..." : "📄 Upload & Teach KUDOS"}
            </button>
          </form>
        </div>

        <div>
          <h3 className="font-semibold text-lg mb-4">Knowledge Base ({docs.length} documents)</h3>
          {docs.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border">
              <p className="text-4xl mb-3">📭</p>
              <p className="text-gray-500">No documents uploaded yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {docs.map((doc: any) => (
                <div key={doc.id} className="bg-white rounded-lg border p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-medium">{doc.title}</h4>
                      <p className="text-xs text-gray-400">
                        {doc.filename} • {doc.chunk_count} chunks • {doc.file_type}
                      </p>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        doc.is_approved
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {doc.is_approved ? "Approved" : "Pending"}
                    </span>
                  </div>
                  {doc.summary && (
                    <p className="text-xs text-gray-500 mt-2 line-clamp-2">{doc.summary}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
