import { useState, useEffect, FormEvent } from "react";
import Layout from "@/components/Layout";

interface Connector {
  id: number;
  name: string;
  connector_type: string;
  source_url: string;
  status: string;
  last_synced_at: string | null;
  items_learned: number;
  error_message: string;
  is_approved: boolean;
  created_at: string;
}

interface KnowledgePack {
  id: number;
  name: string;
  description: string;
  item_count: number;
  size_bytes: number;
  is_shared: boolean;
  created_at: string;
}

interface AutoSyncStatus {
  running: boolean;
  interval_minutes: number;
  last_sync: string | null;
  recent_results: { connector: string; items_new?: number; status: string; error?: string }[];
}

const CONNECTOR_TYPES = [
  { value: "github", label: "📦 GitHub Repo", placeholder: "https://github.com/owner/repo", desc: "README, code, issues, file tree" },
  { value: "gitlab", label: "🦊 GitLab Repo", placeholder: "https://gitlab.com/owner/repo", desc: "Project info, README, code" },
  { value: "website", label: "🌐 Website Crawler", placeholder: "https://docs.example.com", desc: "Multi-page crawl (follows links)" },
  { value: "api", label: "⚡ REST API", placeholder: "https://api.example.com/data", desc: "Fetch JSON/text from any endpoint" },
  { value: "rss", label: "📰 RSS/Atom Feed", placeholder: "https://example.com/feed.xml", desc: "Subscribe to news/blog feeds" },
  { value: "npm", label: "📦 npm Package", placeholder: "react", desc: "Package info, README, metadata" },
  { value: "pypi", label: "🐍 PyPI Package", placeholder: "fastapi", desc: "Package info, description, metadata" },
];

const TYPE_ICONS: Record<string, string> = {
  github: "📦", gitlab: "🦊", website: "🌐", api: "⚡", rss: "📰", npm: "📦", pypi: "🐍",
};

