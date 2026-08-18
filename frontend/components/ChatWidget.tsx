import { useEffect, useRef, useState } from "react";
import { X, MessageSquare, Send, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ChatMessage {
  id: number;
  role: string;
  content: string;
  created_at?: string;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const getSessionId = () => {
    if (typeof window === "undefined") return "";
    let id = window.localStorage.getItem("kudos_session_id");
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem("kudos_session_id", id);
    }
    return id;
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isOpen]);

  const send = async () => {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setLoading(true);

    const newUserMsg = { id: Date.now(), role: "user", content: question };
    setMessages((prev) => [...prev, newUserMsg]);

    try {
      const data = await apiFetch("/api/v1/kudos/chat", {
        method: "POST",
        body: JSON.stringify({ message: question, sessionId: getSessionId() }),
      });
      
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "kudos", content: data.reply },
      ]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-purple-700 hover:bg-purple-800 text-white p-4 rounded-full shadow-lg z-50 flex items-center gap-2 transition"
        aria-label="Open chat"
      >
        <MessageSquare size={24} />
        <span className="font-semibold text-sm">Chat with Kudos</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-white rounded-2xl border border-gray-200 shadow-2xl z-50 flex flex-col overflow-hidden">
      <div className="bg-purple-700 p-4 text-white flex justify-between items-center">
        <h3 className="font-semibold flex items-center gap-2">
          <MessageSquare size={18} /> Chat with Kudos
        </h3>
        <button onClick={() => setIsOpen(false)} className="hover:bg-purple-800 p-1 rounded transition">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${m.role === "user" ? "bg-purple-600 text-white" : "bg-white border border-gray-200 text-gray-800"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-gray-400">
              <Loader2 className="animate-spin" size={16} />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="p-3 border-t bg-white flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
          placeholder="Ask Kudos anything..."
        />
        <button onClick={send} className="bg-purple-700 text-white p-2 rounded-lg hover:bg-purple-800 disabled:opacity-50" disabled={loading}>
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
