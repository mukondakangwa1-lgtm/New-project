import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { getAuthHeader, signOut } from "@/lib/api";
import Layout from "@/components/Layout";
import { ProgressBar, useLongProcess } from "@/components/ProgressBar";
import KudosGuestChat from "@/components/KudosGuestChat";
import RadioPanel from "@/components/RadioPanel";
import MessageContent, { CopyButton } from "@/components/MessageContent";

interface Message {
  id: number;
  role: string;
  content: string;
  sources: string;
  media?: string;
  learned?: string;
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

export default function KudosChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastSources, setLastSources] = useState<Source[]>([]);
  const [arenaMode, setArenaMode] = useState("directchat");
  const [arenaResult, setArenaResult] = useState<any>(null);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const askProgress = useLongProcess();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Anonymous visitors get the guest chat (no login required)
  const [guestMode, setGuestMode] = useState<boolean | null>(null);
  const [userName, setUserName] = useState<string>("");
  useEffect(() => {
    fetch("/api/v1/users/me")
      .then(async (r) => {
        setGuestMode(r.status !== 200);
        if (r.status === 200) {
          const me = await r.json().catch(() => null);
          if (me?.full_name) {
            setUserName(me.full_name.split(" ")[0] || me.full_name);
          }
        }
      })
      .catch(() => setGuestMode(true));
  }, []);

  const handleLogout = () => {
    if (!window.confirm("Logging out?")) return;
    signOut();
    window.location.assign("/kudos");
  };

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
    askProgress.start("Asking KUDOS…");
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
            media: JSON.stringify(data.media || []),
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
    askProgress.stop();
  };

  const handleFilesSelected = (e: any) => {
    const files: File[] = Array.from(e.target?.files || []);
    if (!files.length) return;
    setAttachments((prev) => [...prev, ...files]);
    e.target.value = "";
  };

  // Send text and/or files straight to KUDOS via the chat/send endpoint.
  // Text docs/PDFs/code are ingested as knowledge; images/videos are seen
  // (vision) and described; audio + any other file type is stored and attached.
  const sendWithFiles = async (files: File[], text: string) => {
    if (loading) return;
    const question = text.trim() || "I sent you an attachment. Tell me what you learned from it.";
    setInput("");
    setLoading(true);
    setUploading(true);
    askProgress.start("Feeding KUDOS…");
    setArenaResult(null);

    // Optimistic previews use local object URLs; server URLs replace them
    // when the conversation is reloaded.
    const localMedia = files.map((f) => ({
      kind: "media",
      url: URL.createObjectURL(f),
      mime: f.type || "",
      caption: f.name,
    }));

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: question,
        sources: "",
        media: JSON.stringify(localMedia),
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const form = new FormData();
      form.append("message", question);
      form.append("conversation_id", String(currentConvId || 0));
      files.forEach((f) => form.append("files", f));

      const res = await fetch("/api/v1/kudos/chat/send", {
        method: "POST",
        headers: getAuthHeader(),
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Upload failed (${res.status})`);
      }
      const data = await res.json();
      setCurrentConvId(data.conversation_id);
      setArenaResult(data);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "kudos",
          content: data.answer,
          sources: "[]",
          learned: JSON.stringify(data.learned || []),
          media: JSON.stringify(data.media || []),
          created_at: new Date().toISOString(),
        },
      ]);

      const convRes = await fetch("/api/v1/kudos/conversations", {
        headers: getAuthHeader(),
      });
      if (convRes.ok) setConversations(await convRes.json());
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "kudos",
          content: `⚠️ ${e.message}`,
          sources: "",
          learned: "",
          created_at: new Date().toISOString(),
        },
      ]);
    }
    setUploading(false);
    setLoading(false);
    askProgress.stop();
  };

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  };

  const submit = () => {
    if (loading) return;
    if (attachments.length > 0) {
      sendWithFiles(attachments, input);
    } else {
      ask();
    }
  };

  const newConversation = () => {
    setCurrentConvId(null);
    setMessages([]);
    setLastSources([]);
    setAttachments([]);
  };

  const writeEssay = async () => {
    const topic = prompt("Essay topic:");
    if (!topic || !topic.trim()) return;
    const pagesStr = prompt("How many pages? (up to 50)", "5");
    if (!pagesStr) return;
    const pages = Math.max(1, Math.min(parseInt(pagesStr, 10) || 5, 50));
    setLoading(true);
    askProgress.start(`Writing a ${pages}-page essay…`);
    try {
      const body = new URLSearchParams();
      body.set("topic", topic.trim());
      body.set("pages", String(pages));
      body.set("conversation_id", currentConvId ? String(currentConvId) : "0");
      const res = await fetch("/api/v1/kudos/essay", {
        method: "POST",
        headers: { ...getAuthHeader(), "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Essay failed");
      setCurrentConvId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "user",
          content: `Write a ${data.target_pages || pages}-page essay on: ${topic.trim()}`,
          sources: "",
          created_at: new Date().toISOString(),
        },
        {
          id: Date.now() + 1,
          role: "kudos",
          content: data.essay,
          sources: JSON.stringify(
            (data.source_count ? [{ title: `${data.source_count} knowledge sources grounded this essay` }] : [])
          ),
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (e: any) {
      alert(`⚠️ ${e.message}`);
    } finally {
      setLoading(false);
      askProgress.stop();
    }
  };

  const deleteConv = async (id: number) => {
    await fetch(`/api/v1/kudos/conversations/${id}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (currentConvId === id) newConversation();
  };

  if (guestMode === null) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[50vh] text-gray-400">
          Checking session…
        </div>
      </Layout>
    );
  }
  if (guestMode) return <KudosGuestChat />;

  return (
    <Layout>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-3xl font-bold">🧠 KUDOS</h2>
          <p className="text-gray-600">
            Your AI knowledge assistant — ask questions, upload documents, teach it web pages
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={handleLogout}
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 hover:border-red-300 hover:text-red-600 transition"
            title="Logging out?"
          >
            🚪 Log out
          </button>
          <Link href="/kudos/upload"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            📄 Upload Doc
          </Link>
          <Link
            href="/kudos/learn"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            🌐 Teach Web
          </Link>
          <Link
            href="/kudos/admin"
            className="bg-white border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            ⚙️ Admin
          </Link>
          <Link
            href="/kudos/guardian"
            className="bg-red-50 border border-red-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-100 transition text-red-700"
          >
            🛡️ Guardian
          </Link>
          <Link
            href="/kudos/llm"
            className="bg-yellow-50 border border-yellow-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-yellow-100 transition text-yellow-700"
          >
            ✨ LLM
          </Link>
          <Link
            href="/kudos/agent"
            className="bg-indigo-50 border border-indigo-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-100 transition text-indigo-700"
          >
            🤖 Agent
          </Link>
          <Link
            href="/kudos/archive"
            className="bg-amber-50 border border-amber-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-amber-100 transition text-amber-700"
          >
            🕰️ Archive
          </Link>
          <Link
            href="/kudos/autolearn"
            className="bg-green-50 border border-green-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-100 transition text-green-700"
          >
            🚀 Auto-Learn
          </Link>
          <Link
            href="/kudos/maps"
            className="bg-cyan-50 border border-cyan-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-cyan-100 transition text-cyan-700"
          >
            🗺️ Maps
          </Link>
          <Link
            href="/kudos/networks"
            className="bg-purple-50 border border-purple-200 px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-100 transition text-purple-700"
          >
            📡 Networks
          </Link>
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
                  onClick={() => { setCurrentConvId(conv.id); setAttachments([]); }}
                >                  <p className="text-sm truncate flex-1">{conv.title}</p>
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
                  {userName ? `Welcome back, ${userName}!` : "Hi! I'm KUDOS"}
                </h3>
                <p className="text-gray-500 max-w-md mx-auto mb-6">
                  Your AI knowledge assistant. I learn from documents you upload and
                  web pages you teach me. Ask me anything!
                </p>
                {userName && (
                  <button
                    onClick={handleLogout}
                    className="mb-6 px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:border-red-300 hover:text-red-600 transition"
                  >
                    Log out
                  </button>
                )}
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
                                          const res = await fetch(`/api/v1/kudos/social/google?query=${encodeURIComponent(q)}&max_results=3`, {
                          method: "POST",
                          headers: getAuthHeader(),
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
                                          const res = await fetch(`/api/v1/kudos/social/learn-wikipedia-batch?topics=${encodeURIComponent(q)}`, {
                          method: "POST",
                          headers: getAuthHeader(),
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
                                      const res = await fetch("/api/v1/kudos/social/learn-social?platform=general", {
                        method: "POST",
                        headers: getAuthHeader(),
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
                                      const res = await fetch("/api/v1/kudos/social/learn-emotions", {
                        method: "POST",
                        headers: getAuthHeader(),
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
                                          const res = await fetch(`/api/v1/kudos/social/learn-reddit?subreddit=${encodeURIComponent(sub)}&limit=5`, {
                          method: "POST",
                          headers: getAuthHeader(),
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
                                      const res = await fetch("/api/v1/kudos/social/learn-social?platform=discord", {
                        method: "POST",
                        headers: getAuthHeader(),
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
                    <div className="flex items-center justify-between gap-3 mb-1">
                      <p className="text-xs font-bold text-primary">🧠 KUDOS</p>
                      <CopyButton text={msg.content} label="⧉ Copy" />
                    </div>
                  )}
                  {msg.role === "kudos" ? (
                    <MessageContent text={msg.content} />
                  ) : (
                    <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                  )}

                  {/* User attachments (images, audio, video, files) */}
                  {msg.role === "user" && msg.media && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(() => {
                        try {
                          const items: any[] = JSON.parse(msg.media);
                          return items.filter((m: any) => m.url).map((m: any, i: number) => {
                            const mime = m.mime || "";
                            if (mime.startsWith("image/")) {
                              return (
                                <img
                                  key={i}
                                  src={m.url}
                                  alt={m.caption || "attachment"}
                                  className="rounded-lg border border-gray-300 max-h-40"
                                />
                              );
                            }
                            if (mime.startsWith("audio/")) {
                              return (
                                <audio
                                  key={i}
                                  src={m.url}
                                  controls
                                  className="max-w-full"
                                  title={m.caption || "audio"}
                                />
                              );
                            }
                            if (mime.startsWith("video/")) {
                              return (
                                <video
                                  key={i}
                                  src={m.url}
                                  controls
                                  className="rounded-lg border border-gray-300 max-h-40"
                                />
                              );
                            }
                            return (
                              <a
                                key={i}
                                href={m.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-xs bg-white border border-gray-300 text-gray-600 rounded px-2 py-1 hover:bg-gray-50"
                              >
                                📄 {m.caption || "Attachment"}
                              </a>
                            );
                          });
                        } catch {
                          return null;
                        }
                      })()}
                    </div>
                  )}

                  {/* Generated media (images, transient short videos) */}
                  {msg.role === "kudos" && msg.media && (
                    <div className="mt-3 space-y-3">
                      {(() => {
                        try {
                          const items: any[] = JSON.parse(msg.media);
                          return items.filter((m: any) => m.kind === "image" || m.kind === "video").map((m: any, i: number) =>
                            m.kind === "image" ? (
                              <div key={i} className="space-y-1">
                                <img
                                  src={m.url}
                                  alt={m.caption || "KUDOS generated image"}
                                  className="rounded-lg border border-gray-200 max-w-full"
                                />
                                <div className="flex gap-2">
                                  <CopyButton text={window.location.origin + m.url} label="Copy image URL" />
                                  <a
                                    href={m.url}
                                    download
                                    className="text-xs px-2 py-1 rounded border bg-white text-gray-500 hover:bg-gray-100 transition"
                                  >
                                    ⬇ Download
                                  </a>
                                </div>
                              </div>
                            ) : (
                              <div key={i} className="space-y-1">
                                <video
                                  src={m.url}
                                  controls
                                  className="rounded-lg border border-gray-200 max-w-full bg-black"
                                  style={{ maxHeight: 320 }}
                                />
                                <div className="flex gap-2">
                                  <CopyButton text={window.location.origin + m.url} label="Copy video URL" />
                                  <a
                                    href={`${m.url}?dl=1`}
                                    className="text-xs px-2 py-1 rounded border bg-white text-gray-500 hover:bg-gray-100 transition"
                                    title="Download short clip (not stored on the server)"
                                  >
                                    ⬇ Download clip
                                  </a>
                                </div>
                              </div>
                            )
                          );
                        } catch {
                          return null;
                        }
                      })()}
                    </div>
                  )}

                  {/* What KUDOS ingested from attachments */}
                  {msg.role === "kudos" && msg.learned && (() => {
                    try {
                      const learned: any[] = JSON.parse(msg.learned);
                      return learned.length > 0 ? (
                        <div className="mt-3 pt-2 border-t border-gray-200">
                          <p className="text-xs text-gray-500 font-medium mb-1">Learned from your attachments:</p>
                          {learned.map((l, i) => (
                            <p key={i} className="text-xs text-gray-500">
                              📚 {l.title}
                              {l.chunk_count ? ` — ${l.chunk_count} chunk${l.chunk_count === 1 ? "" : "s"}` : ""}
                              {l.description ? ` — ${String(l.description).slice(0, 80)}…` : ""}
                            </p>
                          ))}
                        </div>
                      ) : null;
                    } catch {
                      return null;
                    }
                  })()}

                  {/* Sources */}
                  {msg.role === "kudos" && msg.sources && (                    <div className="mt-3 pt-2 border-t border-gray-200">
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
            <div className="flex gap-1 mb-2">
              <button
                onClick={writeEssay}
                disabled={loading}
                className="text-xs px-3 py-1 rounded-full bg-amber-100 text-amber-800 hover:bg-amber-200 transition disabled:opacity-50"
              >
                📝 Essay (up to 50 pages)
              </button>
              <button
                onClick={() => {
                  const doc = prompt("Paste text to summarize, or leave blank to open your documents:");
                  if (doc === null) return;
                  if (doc.trim()) {
                    const body = new URLSearchParams();
                    body.set("text", doc);
                    fetch("/api/v1/kudos/summarize", {
                      method: "POST",
                      headers: { ...getAuthHeader(), "Content-Type": "application/x-www-form-urlencoded" },
                      body,
                    })
                      .then((r) => r.json())
                      .then((d) => alert(`📋 ${d.title}\n\n${d.summary}`))
                      .catch(() => alert("Could not summarize that text."));
                  } else {
                    window.location.assign("/kudos/archive");
                  }
                }}
                className="text-xs px-3 py-1 rounded-full bg-sky-100 text-sky-800 hover:bg-sky-200 transition"
              >
                📋 Summarize
              </button>
            </div>
            <RadioPanel />
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
                ref={fileInputRef}
                type="file"
                multiple
                hidden
                onChange={handleFilesSelected}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                className="bg-white border px-3 py-3 rounded-xl text-lg hover:bg-gray-100 transition disabled:opacity-50"
                title="Attach files for KUDOS — images, video, audio, PDF, documents, code, or any file"
              >
                📎
              </button>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                className="flex-1 rounded-xl border px-4 py-3 text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none"
                placeholder="Ask KUDOS anything, or attach a file to teach it…"
                disabled={loading}
              />
              <button
                onClick={submit}
                disabled={loading || (attachments.length === 0 && !input.trim())}
                className="bg-purple-600 text-white px-6 py-3 rounded-xl font-medium hover:bg-purple-700 disabled:opacity-50 transition"
              >
                {loading ? "Thinking..." : attachments.length > 0 ? "📤 Feed KUDOS" : "⚔️ Ask"}
              </button>
            </div>

            {/* Pending attachments */}
            {attachments.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 mt-3">
                {attachments.map((f, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 text-xs bg-purple-50 border border-purple-200 text-purple-700 px-2 py-1 rounded-full max-w-[220px]"
                    title={f.name}
                  >
                    <span>{f.type.startsWith("image/") ? "🖼️" : f.type.startsWith("audio/") ? "🎵" : f.type.startsWith("video/") ? "🎬" : "📄"}</span>
                    <span className="truncate">{f.name}</span>
                    <button
                      onClick={() => removeAttachment(i)}
                      className="text-purple-400 hover:text-red-500"
                      title="Remove"
                    >
                      ✕
                    </button>
                  </span>
                ))}
                <button
                  onClick={() => setAttachments([])}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Clear all
                </button>
              </div>
            )}
            {askProgress.active && (
              <div className="mt-3">
                <ProgressBar label={askProgress.label} elapsed={askProgress.elapsed} />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
