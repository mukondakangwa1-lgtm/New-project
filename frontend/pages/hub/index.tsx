import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { getAuthHeader } from "@/lib/api";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";

interface Post {
  id: number;
  title: string;
  description: string;
  storage_url: string;
  storage_type: string;
  content_type: string;
  thumbnail_url: string;
  is_public: boolean;
  tags: string;
  view_count: number;
  created_at: string;
  author: { id: number; full_name: string; email: string };
  reaction_count: number;
  comment_count: number;
}
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

const STORAGE_ICONS: Record<string, string> = {
  youtube: "▶️",
  image: "🖼️",
  video: "🎬",
  document: "📄",
  link: "🔗",
};

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

export default function Hub() {
  const [tab, setTab] = useState<"feed" | "chat">("feed");

  // Feed state
  const [posts, setPosts] = useState<Post[]>([]);
  const [filter, setFilter] = useState("");
  const [feedLoading, setFeedLoading] = useState(true);

  // Chat state
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [newRoomName, setNewRoomName] = useState("");
  const [showNewRoom, setShowNewRoom] = useState(false);
  const [currentUserId, setCurrentUserId] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Current user id for chat / offline messages
  useEffect(() => {
    fetch("/api/v1/users/me", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => u && setCurrentUserId(u.id))
      .catch(() => {});
  }, []);

  // ── Feed ──────────────────────────────────────────────
  useEffect(() => {
    if (tab !== "feed") return;
    let url = "/api/v1/social/feed?limit=50";
    if (filter) url += `&storage_type=${filter}`;
    setFeedLoading(true);
    fetch(url)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setPosts(Array.isArray(d) ? d : []))
      .catch(() => setPosts([]))
      .finally(() => setFeedLoading(false));
  }, [tab, filter]);

  const react = async (postId: number) => {
    await fetch(`/api/v1/social/${postId}/react`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ emoji: "👍" }),
    });
    setTab("feed");
  };

  // ── Chat ──────────────────────────────────────────────
  const fetchRooms = async () => {
    const res = await fetch("/api/v1/chat/rooms", { headers: getAuthHeader() });
    if (res.ok) setRooms(await res.json());
  };

  useEffect(() => {
    if (tab === "chat") fetchRooms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!selectedRoom) return;

    fetch(`/api/v1/chat/rooms/${selectedRoom.id}/messages?limit=100`, { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => setMessages(Array.isArray(d) ? d : []))
      .catch(() => setMessages([]));

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/chat/ws/${selectedRoom.id}`);
    ws.onopen = () => {
      setIsConnected(true);
      const queue = getOfflineQueue().filter((m) => m.room_id === selectedRoom.id);
      if (queue.length > 0) {
        fetch(`/api/v1/chat/rooms/${selectedRoom.id}/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getAuthHeader() },
          body: JSON.stringify({ messages: queue, room_id: selectedRoom.id }),
        })
          .then((r) => r.ok && clearOfflineQueue())
          .catch(() => {});
      }
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "message") setMessages((prev) => [...prev, data]);
      else if (data.type === "online") setOnlineUsers(data.user_ids || []);
    };
    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);
    wsRef.current = ws;
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [selectedRoom?.id]);

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

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const timeStr = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <RequireRole roles={["user", "student", "admin"]} redirectTo="/kudos">
      <Layout>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-3xl font-bold">🌐 Hub</h2>
            <p className="text-gray-600 text-sm">
              Public campus posts + private 1:1 and group chats — all in one place
            </p>
          </div>
          <Link
            href="/hub/new"
            className="bg-primary text-white px-5 py-2 rounded-lg font-medium hover:bg-blue-800 transition"
          >
            + Share Resource
          </Link>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setTab("feed")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "feed" ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"
            }`}
          >
            📢 Campus Feed
          </button>
          <button
            onClick={() => setTab("chat")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === "chat" ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"
            }`}
          >
            💬 Private Chats
          </button>
        </div>

        {tab === "feed" && (
          <div>
            {/* Filters */}
            <div className="flex gap-2 mb-6 flex-wrap">
              {["", "link", "youtube", "image", "video", "document"].map((t) => (
                <button
                  key={t}
                  onClick={() => setFilter(t)}
                  className={`px-3 py-1 rounded-full text-sm transition ${
                    filter === t ? "bg-primary text-white" : "bg-white border text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {t || "All"}
                </button>
              ))}
            </div>

            {feedLoading ? (
              <p className="text-gray-500">Loading feed...</p>
            ) : posts.length === 0 ? (
              <div className="text-center py-16 bg-white rounded-xl border">
                <p className="text-5xl mb-3">🌐</p>
                <p className="text-xl text-gray-600 mb-2">No posts yet</p>
                <p className="text-gray-500">Be the first to share a resource!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {posts.map((post) => (
                  <div
                    key={post.id}
                    className="bg-white rounded-xl border shadow hover:shadow-lg transition overflow-hidden"
                  >
                    {post.thumbnail_url ? (
                      <img src={post.thumbnail_url} alt={post.title} className="w-full h-48 object-cover" />
                    ) : (
                      <div className="w-full h-32 bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center text-5xl">
                        {STORAGE_ICONS[post.storage_type] || "🔗"}
                      </div>
                    )}
                    <div className="p-5">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                          {STORAGE_ICONS[post.storage_type]} {post.storage_type}
                        </span>
                        {post.content_type && (
                          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                            {post.content_type}
                          </span>
                        )}
                      </div>
                      <h3 className="font-semibold text-lg mb-1 line-clamp-2">{post.title}</h3>
                      {post.description && (
                        <p className="text-sm text-gray-500 mb-3 line-clamp-2">{post.description}</p>
                      )}
                      <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
                        <span>by {post.author?.full_name || "Unknown"}</span>
                        <span>{timeAgo(post.created_at)}</span>
                      </div>
                      {post.tags && (
                        <div className="flex gap-1 flex-wrap mb-3">
                          {post.tags.split(",").map((tag, i) => (
                            <span key={i} className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                              #{tag.trim()}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center gap-4 pt-3 border-t">
                        <a
                          href={post.storage_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary text-sm font-medium hover:underline flex-1"
                        >
                          Open Resource →
                        </a>
                        <button
                          onClick={() => react(post.id)}
                          className="text-sm text-gray-500 hover:text-primary transition"
                        >
                          👍 {post.reaction_count || ""}
                        </button>
                        <span className="text-sm text-gray-400">👁 {post.view_count}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "chat" && (
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
                  <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
                    {messages.length === 0 && (
                      <p className="text-center text-gray-400 text-sm py-8">No messages yet. Say hello! 👋</p>
                    )}
                    {messages.map((msg, i) => {
                      const isMe = msg.user_id === currentUserId;
                      return (
                        <div key={i} className={`flex ${isMe ? "justify-end" : "justify-start"}`}>
                          <div
                            className={`max-w-[70%] rounded-lg px-4 py-2 ${
                              isMe ? "bg-primary text-white" : "bg-white border shadow-sm"
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
        )}
      </Layout>
    </RequireRole>
  );
}
