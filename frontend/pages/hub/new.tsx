import { useState, FormEvent } from "react";
import { useRouter } from "next/router";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function NewPost() {
  const router = useRouter();
  const [mode, setMode] = useState<"upload" | "link">("upload");
  const [form, setForm] = useState({
    title: "",
    description: "",
    storage_url: "",
    storage_type: "s3",
    content_type: "",
    thumbnail_url: "",
    is_public: true,
    tags: "",
  });
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLinkSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // normalize dead types to link/s3
      const payload = { ...form, storage_type: form.storage_type === "minio" ? "s3" : form.storage_type };
      const res = await fetch("/api/v1/social/", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to create post");
      }
      router.push("/hub/feed");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    if (!form.title) {
      setError("Title required");
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({
        title: form.title,
        description: form.description,
        tags: form.tags,
        is_public: String(form.is_public),
      });
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/v1/social/upload?${params.toString()}`, {
        method: "POST",
        headers: getAuthHeader(),
        body: fd,
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Upload failed - is MinIO running? docker-compose up -d minio");
      }
      router.push("/hub/feed");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold mb-2">📤 Share a Resource</h2>
        <p className="text-gray-600 mb-6">
          Upload to <span className="font-semibold">MinIO/S3 (private, AES256)</span> or link external URL — SQLite/Postgres stores metadata
        </p>

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMode("upload")}
            className={`flex-1 py-2 rounded-lg font-medium border ${mode === "upload" ? "bg-primary text-white border-primary" : "bg-white text-gray-700 hover:bg-gray-50"}`}
          >
            📦 Upload to S3 (MinIO)
          </button>
          <button
            onClick={() => setMode("link")}
            className={`flex-1 py-2 rounded-lg font-medium border ${mode === "link" ? "bg-primary text-white border-primary" : "bg-white text-gray-700 hover:bg-gray-50"}`}
          >
            🔗 External Link
          </button>
        </div>

        <div className="bg-white rounded-xl border shadow p-6 md:p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>
          )}

          {mode === "upload" ? (
            <form onSubmit={handleUpload} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-1">Title *</label>
                <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" placeholder="My lecture notes" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">File * (250MB max)</label>
                <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="w-full rounded border px-3 py-2 text-sm" required />
                <p className="text-xs text-gray-400 mt-1">Stored in MinIO `campus-media/posts/...` (private). Free, secure, works offline. Backend: <code>POST /api/v1/social/upload</code></p>
                {file && <p className="text-xs text-green-600 mt-1">Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={3} placeholder="What's in this resource?" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
                <input type="text" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="cs101, notes, midterm" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="pub1" checked={form.is_public} onChange={(e) => setForm({ ...form, is_public: e.target.checked })} className="rounded" />
                <label htmlFor="pub1" className="text-sm">Make public (anyone can view)</label>
              </div>
              <button type="submit" disabled={loading} className="w-full bg-primary text-white py-3 rounded-lg font-medium hover:bg-blue-800 transition disabled:opacity-50">
                {loading ? "Uploading to MinIO..." : "📦 Upload to S3"}
              </button>
              <p className="text-xs text-center text-gray-400">Requires MinIO: <code>docker-compose up -d minio</code> or Download from min.io/download</p>
            </form>
          ) : (
            <form onSubmit={handleLinkSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-1">Title *</label>
                <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" placeholder="My lecture notes" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Resource URL *</label>
                <input type="url" value={form.storage_url} onChange={(e) => setForm({ ...form, storage_url: e.target.value })} className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" placeholder="https://example.com/file.pdf or https://youtube.com/watch?v=..." required />
                <p className="text-xs text-gray-400 mt-1">For files you host elsewhere. Prefer <b>Upload to S3</b> for private secure storage.</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Storage Type</label>
                  <select value={form.storage_type} onChange={(e) => setForm({ ...form, storage_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm">
                    <option value="s3">🪣 S3/MinIO</option>
                    <option value="link">🔗 Generic Link</option>
                    <option value="youtube">▶️ YouTube</option>
                    <option value="image">🖼️ Image</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Content Type</label>
                  <select value={form.content_type} onChange={(e) => setForm({ ...form, content_type: e.target.value })} className="w-full rounded border px-3 py-2 text-sm">
                    <option value="">Auto-detect</option>
                    <option value="image">Image</option>
                    <option value="video">Video</option>
                    <option value="document">Document</option>
                    <option value="audio">Audio</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" rows={3} placeholder="What's in this resource?" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Thumbnail URL (optional)</label>
                <input type="url" value={form.thumbnail_url} onChange={(e) => setForm({ ...form, thumbnail_url: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="https://example.com/thumb.jpg" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tags</label>
                <input type="text" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="cs101, notes, midterm" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="pub2" checked={form.is_public} onChange={(e) => setForm({ ...form, is_public: e.target.checked })} className="rounded" />
                <label htmlFor="pub2" className="text-sm">Make public</label>
              </div>
              <button type="submit" disabled={loading} className="w-full bg-primary text-white py-3 rounded-lg font-medium hover:bg-blue-800 transition disabled:opacity-50">
                {loading ? "Sharing..." : "🔗 Share Link"}
              </button>
            </form>
          )}
        </div>
      </div>
    </Layout>
  );
}
