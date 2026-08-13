import { useEffect, useRef, useState } from "react";
import Layout from "@/components/Layout";
import KudosMic from "@/components/KudosMic";

interface GuestMessage {
  id: number;
  role: string;
  content: string;
  created_at?: string;
}

/**
 * Public KUDOS chat for anonymous visitors. The browser generates a
 * persistent guest_id (localStorage) so the conversation survives refreshes.
 * When the user signs in, an inline prompt converts the chat into a real
 * account conversation.
 */
export default function KudosGuestChat() {
  const [messages, setMessages] = useState<GuestMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const getGuestId = () => {
    if (typeof window === "undefined") return "";
    let id = window.localStorage.getItem("kudos_guest_id");
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem("kudos_guest_id", id);
    }
    return id;
  };

  // Play KUDOS's spoken answer from the base64 audio payload.
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

  // Voice loop result: show the transcript + answer and speak the reply.
  const handleMicResult = (res: { transcript: string; answer: string; audioB64: string; mimeType: string }) => {
    const now = new Date().toISOString();
    if (res.transcript) {
      setMessages((prev) => [...prev, { id: Date.now(), role: "user", content: res.transcript, created_at: now }]);
    }
    setMessages((prev) => [...prev, { id: Date.now() + 1, role: "kudos", content: res.answer, created_at: now }]);
    if (res.audioB64) playBase64Audio(res.audioB64, res.mimeType);
  };

  useEffect(() => {
    const id = getGuestId();
    fetch(`/api/v1/kudos/guest/messages?guest_id=${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then((d) => Array.isArray(d) && d.length > 0 && setMessages(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setLoading(true);
    setError("");

    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content: question },
    ]);

    try {
      const res = await fetch("/api/v1/kudos/guest/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, guest_id: getGuestId() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "KUDOS couldn't answer right now");
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "kudos", content: data.answer },
      ]);
    } catch (e: any) {
      setError(e.message || "Something went wrong — please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto mt-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-[78vh]">
          {/* Header */}
          <div className="px-5 py-4 border-b bg-gradient-to-r from-purple-700 to-indigo-700 text-white">
            <h2 className="text-xl font-bold">🧠 KUDOS — public chat</h2>
            <p className="text-sm text-purple-100 mt-1">
              No account needed. Ask about courses, assignments, campus life and more.{" "}
              <a href="/login" className="underline font-medium hover:text-white">
                Sign in
              </a>{" "}
              to keep your conversations.
            </p>
          </div>

          {/* Messages */}
          <div className="flex-1 p-4 overflow-y-auto bg-gray-50 space-y-3" style={{ minHeight: 420 }}>
            {messages.length === 0 && !loading && (
              <div className="h-full flex flex-col items-center justify-center text-center py-10">
                <div className="text-6xl mb-3">🤖</div>
                <h3 className="text-2xl font-bold text-gray-800">Hi! I'm KUDOS</h3>
                <p className="text-gray-500 mt-2 max-w-xs">
                  Ask me anything — courses, assignments, timetables, campus services. No account needed.
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-primary text-white rounded-br-sm"
                      : "bg-white border border-gray-200 rounded-bl-sm"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-400">
                  KUDOS is thinking…
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="border-t bg-white px-4 py-3">
            {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
            <div className="flex gap-2 items-center">
              <KudosMic
                variant="guest"
                guestId={getGuestId()}
                disabled={loading}
                onResult={handleMicResult}
                onError={(m) => setError(m)}
              />
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Ask KUDOS anything, or turn the mic on…"
                className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={send}
                disabled={loading}
                className="px-5 py-2.5 rounded-lg bg-purple-700 text-white text-sm font-semibold hover:bg-purple-800 disabled:opacity-50 transition"
              >
                {loading ? "…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}