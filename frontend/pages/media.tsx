import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface Source {
  name: string;
  url: string;
  description: string;
  icon: string;
}
interface SearchResult {
  title: string;
  url: string;
  source: string;
  icon: string;
  description?: string;
  snippet?: string;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function MediaHub() {
  const [sources, setSources] = useState<Record<string, Source[]>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [activeCategory, setActiveCategory] = useState("movies");
  const [activeTab, setActiveTab] = useState<"browse" | "search" | "vlc">("browse");
  const [vlcUrl, setVlcUrl] = useState("");
  const [vlcTitle, setVlcTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    fetch("/api/v1/media/sources")
      .then((r) => r.json())
      .then((d) => setSources(d.sources || {}))
      .catch(() => {});
    setLoading(false);
  }, []);

  const searchMedia = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const [mediaRes, fmhyRes] = await Promise.all([
        fetch(`/api/v1/media/search?query=${encodeURIComponent(searchQuery)}`),
        fetch(`/api/v1/media/fmhy?query=${encodeURIComponent(searchQuery)}`),
      ]);
      const results: SearchResult[] = [];
      if (mediaRes.ok) {
        const d = await mediaRes.json();
        results.push(...(d.results || []));
      }
      if (fmhyRes.ok) {
        const d = await fmhyRes.json();
        results.push(...(d.results || []));
      }
      setSearchResults(results);
    } catch {}
    setSearching(false);
  };

  const openInVlc = (url: string, title: string) => {
    // Try VLC protocol
    const vlcLink = `vlc://${url}`;
    window.open(vlcLink, "_blank");
    // Fallback: open in new tab
    setTimeout(() => {
      if (confirm("If VLC didn't open, click OK to play in browser instead.")) {
        window.open(url, "_blank");
      }
    }, 2000);
  };

  const CATEGORIES = [
    { id: "movies", label: "🎬 Movies", icon: "🎬" },
    { id: "tv", label: "📺 TV Shows", icon: "📺" },
    { id: "anime", label: "🎌 Anime", icon: "🎌" },
    { id: "music", label: "🎵 Music", icon: "🎵" },
    { id: "educational", label: "🎓 Educational", icon: "🎓" },
  ];

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold">🎬 Media Hub</h2>
          <p className="text-gray-600 text-sm">
            Free movies, TV, music & more — powered by FMHY & 1flex
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: "browse" as const, label: "📺 Browse Sources" },
          { id: "search" as const, label: "🔍 Search" },
          { id: "vlc" as const, label: "🎥 VLC Player" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === t.id
                ? "bg-primary text-white"
                : "bg-white border hover:bg-gray-50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "browse" && (
        <div>
          {/* Category Tabs */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition ${
                  activeCategory === cat.id
                    ? "bg-primary text-white"
                    : "bg-white border hover:bg-gray-50"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Source Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(sources[activeCategory] || []).map((source, i) => (
              <div
                key={i}
                className="bg-white rounded-xl border shadow p-5 hover:shadow-lg transition"
              >
                <div className="flex items-start gap-3 mb-3">
                  <span className="text-3xl">{source.icon}</span>
                  <div>
                    <h3 className="font-semibold text-lg">{source.name}</h3>
                    <p className="text-sm text-gray-500">{source.description}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 bg-primary text-white text-center py-2 rounded text-sm font-medium hover:bg-blue-800"
                  >
                    Open Site →
                  </a>
                  <button
                    onClick={() => openInVlc(source.url, source.name)}
                    className="bg-orange-100 text-orange-700 px-3 py-2 rounded text-sm hover:bg-orange-200"
                    title="Open in VLC"
                  >
                    🎥
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* FMHY Link */}
          <div className="mt-8 p-4 bg-purple-50 border border-purple-200 rounded-xl">
            <p className="text-sm text-purple-700">
              <strong>💡 Tip:</strong> Visit{" "}
              <a
                href="https://fmhy.net"
                target="_blank"
                rel="noopener noreferrer"
                className="underline font-semibold"
              >
                fmhy.net
              </a>{" "}
              for the complete directory of free resources — movies, music, books,
              software, and more!
            </p>
          </div>
        </div>
      )}

      {activeTab === "search" && (
        <div>
          {/* Search Bar */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchMedia()}
              className="flex-1 rounded-xl border px-4 py-3 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
              placeholder="Search for movies, shows, music..."
            />
            <button
              onClick={searchMedia}
              disabled={searching || !searchQuery.trim()}
              className="bg-primary text-white px-6 py-3 rounded-xl font-medium hover:bg-blue-800 disabled:opacity-50"
            >
              {searching ? "Searching..." : "🔍 Search"}
            </button>
          </div>

          {/* Search Results */}
          {searchResults.length > 0 ? (
            <div className="space-y-3">
              {searchResults.map((result, i) => (
                <div
                  key={i}
                  className="bg-white rounded-xl border shadow p-4 hover:shadow-md transition"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold">{result.title}</h3>
                      {result.snippet && (
                        <p className="text-sm text-gray-500 mt-1">{result.snippet}</p>
                      )}
                      {result.description && (
                        <p className="text-sm text-gray-500 mt-1">{result.description}</p>
                      )}
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded mt-2 inline-block">
                        {result.source}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <a
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-primary text-white px-4 py-2 rounded text-sm hover:bg-blue-800"
                      >
                        Open
                      </a>
                      <button
                        onClick={() => openInVlc(result.url, result.title)}
                        className="bg-orange-100 text-orange-700 px-3 py-2 rounded text-sm hover:bg-orange-200"
                      >
                        🎥 VLC
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : searchQuery && !searching ? (
            <div className="text-center py-16 bg-white rounded-xl border">
              <p className="text-5xl mb-3">🔍</p>
              <p className="text-gray-600">No results found</p>
              <p className="text-sm text-gray-400 mt-2">
                Try different keywords or browse sources
              </p>
            </div>
          ) : null}
        </div>
      )}

      {activeTab === "vlc" && (
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">🎥 VLC Media Player</h3>
            <p className="text-sm text-gray-500 mb-4">
              Enter a media URL to play in VLC or HTML5 player
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Media URL</label>
                <input
                  type="url"
                  value={vlcUrl}
                  onChange={(e) => setVlcUrl(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  placeholder="https://example.com/video.mp4"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={vlcTitle}
                  onChange={(e) => setVlcTitle(e.target.value)}
                  className="w-full rounded border px-3 py-2 text-sm"
                  placeholder="My Video"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => openInVlc(vlcUrl, vlcTitle)}
                  disabled={!vlcUrl}
                  className="flex-1 bg-orange-500 text-white py-2 rounded-lg font-medium hover:bg-orange-600 disabled:opacity-50"
                >
                  🎥 Open in VLC
                </button>
                <a
                  href={vlcUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 bg-primary text-white py-2 rounded-lg font-medium hover:bg-blue-800 text-center"
                >
                  🌐 Open in Browser
                </a>
              </div>
            </div>

            {/* HTML5 Player Preview */}
            {vlcUrl && (
              <div className="mt-6">
                <h4 className="font-medium mb-2">Preview</h4>
                {vlcUrl.match(/\.(mp4|webm|ogg|mov)$/i) ? (
                  <video
                    controls
                    src={vlcUrl}
                    className="w-full rounded-lg"
                    style={{ maxHeight: "400px" }}
                  />
                ) : vlcUrl.match(/\.(mp3|wav|ogg|flac|aac)$/i) ? (
                  <audio controls src={vlcUrl} className="w-full" />
                ) : (
                  <iframe
                    src={vlcUrl}
                    className="w-full h-96 rounded-lg border"
                    title={vlcTitle || "Media Preview"}
                  />
                )}
              </div>
            )}
          </div>

          {/* VLC Install Help */}
          <div className="mt-6 p-4 bg-orange-50 border border-orange-200 rounded-xl">
            <h4 className="font-semibold text-orange-700 mb-2">📹 Don&apos;t have VLC?</h4>
            <p className="text-sm text-orange-600 mb-2">
              VLC is a free, open-source media player that plays almost anything.
            </p>
            <a
              href="https://www.videolan.org/vlc/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-orange-700 underline font-medium"
            >
              Download VLC → videolan.org
            </a>
          </div>
        </div>
      )}
    </Layout>
  );
}
