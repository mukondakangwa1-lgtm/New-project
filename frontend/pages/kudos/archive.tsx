import { useState } from "react";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function InternetArchive() {
  const [waybackUrl, setWaybackUrl] = useState("");
  const [waybackYear, setWaybackYear] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchType, setSearchType] = useState("texts");
  const [timemachineUrl, setTimemachineUrl] = useState("");
  const [timemachineStart, setTimemachineStart] = useState("2010");
  const [timemachineEnd, setTimemachineEnd] = useState("2024");
  const [batchTopics, setBatchTopics] = useState("computer science,mathematics,physics,history,philosophy");
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [activeTab, setActiveTab] = useState<"wayback" | "search" | "timemachine" | "batch">("wayback");

  const fetchWayback = async () => {
    if (!waybackUrl) return;
    setLoading(true);
    setMessage({ text: "", type: "" });
    const params = new URLSearchParams({ url: waybackUrl });
    if (waybackYear) params.append("year", waybackYear);
    const res = await fetch(`/api/v1/kudos/archive/wayback?${params}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data);
      setMessage({ text: `✅ ${data.message}`, type: "success" });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
    setLoading(false);
  };

  const fetchHistory = async () => {
    if (!waybackUrl) return;
    const res = await fetch(`/api/v1/kudos/archive/wayback/history?url=${encodeURIComponent(waybackUrl)}&limit=15`);
    if (res.ok) {
      const data = await res.json();
      setHistory(data.snapshots || []);
    }
  };

  const searchArchive = async () => {
    if (!searchQuery) return;
    setLoading(true);
    setMessage({ text: "", type: "" });
    const res = await fetch(`/api/v1/kudos/archive/search?query=${encodeURIComponent(searchQuery)}&media_type=${searchType}&max_results=5`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data);
      setMessage({ text: `✅ ${data.message}`, type: "success" });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
    setLoading(false);
  };

  const timemachineLearn = async () => {
    if (!timemachineUrl) return;
    setLoading(true);
    setMessage({ text: "", type: "" });
    const res = await fetch(`/api/v1/kudos/archive/timemachine?url=${encodeURIComponent(timemachineUrl)}&start_year=${timemachineStart}&end_year=${timemachineEnd}&interval=2`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data);
      setMessage({ text: `✅ ${data.message}`, type: "success" });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
    setLoading(false);
  };

  const batchLearn = async () => {
    setLoading(true);
    setMessage({ text: "", type: "" });
    const res = await fetch(`/api/v1/kudos/archive/batch-learn?topics=${encodeURIComponent(batchTopics)}&media_type=texts`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setResult(data);
      setMessage({ text: `✅ ${data.message}`, type: "success" });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
    setLoading(false);
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold">🕰️ Internet Archive</h2>
          <p className="text-gray-600">Connect KUDOS to archive.org — the history of everything on the internet</p>
        </div>
      </div>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>{message.text}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: "wayback" as const, icon: "🌐", label: "Wayback Machine" },
          { id: "search" as const, icon: "🔍", label: "Search Archive" },
          { id: "timemachine" as const, icon: "⏰", label: "Time Machine" },
          { id: "batch" as const, icon: "📚", label: "Batch Learn" },
        ].map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${activeTab === t.id ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Input */}
        <div className="bg-white rounded-xl border shadow p-6">
          {activeTab === "wayback" && (
            <>
              <h3 className="font-semibold text-lg mb-4">🌐 Wayback Machine</h3>
              <p className="text-sm text-gray-500 mb-4">Fetch archived snapshots of any website from the past 25+ years.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Website URL</label>
                  <input type="url" value={waybackUrl} onChange={(e) => setWaybackUrl(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm" placeholder="https://example.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Year (optional)</label>
                  <input type="number" value={waybackYear} onChange={(e) => setWaybackYear(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm" placeholder="2015" min="1996" max="2026" />
                </div>
                <div className="flex gap-2">
                  <button onClick={fetchWayback} disabled={loading || !waybackUrl}
                    className="flex-1 bg-primary text-white py-2 rounded font-medium hover:bg-blue-800 disabled:opacity-50">
                    {loading ? "Fetching..." : "🕰️ Fetch & Learn"}
                  </button>
                  <button onClick={fetchHistory} disabled={!waybackUrl}
                    className="bg-white border px-4 py-2 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
                    📋 History
                  </button>
                </div>
              </div>
              {history.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium mb-2">Available Snapshots ({history.length})</p>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {history.map((h, i) => (
                      <a key={i} href={h.url} target="_blank" rel="noopener noreferrer"
                        className="block text-xs text-blue-600 hover:underline">
                        {h.year}-{h.month}-{h.day}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === "search" && (
            <>
              <h3 className="font-semibold text-lg mb-4">🔍 Search Internet Archive</h3>
              <p className="text-sm text-gray-500 mb-4">Search billions of archived texts, books, media, and software.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Search Query</label>
                  <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm" placeholder="machine learning" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Media Type</label>
                  <select value={searchType} onChange={(e) => setSearchType(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm">
                    <option value="texts">📚 Texts & Books</option>
                    <option value="movies">🎬 Movies</option>
                    <option value="audio">🎵 Audio</option>
                    <option value="software">💾 Software</option>
                    <option value="image">🖼️ Images</option>
                    <option value="web">🌐 Web Pages</option>
                  </select>
                </div>
                <button onClick={searchArchive} disabled={loading || !searchQuery}
                  className="w-full bg-primary text-white py-2 rounded font-medium hover:bg-blue-800 disabled:opacity-50">
                  {loading ? "Searching..." : "🔍 Search & Learn"}
                </button>
              </div>
            </>
          )}

          {activeTab === "timemachine" && (
            <>
              <h3 className="font-semibold text-lg mb-4">⏰ Time Machine</h3>
              <p className="text-sm text-gray-500 mb-4">Learn how a website evolved over time — fetches snapshots from multiple years.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Website URL</label>
                  <input type="url" value={timemachineUrl} onChange={(e) => setTimemachineUrl(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm" placeholder="https://google.com" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Start Year</label>
                    <input type="number" value={timemachineStart} onChange={(e) => setTimemachineStart(e.target.value)}
                      className="w-full rounded border px-3 py-2 text-sm" min="1996" max="2026" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">End Year</label>
                    <input type="number" value={timemachineEnd} onChange={(e) => setTimemachineEnd(e.target.value)}
                      className="w-full rounded border px-3 py-2 text-sm" min="1996" max="2026" />
                  </div>
                </div>
                <button onClick={timemachineLearn} disabled={loading || !timemachineUrl}
                  className="w-full bg-purple-600 text-white py-2 rounded font-medium hover:bg-purple-700 disabled:opacity-50">
                  {loading ? "Traveling through time..." : "⏰ Learn History"}
                </button>
              </div>
            </>
          )}

          {activeTab === "batch" && (
            <>
              <h3 className="font-semibold text-lg mb-4">📚 Batch Learn</h3>
              <p className="text-sm text-gray-500 mb-4">KUDOS learns from the most popular texts on each topic.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Topics (comma-separated)</label>
                  <textarea value={batchTopics} onChange={(e) => setBatchTopics(e.target.value)}
                    className="w-full rounded border px-3 py-2 text-sm" rows={3}
                    placeholder="computer science, mathematics, physics" />
                </div>
                <button onClick={batchLearn} disabled={loading}
                  className="w-full bg-green-600 text-white py-2 rounded font-medium hover:bg-green-700 disabled:opacity-50">
                  {loading ? "Learning from archive.org..." : "📚 Batch Learn All Topics"}
                </button>
              </div>
            </>
          )}
        </div>

        {/* Right: Results */}
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold text-lg mb-4">📊 Results</h3>
          {!result ? (
            <div className="text-center py-12 text-gray-400">
              <p className="text-5xl mb-3">🕰️</p>
              <p>Results will appear here</p>
              <p className="text-sm mt-2">Try fetching a Wayback Machine snapshot or searching for texts</p>
            </div>
          ) : (
            <div className="space-y-3">
              {result.results && result.results.map((r: any, i: number) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <h4 className="font-medium text-sm">{r.title}</h4>
                  {r.creator && <p className="text-xs text-gray-500">By: {r.creator}</p>}
                  {r.year && <p className="text-xs text-gray-500">Year: {r.year}</p>}
                  {r.chars && <p className="text-xs text-gray-400">{r.chars.toLocaleString()} chars learned</p>}
                  {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">View on archive.org →</a>}
                </div>
              ))}
              {result.message && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-700">{result.message}</p>
                </div>
              )}
              {result.snapshots_learned !== undefined && (
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm text-blue-700">Learned {result.snapshots_learned} snapshots from {result.years_scanned?.join(", ")}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
