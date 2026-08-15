import { useState, useEffect, useRef } from 'react';
import { ChatBubbleLeftRightIcon, XMarkIcon } from '@heroicons/react/24/outline';

/**
 * ChatWidget: A floating, bottom-right component that provides a
 * collapsible interface to interact with KudosGuestChat logic.
 */
export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const getSessionId = () => {
    if (typeof window === "undefined") return "";
    let id = window.localStorage.getItem("kudos_guest_id");
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem("kudos_guest_id", id);
    }
    return id;
  };

  useEffect(() => {
    if (isOpen) {
      // Load initial chat state if empty
      if (messages.length === 0) {
        setMessages([{ id: 0, role: 'kudos', content: "Hi 👋 Welcome to Digital Campus — I'm KUDOS. How can I help you today?" }]);
      }
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isOpen]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;
    
    setInput("");
    setLoading(true);
    setError("");

    setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: question }]);

    try {
      const res = await fetch('/api/v1/kudos/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, sessionId: getSessionId() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error connecting to KUDOS");
      
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: 'kudos', content: data.reply }]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen ? (
        <div className="w-[350px] h-[500px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden animate-in fade-in zoom-in duration-300">
          <div className="bg-gradient-to-r from-purple-700 to-indigo-700 p-4 text-white flex justify-between items-center">
            <h3 className="font-bold">Chat with Kudos</h3>
            <button onClick={() => setIsOpen(false)} className="hover:bg-white/20 p-1 rounded-full">
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-800'}`}>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && <div className="text-xs text-gray-500 italic px-2">Kudos is thinking...</div>}
            <div ref={endRef} />
          </div>

          <div className="p-3 border-t bg-white">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask Kudos..."
                className="flex-1 border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button 
                onClick={sendMessage}
                disabled={loading}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                Send
              </button>
            </div>
            {error && <p className="text-red-500 text-[10px] mt-1">{error}</p>}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-indigo-700 text-white p-4 rounded-full shadow-lg hover:scale-105 transition-transform flex items-center justify-center gap-2 group"
          aria-label="Open Chat with Kudos"
        >
          <ChatBubbleLeftRightIcon className="w-6 h-6" />
          <span className="hidden group-hover:block text-sm font-medium pr-1">Chat with Kudos</span>
        </button>
      )}
    </div>
  );
}
