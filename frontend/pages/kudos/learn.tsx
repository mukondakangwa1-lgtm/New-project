import { useState, FormEvent } from "react";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosLearn() {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(false);
  const [webItems, setWebItems] = useState<any[]>([]);

  useState(() => {
    fetch("/api/v1/kudos/learn/web", { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && setWebItems(d))
      .catch(() => {});
  });

  const handleLearn = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ text: "", type: "" });

    try {
      const res = await fetch("/api/v1/kudos/learn/web", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ url, title }),
      });

      if (res.ok) {
        const data = await res.json();
        setMessage({
          text: `✅ Learned "${data.title}" — ${data.is_approved ? "Auto-approved." : "Pending admin approval."}`,
          type: "success",
        });
        setUrl("");
        setTitle("");
        const listRes = await fetch("/api/v1/kudos/learn/web", { headers: getAuthHeader() });
        if (listRes.ok) setWebItems(await listRes.json());
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
      <h2 className="text-3xl font-bold mb-2">🌐 Teach KUDOS — Web Pages</h2>
      <p className="text-gray-600 mb-8">
        Paste any URL — KUDOS will fetch the page, extract the text, and learn from it.
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
          <h3 className="font-semibold text-lg mb-4">Teach a Web Page</h3>
          <form onSubmit={handleLearn} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">URL *</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                placeholder="https://en.wikipedia.org/wiki/Computer_science"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Title (optional)</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm"
                placeholder="Auto-detected from page"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 text-white py-2 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? "Fetching & Learning..." : "🌐 Learn This Page"}
            </button>
          </form>
        </div>

        <div>
          <h3 className="font-semibold text-lg mb-4">Learned Pages ({webItems.length})</h3>
          {webItems.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-xl border">
              <p className="text-4xl mb-3">🌐</p>
              <p className="text-gray-500">No web pages learned yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {webItems.map((item: any) => (
                <div key={item.id} className="bg-white rounded-lg border p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium truncate">{item.title}</h4>
                      <p className="text-xs text-gray-400 truncate">{item.url}</p>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded ml-2 ${
                        item.is_approved
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {item.is_approved ? "Approved" : "Pending"}
                    </span>
                  </div>
                  {item.summary && (
                    <p className="text-xs text-gray-500 mt-2 line-clamp-2">{item.summary}</p>
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
