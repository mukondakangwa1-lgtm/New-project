import { useState, useEffect, useCallback } from "react";
import { getAuthHeader } from "@/lib/api";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";

interface LibraryItem {
  key: string;
  kind: string;
  title: string;
  subtitle: string;
  preview_url: string;
  url: string;
  meta: string;
  order: string;
  icon: string;
}

const KIND_ICONS: Record<string, string> = {
  document: "📄",
  video: "🎬",
  audio: "🎵",
};

export default function Library() {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<LibraryItem | null>(null);

  const fetchLibrary = useCallback(async (q = query, k = kind) => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "40" });
    if (q.trim()) params.set("q", q.trim());
    if (k) params.set("kind", k);
    try {
      const res = await fetch(`/api/v1/library/?${params.toString()}`, { headers: getAuthHeader() });
      if (res.ok) {
        const data = await res.json();
        setItems(Array.isArray(data.items) ? data.items : []);
      } else {
        setItems([]);
      }
    } catch {
      setItems([]);
    }
    setLoading(false);
  }, [query, kind]);

  useEffect(() => {
    fetchLibrary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  const saveProgress = async (item: LibraryItem) => {
    try {
      await fetch("/api/v1/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({
          content_key: item.key,
          kind: item.kind === "audio" ? "audio" : item.kind === "document" ? "book" : "movie",
          title: item.title,
          url: item.url,
          source: "library",
          position_pct: item.kind === "document" ? 0 : 5,
        }),
      });
    } catch {}
  };

  const openPreview = (item: LibraryItem) => {
    saveProgress(item);
    setPreview(item);
  };

  return (
    <RequireRole roles={["user", "student", "admin"]} redirectTo="/kudos">
      <Layout>
        <h2 className="text-3xl font-bold mb-2">📚 Smart Library</h2>
        <p className="text-gray-600 mb-6">
          The ordered campus collection — documents, books, audio &amp; video. Material previews here, in the
          library.
        </p>

        {/* Searchbar */}
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchLibrary()}
            placeholder="Search the library..."
            className="flex-1 rounded-xl border px-4 py-3 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
          />
          <button
            onClick={() => fetchLibrary()}
            disabled={loading}
            className="bg-primary text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-800 disabled:opacity-50"
          >
            {loading ? "Searching..." : "🔍 Search"}
          </button>
        </div>

        {/* Kind filter */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {[
            { id: "", label: "All" },
            { id: "document", label: "📄 Documents" },
            { id: "video", label: "🎬 Video" },
            { id: "audio", label: "🎵 Audio" },
          ].map((k) => (
            <button
              key={k.id}
              onClick={() => setKind(k.id)}
              className={`px-3 py-1 rounded-full text-sm transition ${
                kind === k.id ? "bg-primary text-white" : "bg-white border text-gray-600 hover:bg-gray-50"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>

        {/* Bookshelf */}
        {loading ? (
          <div className="bookshelf">
            <div className="bookshelf-empty"><span className="inline-block animate-pulse text-lg">Reading the catalogue…</span></div>
          </div>
        ) : items.length === 0 ? (
          <div className="bookshelf">
            <div className="bookshelf-empty">
              <p className="text-4xl mb-2">🪤</p>
              <p className="text-lg font-semibold mb-1">Nothing found</p>
              <p className="text-sm opacity-80">Try different keywords, or browse by kind above.</p>
            </div>
          </div>
        ) : (
          (() => {
            const chunkSize = 14;
            const rows = [];
            for (let i = 0; i < items.length; i += chunkSize) rows.push(items.slice(i, i + chunkSize));
            return (
              <div className="bookshelf">
                {rows.map((row, ri) => (
                  <div key={ri}>
                    <div className="bookshelf-row">
                      {row.map((item, idx) => {
                        const colorClass =
                          item.kind === "document"
                            ? `book-k-document-${(ri * chunkSize + idx) % 5}`
                            : item.kind === "video"
                            ? "book-k-video"
                            : item.kind === "audio"
                            ? "book-k-audio"
                            : "book-k-other";
                        return (
                          <div
                            key={item.key}
                            className={`book ${colorClass}`}
                            onClick={() => openPreview(item)}
                            title={`${item.title} — ${item.subtitle || item.meta || ""}`}
                          >
                            <span className="book-caption">{item.subtitle || item.meta || item.kind}</span>
                            <span className="book-title">{item.title}</span>
                            <span className="book-icon">{item.icon || KIND_ICONS[item.kind] || "📎"}</span>
                          </div>
                        );
                      })}
                    </div>
                    <div className="bookshelf-shelf" />
                  </div>
                ))}
                <p className="bookshelf-shelf-label text-xs text-center pb-2 opacity-80">
                  {items.length} {items.length === 1 ? "item" : "items"} on this shelf
                </p>
              </div>
            );
          })()
        )}

        {/* Preview screen — pops up when you read/listen/watch anything in the library */}
        {preview && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setPreview(null)}>
            <div
              className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden shadow-2xl flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b">
                <div className="min-w-0">
                  <h3 className="font-semibold text-lg truncate">
                    {preview.icon} {preview.title}
                  </h3>
                  <p className="text-xs text-gray-400">{preview.subtitle || preview.meta}</p>
                </div>
                <button
                  onClick={() => setPreview(null)}
                  className="text-gray-500 hover:text-gray-800 text-2xl px-2"
                  aria-label="Close preview"
                >
                  ✕
                </button>
              </div>

              <div className="flex-1 overflow-auto p-6">
                {preview.kind === "document" && preview.preview_url ? (
                  <iframe src={preview.preview_url} title={preview.title} className="w-full h-[60vh] rounded-lg border" />
                ) : preview.kind === "audio" ? (
                  <audio controls src={preview.preview_url} className="w-full" autoPlay />
                ) : preview.preview_url && (preview.preview_url.includes("archive.org/embed") || preview.url) ? (
                  <iframe
                    src={preview.preview_url}
                    title={preview.title}
                    className="w-full h-[60vh] rounded-lg border"
                    allowFullScreen
                  />
                ) : preview.preview_url ? (
                  <a
                    href={preview.preview_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block bg-primary text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-800"
                  >
                    Open in new tab →
                  </a>
                ) : (
                  <p className="text-gray-500">No inline preview available for this item.</p>
                )}
              </div>

              <div className="px-6 py-4 border-t flex items-center justify-between">
                <p className="text-xs text-gray-400">Preview only — this material stays inside the library.</p>
                {preview.url && (
                  <a
                    href={preview.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary text-sm font-medium hover:underline"
                  >
                    Details →
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </Layout>
    </RequireRole>
  );
}
