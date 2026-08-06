import { useState, useEffect } from "react";
import Layout from "@/components/Layout";

interface LLMProvider {
  id: string;
  name: string;
  icon: string;
  enabled: boolean;
  configured: boolean;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function LLMConfig() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState({ text: "", type: "" });
  const [testResult, setTestResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/kudos/llm/status", { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => {
        setProviders(d.providers || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const configureProvider = async (provider: string) => {
    const key = apiKeys[provider];
    if (!key) {
      setMessage({ text: "❌ Please enter an API key", type: "error" });
      return;
    }

    const res = await fetch(`/api/v1/kudos/llm/configure?provider=${provider}&api_key=${encodeURIComponent(key)}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      setMessage({ text: `✅ ${data.message}`, type: "success" });
      // Refresh status
      const statusRes = await fetch("/api/v1/kudos/llm/status", { headers: getAuthHeader() });
      if (statusRes.ok) setProviders((await statusRes.json()).providers || []);
      setApiKeys({ ...apiKeys, [provider]: "" });
    } else {
      const data = await res.json();
      setMessage({ text: `❌ ${data.detail}`, type: "error" });
    }
  };

  const testLLM = async () => {
    setTestResult(null);
    const res = await fetch("/api/v1/kudos/llm/test?prompt=Hello, who are you?", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) {
      setTestResult(await res.json());
    }
  };

  const PROVIDER_INFO: Record<string, { setup: string; free: string; url: string }> = {
    google_gemini: {
      setup: "Go to Google AI Studio → Get API Key → Copy",
      free: "Free tier: 15 requests/min, 1M tokens/day",
      url: "https://aistudio.google.com/app/apikey",
    },
    openai: {
      setup: "Go to OpenAI Platform → API Keys → Create new",
      free: "Free tier: $5 credit for new accounts",
      url: "https://platform.openai.com/api-keys",
    },
    groq: {
      setup: "Go to Groq Console → API Keys → Create",
      free: "Free tier: Very fast inference, generous limits",
      url: "https://console.groq.com/keys",
    },
    ollama: {
      setup: "Install Ollama locally → run 'ollama pull llama3'",
      free: "100% free, runs on your computer",
      url: "https://ollama.ai",
    },
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">✨ KUDOS LLM Configuration</h2>
      <p className="text-gray-600 mb-8">
        Connect KUDOS to external AI models for human-like responses
      </p>

      {message.text && (
        <div className={`mb-6 p-4 rounded-lg text-sm ${
          message.type === "success" ? "bg-green-50 border border-green-200 text-green-700"
            : "bg-red-50 border border-red-200 text-red-700"
        }`}>{message.text}</div>
      )}

      {/* Status bar */}
      <div className="mb-6 p-4 bg-white rounded-xl border shadow flex justify-between items-center">
        <div>
          <span className="font-medium">LLM Status:</span>
          <span className="ml-2 text-sm text-gray-600">
            {providers.filter(p => p.configured).length} of {providers.length} configured
          </span>
        </div>
        <button
          onClick={testLLM}
          className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700"
        >
          🧪 Test LLM
        </button>
      </div>

      {testResult && (
        <div className="mb-6 p-4 bg-gray-50 rounded-xl border">
          <p className="font-medium text-sm mb-2">Test Result:</p>
          <p className="text-sm"><strong>Provider:</strong> {testResult.provider}</p>
          <p className="text-sm mt-1"><strong>Response:</strong> {testResult.response || testResult.message}</p>
        </div>
      )}

      {/* Provider cards */}
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {providers.map((provider) => {
            const info = PROVIDER_INFO[provider.id];
            return (
              <div key={provider.id} className="bg-white rounded-xl border shadow p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-semibold">{provider.icon} {provider.name}</h3>
                    {info && (
                      <p className="text-xs text-gray-500 mt-1">{info.free}</p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${
                    provider.configured ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                  }`}>
                    {provider.configured ? "✅ Active" : "Not configured"}
                  </span>
                </div>

                {info && (
                  <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                    <p className="text-xs text-blue-700">{info.setup}</p>
                    <a href={info.url} target="_blank" rel="noopener noreferrer"
                       className="text-xs text-blue-500 underline mt-1 inline-block">
                      Get API Key →
                    </a>
                  </div>
                )}

                <div className="flex gap-2">
                  <input
                    type="password"
                    value={apiKeys[provider.id] || ""}
                    onChange={(e) => setApiKeys({ ...apiKeys, [provider.id]: e.target.value })}
                    className="flex-1 rounded border px-3 py-2 text-sm"
                    placeholder="Paste API key here"
                  />
                  <button
                    onClick={() => configureProvider(provider.id)}
                    className="bg-primary text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-800"
                  >
                    Save
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Instructions */}
      <div className="mt-8 p-6 bg-gray-50 rounded-xl border">
        <h3 className="font-semibold mb-3">🚀 Quick Start (Free)</h3>
        <ol className="space-y-2 text-sm text-gray-600">
          <li>1. <strong>Google Gemini</strong> (recommended): Go to <a href="https://aistudio.google.com/app/apikey" className="text-blue-500 underline" target="_blank">aistudio.google.com</a> → Create API Key → Paste above</li>
          <li>2. <strong>Groq</strong> (fastest): Go to <a href="https://console.groq.com/keys" className="text-blue-500 underline" target="_blank">console.groq.com</a> → Create API Key → Paste above</li>
          <li>3. <strong>Ollama</strong> (local, 100% free): Install <a href="https://ollama.ai" className="text-blue-500 underline" target="_blank">Ollama</a> → Run <code className="bg-gray-200 px-1 rounded">ollama pull llama3</code></li>
        </ol>
        <p className="text-xs text-gray-500 mt-3">
          Once configured, KUDOS will automatically use the LLM for all conversations.
          It combines the LLM's knowledge with the internal knowledge base for the best answers.
        </p>
      </div>
    </Layout>
  );
}
