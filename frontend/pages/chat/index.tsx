import { useState, useEffect, useRef, useCallback } from "react";
import Layout from "@/components/Layout";

interface Room {
  id: number;
  name: string;
  is_group: boolean;
  created_by: number;
  created_at: string;
}
interface Message {
  id?: number;
  room_id: number;
  user_id: number;
  user_name?: string;
  content: string;
  message_type: string;
  is_offline: boolean;
  created_at: string;
  user?: { id: number; full_name: string; email: string };
}
interface User {
  id: number;
  full_name: string;
  email: string;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

function getCurrentUserId(): number {
  if (typeof window === "undefined") return 0;
  try {
    const token = localStorage.getItem("token");
    if (!token) return 0;
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.user_id || 0;
  } catch {
    return 0;
  }
}

// Offline message queue (persisted in localStorage)
const OFFLINE_QUEUE_KEY = "dc_offline_messages";

function getOfflineQueue(): Message[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function addToOfflineQueue(msg: Message) {
  const queue = getOfflineQueue();
  queue.push(msg);
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
}

function clearOfflineQueue() {
  localStorage.removeItem(OFFLINE_QUEUE_KEY);
}

export default function ChatPage() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [newRoomName, setNewRoomName] = useState("");
  const [showNewRoom, setShowNewRoom] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentUserId = getCurrentUserId();

  // Load rooms
  useEffect(() => {
    fetchRooms();
  }, []);

  const fetchRooms = async () => {
    const res = await fetch("/api/v1/chat/rooms", { headers: getAuthHeader() });
    if (res.ok) setRooms(await res.json());
  };

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Connect WebSocket when room selected
  useEffect(() => {
    if (!selectedRoom) return;

    // Load history
    fetch(`/api/v1/chat/rooms/${selectedRoom.id}/messages?limit=100`, {
      headers: getAuthHeader(),
    })
      .then((r) => r.json())
      .then((data) => setMessages(Array.isArray(data) ? data : []))
      .catch(() => setMessages([]));

    // Connect WebSocket
    const token = getToken();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(
      `${protocol}//${host}/api/v1/chat/ws/${selectedRoom.id}?token=${token}`
    );

    ws.onopen = () => {
      setIsConnected(true);
      // Sync offline messages
      syncOfflineMessages(selectedRoom.id);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "message") {
        setMessages((prev) => [...prev, data]);
      } else if (data.type === "online") {
        setOnlineUsers(data.user_ids || []);
      }
    };

    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);

    wsRef.current = ws;
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [selectedRoom?.id]);

  const syncOfflineMessages = async (roomId: number) => {
    const queue = getOfflineQueue().filter((m) => m.room_id === roomId);
    if (queue.length === 0) return;

    try {
      const res = await fetch(`/api/v1/chat/rooms/${roomId}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ messages: queue, room_id: roomId }),
      });
      if (res.ok) {
        clearOfflineQueue();
      }
    } catch {}
  };

  const sendMessage = () => {
    if (!input.trim() || !selectedRoom) return;

    const msg: Message = {
      room_id: selectedRoom.id,
      user_id: currentUserId,
      content: input.trim(),
      message_type: "text",
      is_offline: !isConnected,
      created_at: new Date().toISOString(),
    };

    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({ content: input.trim(), message_type: "text" }));
    } else {
      // Offline — queue locally and show immediately
      addToOfflineQueue(msg);
      setMessages((prev) => [...prev, { ...msg, user_name: "You (offline)" }]);
    }

    setInput("");
  };

  const createRoom = async () => {
    if (!newRoomName.trim()) return;
    const res = await fetch("/api/v1/chat/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ name: newRoomName, is_group: true }),
    });
    if (res.ok) {
      setNewRoomName("");
      setShowNewRoom(false);
      fetchRooms();
    }
  };

  const timeStr = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">💬 Chat</h2>
      <p className="text-gray-600 mb-6">
        Real-time messaging — works online via WebSocket, offline messages sync when reconnected
      </p>

      <div className="flex gap-4 h-[600px] bg-white rounded-xl border shadow overflow-hidden">
        {/* Sidebar — rooms */}
        <div className="w-64 border-r flex flex-col">
          <div className="p-4 border-b flex justify-between items-center">
            <h3 className="font-semibold">Rooms</h3>
            <button
              onClick={() => setShowNewRoom(!showNewRoom)}
              className="text-primary text-xl hover:bg-gray-100 w-8 h-8 rounded"
            >
              +
            </button>
          </div>

          {showNewRoom && (
            <div className="p-3 border-b bg-gray-50">
              <input
                type="text"
                value={newRoomName}
                onChange={(e) => setNewRoomName(e.target.value)}
                placeholder="Room name..."
                className="w-full rounded border px-2 py-1 text-sm mb-2"
                onKeyDown={(e) => e.key === "Enter" && createRoom()}
              />
              <button
                onClick={createRoom}
                className="w-full bg-primary text-white text-sm py-1 rounded hover:bg-blue-800"
              >
                Create Room
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {rooms.length === 0 ? (
              <p className="text-sm text-gray-400 p-4">No rooms yet. Create one!</p>
            ) : (
              rooms.map((room) => (
                <button
                  key={room.id}
                  onClick={() => setSelectedRoom(room)}
                  className={`w-full text-left px-4 py-3 border-b hover:bg-gray-50 transition ${
                    selectedRoom?.id === room.id ? "bg-blue-50 border-l-4 border-l-primary" : ""
                  }`}
                >
                  <p className="font-medium text-sm">{room.is_group ? "👥 " : ""}{room.name}</p>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col">
          {!selectedRoom ? (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <p className="text-5xl mb-3">💬</p>
                <p>Select a room to start chatting</p>
              </div>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="px-4 py-3 border-b flex justify-between items-center bg-gray-50">
                <div>
                  <h4 className="font-semibold">{selectedRoom.name}</h4>
                  <p className="text-xs text-gray-400">
                    {isConnected ? (
                      <span className="text-green-600">● Online</span>
                    ) : (
                      <span className="text-orange-500">● Offline — messages will sync</span>
                    )}
                    {onlineUsers.length > 0 && ` • ${onlineUsers.length} online`}
                  </p>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
                {messages.length === 0 && (
                  <p className="text-center text-gray-400 text-sm py-8">
                    No messages yet. Say hello! 👋
                  </p>
                )}
                {messages.map((msg, i) => {
                  const isMe = msg.user_id === currentUserId;
                  return (
                    <div key={i} className={`flex ${isMe ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[70%] rounded-lg px-4 py-2 ${
                          isMe
                            ? "bg-primary text-white"
                            : "bg-white border shadow-sm"
                        } ${msg.is_offline ? "opacity-70" : ""}`}
                      >
                        {!isMe && (
                          <p className={`text-xs font-semibold mb-1 ${isMe ? "text-blue-200" : "text-primary"}`}>
                            {msg.user_name || msg.user?.full_name || `User ${msg.user_id}`}
                          </p>
                        )}
                        <p className="text-sm">{msg.content}</p>
                        <p className={`text-xs mt-1 ${isMe ? "text-blue-200" : "text-gray-400"}`}>
                          {timeStr(msg.created_at)}
                          {msg.is_offline && " 📤"}
                        </p>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="p-4 border-t bg-white">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    className="flex-1 rounded-lg border px-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    placeholder={isConnected ? "Type a message..." : "Type (will send when online)..."}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim()}
                    className="bg-primary text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-800 disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
