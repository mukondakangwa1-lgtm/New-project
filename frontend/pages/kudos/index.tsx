import { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";

interface Message {
  id: number;
  role: string;
  content: string;
  sources: string;
  created_at: string;
}
interface Conversation {
  id: number;
  title: string;
  created_at: string;
}
interface Source {
  document_id: number | null;
  web_id: number | null;
  title: string;
  preview: string;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function KudosChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastSources, setLastSources] = useState<Source[]>([]);
  const [arenaMode, setArenaMode] = useState("directchat");
  const [arenaResult, setArenaResult] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/v1/kudos/conversations", { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && setConversations(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (currentConvId) {
      fetch(`/api/v1/kudos/conversations/${currentConvId}/messages`, {
        headers: getAuthHeader(),
      })
        .then((r) => r.json())
        .then((d) => Array.isArray(d) && setMessages(d))
        .catch(() => {});
    } else {
      setMessages([]);
    }
  }, [currentConvId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setLoading(true);
    setLastSources([]);
    setArenaResult(null);

    // Show user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: question,
        sources: "",
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      // Use direct ask endpoint for speed
      const endpoint = arenaMode === "directchat"
        ? "/api/v1/kudos/ask"
        : `/api/v1/kudos/arena/query?mode=${arenaMode}`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({
          question,
          conversation_id: currentConvId,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setCurrentConvId(data.conversation_id);
        setLastSources(data.alternatives || []);
        setArenaResult(data);

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "kudos",
            content: data.answer,
            sources: JSON.stringify(data.alternatives || []),
            created_at: new Date().toISOString(),
          },
        ]);

        // Refresh conversations list
        const convRes = await fetch("/api/v1/kudos/conversations", {
          headers: getAuthHeader(),
        });
        if (convRes.ok) setConversations(await convRes.json());
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "kudos",
          content: "Sorry, I encountered an error. Please try again.",
          sources: "",
          created_at: new Date().toISOString(),
        },
      ]);
    }
    setLoading(false);
  };

  const newConversation = () => {
    setCurrentConvId(null);
    setMessages([]);
    setLastSources([]);
  };

  const deleteConv = async (id: number) => {
    await fetch(`/api/v1/kudos/conversations/${id}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (currentConvId === id) newConversation();
  };

  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-3xl font-bold">🧠 KUDOS</h2>
          <p className="text-gray-600">
            Your AI knowledge assistant — ask questions, upload documents, teach it web pages
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="/kudos/upload"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            📄 Upload Doc
          </a>
          <a
            href="/kudos/learn"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            🌐 Teach Web
          </a>
          <a
            href="/kudos/connect"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            🔌 Connectors
          </a>
          <a
            href="/kudos/admin"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            ⚙️ Admin
          </a>
          <a
            href="/kudos/guardian"
            className="bg-red-50 border border-red-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-100 transition text-red-700"
          >
            🛡️ Guardian
          </a>
          <a
            href="/kudos/llm"
            className="bg-yellow-50 border border-yellow-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-yellow-100 transition text-yellow-700"
          >
            ✨ LLM
          </a>
          <a
            href="/kudos/agent"
            className="bg-indigo-50 border border-indigo-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-100 transition text-indigo-700"
          >
            🤖 Agent
          </a>
          <a
            href="/kudos/archive"
            className="bg-amber-50 border border-amber-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-amber-100 transition text-amber-700"
          >
            🕰️ Archive
          </a>
          <a
            href="/kudos/autolearn"
            className="bg-green-50 border border-green-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-100 transition text-green-700"
          >
            🚀 Auto-Learn
          </a>
        </div>
      </div>

      <div className="flex gap-4 h-[600px] bg-white rounded-xl border shadow overflow-hidden">
        {/* Sidebar — conversations */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-3 border-b">
            <button
              onClick={newConversation}
              className="w-full bg-primary text-white text-sm py-2 rounded-lg hover:bg-blue-800 transition"
            >
              + New Conversation
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <p className="text-xs text-gray-400 p-4">No conversations yet</p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`px-3 py-2 border-b cursor-pointer hover:bg-gray-50 group flex justify-between items-center ${
                    currentConvId === conv.id ? "bg-blue-50" : ""
                  }`}
                  onClick={() => setCurrentConvId(conv.id)}
                >
                  <p className="text-sm truncate flex-1">{conv.title}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConv(conv.id);
                    }}
                    className="text-xs text-red-400 opacity-0 group-hover:opacity-100 ml-2"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-16">
                <p className="text-6xl mb-4">🧠</p>
                <h3 className="text-2xl font-bold text-gray-700 mb-2">
                  Hi! I&apos;m KUDOS
                </h3>
                <p className="text-gray-500 max-w-md mx-auto mb-6">
                  Your AI knowledge assistant. I learn from documents you upload and
                  web pages you teach me. Ask me anything!
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 max-w-lg mx-auto text-left">
                  <button
                    onClick={() => setInput("What documents do you have?")}
                    className="p-3 bg-gray-50 rounded-lg text-sm hover:bg-gray-100 transition text-left"
                  >
                    📄 &quot;What documents do you have?&quot;
                  </button>
                  <button
                    onClick={() => setInput("Summarize what you know")}
                    className="p-3 bg-gray-50 rounded-lg text-sm hover:bg-gray-100 transition text-left"
                  >
                    📝 &quot;Summarize what you know&quot;
                  </button>
                  <button
                    onClick={() => setInput("Help me find information about...")}
                    className="p-3 bg-gray-50 rounded-lg text-sm hover:bg-gray-100 transition text-left"
                  >
                    🔍 &quot;Help me find...&quot;
                  </button>
                </div>

                {/* Quick actions */}
                <div className="flex flex-wrap gap-2 justify-center mt-4">
                  <button
                    onClick={async () => {
                      const q = prompt("What do you want me to search Google for?");
                      if (q) {
                        const token = localStorage.getItem("token");
                        const res = await fetch(`/api/v1/kudos/social/google?query=${encodeURIComponent(q)}&max_results=3`, {
                          method: "POST",
                          headers: { Authorization: `Bearer ${token}` },
                        });
                        if (res.ok) {
                          const data = await res.json();
                          alert(`✅ ${data.message}`);
                        }
                      }
                    }}
                    className="text-xs bg-blue-50 text-blue-700 px-3 py-1 rounded-full hover:bg-blue-100"
                  >
                    🔍 Google Search
                  </button>
                  <button
                    onClick={async () => {
                      const q = prompt("What topic should I learn from Wikipedia?");
                      if (q) {
                        const token = localStorage.getItem("token");
                        const res = await fetch(`/api/v1/kudos/social/learn-wikipedia-batch?topics=${encodeURIComponent(q)}`, {
                          method: "POST",
                          headers: { Authorization: `Bearer ${token}` },
                        });
                        if (res.ok) {
                          const data = await res.json();
                          alert(`✅ ${data.message}`);
                        }
                      }
                    }}
                    className="text-xs bg-green-50 text-green-700 px-3 py-1 rounded-full hover:bg-green-100"
                  >
                    📚 Wikipedia
                  </button>
                  <button
                    onClick={async () => {
                      const token = localStorage.getItem("token");
                      const res = await fetch("/api/v1/kudos/social/learn-social?platform=general", {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                      });
                      if (res.ok) {
                        const data = await res.json();
                        alert(`✅ ${data.message}`);
                      }
                    }}
                    className="text-xs bg-purple-50 text-purple-700 px-3 py-1 rounded-full hover:bg-purple-100"
                  >
                    🗣️ Social Skills
                  </button>
                  <button
                    onClick={async () => {
                      const token = localStorage.getItem("token");
                      const res = await fetch("/api/v1/kudos/social/learn-emotions", {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                      });
                      if (res.ok) {
                        const data = await res.json();
                        alert(`✅ ${data.message}`);
                      }
                    }}
                    className="text-xs bg-pink-50 text-pink-700 px-3 py-1 rounded-full hover:bg-pink-100"
                  >
                    💝 Human Emotions
                  </button>
                  <button
                    onClick={async () => {
                      const sub = prompt("Which subreddit? (e.g. LifeProTips, AskReddit, advice)");
                      if (sub) {
                        const token = localStorage.getItem("token");
                        const res = await fetch(`/api/v1/kudos/social/learn-reddit?subreddit=${encodeURIComponent(sub)}&limit=5`, {
                          method: "POST",
                          headers: { Authorization: `Bearer ${token}` },
                        });
                        if (res.ok) {
                          const data = await res.json();
                          alert(`✅ ${data.message}`);
                        }
                      }
                    }}
                    className="text-xs bg-orange-50 text-orange-700 px-3 py-1 rounded-full hover:bg-orange-100"
                  >
                    🤖 Reddit
                  </button>
                  <button
                    onClick={async () => {
                      const token = localStorage.getItem("token");
                      const res = await fetch("/api/v1/kudos/social/learn-social?platform=discord", {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                      });
                      if (res.ok) {
                        const data = await res.json();
                        alert(`✅ ${data.message}`);
                      }
                    }}
                    className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full hover:bg-indigo-100"
                  >
                    💬 Discord
                  </button>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-xl px-5 py-3 ${
                    msg.role === "user"
                      ? "bg-primary text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {msg.role === "kudos" && (
                    <p className="text-xs font-bold text-primary mb-1">🧠 KUDOS</p>
                  )}
                  <div className="text-sm whitespace-pre-wrap">{msg.content}</div>

                  {/* Sources */}
                  {msg.role === "kudos" && msg.sources && (
                    <div className="mt-3 pt-2 border-t border-gray-200">
                      {(() => {
                        try {
                          const srcs: Source[] = JSON.parse(msg.sources);
                          return srcs.length > 0 ? (
                            <div className="space-y-1">
                              <p className="text-xs text-gray-500 font-medium">Sources:</p>
                              {srcs.map((s, i) => (
                                <p key={i} className="text-xs text-gray-500">
                                  📖 {s.title || `Document #${s.document_id}`}
                                </p>
                              ))}
                            </div>
                          ) : null;
                        } catch {
                          return null;
                        }
                      })()}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-xl px-5 py-3">
                  <p className="text-xs font-bold text-primary mb-1">🧠 KUDOS</p>
                  <p className="text-sm text-gray-500 animate-pulse">Thinking...</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t bg-gray-50">
            {/* Arena Mode Selector */}
            <div className="flex gap-1 mb-2">
              {[{ id: "battlemode", icon: "⚔️", label: "Battle" }, { id: "agent", icon: "🤖", label: "Agent" }, { id: "sidebyside", icon: "📊", label: "Compare" }, { id: "directchat", icon: "💬", label: "Direct" }].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setArenaMode(m.id)}
                  className={`text-xs px-3 py-1 rounded-full transition ${arenaMode === m.id ? "bg-purple-600 text-white" : "bg-white border text-gray-600 hover:bg-gray-50"}`}
                >
                  {m.icon} {m.label}
                </button>
              ))}
            </div>
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ask()}
                className="flex-1 rounded-xl border px-4 py-3 text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none"
                placeholder="Ask KUDOS anything..."
                disabled={loading}
              />
              <button
                onClick={ask}
                disabled={loading || !input.trim()}
                className="bg-purple-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-purple-700 disabled:opacity-50 transition"
              >
                {loading ? "Thinking..." : "⚔️ Ask"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
