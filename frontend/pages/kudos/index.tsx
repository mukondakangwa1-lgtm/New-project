import { useState, useEffect, useRef } from "react";
import { getAuthHeader, signOut } from "@/lib/api";
import Layout from "@/components/Layout";
import { ProgressBar, useLongProcess } from "@/components/ProgressBar";
import KudosGuestChat from "@/components/KudosGuestChat";
import RadioPanel from "@/components/RadioPanel";
import MessageContent from "@/components/MessageContent";
import KudosMic from "@/components/KudosMic";
import LauncherDock from "@/components/LauncherDock";
import SiteMaker, { type SiteKind } from "@/components/SiteMaker";

interface MicResult {
  transcript: string;
  answer: string;
  audioB64: string;
  mimeType: string;
}

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
  last_message?: string;
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
  const [siteMakerOpen, setSiteMakerOpen] = useState<SiteKind | null>(null);
  const askProgress = useLongProcess();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [sidebarVisible, setSidebarVisible] = useState(true);
  const sidebarTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (sidebarTimer.current) clearTimeout(sidebarTimer.current);
    sidebarTimer.current = setTimeout(() => setSidebarVisible(false), 3000);
    return () => {
      if (sidebarTimer.current) clearTimeout(sidebarTimer.current);
    };
  }, []);

  // Play KUDOS's spoken answer (TTS) straight from the base64 payload.
  const playBase64Audio = (b64: string, mime: string) => {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const url = URL.createObjectURL(new Blob([bytes], { type: mime || "audio/mpeg" }));
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audio.play().catch(() => URL.revokeObjectURL(url));
    } catch {
      /* best-effort playback */
    }
  };

  // Result of the voice loop (short-press = text answer, long-press = + spoken reply).
  const handleMicResult = (res: MicResult) => {
    const now = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: res.transcript || "🎤 Voice message",
        sources: "",
        created_at: now,
      },
      {
        id: Date.now() + 1,
        role: "kudos",
        content: res.answer,
        sources: "",
        created_at: now,
      },
    ]);
    if (res.audioB64) playBase64Audio(res.audioB64, res.mimeType);
  };

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
        await refreshConversations();
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

      await refreshConversations();
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

  const hideSidebarSoon = (ms = 3000) => {
    if (sidebarTimer.current) clearTimeout(sidebarTimer.current);
    sidebarTimer.current = setTimeout(() => setSidebarVisible(false), ms);
  };

  const showSidebar = () => {
    setSidebarVisible(true);
    hideSidebarSoon();
  };

  const refreshConversations = async () => {
    const convRes = await fetch("/api/v1/kudos/conversations", { headers: getAuthHeader() });
    if (convRes.ok) {
      setConversations(await convRes.json());
      showSidebar();
    }
  };

  const summarizeDoc = async () => {
    const doc = prompt("Paste text to summarize, or leave blank to open your documents:");
    if (doc === null) return;
    if (doc.trim()) {
      const body = new URLSearchParams();
      body.set("text", doc);
      try {
        const res = await fetch("/api/v1/kudos/summarize", {
          method: "POST",
          headers: { ...getAuthHeader(), "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });
        const data = await res.json();
        alert(`📋 ${data.title}\n\n${data.summary}`);
      } catch {
        alert("Could not summarize that text.");
      }
    } else {
      window.location.assign("/kudos/archive");
    }
  };

  const learnGoogle = async () => {
    const q = prompt("What do you want me to search Google for?");
    if (!q) return;
    const res = await fetch(`/api/v1/kudos/social/google?query=${encodeURIComponent(q)}&max_results=3`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) alert(`✅ ${(await res.json()).message}`);
  };

  const learnWikipedia = async () => {
    const q = prompt("What topic should I learn from Wikipedia?");
    if (!q) return;
    const res = await fetch(`/api/v1/kudos/social/learn-wikipedia-batch?topics=${encodeURIComponent(q)}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) alert(`✅ ${(await res.json()).message}`);
  };

  const learnSocial = async (platform = "general") => {
    const res = await fetch(`/api/v1/kudos/social/learn-social?platform=${platform}`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) alert(`✅ ${(await res.json()).message}`);
  };

  const learnEmotions = async () => {
    const res = await fetch("/api/v1/kudos/social/learn-emotions", {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) alert(`✅ ${(await res.json()).message}`);
  };

  const learnReddit = async () => {
    const sub = prompt("Which subreddit? (e.g. LifeProTips, AskReddit, advice)");
    if (!sub) return;
    const res = await fetch(`/api/v1/kudos/social/learn-reddit?subreddit=${encodeURIComponent(sub)}&limit=5`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (res.ok) alert(`✅ ${(await res.json()).message}`);
  };

  const launcherActions = [
    { icon: "💬", label: "Conversations", hint: "Show the sidebar", onClick: showSidebar },
    { icon: "➕", label: "New Conversation", onClick: newConversation },
    { icon: "📝", label: "Essay (up to 50 pages)", onClick: writeEssay },
    { icon: "📋", label: "Summarize", onClick: summarizeDoc },
    ...[
      { id: "battlemode", icon: "⚔️", label: "Arena: Battle" },
      { id: "agent", icon: "🤖", label: "Arena: Agent" },
      { id: "sidebyside", icon: "📊", label: "Arena: Compare" },
      { id: "directchat", icon: "💬", label: "Arena: Direct" },
    ].map((m) => ({
      icon: m.icon,
      label: m.label,
      hint: "Set how KUDOS answers",
      active: arenaMode === m.id,
      onClick: () => setArenaMode(m.id),
    })),
    { icon: "🔍", label: "Google Search", onClick: learnGoogle },
    { icon: "📚", label: "Learn Wikipedia", onClick: learnWikipedia },
    { icon: "🗣️", label: "Social Skills", onClick: () => learnSocial("general") },
    { icon: "💝", label: "Human Emotions", onClick: learnEmotions },
    { icon: "🤖", label: "Reddit", onClick: learnReddit },
    { icon: "💬", label: "Discord", onClick: () => learnSocial("discord") },
    { icon: "🚪", label: "Log out", onClick: handleLogout },
  ];

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
      <div className="min-h-[calc(100vh-150px)] flex flex-col rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
        {/* Header */}
        <div className="px-4 md:px-5 py-4 border-b border-zinc-800 bg-zinc-900 flex flex-wrap justify-between items-center gap-3">
          <div>
            <h2 className="text-2xl font-bold text-zinc-50">🧠 KUDOS</h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Your AI knowledge assistant — everything is a tap away on the ✦ launcher
            </p>
          </div>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* Sidebar — conversations */}
          <div
            className={`shrink-0 overflow-hidden transition-all duration-500 ${sidebarVisible ? "opacity-100" : "opacity-0"}`}
            style={{ maxWidth: sidebarVisible ? 280 : 0 }}
            onMouseEnter={() => {
              if (sidebarTimer.current) clearTimeout(sidebarTimer.current);
            }}
            onMouseLeave={() => hideSidebarSoon()}
          >
            <div className="w-52 md:w-64 h-full flex-col border-r border-zinc-800 bg-zinc-950 flex">
              <div className="p-3 border-b border-zinc-800">
                <button
                  onClick={newConversation}
                  className="w-full bg-amber-500 text-zinc-950 text-sm font-semibold py-2 rounded-lg hover:bg-amber-400 transition"
                >
                  + New Conversation
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {conversations.length === 0 ? (
                  <p className="text-xs text-zinc-600 p-4">No conversations yet</p>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.id}
                      className={`px-3 py-2 border-b border-zinc-900 cursor-pointer hover:bg-zinc-900 group flex justify-between items-start gap-2 ${
                        currentConvId === conv.id ? "bg-amber-500/10" : ""
                      }`}
                      onClick={() => { setCurrentConvId(conv.id); setAttachments([]); }}
                    >
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm truncate ${currentConvId === conv.id ? "text-amber-300" : "text-zinc-300"}`}>
                          {conv.title}
                        </p>
                        {conv.last_message && (
                          <p className="text-xs text-zinc-500 truncate mt-0.5">{conv.last_message}</p>
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConv(conv.id);
                        }}
                        className="text-xs text-red-400 opacity-0 group-hover:opacity-100 shrink-0"
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Chat area */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-zinc-900">
              {messages.length === 0 && (
                <div className="text-center py-10">
                  <p className="text-6xl mb-4">🧠</p>
                  <h3 className="text-2xl font-bold text-zinc-100 mb-2">
                    {userName ? `Welcome back, ${userName}!` : "Hi! I'm KUDOS"}
                  </h3>
                  <p className="text-zinc-400 max-w-md mx-auto">
                    Ask me anything — everything else lives on the ✦ launcher button
                    (bottom-right): documents, teaching, admin, essays, learning and more.
                  </p>
                  <p className="text-zinc-600 text-xs mt-4">
                    Tip: press Enter to send, attach files, or hold the mic to talk.
                  </p>
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-5 py-3 ${
                      msg.role === "user"
                        ? "bg-amber-500 text-zinc-950 rounded-br-sm"
                        : "bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-bl-sm"
                    }`}
                  >
                    {msg.role === "kudos" && (
                      <div className="flex items-center gap-3 mb-1">
                        <p className="text-xs font-bold text-amber-400">🧠 KUDOS</p>
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
                                    className="rounded-lg border border-zinc-600 max-h-40"
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
                                    className="rounded-lg border border-zinc-600 max-h-40"
                                  />
                                );
                              }
                              return (
                                <a
                                  key={i}
                                  href={m.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-xs bg-zinc-900 border border-zinc-700 text-zinc-400 rounded px-2 py-1 hover:bg-zinc-800"
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
                                    className="rounded-lg border border-zinc-700 max-w-full"
                                  />
                                </div>
                              ) : (
                                <div key={i} className="space-y-1">
                                  <video
                                    src={m.url}
                                    controls
                                    className="rounded-lg border border-zinc-700 max-w-full bg-black"
                                    style={{ maxHeight: 320 }}
                                  />
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
                          <div className="mt-3 pt-2 border-t border-zinc-700">
                            <p className="text-xs text-zinc-500 font-medium mb-1">Learned from your attachments:</p>
                            {learned.map((l, i) => (
                              <p key={i} className="text-xs text-zinc-500">
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
                    {msg.role === "kudos" && msg.sources && (
                      <div className="mt-3 pt-2 border-t border-zinc-700">
                        {(() => {
                          try {
                            const srcs: Source[] = JSON.parse(msg.sources);
                            return srcs.length > 0 ? (
                              <div className="space-y-1">
                                <p className="text-xs text-zinc-500 font-medium">Sources:</p>
                                {srcs.map((s, i) => (
                                  <p key={i} className="text-xs text-zinc-500">
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
                  <div className="bg-zinc-800 border border-zinc-700 rounded-2xl rounded-bl-sm px-5 py-3">
                    <p className="text-xs font-bold text-amber-400 mb-1">🧠 KUDOS</p>
                    <p className="text-sm text-zinc-400 animate-pulse">Thinking...</p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-900">
              <RadioPanel />
              <div className="flex gap-3 items-center">
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
                  className="bg-zinc-800 border border-zinc-700 px-3 py-3 rounded-xl text-lg hover:bg-zinc-700 transition disabled:opacity-50 text-zinc-300"
                  title="Attach files for KUDOS — images, video, audio, PDF, documents, code, or any file"
                >
                  📎
                </button>
                <KudosMic
                  conversationId={currentConvId}
                  disabled={loading}
                  onResult={handleMicResult}
                  onError={(m) => alert(m)}
                />
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  className="flex-1 rounded-xl bg-zinc-800 border border-zinc-700 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:ring-2 focus:ring-amber-400 focus:border-amber-400 focus:outline-none"
                  placeholder="Ask KUDOS anything, attach a file, or hold the mic…"
                  disabled={loading}
                />
                <button
                  onClick={submit}
                  disabled={loading || (attachments.length === 0 && !input.trim())}
                  className="bg-amber-500 text-zinc-950 px-6 py-3 rounded-xl font-semibold hover:bg-amber-400 disabled:opacity-50 transition"
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
                      className="inline-flex items-center gap-1 text-xs bg-amber-500/10 border border-amber-500/40 text-amber-300 px-2 py-1 rounded-full max-w-[220px]"
                      title={f.name}
                    >
                      <span>{f.type.startsWith("image/") ? "🖼️" : f.type.startsWith("audio/") ? "🎵" : f.type.startsWith("video/") ? "🎬" : "📄"}</span>
                      <span className="truncate">{f.name}</span>
                      <button
                        onClick={() => removeAttachment(i)}
                        className="text-amber-400 hover:text-red-400"
                        title="Remove"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                  <button
                    onClick={() => setAttachments([])}
                    className="text-xs text-zinc-500 hover:text-zinc-300 underline"
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
      </div>

      <LauncherDock onOpen={setSiteMakerOpen} actions={launcherActions} />
      <SiteMaker open={siteMakerOpen !== null} kind={siteMakerOpen || "site"} onClose={() => setSiteMakerOpen(null)} />
    </Layout>
  );
}
