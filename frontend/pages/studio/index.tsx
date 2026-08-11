import { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";
import RequireRole from "@/components/RequireRole";
import {
  getAuthHeader,
  handleSignal,
  makePeerConnection,
  createOffer,
  createAnswer,
  stopTracks,
} from "@/lib/webrtc";

// ──────────────────────────────────────────────
// SPEAKING PRACTICE (real audio recording)
// ──────────────────────────────────────────────

function SpeakingPractice() {
  const [difficulty, setDifficulty] = useState("beginner");
  const [prompt, setPrompt] = useState("");
  const [timer, setTimer] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [rating, setRating] = useState(0);
  const [history, setHistory] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [audioDownloadUrl, setAudioDownloadUrl] = useState("");
  const intervalRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const loadHistory = async () => {
    const res = await fetch("/api/v1/studio/speaking/history", { headers: getAuthHeader() });
    if (res.ok) setHistory((await res.json()).sessions || []);
  };

  useEffect(() => {
    loadHistory();
    return () => {
      clearInterval(intervalRef.current);
      stopTracks(streamRef.current);
    };
  }, []);

  const getPrompt = async () => {
    const res = await fetch(`/api/v1/studio/speaking/random-prompt?difficulty=${difficulty}`);
    if (res.ok) {
      const data = await res.json();
      setPrompt(data.prompt);
      setAudioUrl("");
      setAudioDownloadUrl("");
      setRating(0);
    }
  };

  const startPractice = async () => {
    if (!prompt) return;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setMessage("❌ Microphone access denied. Allow the mic and try again (HTTPS required).");
      return;
    }

    const res = await fetch("/api/v1/studio/speaking/session", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ prompt, duration_seconds: 120, difficulty }),
    });
    if (!res.ok) {
      stopTracks(stream);
      return;
    }
    const data = await res.json();

    streamRef.current = stream;
    chunksRef.current = [];
    try {
      const mime = pickMime();
      mediaRecorderRef.current = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
    } catch {
      mediaRecorderRef.current = new MediaRecorder(stream);
    }
    mediaRecorderRef.current.ondataavailable = (ev) => {
      if (ev.data.size > 0) chunksRef.current.push(ev.data);
    };
    try {
      mediaRecorderRef.current.start();
    } catch (e: any) {
      setMessage("❌ Could not start recording in this browser. Please use a recent Chrome, Edge, Firefox or Safari.");
      stopTracks(stream);
      return;
    }

    setSessionId(data.id);
    setIsRecording(true);
    setTimer(0);
    setMessage("");
    intervalRef.current = setInterval(() => setTimer((t) => t + 1), 1000);
  };

  const stopPractice = async () => {
    setIsRecording(false);
    clearInterval(intervalRef.current);
    stopTracks(streamRef.current);

    if (!sessionId) return;

    // Finish recording into a blob
    const recorder = mediaRecorderRef.current;
    const done = new Promise<Blob | null>((resolve) => {
      if (!recorder || recorder.state === "inactive") return resolve(null);
      recorder.onstop = () => {
        const mime = recorder.mimeType || "audio/webm";
        resolve(new Blob(chunksRef.current, { type: mime }));
      };
      recorder.stop();
    });
    const blob = await done;

    // Report self-assessment
    await fetch(`/api/v1/studio/speaking/session/${sessionId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ session_id: sessionId, duration_spoken: timer, self_rating: rating || 3 }),
    });

    // Upload the recording
    if (blob && blob.size > 0) {
      const formData = new FormData();
      const mime = blob.type || "audio/webm";
      formData.append("file", blob, `recording_${sessionId}.${fileExtForMime(mime)}`);
      const up = await fetch(`/api/v1/studio/speaking/session/${sessionId}/audio`, {
        method: "POST",
        headers: getAuthHeader(),
        body: formData,
      });
      if (up.ok) {
        const data = await up.json();
        setAudioUrl(data.audio_url);
        setAudioDownloadUrl(data.audio_download_url || "");
      } else {
        setMessage("⚠️ Recording could not be uploaded — please try again.");
      }
    }
    loadHistory();
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;

  // Pick the first audio container this browser can actually record. Forcing
  // "audio/webm" breaks recording on Safari and some browsers (NotSupportedError),
  // which is why recordings used to end up missing or unplayable.
  const pickMime = () => {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
      "audio/mp4",
      "audio/aac",
      "audio/wav",
    ];
    if (typeof MediaRecorder === "undefined") return "";
    for (const mime of candidates) {
      try {
        if (MediaRecorder.isTypeSupported(mime)) return mime;
      } catch {
        /* ignore */
      }
    }
    return "";
  };

  const fileExtForMime = (mime: string) => {
    if (mime.includes("ogg")) return "ogg";
    if (mime.includes("mp4") || mime.includes("aac")) return "m4a";
    if (mime.includes("wav")) return "wav";
    if (mime.includes("mpeg")) return "mp3";
    return "webm";
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border shadow p-6">
        <h3 className="font-semibold text-lg mb-4">🎤 Speaking Practice</h3>
        {message && <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{message}</div>}
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
            <p className="text-gray-600 mb-4">Recording your voice... Speak now!</p>
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
        {audioUrl && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-sm text-green-700 mb-2">✅ Recording saved — play it back:</p>
            <audio controls src={audioUrl} className="w-full" />
            <a
              href={audioDownloadUrl || audioUrl}
              download
              className="inline-block mt-2 text-xs px-3 py-1.5 rounded bg-white border border-green-300 text-green-700 hover:bg-green-100 transition"
            >
              ⬇ Download recording
            </a>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border shadow p-6">
        <h3 className="font-semibold text-lg mb-4">📜 Practice History ({history.length})</h3>
        {history.length === 0 ? (
          <p className="text-gray-500 text-sm">No sessions yet</p>
        ) : (
          <div className="space-y-3">
            {history.map((s) => (
              <div key={s.id} className="border rounded-lg p-3 flex flex-wrap items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{s.prompt}</p>
                  <p className="text-xs text-gray-400">
                    {s.difficulty} • {s.duration_spoken}s • ⭐{s.self_rating ?? "–"} • {new Date(s.started_at).toLocaleString()}
                  </p>
                </div>
                {s.audio_url && (
                  <div className="flex items-center gap-2">
                    <audio controls src={s.audio_url} className="h-9 w-48" />
                    <a
                      href={s.audio_download_url || s.audio_url}
                      download
                      className="shrink-0 text-xs px-2 py-1 rounded border bg-white text-gray-500 hover:bg-gray-100 transition"
                      title="Download recording"
                    >
                      ⬇
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────
// LIVE BROADCAST (WebRTC audio mesh)
// ──────────────────────────────────────────────

function LiveBroadcast() {
  const [broadcasts, setBroadcasts] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(30);
  const [myBroadcast, setMyBroadcast] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [listening, setListening] = useState<any>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const peersRef = useRef<Map<number, RTCPeerConnection>>(new Map());
  const hostStreamRef = useRef<MediaStream | null>(null);
  const pollRef = useRef<any>(null);

  useEffect(() => {
    fetch("/api/v1/users/me", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => u && setUserId(u.id))
      .catch(() => {});
    fetchBroadcasts();
    const interval = setInterval(fetchBroadcasts, 5000);
    return () => {
      clearInterval(interval);
      clearInterval(pollRef.current);
      leaveEverything();
    };
  }, []);

  const fetchBroadcasts = async () => {
    const res = await fetch("/api/v1/studio/broadcast/active");
    if (res.ok) {
      const data = await res.json();
      setBroadcasts(data.broadcasts || []);
    }
  };

  const sendSignal = (bid: number, recipientId: number, signalType: string, payload: string) => {
    fetch(`/api/v1/studio/broadcast/${bid}/signal`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ recipient_id: recipientId, signal_type: signalType, payload }),
    }).catch(() => {});
  };

  const closeAllPeers = () => {
    peersRef.current.forEach((pc) => pc.close());
    peersRef.current.clear();
    stopTracks(hostStreamRef.current);
    hostStreamRef.current = null;
  };

  const leaveEverything = () => {
    closeAllPeers();
    if (audioRef.current) audioRef.current.srcObject = null;
  };

  const startBroadcast = async () => {
    if (!title) return;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setMessage("❌ Microphone access denied (HTTPS required on LAN).");
      return;
    }
    const res = await fetch("/api/v1/studio/broadcast/start", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title, description, duration_minutes: duration }),
    });
    if (!res.ok) {
      stopTracks(stream);
      setMessage("❌ Could not start broadcast.");
      return;
    }
    const data = await res.json();
    hostStreamRef.current = stream;
    setMyBroadcast(data);
    setListening(null);
    setMessage("🔴 You are now LIVE! Listeners connect automatically.");
    fetchBroadcasts();
    pollSignals(data.id);
  };

  const pollSignals = (bid: number) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const res = await fetch(`/api/v1/studio/broadcast/${bid}/signals`, { headers: getAuthHeader() });
      if (!res.ok) return;
      const { signals } = await res.json();
      for (const sig of signals) {
        if (sig.signal_type === "offer") {
          // Host answering a listener's offer
          const pc = makePeerConnection({
            kind: "broadcast", roomId: bid, remoteId: sig.sender_id,
            localStream: hostStreamRef.current,
            onSignal: (t, p) => sendSignal(bid, sig.sender_id, t, p),
          });
          peersRef.current.set(sig.sender_id, pc);
          await handleSignal(pc, "offer", sig.payload);
          await createAnswer(pc, (t, p) => sendSignal(bid, sig.sender_id, t, p));
        } else if (sig.signal_type === "answer" && userId !== null) {
          const pc = peersRef.current.get(sig.sender_id);
          if (pc) await handleSignal(pc, "answer", sig.payload);
        } else if (sig.signal_type === "ice") {
          const pc = peersRef.current.get(sig.sender_id);
          if (pc) await handleSignal(pc, "ice", sig.payload);
        }
      }
    }, 1500);
  };

  const stopBroadcast = async () => {
    await fetch("/api/v1/studio/broadcast/stop", { method: "POST", headers: getAuthHeader() });
    clearInterval(pollRef.current);
    closeAllPeers();
    setMyBroadcast(null);
    setMessage("Broadcast ended");
    fetchBroadcasts();
  };

  const listenTo = async (b: any) => {
    if (userId === null) return;
    const res = await fetch(`/api/v1/studio/broadcast/${b.id}/join`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (!res.ok) return;
    setListening(b);
    setMessage("");
    // Send an offer to the host with a recvonly audio transceiver
    const pc = makePeerConnection({
      kind: "broadcast", roomId: b.id, remoteId: b.host_id,
      localStream: null,
      remoteVideo: audioRef.current,
      onSignal: (t, p) => sendSignal(b.id, b.host_id, t, p),
    });
    pc.addTransceiver("audio", { direction: "recvonly" });
    peersRef.current.set(b.host_id, pc);
    await createOffer(pc, (t, p) => sendSignal(b.id, b.host_id, t, p));
    pollSignals(b.id);
  };

  const stopListening = () => {
    clearInterval(pollRef.current);
    closeAllPeers();
    setListening(null);
    if (audioRef.current) audioRef.current.srcObject = null;
  };

  return (
    <div className="space-y-6">
      {message && <div className="p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">{message}</div>}
      <audio ref={audioRef} className="hidden" autoPlay />

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
              🔴 Go Live (mic audio)
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-red-50 border-2 border-red-500 rounded-xl p-6 text-center">
          <p className="text-2xl font-bold text-red-600 mb-2">🔴 LIVE</p>
          <p className="text-lg font-semibold">{myBroadcast.title}</p>
          <p className="text-gray-600">{myBroadcast.description}</p>
          <p className="text-sm text-gray-500 mt-2">{myBroadcast.listeners} listener(s) • streaming your mic via WebRTC</p>
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
                  {listening?.id === b.id ? (
                    <button onClick={stopListening} className="bg-gray-800 text-white px-3 py-1 rounded text-sm">⏹ Leave</button>
                  ) : (
                    <button onClick={() => listenTo(b)} className="bg-green-600 text-white px-3 py-1 rounded text-sm">📻 Listen</button>
                  )}
                  <span className="text-sm text-red-600 font-medium">LIVE</span>
                </div>
              </div>
            ))}
          </div>
        )}
        {listening && (
          <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded flex items-center gap-3">
            <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            <span className="text-sm text-green-700">Listening to {listening.title} — mic audio via WebRTC</span>
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
// VIDEO CALL (WebRTC mesh + synced whiteboard)
// ──────────────────────────────────────────────

function VideoCalls() {
  const [calls, setCalls] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [isGroup, setIsGroup] = useState(false);
  const [activeCall, setActiveCall] = useState<any>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [muted, setMuted] = useState(false);
  const [videoOff, setVideoOff] = useState(true);
  const [sharing, setSharing] = useState(false);
  const [callError, setCallError] = useState("");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideosRef = useRef<Map<number, HTMLVideoElement>>(new Map());
  const peersRef = useRef<Map<number, RTCPeerConnection>>(new Map());
  const pollRef = useRef<any>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawColor, setDrawColor] = useState("#000000");
  const [drawSize, setDrawSize] = useState(3);
  const [showWhiteboard, setShowWhiteboard] = useState(false);
  const strokeRef = useRef<any[]>([]);
  const remoteStrokeCountRef = useRef(0);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const [participants, setParticipants] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/v1/users/me", { headers: getAuthHeader() })
      .then((r) => (r.ok ? r.json() : null))
      .then((u) => u && setUserId(u.id))
      .catch(() => {});
    fetchCalls();
    const interval = setInterval(fetchCalls, 5000);
    return () => {
      clearInterval(interval);
      cleanup();
    };
  }, []);

  const fetchCalls = async () => {
    const res = await fetch("/api/v1/studio/calls/active");
    if (res.ok) {
      const data = await res.json();
      setCalls(data.calls || []);
    }
  };

  const cleanup = () => {
    clearInterval(pollRef.current);
    peersRef.current.forEach((pc) => pc.close());
    peersRef.current.clear();
    stopTracks(screenStreamRef.current);
    screenStreamRef.current = null;
    if (localStream) {
      stopTracks(localStream);
      setLocalStream(null);
    }
  };

  const sendSignal = (cid: number, recipientId: number, signalType: string, payload: string) => {
    fetch(`/api/v1/studio/calls/${cid}/signal`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ recipient_id: recipientId, signal_type: signalType, payload }),
    }).catch(() => {});
  };

  const refreshParticipants = async (cid: number) => {
    const res = await fetch(`/api/v1/studio/calls/${cid}/participants`, { headers: getAuthHeader() });
    if (res.ok) setParticipants((await res.json()).participants || []);
  };

  const connectToPeer = (cid: number, remoteId: number, videoEl: HTMLVideoElement | null) => {
    if (peersRef.current.has(remoteId)) return;
    const pc = makePeerConnection({
      kind: "call", roomId: cid, remoteId,
      localStream,
      remoteVideo: videoEl,
      onSignal: (t, p) => sendSignal(cid, remoteId, t, p),
    });
    peersRef.current.set(remoteId, pc);
    return pc;
  };

  const enterCall = async (call: any) => {
    setCallError("");
    const res = await fetch(`/api/v1/studio/calls/${call.id}/join`, {
      method: "POST",
      headers: getAuthHeader(),
    });
    if (!res.ok) {
      setCallError("❌ Could not join call.");
      return;
    }
    const data = await res.json();

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setCallError("❌ Mic access denied (HTTPS required on LAN). Camera starts when you enable it.");
      return;
    }
    setLocalStream(stream);
    if (localVideoRef.current) localVideoRef.current.srcObject = stream;

    setActiveCall(data.call || call);
    await refreshParticipants(data.call?.id || call.id);
    await loadWhiteboard(data.call?.id || call.id);
    poll(data.call?.id || call.id);
  };

  const poll = (cid: number) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const res = await fetch(`/api/v1/studio/calls/${cid}/signals`, { headers: getAuthHeader() });
      if (!res.ok) return;
      const { signals } = await res.json();
      for (const sig of signals) {
        let pc = peersRef.current.get(sig.sender_id);
        if (sig.signal_type === "offer") {
          if (!pc) {
            const el = getRemoteVideoEl(sig.sender_id);
            pc = connectToPeer(cid, sig.sender_id, el);
          }
          if (!pc) continue;
          await handleSignal(pc, "offer", sig.payload);
          await createAnswer(pc, (t, p) => sendSignal(cid, sig.sender_id, t, p));
        } else if (sig.signal_type === "answer") {
          if (pc) await handleSignal(pc, "answer", sig.payload);
        } else if (sig.signal_type === "ice") {
          if (pc) await handleSignal(pc, "ice", sig.payload);
        }
      }
      // discover new joiners and send them offers
      const parts = await fetch(`/api/v1/studio/calls/${cid}/participants`, { headers: getAuthHeader() });
      if (parts.ok) {
        const list = (await parts.json()).participants || [];
        setParticipants(list);
        for (const p of list) {
          if (p.user_id !== userId && !peersRef.current.has(p.user_id)) {
            const el = getRemoteVideoEl(p.user_id);
            const pc = connectToPeer(cid, p.user_id, el);
            if (pc) await createOffer(pc, (t, sig) => sendSignal(cid, p.user_id, t, sig));
          }
        }
      }
      // whiteboard sync
      if (showWhiteboard) await syncWhiteboard(cid);
    }, 1500);
  };

  const getRemoteVideoEl = (uid: number): HTMLVideoElement | null => {
    let el = remoteVideosRef.current.get(uid);
    if (!el) {
      el = document.createElement("video");
      el.autoplay = true;
      el.playsInline = true;
      el.className = "w-full h-full object-cover";
      remoteVideosRef.current.set(uid, el);
    }
    return el;
  };

  const createCall = async () => {
    setCallError("");
    const res = await fetch("/api/v1/studio/calls/create", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ title: title || "Video Call", is_group: isGroup, max_participants: 0, enable_whiteboard: true, enable_screen_share: true }),
    });
    if (res.ok) await enterCall(await res.json());
  };

  const joinCall = async (c: any) => {
    await enterCall(c);
  };

  const leaveCall = async () => {
    if (activeCall) {
      await fetch(`/api/v1/studio/calls/${activeCall.id}/leave`, {
        method: "POST",
        headers: getAuthHeader(),
      });
    }
    clearInterval(pollRef.current);
    peersRef.current.forEach((pc) => pc.close());
    peersRef.current.clear();
    remoteVideosRef.current.clear();
    stopTracks(screenStreamRef.current);
    screenStreamRef.current = null;
    if (localStream) {
      stopTracks(localStream);
      setLocalStream(null);
    }
    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    setActiveCall(null);
    setParticipants([]);
    setMuted(false);
    setVideoOff(true);
    setSharing(false);
    setShowWhiteboard(false);
    setCallError("");
    fetchCalls();
  };

  const toggleMute = () => {
    const audioTracks = localStream?.getAudioTracks() || [];
    audioTracks.forEach((t) => (t.enabled = muted));
    setMuted(!muted);
  };

  const toggleVideo = async () => {
    if (videoOff) {
      try {
        if (!localStream) {
          setCallError("❌ Not in a call yet.");
          return;
        }
        let videoTrack: MediaStreamTrack | undefined = localStream.getVideoTracks()[0];
        if (!videoTrack) {
          const cam = await navigator.mediaDevices.getUserMedia({ video: true });
          videoTrack = cam.getVideoTracks()[0];
          cam.getAudioTracks().forEach((t) => t.stop());
          localStream.addTrack(videoTrack);
        }
        videoTrack.enabled = true;
        for (const [, pc] of Array.from(peersRef.current.entries())) {
          if (pc.signalingState !== "closed") pc.addTrack(videoTrack, localStream);
        }
      } catch {
        setCallError("❌ Could not start camera — check permissions.");
        return;
      }
      try {
        for (const [remoteId, pc] of Array.from(peersRef.current.entries())) {
          if (pc.signalingState === "stable") {
            await createOffer(pc, (t, p) => sendSignal(activeCall.id, remoteId, t, p));
          }
        }
      } catch {}
      if (localVideoRef.current) localVideoRef.current.srcObject = localStream;
      setVideoOff(false);
    } else {
      const videoTracks = localStream?.getVideoTracks() || [];
      videoTracks.forEach((t) => (t.enabled = false));
      setVideoOff(true);
    }
  };

  const toggleShare = async () => {
    if (sharing) {
      // revert to camera
      const videoTrack = localStream?.getVideoTracks()[0];
      if (videoTrack && localStream) {
        const pcs = Array.from(peersRef.current.values());
        for (const pc of pcs) {
          const s = pc.getSenders().find((x: RTCRtpSender) => x.track?.kind === "video");
          if (s && videoTrack) await s.replaceTrack(videoTrack);
        }
      }
      stopTracks(screenStreamRef.current);
      screenStreamRef.current = null;
      setSharing(false);
      return;
    }
    try {
      const screen = await (navigator.mediaDevices as any).getDisplayMedia({ video: true, audio: false });
      screenStreamRef.current = screen;
      const track = screen.getVideoTracks()[0];
      const pcs = Array.from(peersRef.current.values());
      for (const pc of pcs) {
        const s = pc.getSenders().find((x: RTCRtpSender) => x.track?.kind === "video");
        if (s) await s.replaceTrack(track);
      }
      track.onended = () => {
        stopTracks(screenStreamRef.current);
        screenStreamRef.current = null;
        setSharing(false);
      };
      setSharing(true);
    } catch {
      setCallError("❌ Screen share cancelled or unavailable.");
    }
  };

  // ── Whiteboard ──
  const startDraw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    strokeRef.current = [{ color: drawColor, size: drawSize, points: [getPoint(e)] }];
    drawPoint(strokeRef.current[0].points[0], drawColor, drawSize);
  };

  const getPoint = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * canvas.width,
      y: ((e.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const drawPoint = (p: any, color: string, size: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx || !canvas) return;
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.lineCap = "round";
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const p = getPoint(e);
    strokeRef.current[0]?.points.push(p);
    drawPoint(p, strokeRef.current[0].color, strokeRef.current[0].size);
  };

  const stopDraw = () => {
    setIsDrawing(false);
    if (!activeCall || !strokeRef.current[0]?.points.length) return;
    const stroke = strokeRef.current[0];
    fetch(`/api/v1/studio/calls/${activeCall.id}/whiteboard/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ strokes: [stroke] }),
    }).catch(() => {});
    strokeRef.current = [];
  };

  const clearWhiteboard = async () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!activeCall) return;
    await fetch(`/api/v1/studio/calls/${activeCall.id}/whiteboard/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ strokes: [{ clear: true }] }),
    }).catch(() => {});
  };

  const loadWhiteboard = async (cid: number) => {
    const res = await fetch(`/api/v1/studio/calls/${cid}/whiteboard`);
    if (!res.ok) return;
    const { strokes } = await res.json();
    remoteStrokeCountRef.current = strokes.length;
    replayStrokes(strokes);
  };

  const syncWhiteboard = async (cid: number) => {
    const res = await fetch(`/api/v1/studio/calls/${cid}/whiteboard`);
    if (!res.ok) return;
    const { strokes } = await res.json();
    if (strokes.length > remoteStrokeCountRef.current) {
      const fresh = strokes.slice(remoteStrokeCountRef.current);
      replayStrokes(fresh);
      remoteStrokeCountRef.current = strokes.length;
    }
  };

  const replayStrokes = (strokes: any[]) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx || !canvas) return;
    for (const s of strokes) {
      if (s.clear) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        continue;
      }
      ctx.strokeStyle = s.color || "#000";
      ctx.lineWidth = s.size || 3;
      ctx.lineCap = "round";
      ctx.beginPath();
      for (const [i, p] of (s.points || []).entries()) {
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    }
  };

  return (
    <div className="space-y-6">
      {callError && <div className="p-3 rounded bg-red-50 border border-red-200 text-red-700 text-sm">{callError}</div>}
      {!activeCall ? (
        <>
          <div className="bg-white rounded-xl border shadow p-6">
            <h3 className="font-semibold text-lg mb-4">📹 Create Video Call</h3>
            <div className="space-y-3">
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded border px-3 py-2 text-sm" placeholder="Call title" />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
                Group call — unlimited participants
              </label>
              <button onClick={createCall} className="w-full bg-green-600 text-white py-2 rounded-lg font-medium hover:bg-green-700">
                📹 Create Call Room
              </button>
              <p className="text-xs text-gray-400">Peer-to-peer WebRTC — works best on the same LAN. HTTPS required for camera/mic.</p>
            </div>
          </div>

          {calls.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-3">Active Calls</h3>
              {calls.map((c) => (
                <div key={c.id} className="bg-white rounded-lg border p-4 mb-3">
                  <p className="font-medium">{c.title}</p>
                  <p className="text-sm text-gray-500">{c.participants?.length} participant(s)</p>
                  <button onClick={() => joinCall(c)} className="mt-2 bg-green-100 text-green-700 px-4 py-1 rounded text-sm">
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
              <p className="text-xs text-gray-400">{participants.length} participant(s)</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setShowWhiteboard(!showWhiteboard)}
                className={`px-3 py-1 rounded text-sm ${showWhiteboard ? "bg-blue-600" : "bg-gray-700"}`}>
                🖊️ Whiteboard
              </button>
              <button onClick={leaveCall} className="bg-red-600 px-3 py-1 rounded text-sm">
                Leave
              </button>
            </div>
          </div>

          {/* Video Grid */}
          <div className="bg-gray-900 p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {/* Local */}
              <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
                <video ref={localVideoRef} autoPlay playsInline muted
                  className={`w-full h-full object-cover ${videoOff ? "hidden" : ""}`} />
                {videoOff && (
                  <div className="w-full h-full flex items-center justify-center">
                    <p className="text-4xl">🙈</p>
                  </div>
                )}
                <span className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded">
                  You {muted ? "🔇" : "🎙️"}
                </span>
              </div>
              {/* Remote peers */}
              {participants
                .filter((p) => p.user_id !== userId)
                .map((p) => (
                  <div key={p.user_id} className="relative rounded-lg overflow-hidden bg-black aspect-video">
                    <VideoSlot uid={p.user_id} videoElRefs={remoteVideosRef} label={p.name} />
                  </div>
                ))}
            </div>
          </div>

          {/* Whiteboard Overlay */}
          {showWhiteboard && (
            <div className="relative">
              <div className="flex gap-2 p-2 bg-gray-100 border-b flex-wrap items-center">
                <input type="color" value={drawColor} onChange={(e) => setDrawColor(e.target.value)} className="w-8 h-8" />
                <input type="range" min={1} max={20} value={drawSize} onChange={(e) => setDrawSize(parseInt(e.target.value))} className="w-32" />
                <button onClick={clearWhiteboard} className="bg-red-100 text-red-700 px-3 py-1 rounded text-xs">Clear</button>
                <span className="text-xs text-gray-500">Whiteboard syncs with all participants</span>
              </div>
              <canvas ref={canvasRef} width={960} height={540}
                className="w-full cursor-crosshair bg-white"
                onMouseDown={startDraw} onMouseMove={draw} onMouseUp={stopDraw} onMouseLeave={stopDraw}
              />
            </div>
          )}

          {/* Call Controls */}
          <div className="bg-gray-800 p-4 flex justify-center gap-4 flex-wrap">
            <button onClick={toggleMute}
              className={`px-4 py-2 rounded-lg text-sm ${muted ? "bg-red-600" : "bg-gray-700"} text-white hover:bg-gray-600`}>
              {muted ? "🔇 Unmute" : "🎤 Mute"}
            </button>
            <button onClick={toggleVideo}
              className={`px-4 py-2 rounded-lg text-sm ${videoOff ? "bg-red-600" : "bg-gray-700"} text-white hover:bg-gray-600`}>
              {videoOff ? "📷 Turn camera on" : "🙈 Turn camera off"}
            </button>
            <button onClick={toggleShare}
              className={`px-4 py-2 rounded-lg text-sm ${sharing ? "bg-blue-600" : "bg-gray-700"} text-white hover:bg-gray-600`}>
              {sharing ? "🖥️ Stop Share" : "🖥️ Share Screen"}
            </button>
            <button onClick={() => setShowWhiteboard(!showWhiteboard)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-500">🖊️ Whiteboard</button>
            <button onClick={leaveCall}
              className="bg-red-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-red-700">📞 Leave</button>
          </div>
        </div>
      )}
    </div>
  );
}

function VideoSlot({ uid, videoElRefs, label }: { uid: number; videoElRefs: React.MutableRefObject<Map<number, HTMLVideoElement>>; label: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (ref.current) videoElRefs.current.set(uid, ref.current);
    return () => {
      videoElRefs.current.delete(uid);
    };
  }, [uid]);

  return (
    <div className="relative w-full h-full">
      <video ref={ref} autoPlay playsInline className="w-full h-full object-cover" />
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <p className="text-4xl opacity-20">👤</p>
      </div>
      <span className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-0.5 rounded">{label}</span>
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
    <RequireRole roles={["user", "student", "admin"]} redirectTo="/kudos">
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
    </RequireRole>
  );
}
