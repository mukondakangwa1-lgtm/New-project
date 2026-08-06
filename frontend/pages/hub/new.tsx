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
  const [form, setForm] = useState({
    title: "",
    description: "",
    storage_url: "",
    storage_type: "link",
    content_type: "",
    thumbnail_url: "",
    is_public: true,
    tags: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/social/", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify(form),
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

  const detectType = (url: string) => {
    if (url.includes("drive.google.com")) return "gdrive";
    if (url.includes("dropbox.com")) return "dropbox";
    if (url.includes("onedrive.live.com") || url.includes("sharepoint.com")) return "onedrive";
    if (url.includes("youtube.com") || url.includes("youtu.be")) return "youtube";
    if (url.includes("amazonaws.com") || url.includes("s3.")) return "s3";
    if (url.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i)) return "image";
    if (url.match(/\.(mp4|mov|avi|mkv|webm)$/i)) return "video";
    if (url.match(/\.(pdf|doc|docx|ppt|pptx)$/i)) return "document";
    return "link";
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold mb-2">📤 Share a Resource</h2>
        <p className="text-gray-600 mb-8">
          Link to any external storage — files are never stored on this platform
        </p>

        <div className="bg-white rounded-xl border shadow p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium mb-1">Title *</label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                placeholder="My lecture notes"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Resource URL *</label>
              <input
                type="url"
                value={form.storage_url}
                onChange={(e) => {
                  const url = e.target.value;
                  setForm({
                    ...form,
                    storage_url: url,
                    storage_type: detectType(url),
                  });
                }}
                className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                placeholder="https://drive.google.com/file/d/..."
                required
              />
              <p className="text-xs text-gray-400 mt-1">
                Supports Google Drive, Dropbox, OneDrive, S3, YouTube, or any public URL
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Storage Type</label>
                <select
                  value={form.storage_type}
                  onChange={(e) => setForm({ ...form, storage_type: e.target.value })}
                  className="w-full rounded border px-3 py-2 text-sm"
                >
                  <option value="link">🔗 Generic Link</option>
                  <option value="gdrive">📁 Google Drive</option>
                  <option value="dropbox">📦 Dropbox</option>
                  <option value="onedrive">☁️ OneDrive</option>
                  <option value="s3">🪣 Amazon S3</option>
                  <option value="youtube">▶️ YouTube</option>
                  <option value="image">🖼️ Image</option>
                  <option value="video">🎬 Video</option>
                  <option value="document">📄 Document</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Content Type</label>
                <select
                  value={form.content_type}
                  onChange={(e) => setForm({ ...form, content_type: e.target.value })}
                  className="w-full rounded border px-3 py-2 text-sm"
                >
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
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                rows={3}
                placeholder="What's in this resource?"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Thumbnail URL (optional)</label>
              <input
                type="url"
                value={form.thumbnail_url}
                onChange={(e) => setForm({ ...form, thumbnail_url: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
                placeholder="https://example.com/thumb.jpg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
              <input
                type="text"
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                className="w-full rounded border px-3 py-2 text-sm"
                placeholder="cs101, notes, midterm"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_public"
                checked={form.is_public}
                onChange={(e) => setForm({ ...form, is_public: e.target.checked })}
                className="rounded"
              />
              <label htmlFor="is_public" className="text-sm">
                Make this post public (anyone can view)
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-white py-3 rounded-lg font-medium hover:bg-blue-800 transition disabled:opacity-50"
            >
              {loading ? "Sharing..." : "📤 Share Resource"}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  );
}
