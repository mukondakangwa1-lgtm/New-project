import { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ──────────────────────────────────────────────
// SPEAKING PRACTICE COMPONENT
// ──────────────────────────────────────────────

function SpeakingPractice() {
  const [difficulty, setDifficulty] = useState("beginner");
  const [prompt, setPrompt] = useState("");
  const [timer, setTimer] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [rating, setRating] = useState(0);
  const intervalRef = useRef<any>(null);

  const getPrompt = async () => {
    const res = await fetch(`/api/v1/studio/speaking/random-prompt?difficulty=${difficulty}`);
    if (res.ok) {
      const data = await res.json();
      setPrompt(data.prompt);
    }
  };

  const startPractice = async () => {
    if (!prompt) return;
    const res = await fetch("/api/v1/studio/speaking/session", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ prompt, duration_seconds: 120, difficulty }),
    });
    if (res.ok) {
      const data = await res.json();
      setSessionId(data.id);
      setIsRecording(true);
      setTimer(0);
      intervalRef.current = setInterval(() => setTimer((t) => t + 1), 1000);
    }
  };

  const stopPractice = async () => {
    setIsRecording(false);
    clearInterval(intervalRef.current);
    if (sessionId) {
      await fetch(`/api/v1/studio/speaking/session/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ session_id: sessionId, duration_spoken: timer, self_rating: rating || 3 }),
      });
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border shadow p-6">
        <h3 className="font-semibold text-lg mb-4">🎤 Speaking Practice</h3>
        <div className="flex gap-2 mb-4">
          {["beginner", "intermediate", "advanced", "debate"].map((d) => (
            <button key={d} onClick={() => setDifficulty(d)}
              className={`px-3 py-1 rounded-full text-sm ${difficulty === d ? "bg-primary text-white" : "bg-gray-100 hover:bg-gray-200"}`}>
              {d}
            </button>
          ))}
        </div>
        <button onClick={getPrompt} className="bg-blue-100 text-blue-700 px-4 py-2 rounded text-sm hover:bg-blue-200 mb-4">
          🎲 Get Random Prompt
        </button>
        {prompt && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg mb-4">
            <p className="font-medium text-sm text-yellow-800">Your Prompt:</p>
            <p className="text-lg mt-1">{prompt}</p>
          </div>
        )}
        {prompt && !isRecording && (
          <button onClick={startPractice} className="bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700">
            🎙️ Start Speaking
          </button>
        )}
        {isRecording && (
          <div className="text-center">
            <p className="text-6xl font-mono font-bold text-red-600 mb-4">{formatTime(timer)}</p>
            <div className="w-16 h-16 bg-red-500 rounded-full mx-auto mb-4 animate-pulse" />
            <p className="text-gray-600 mb-4">Recording... Speak now!</p>
            <div className="flex gap-2 justify-center mb-4">
              {[1, 2, 3, 4, 5].map((s) => (
                <button key={s} onClick={() => setRating(s)}
                  className={`text-2xl ${s <= rating ? "opacity-100" : "opacity-30"}`}>⭐</button>
              ))}
            </div>
            <button onClick={stopPractice} className="bg-red-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-red-700">
              ⏹ Stop & Save
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// LIVE BROADCAST COMPONENT
// ──────────────────────────────────────────────

function LiveBroadcast() {
  const [broadcasts, setBroadcasts] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(30);
  const [myBroadcast, setMyBroadcast] = useState<any>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchBroadcasts();
    const interval = setInterval(fetchBroadcasts, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchBroadcasts = async () => {
    const res = await fetch("/api/v1/studio/broadcast/active");
    if (res.ok) {
      const data = await res.json();
      setBroadcasts(data.broadcasts || []);
    }
  };

  const startBroadcast = async () => {
    if (!title) return;
    const res = await fetch("/api/v1/studio/broadcast/start", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title, description, duration_minutes: duration }),
    });
    if (res.ok) {
      const data = await res.json();
      setMyBroadcast(data);
      setMessage("🔴 You are now LIVE!");
      fetchBroadcasts();
    }
  };

  const stopBroadcast = async () => {
    await fetch("/api/v1/studio/broadcast/stop", { method: "POST", headers: getAuthHeader() });
    setMyBroadcast(null);
    setMessage("Broadcast ended");
    fetchBroadcasts();
  };

  return (
    <div className="space-y-6">
      {message && <div className="p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">{message}</div>}

      {!myBroadcast ? (
        <div className="bg-white rounded-xl border shadow p-6">
          <h3 className="font-semibold text-lg mb-4">📻 Start Broadcasting</h3>
          <div className="space-y-3">
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded border px-3 py-2 text-sm" placeholder="Broadcast title" />
            <textarea value={description} onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded border px-3 py-2 text-sm" rows={2} placeholder="Description (optional)" />
            <div>
              <label className="text-sm font-medium">Duration: {duration} minutes</label>
              <input type="range" min={5} max={120} value={duration} onChange={(e) => setDuration(parseInt(e.target.value))}
                className="w-full" />
            </div>
            <button onClick={startBroadcast} disabled={!title}
              className="w-full bg-red-600 text-white py-3 rounded-lg font-medium hover:bg-red-700 disabled:opacity-50">
              🔴 Go Live
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-red-50 border-2 border-red-500 rounded-xl p-6 text-center">
          <p className="text-2xl font-bold text-red-600 mb-2">🔴 LIVE</p>
          <p className="text-lg font-semibold">{myBroadcast.title}</p>
          <p className="text-gray-600">{myBroadcast.description}</p>
          <p className="text-sm text-gray-500 mt-2">{myBroadcast.listeners} listener(s)</p>
          <button onClick={stopBroadcast} className="mt-4 bg-gray-800 text-white px-6 py-2 rounded-lg hover:bg-gray-900">
            ⏹ End Broadcast
          </button>
        </div>
      )}

      {/* Active Broadcasts */}
      <div>
        <h3 className="font-semibold text-lg mb-3">🔴 Live Now ({broadcasts.length})</h3>
        {broadcasts.length === 0 ? (
          <p className="text-gray-500 text-sm">No active broadcasts</p>
        ) : (
          <div className="space-y-3">
            {broadcasts.map((b) => (
              <div key={b.id} className="bg-white rounded-lg border p-4 flex justify-between items-center">
                <div>
                  <p className="font-medium">{b.title}</p>
                  <p className="text-sm text-gray-500">by {b.host_name} • {b.listeners} listeners</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                  <span className="text-sm text-red-600 font-medium">LIVE</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Radio Garden */}
      <div className="bg-white rounded-xl border shadow p-6">
        <h3 className="font-semibold text-lg mb-4">🌍 Live Radio (Radio Garden)</h3>
        <p className="text-sm text-gray-500 mb-4">Listen to live radio stations from around the world</p>
        <iframe
          src="https://radio.garden/embed"
          className="w-full h-96 rounded-lg border"
          allow="autoplay"
          title="Radio Garden"
        />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// VIDEO CALL WITH WHITEBOARD COMPONENT
// ──────────────────────────────────────────────

function VideoCalls() {
  const [calls, setCalls] = useState<any[]>([]);
  const [title, setTitle] = useState("Video Call");
  const [isGroup, setIsGroup] = useState(false);
  const [activeCall, setActiveCall] = useState<any>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawColor, setDrawColor] = useState("#000000");
  const [drawSize, setDrawSize] = useState(3);
  const [strokes, setStrokes] = useState<any[]>([]);
  const [showWhiteboard, setShowWhiteboard] = useState(false);

  useEffect(() => {
    fetchCalls();
    const interval = setInterval(fetchCalls, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchCalls = async () => {
    const res = await fetch("/api/v1/studio/calls/active");
    if (res.ok) {
      const data = await res.json();
      setCalls(data.calls || []);
    }
  };

  const createCall = async () => {
    const res = await fetch("/api/v1/studio/calls/create", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title, is_group, max_participants: 10, enable_whiteboard: true, enable_screen_share: true }),
    });
    if (res.ok) {
      const data = await res.json();
      setActiveCall(data);
    }
  };

  // Whiteboard drawing
  const startDraw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.beginPath();
    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;
    const rect = canvasRef.current.getBoundingClientRect();
    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    ctx.strokeStyle = drawColor;
    ctx.lineWidth = drawSize;
    ctx.lineCap = "round";
    ctx.stroke();
  };

  const stopDraw = () => setIsDrawing(false);

  const clearWhiteboard = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  return (
    <div className="space-y-6">
      {!activeCall ? (
        <>
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">📹 Create Video Call</h3>
            <div className="space-y-3">
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm" placeholder="Call title" />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
                Group call (up to 10 participants)
              </label>
              <button onClick={createCall} className="w-full bg-green-600 text-white py-2 rounded-lg font-medium hover:bg-green-700">
                📹 Create Call Room
              </button>
            </div>
          </div>

          {calls.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-3">Active Calls</h3>
              {calls.map((c) => (
                <div key={c.id} className="bg-white rounded-lg border p-4 mb-3">
                  <p className="font-medium">{c.title}</p>
                  <p className="text-sm text-gray-500">{c.participants?.length} participant(s)</p>
                  <button onClick={() => setActiveCall(c)} className="mt-2 bg-green-100 text-green-700 px-4 py-1 rounded text-sm">
                    Join
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="bg-white rounded-xl border shadow overflow-hidden">
          {/* Call Header */}
          <div className="bg-gray-900 text-white p-4 flex justify-between items-center">
            <div>
              <p className="font-semibold">{activeCall.title}</p>
              <p className="text-xs text-gray-400">{activeCall.participants?.length} participant(s)</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setShowWhiteboard(!showWhiteboard)}
                className={`px-3 py-1 rounded text-sm ${showWhiteboard ? "bg-blue-600" : "bg-gray-700"}`}>
                🖊️ Whiteboard
              </button>
              <button onClick={() => setActiveCall(null)} className="bg-red-600 px-3 py-1 rounded text-sm">
                Leave
              </button>
            </div>
          </div>

          {/* Video Area */}
          <div className="relative">
            <div className="bg-gray-900 h-96 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <p className="text-6xl mb-4">📹</p>
                <p className="text-lg">Video call active</p>
                <p className="text-sm">WebRTC video would appear here</p>
                <div className="flex gap-2 justify-center mt-4">
                  {activeCall.participants?.map((p: any) => (
                    <div key={p.user_id} className="bg-gray-800 rounded-lg p-3 text-center">
                      <p className="text-3xl mb-1">👤</p>
                      <p className="text-xs">{p.name}</p>
                      <p className="text-xs text-gray-500">{p.role}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Whiteboard Overlay */}
            {showWhiteboard && (
              <div className="absolute inset-0 bg-white/90">
                <div className="flex gap-2 p-2 bg-gray-100 border-b">
                  <input type="color" value={drawColor} onChange={(e) => setDrawColor(e.target.value)} className="w-8 h-8" />
                  <input type="range" min={1} max={20} value={drawSize} onChange={(e) => setDrawSize(parseInt(e.target.value))} className="w-32" />
                  <button onClick={clearWhiteboard} className="bg-red-100 text-red-700 px-3 py-1 rounded text-xs">Clear</button>
                </div>
                <canvas ref={canvasRef} width={800} height={500}
                  className="w-full cursor-crosshair"
                  onMouseDown={startDraw} onMouseMove={draw} onMouseUp={stopDraw} onMouseLeave={stopDraw}
                />
              </div>
            )}
          </div>

          {/* Call Controls */}
          <div className="bg-gray-800 p-4 flex justify-center gap-4">
            <button className="bg-gray-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-600">🎤 Mute</button>
            <button className="bg-gray-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-600">📹 Video</button>
            <button className="bg-gray-700 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-600">🖥️ Share Screen</button>
            <button onClick={() => setShowWhiteboard(!showWhiteboard)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">🖊️ Whiteboard</button>
            <button onClick={() => setActiveCall(null)}
              className="bg-red-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-red-700">📞 Leave</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// JOURNAL PAGE (for journalists)
// ──────────────────────────────────────────────

function JournalPage() {
  const [blocks, setBlocks] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [blockType, setBlockType] = useState("webpage");
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetch("/api/v1/studio/journal/my", { headers: getAuthHeader() })
      .then((r) => r.json())
      .then((d) => setBlocks(d.blocks || []))
      .catch(() => {});
  }, []);

  const addBlock = async () => {
    if (!title) return;
    const res = await fetch("/api/v1/studio/journal/blocks", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title, block_type: blockType, url, position: blocks.length }),
    });
    if (res.ok) {
      const data = await res.json();
      setBlocks([...blocks, data]);
      setTitle("");
      setUrl("");
      setMessage("✅ Block added!");
    }
  };

  const removeBlock = async (id: number) => {
    await fetch(`/api/v1/studio/journal/blocks/${id}`, { method: "DELETE", headers: getAuthHeader() });
    setBlocks(blocks.filter((b) => b.id !== id));
  };

  return (
    <div className="space-y-6">
      {message && <div className="p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">{message}</div>}

      <div className="bg-white rounded-xl border shadow p-6">
        <h3 className="font-semibold text-lg mb-4">📰 Add Journal Block</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {[
            { value: "webpage", label: "🌐 Web Page", icon: "🌐" },
            { value: "youtube", label: "▶️ YouTube", icon: "▶️" },
            { value: "social", label: "📱 Social Media", icon: "📱" },
            { value: "video", label: "🎬 Video", icon: "🎬" },
            { value: "photo", label: "🖼️ Photo Gallery", icon: "🖼️" },
            { value: "text", label: "📝 Text Block", icon: "📝" },
            { value: "twitter", label: "🐦 Twitter/X", icon: "🐦" },
            { value: "facebook", label: "📘 Facebook", icon: "📘" },
          ].map((t) => (
            <button key={t.value} onClick={() => setBlockType(t.value)}
              className={`p-2 rounded text-xs ${blockType === t.value ? "bg-primary text-white" : "bg-gray-100 hover:bg-gray-200"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
            className="flex-1 rounded border px-3 py-2 text-sm" placeholder="Block title" />
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
            className="flex-1 rounded border px-3 py-2 text-sm" placeholder="URL (YouTube, Facebook, etc.)" />
          <button onClick={addBlock} className="bg-primary text-white px-4 py-2 rounded text-sm hover:bg-blue-800">
            Add
          </button>
        </div>
      </div>

      {/* Journal Blocks Grid */}
      {blocks.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <p className="text-5xl mb-3">📰</p>
          <p className="text-xl text-gray-600">Your Journal Page</p>
          <p className="text-gray-500">Add blocks to create your multi-platform dashboard</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {blocks.map((block) => (
            <div key={block.id} className="bg-white rounded-xl border shadow overflow-hidden">
              <div className="flex justify-between items-center p-3 bg-gray-50 border-b">
                <p className="font-medium text-sm">{block.title}</p>
                <button onClick={() => removeBlock(block.id)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
              </div>
              {block.url && (block.block_type === "youtube" || block.block_type === "video") ? (
                <iframe src={block.url.replace("watch?v=", "embed/")} className="w-full h-48" allowFullScreen title={block.title} />
              ) : block.url && block.block_type === "webpage" ? (
                <iframe src={block.url} className="w-full h-64" title={block.title} />
              ) : block.url && (block.block_type === "social" || block.block_type === "twitter" || block.block_type === "facebook") ? (
                <iframe src={block.url} className="w-full h-96" title={block.title} />
              ) : (
                <div className="p-4">
                  <p className="text-sm text-gray-600">{block.content || block.url || "No content"}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────
// MAIN STUDIO PAGE
// ──────────────────────────────────────────────

export default function Studio() {
  const [activeTab, setActiveTab] = useState<"speaking" | "broadcast" | "calls" | "journal">("speaking");

  return (
    <Layout>
      <h2 className="text-3xl font-bold mb-2">🎙️ Studio</h2>
      <p className="text-gray-600 mb-6">Practice speaking, broadcast live, video calls with whiteboard, and journalist pages</p>

      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { id: "speaking" as const, icon: "🎤", label: "Speaking Practice" },
          { id: "broadcast" as const, icon: "📻", label: "Live Broadcast" },
          { id: "calls" as const, icon: "📹", label: "Video Calls" },
          { id: "journal" as const, icon: "📰", label: "Journal" },
        ].map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${activeTab === t.id ? "bg-primary text-white" : "bg-white border hover:bg-gray-50"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {activeTab === "speaking" && <SpeakingPractice />}
      {activeTab === "broadcast" && <LiveBroadcast />}
      {activeTab === "calls" && <VideoCalls />}
      {activeTab === "journal" && <JournalPage />}
    </Layout>
  );
}