const CATEGORIES = [
  { name: "Code Repositories", icon: "💻", filter: (c: Connector) => c.connector_type === "github" || (c.connector_type === "website" && (c.name.includes("Docs") || c.name.includes("Handbook"))) },
  { name: "Package Registries", icon: "📦", filter: (c: Connector) => c.connector_type === "npm" || c.connector_type === "pypi" },
  { name: "Knowledge & Education", icon: "📚", filter: (c: Connector) => c.connector_type === "website" && (c.name.includes("Wikipedia") || c.name.includes("W3Schools") || c.name.includes("MDN")) },
  { name: "RSS Feeds", icon: "📰", filter: (c: Connector) => c.connector_type === "rss" },
  { name: "Search & Social", icon: "🔍", filter: (c: Connector) => c.connector_type === "website" && !c.name.includes("Docs") && !c.name.includes("Wikipedia") && !c.name.includes("W3Schools") && !c.name.includes("MDN") && !c.name.includes("Handbook") },
];

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosConnect() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [packs, setPacks] = useState<KnowledgePack[]>([]);
  const [form, setForm] = useState({ name: "", connector_type: "github", source_url: "", config: "{}" });
  const [packForm, setPackForm] = useState({ name: "", description: "", is_shared: false });
  const [message, setMessage] = useState({ text: "", type: "" });
  const [syncing, setSyncing] = useState<number | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const [bulkResults, setBulkResults] = useState<any[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [showPack, setShowPack] = useState(false);
  const [activeTab, setActiveTab] = useState<"connectors" | "packs">("connectors");
  const [loading, setLoading] = useState(true);
  const [autoSyncStatus, setAutoSyncStatus] = useState<AutoSyncStatus | null>(null);

  const selectedType = CONNECTOR_TYPES.find((t) => t.value === form.connector_type);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [connRes, packRes] = await Promise.all([
        fetch("/api/v1/kudos/connectors/"),
        fetch("/api/v1/kudos/connectors/packs"),
      ]);
      if (connRes.ok) {
        const connData = await connRes.json();
        setConnectors(Array.isArray(connData) ? connData : []);
      }
      if (packRes.ok) {
        const packData = await packRes.json();
        setPacks(Array.isArray(packData) ? packData : []);
      }
    } catch {}
    setLoading(false);
  };

  const fetchAutoSync = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;
      const res = await fetch("/api/v1/kudos/connectors/auto-sync/status", { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setAutoSyncStatus(await res.json());
    } catch {}
  };

  useEffect(() => { fetchData(); fetchAutoSync(); }, []);

  const createConnector = async (e: FormEvent) => {
    e.preventDefault();
    setMessage({ text: "", type: "" });
    const token = localStorage.getItem("token");
    if (!token) { setMessage({ text: "❌ Please log in to add connectors", type: "error" }); return; }
    const res = await fetch("/api/v1/kudos/connectors/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      setMessage({ text: "✅ Connector created! Click Sync to start learning.", type: "success" });
      setForm({ name: "", connector_type: "github", source_url: "", config: "{}" });
      setShowNew(false);
      fetchData();
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const syncConnector = async (id: number) => {
    setSyncing(id);
    setMessage({ text: "", type: "" });
    try {
      const res = await fetch(`/api/v1/kudos/connectors/${id}/sync`, { method: "POST", headers: getAuthHeader() });
      if (res.ok) {
        const data = await res.json();
        setMessage({ text: `✅ ${data.details}`, type: "success" });
        fetchData();
      } else {
        const data = await res.json();
        setMessage({ text: `❌ ${data.detail}`, type: "error" });
      }
    } catch (err: any) {
      setMessage({ text: `❌ ${err.message}`, type: "error" });
    }
    setSyncing(null);
  };

  const syncAll = async () => {
    setSyncingAll(true);
    setMessage({ text: "", type: "" });
    setBulkResults([]);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/kudos/connectors/sync-all", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setBulkResults(data.results || []);
        setMessage({ text: `✅ ${data.message}`, type: "success" });
        fetchData();
      }
    } catch (err: any) {
      setMessage({ text: `❌ ${err.message}`, type: "error" });
    }
    setSyncingAll(false);
  };

  const toggleAutoSync = async (enable: boolean) => {
    const token = localStorage.getItem("token");
    const url = enable ? "/api/v1/kudos/connectors/auto-sync/start?interval_minutes=60" : "/api/v1/kudos/connectors/auto-sync/stop";
    const res = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      fetchAutoSync();
    }
  };

  const deleteConnector = async (id: number) => {
    if (!confirm("Delete this connector?")) return;
    await fetch(`/api/v1/kudos/connectors/${id}`, { method: "DELETE", headers: getAuthHeader() });
    fetchData();
  };

  const createPack = async (e: FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("token");
    const res = await fetch("/api/v1/kudos/connectors/packs", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(packForm),
    });
    if (res.ok) {
      setMessage({ text: "✅ Knowledge pack exported!", type: "success" });
      setPackForm({ name: "", description: "", is_shared: false });
      setShowPack(false);
      fetchData();
    }
  };

  const importPack = async (id: number) => {
    const res = await fetch(`/api/v1/kudos/connectors/packs/${id}/import`, { method: "POST", headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ Imported ${data.imported} items from "${data.pack_name}"`, type: "success" });
    }
  };

  const timeAgo = (iso: string | null) => {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  };

  const totalItems = connectors.reduce((sum, c) => sum + c.items_learned, 0);
  const syncedCount = connectors.filter(c => c.last_synced_at).length;

  return (
    <Layout>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-3xl font-bold">🔌 KUDOS Connectors</h2>
          <p className="text-gray-600">Connect to {connectors.length} sources • {totalItems} items learned • {syncedCount} synced</p>
        </div>
        <div className="flex gap-2">
          <button onClick={syncAll} disabled={syncingAll || connectors.length === 0}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
            {syncingAll ? "⏳ Syncing All..." : "⚡ Sync All"}
          </button>
          <button onClick={() => toggleAutoSync(!autoSyncStatus?.running)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${autoSyncStatus?.running ? "bg-orange-100 text-orange-700 hover:bg-orange-200" : "bg-white border hover:bg-gray-50"}`}>
            {autoSyncStatus?.running ? "⏹ Stop Auto-Sync" : "🔄 Start Auto-Sync"}
          </button>
          <button onClick={() => { setShowNew(!showNew); setShowPack(false); }} className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-800">+ Add Connector</button>
          <button onClick={() => { setShowPack(!showPack); setShowNew(false); }} className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">📦 Export Pack</button>
        </div>
      </div>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"}`}>{message.text}</div>
      )}

      {autoSyncStatus?.running && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex justify-between items-center">
          <span className="text-sm font-medium text-green-700">🔄 Auto-Sync Active — Every {autoSyncStatus.interval_minutes} min{autoSyncStatus.last_sync ? ` • Last: ${new Date(autoSyncStatus.last_sync).toLocaleTimeString()}` : ""}</span>
        </div>
      )}

      {bulkResults.length > 0 && (
        <div className="mb-4 p-4 bg-white rounded-xl border shadow">
          <h4 className="font-semibold text-sm mb-2">⚡ Bulk Sync Results</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
            {bulkResults.map((r, i) => (
              <div key={i} className={`p-2 rounded text-xs text-center ${r.status === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                <p className="font-medium">{r.connector}</p>
                <p>{r.status === "success" ? `+${r.items_new} items` : r.error?.substring(0, 40)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* New connector form */}
      {showNew && (
        <div className="bg-white rounded-xl border shadow p-6 mb-6">
          <h3 className="font-semibold text-lg mb-4">Connect to a Source</h3>
          <form onSubmit={createConnector} className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {CONNECTOR_TYPES.map((t) => (
                <button key={t.value} type="button" onClick={() => setForm({ ...form, connector_type: t.value, source_url: "" })}
                  className={`p-3 rounded-lg border text-left transition ${form.connector_type === t.value ? "border-primary bg-blue-50 ring-2 ring-primary" : "hover:bg-gray-50"}`}>
                  <p className="font-medium text-sm">{t.label}</p>
                  <p className="text-xs text-gray-500">{t.desc}</p>
                </button>
              ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="e.g. FastAPI Docs" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">URL / Package Name</label>
                <input type="text" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder={selectedType?.placeholder} required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Config (JSON, optional)</label>
              <input type="text" value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })} className="w-full rounded border px-3 py-2 text-sm font-mono" placeholder='{"max_pages": 20, "max_depth": 2}' />
            </div>
            <button type="submit" className="bg-primary text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-800">🔌 Connect</button>
          </form>
        </div>
      )}

      {/* Pack export form */}
      {showPack && (
        <div className="bg-white rounded-xl border shadow p-6 mb-6">
          <h3 className="font-semibold text-lg mb-4">📦 Export Knowledge Pack</h3>
          <form onSubmit={createPack} className="space-y-4">
            <input type="text" value={packForm.name} onChange={(e) => setPackForm({ ...packForm, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="Pack name" required />
            <input type="text" value={packForm.description} onChange={(e) => setPackForm({ ...packForm, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" placeholder="Description (optional)" />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={packForm.is_shared} onChange={(e) => setPackForm({ ...packForm, is_shared: e.target.checked })} /> Share with other users</label>
            <button type="submit" className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700">📦 Export Pack</button>
          </form>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-6">
        <button onClick={() => setActiveTab("connectors")} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${activeTab === "connectors" ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"}`}>
          🔌 Connectors ({connectors.length})
        </button>
        <button onClick={() => setActiveTab("packs")} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${activeTab === "packs" ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"}`}>
          📦 Knowledge Packs ({packs.length})
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : activeTab === "connectors" ? (
        connectors.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border">
            <p className="text-5xl mb-3">🔌</p>
            <p className="text-xl text-gray-600 mb-2">No connectors yet</p>
            <p className="text-gray-500">Click &quot;Add Connector&quot; or run seed_kudos.py to load defaults</p>
          </div>
        ) : (
          <div className="space-y-8">
            {CATEGORIES.map((cat) => {
              const catConnectors = connectors.filter(cat.filter);
              if (catConnectors.length === 0) return null;
              return (
                <div key={cat.name}>
                  <h3 className="font-semibold text-lg mb-3">{cat.icon} {cat.name} ({catConnectors.length})</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {catConnectors.map((conn) => (
                      <div key={conn.id} className="bg-white rounded-xl border shadow p-4 hover:shadow-md transition">
                        <div className="flex justify-between items-start mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{TYPE_ICONS[conn.connector_type] || "🔗"}</span>
                            <div>
                              <h4 className="font-semibold text-sm">{conn.name}</h4>
                              <p className="text-xs text-gray-400 font-mono truncate max-w-[200px]">{conn.source_url}</p>
                            </div>
                          </div>
                          <span className={`text-xs px-2 py-0.5 rounded ${conn.status === "active" ? "bg-green-100 text-green-700" : conn.status === "error" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-500"}`}>{conn.status}</span>
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                          <span>{conn.items_learned} items</span>
                          <span>{conn.last_synced_at ? `Synced ${timeAgo(conn.last_synced_at)}` : "Never synced"}</span>
                        </div>
                        <div className="flex gap-2">
                          <button onClick={() => syncConnector(conn.id)} disabled={syncing === conn.id}
                            className="flex-1 text-xs bg-blue-100 text-blue-700 px-3 py-1.5 rounded hover:bg-blue-200 disabled:opacity-50 font-medium">
                            {syncing === conn.id ? "⏳ Syncing..." : "🔄 Sync"}
                          </button>
                          <button onClick={() => deleteConnector(conn.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1.5 rounded hover:bg-red-200">✕</button>
                        </div>
                        {conn.error_message && <p className="text-xs text-red-500 mt-2">{conn.error_message}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        packs.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border">
            <p className="text-5xl mb-3">📦</p>
            <p className="text-xl text-gray-600 mb-2">No knowledge packs yet</p>
            <p className="text-gray-500">Export your knowledge base for offline use</p>
          </div>
        ) : (
          <div className="space-y-4">
            {packs.map((pack) => (
              <div key={pack.id} className="bg-white rounded-xl border shadow p-5 flex justify-between items-center">
                <div>
                  <h4 className="font-semibold">{pack.name}</h4>
                  {pack.description && <p className="text-sm text-gray-500">{pack.description}</p>}
                  <p className="text-xs text-gray-400 mt-1">{pack.item_count} items • {(pack.size_bytes / 1024).toFixed(1)} KB{pack.is_shared && " • 🌐 Shared"}</p>
                </div>
                <button onClick={() => importPack(pack.id)} className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded hover:bg-green-200">📥 Import</button>
              </div>
            ))}
          </div>
        )
      )}
    </Layout>
  );
}
